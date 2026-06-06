from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.mail import send_mail
from users.sha_hasher import hash_pin, check_pin
from django.conf import settings

from .forms import SignUpForm, LoginForm, OTPForm
from .models import CustomUser

def signup_view(request):
    if request.user.is_authenticated:
        return redirect("wallet:dashboard")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, "Account created successfully! Please log in.")
            return redirect("users:login")
        
    else:
        form = SignUpForm()

    return render(request, "users/signup.html", {"form": form})


def login_view(request):
    # This code retrieves and effectively discards all existing messages.
    list(messages.get_messages(request))
    if request.user.is_authenticated:
        return redirect("wallet:dashboard")

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()

            # Generate and send OTP
            otp = user.generate_otp()
            send_mail(
                "Your OTP Code",    #subject of email
                f"Your One-Time Password is: {otp}",    #message body
                settings.DEFAULT_FROM_EMAIL,    #email of sender
                [user.email],   # list of recipient emails
                fail_silently=False,
            )
            print(f"OTP for {user.username}: {otp}")    #prints otp on terminal

            # Store user's pk in session to verify in the next step
            request.session["user_id_for_2fa"] = user.pk
            messages.info(request, "An OTP has been sent to your email.")
            return redirect("users:otp_verify")
    else:
        form = LoginForm()

    return render(request, "users/login.html", {"form": form})


# View for OTP verification
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
            if user.otp_expiry and timezone.now() > user.otp_expiry:    #expiry time exists and expiry time has been crossed
                messages.error(request, "OTP has expired. Please try logging in again.")
                return redirect("users:login")

            # Check if OTP is correct
            if user.otp == entered_otp:
                # Clear OTP fields
                user.otp = None
                user.otp_expiry = None
                user.save()

                # Log the user in
                login(request, user)    #built-in function that marks a user as authenticated and stores their ID in the session.
                del request.session["user_id_for_2fa"]  # Clean up session
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect("wallet:dashboard")
            else:
                messages.error(request, "Invalid OTP. Please try again.")
        else:
            messages.error(request, "Invalid input.")
    else:
        form = OTPForm()

    return render(request, "users/otp_verify.html", {"form": form})


#TRANSACTION PIN MANAGEMENT VIEW

@login_required
def create_pin_view(request):
    """
    Handles the one-time creation of a user's transaction PIN.
    This view is responsible for setting the user's PIN, which is a piece
    of user-specific data, hence why it lives in the 'users' app.
    """
    # Get the URL to redirect to after successful PIN creation. This is passed
    # by the view that sent the user here (e.g., the transfer dispatcher).
    next_url = request.GET.get('next', 'wallet:dashboard')

    if request.method == 'POST':
        pin1 = request.POST.get('pin1')
        pin2 = request.POST.get('pin2')

        # --- Validation ---
        if not pin1 or not pin2:
            messages.error(request, "Please fill out both PIN fields.")
        elif not pin1.isdigit() or not pin2.isdigit() or len(pin1) != 4:
            messages.error(request, "Your PIN must be exactly 4 digits.")
        elif pin1 != pin2:
            messages.error(request, "The PINs you entered do not match. Please try again.")
        else:
            # --- If valid, hash and save the PIN ---
            user = request.user
            # We securely hash the PIN using Django's password hashing system.
            # This means we don't store the plain PIN in the database.
            user.transaction_pin = hash_pin(pin1)
            user.save()
            
            messages.success(request, "Your transaction PIN has been created successfully!")

            # ## --- PIN HASHING DEMO (CONSOLE OUTPUT) --- ##
            # This part will ONLY run when a PIN is successfully created.
            print("\n--- TRANSACTION PIN HASHING DEMO ---")
            print(f"Original PIN entered: {pin1}")
            print(f"Stored Hashed PIN: {user.transaction_pin}")
            
            # Demonstrate checking the PIN
            print(f"Verification Check (Correct PIN '{pin1}'): {check_pin(pin1, user.transaction_pin)}")
            print(f"Verification Check (Incorrect PIN '9999'): {check_pin('9999', user.transaction_pin)}")
            print("--- END OF PIN HASHING DEMO ---\n")
            # ===================================================
            return redirect(next_url) # Redirect to the page they were originally trying to access

    # This context is useful if you want to pass the 'next' URL to the template,
    # although the form's action="" will preserve the GET parameter automatically.
    context = {'next': next_url}
    return render(request, 'users/create_pin.html', context)


# --- LOGOUT CONFIRMATION ---
@login_required
def logout_confirm_view(request):
    """
    Renders the page that asks the user to confirm they want to log out.
    """
    return render(request, 'users/logout_confirm.html')


# --- LOGOUT VIEW ---
def logout_view(request):
    from django.contrib.auth import logout

    logout(request)
    messages.success(request, "You have been logged out successfully.")
    
    # Ensure this redirect points to your homepage
    return redirect("wallet:index")