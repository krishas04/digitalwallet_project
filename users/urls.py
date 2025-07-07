from django.urls import path
from . import views


app_name = "users"

urlpatterns = [
    path("", views.login_view, name="login"),  # Default to login page
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("otp-verify/", views.otp_verify_view, name="otp_verify"),  # otp
    path("logout/", views.logout_view, name="logout"),
    path("create-pin/", views.create_pin_view, name="create_pin"),
]
