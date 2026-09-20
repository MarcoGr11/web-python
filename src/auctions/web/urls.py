from django.urls import path

from . import views

urlpatterns = [
    path("accounts/register/", views.register_view, name="register"),
    path("accounts/login/", views.login_view, name="login"),
    path("accounts/logout/", views.logout_view, name="logout"),
    path("dashboard/user/", views.dashboard_user, name="dashboard_user"),
    path("dashboard/admin/", views.dashboard_admin, name="dashboard_admin"),
    path("lots/", views.lot_list, name="lot_list"),
    path("lots/new/", views.lot_create, name="lot_create"),
    path("lots/<int:pk>/", views.lot_detail, name="lot_detail"),
    path("lots/<int:pk>/edit/", views.lot_edit, name="lot_edit"),
]
