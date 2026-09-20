from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..models import Lot
from .decorators import role_required
from .forms import LotForm, RegisterForm


def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("dashboard_user")
    else:
        form = RegisterForm()
    return render(request, "auctions/register.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect("dashboard_admin" if request.user.is_staff else "dashboard_user")
        return render(request, "auctions/login.html", {"form": form}, status=401)
    return render(request, "auctions/login.html", {"form": AuthenticationForm()})


@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def dashboard_user(request):
    lots = Lot.objects.filter(ends_at__gte=timezone.now()).order_by("ends_at")
    return render(request, "auctions/dashboard_user.html", {"lots": lots})


@role_required("admin")
def dashboard_admin(request):
    return render(
        request,
        "auctions/dashboard_admin.html",
        {"users": User.objects.all(), "lots": Lot.objects.all()},
    )


@login_required
def lot_list(request):
    return render(request, "auctions/lot_list.html", {"lots": Lot.objects.all()})


@login_required
def lot_detail(request, pk):
    lot = get_object_or_404(Lot, pk=pk)
    return render(request, "auctions/lot_detail.html", {"lot": lot})


@login_required
def lot_create(request):
    if request.method == "POST":
        form = LotForm(request.POST)
        if form.is_valid():
            lot = form.save(commit=False)
            lot.owner = request.user
            lot.current_highest_bid = form.cleaned_data["starting_price"]
            lot.save()
            return redirect("lot_detail", pk=lot.pk)
    else:
        form = LotForm()
    return render(request, "auctions/lot_create.html", {"form": form})


@login_required
def lot_edit(request, pk):
    lot = get_object_or_404(Lot, pk=pk)
    if lot.owner_id != request.user.id and not request.user.is_staff:
        raise PermissionDenied
    if request.method == "POST":
        form = LotForm(request.POST, instance=lot)
        if form.is_valid():
            form.save()
            return redirect("lot_detail", pk=lot.pk)
    else:
        form = LotForm(instance=lot)
    return render(request, "auctions/lot_edit.html", {"form": form, "lot": lot})
