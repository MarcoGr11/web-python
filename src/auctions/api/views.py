from decimal import Decimal, InvalidOperation

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import generics, permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import services
from ..models import Bid, Lot
from .serializers import BidSerializer, LotSerializer, RegisterSerializer, UserSerializer


class IsOwnerOrAdmin(permissions.BasePermission):
    """Same rule as the HTML lot_edit view (views.py): owner or is_staff."""

    def has_object_permission(self, request, view, obj):
        return obj.owner_id == request.user.id or request.user.is_staff


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {"token": token.key, "user": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        user = authenticate(
            request,
            username=request.data.get("username"),
            password=request.data.get("password"),
        )
        if user is None:
            return Response(
                {"detail": "Invalid username or password."}, status=status.HTTP_400_BAD_REQUEST
            )
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data})


class LogoutView(APIView):
    def post(self, request):
        request.user.auth_token.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class LotViewSet(viewsets.ModelViewSet):
    """
    GET/POST /api/lots/           — list, create (owner = request.user).
    GET      /api/lots/<id>/      — any authenticated user.
    PATCH/DELETE /api/lots/<id>/  — owner or is_staff only (IsOwnerOrAdmin).
    GET  /api/lots/<id>/bids/     — bid history for the lot.
    POST /api/lots/<id>/bid/      — place a bid via services.place_bid()
                                     (the same function AuctionConsumer uses).
    """

    queryset = Lot.objects.all().order_by("-created_at")
    serializer_class = LotSerializer

    def get_queryset(self):
        services.close_expired_lots()
        return super().get_queryset()

    def get_permissions(self):
        if self.action in ("update", "partial_update", "destroy"):
            return [permissions.IsAuthenticated(), IsOwnerOrAdmin()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(
            owner=self.request.user,
            current_highest_bid=serializer.validated_data["starting_price"],
        )

    @action(detail=True, methods=["get"])
    def bids(self, request, pk=None):
        return Response(BidSerializer(self.get_object().bids.all(), many=True).data)

    @action(detail=True, methods=["post"])
    def bid(self, request, pk=None):
        lot = self.get_object()
        try:
            amount = Decimal(str(request.data.get("amount")))
        except (InvalidOperation, TypeError):
            return Response({"detail": "Invalid amount."}, status=status.HTTP_400_BAD_REQUEST)

        result = services.place_bid(lot.id, request.user.id, amount)
        if result["accepted"]:
            return Response(
                {"accepted": True, "amount": str(result["amount"]), "user": result["username"]},
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {
                "accepted": False,
                "reason": result["reason"],
                "current_highest_bid": str(result["current_highest_bid"]),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


class UserDashboardView(APIView):
    def get(self, request):
        lots = Lot.objects.filter(ends_at__gte=timezone.now()).order_by("ends_at")
        my_bids = Bid.objects.filter(user=request.user).order_by("-created_at")
        return Response(
            {
                "balance": str(request.user.profile.balance),
                "active_lots": LotSerializer(lots, many=True).data,
                "my_bids": BidSerializer(my_bids, many=True).data,
            }
        )


class InventoryView(APIView):
    """GET /api/inventory/ — closed lots the current user won."""

    def get(self, request):
        services.close_expired_lots()
        lots = Lot.objects.filter(current_winner=request.user, is_closed=True).order_by("-ends_at")
        return Response(LotSerializer(lots, many=True).data)


class AdminDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def get(self, request):
        return Response(
            {
                "users": UserSerializer(User.objects.all(), many=True).data,
                "lots": LotSerializer(Lot.objects.all(), many=True).data,
            }
        )
