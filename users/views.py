
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.mail import send_mail
from .forms import SignUpForm, LoginForm, OTPForm  # MODIFIED
from .models import CustomUser


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("users:dashboard")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, "Account created successfully! Please log in.")
            return redirect("users:login")
        else:
            # Add form errors to messages
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = SignUpForm()

    return render(request, "users/signup.html", {"form": form})


# updated for 2FA, Login view now handles the first step of authentication
def login_view(request):
    if request.user.is_authenticated:
        return redirect("users:dashboard")

    if request.method == "POST":
        form = LoginForm(
            request, data=request.POST
        )  # MODIFIED: pass request to LoginForm
        if form.is_valid():
            user = form.get_user()

            # Generate and send OTP
            otp = user.generate_otp()
            send_mail(
                "Your OTP Code",
                f"Your One-Time Password is: {otp}",
                "noreply@digitalwallet.com",  # from@example.com
                [user.email],
                fail_silently=False,
            )
            print(f"OTP for {user.username}: {otp}")  # For console backend viewing

            # Store user's pk in session to verify in the next step
            request.session["user_id_for_2fa"] = user.pk
            messages.info(request, "An OTP has been sent to your email.")
            return redirect("users:otp_verify")
        else:
            messages.error(
                request, "Invalid username or password."
            )  # Simplified error message
    else:
        form = LoginForm()

    return render(request, "users/login.html", {"form": form})


# NEW: View for OTP verification
def otp_verify_view(request):
    user_id = request.session.get("user_id_for_2fa")
    if not user_id:
        messages.error(request, "Session expired. Please log in again.")
        return redirect("users:login")

    try:
        user = CustomUser.objects.get(pk=user_id)
    except CustomUser.DoesNotExist:
        messages.error(request, "User not found. Please log in again.")
        return redirect("users:login")

    if request.method == "POST":
        form = OTPForm(request.POST)
        if form.is_valid():
            entered_otp = form.cleaned_data.get("otp")

            # Check if OTP has expired
            if user.otp_expiry and timezone.now() > user.otp_expiry:
                messages.error(request, "OTP has expired. Please try logging in again.")
                return redirect("users:login")

            # Check if OTP is correct
            if user.otp == entered_otp:
                # Clear OTP fields
                user.otp = None
                user.otp_expiry = None
                user.save()

                # Log the user in
                login(request, user)
                del request.session["user_id_for_2fa"]  # Clean up session
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect("users:dashboard")
            else:
                messages.error(request, "Invalid OTP. Please try again.")
        else:
            messages.error(request, "Invalid input.")
    else:
        form = OTPForm()

    return render(request, "users/otp_verify.html", {"form": form})


@login_required
def dashboard_view(request):
    return render(request, "users/dashboard.html", {"user": request.user})


def logout_view(request):
    from django.contrib.auth import logout

    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("users:login")

