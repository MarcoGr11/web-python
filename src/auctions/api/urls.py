from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("lots", views.LotViewSet, basename="api-lot")

urlpatterns = [
    path("auth/register/", views.RegisterView.as_view(), name="api-register"),
    path("auth/login/", views.LoginView.as_view(), name="api-login"),
    path("auth/logout/", views.LogoutView.as_view(), name="api-logout"),
    path("dashboard/user/", views.UserDashboardView.as_view(), name="api-dashboard-user"),
    path("dashboard/admin/", views.AdminDashboardView.as_view(), name="api-dashboard-admin"),
    path("", include(router.urls)),
]
