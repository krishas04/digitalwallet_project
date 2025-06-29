from django.urls import path
from . import views

app_name = "users"

urlpatterns = [
    path("", views.login_view, name="login"),  # Default to login page
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("otp-verify/", views.otp_verify_view, name="otp_verify"),  # otp
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("logout/", views.logout_view, name="logout"),
]
