from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Lot


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email


class LotForm(forms.ModelForm):
    class Meta:
        model = Lot
        fields = ["title", "description", "starting_price", "ends_at"]
        widgets = {"ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}
