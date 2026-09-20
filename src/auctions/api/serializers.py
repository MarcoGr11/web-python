from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from ..models import Bid, Lot


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "is_staff"]


class LotSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    current_winner = UserSerializer(read_only=True)

    class Meta:
        model = Lot
        fields = [
            "id",
            "title",
            "description",
            "starting_price",
            "current_highest_bid",
            "current_winner",
            "owner",
            "ends_at",
            "created_at",
        ]
        read_only_fields = ["current_highest_bid", "current_winner", "owner", "created_at"]


class BidSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    timestamp = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = Bid
        fields = ["id", "lot", "user", "amount", "timestamp"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email", ""),
            password=validated_data["password"],
        )
