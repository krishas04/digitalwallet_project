from django.urls import path
from . import views

# Import Django's built-in authentication views and give them an alias
from django.contrib.auth import views as auth_views


app_name = "users"

urlpatterns = [
    path("", views.login_view, name="login"),  # Default to login page
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("otp-verify/", views.otp_verify_view, name="otp_verify"),  # otp
    path("logout/", views.logout_view, name="logout"),
    path("create-pin/", views.create_pin_view, name="create_pin"),

    # ==============================================================================
    # ## --- NEW: PASSWORD RESET URLS --- ##
    # ==============================================================================

    # 1. Page to request a password reset (user enters their email)
    path('password_reset/', 
     auth_views.PasswordResetView.as_view(
         template_name='users/password_reset_form.html',
         email_template_name='users/password_reset_email.txt',  # <-- The plain text version
         html_email_template_name='users/password_reset_email.html',  # <-- The HTML version
         subject_template_name='users/password_reset_subject.txt', 
         success_url='/users/password_reset/done/'
     ), 
     name='password_reset'),

    # 2. Page shown to the user after they submit their email
    path('password_reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='users/password_reset_done.html'  # Our custom template
         ), 
         name='password_reset_done'),

    # 3. The link the user clicks in their email (contains a token)
    path('reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='users/password_reset_confirm.html', # Our custom template
             success_url='/users/reset/done/'                  # Redirect here after success
         ), 
         name='password_reset_confirm'),

    # 4. Final success page after the password has been changed
    path('reset/done/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='users/password_reset_complete.html' # Our custom template
         ), 
         name='password_reset_complete'),
]
