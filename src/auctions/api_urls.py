from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api_views

router = DefaultRouter()
router.register("lots", api_views.LotViewSet, basename="api-lot")

urlpatterns = [
    path("auth/register/", api_views.RegisterView.as_view(), name="api-register"),
    path("auth/login/", api_views.LoginView.as_view(), name="api-login"),
    path("auth/logout/", api_views.LogoutView.as_view(), name="api-logout"),
    path("dashboard/user/", api_views.UserDashboardView.as_view(), name="api-dashboard-user"),
    path("dashboard/admin/", api_views.AdminDashboardView.as_view(), name="api-dashboard-admin"),
    path("", include(router.urls)),
]
