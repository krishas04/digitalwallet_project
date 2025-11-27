from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate
from .models import CustomUser

#it inherits from UserCreationForm which handles checking that password1 and password2 match and Securely hash the user's password before saving it
class SignUpForm(UserCreationForm):
    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("others", "Others"),
    ]

    # Use 'full_name' instead of separate first/last name to match your image
    full_name = forms.CharField(
        max_length=60,
        required=True,
        widget=forms.TextInput(),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(),
    )
    mobile_number = forms.CharField(
        max_length=15,
        required=True,
        widget=forms.TextInput(),
    )
    gender = forms.ChoiceField(
        choices=GENDER_CHOICES, required=True, widget=forms.RadioSelect()
    )
    date_of_birth = forms.DateField(
        required=True, widget=forms.SelectDateWidget(years=range(1950, 2007))
    )

    # Override password fields to match your design
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': ' '})
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': ' '})
    )

# inner Meta class is how we connect a form directly to a database model
    class Meta:
        model = CustomUser
        fields = (
            "username",
            "full_name",
            "email",
            "mobile_number",
            "gender",
            "date_of_birth",
            "password1",
            "password2",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hide username field since we'll generate it from email
        self.fields["username"].widget = forms.HiddenInput()
        self.fields["username"].required = False

#   to ensure that every email is unique in your database.
    def clean_email(self):
        email = self.cleaned_data.get("email")
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_mobile_number(self):
        mobile = self.cleaned_data.get("mobile_number")
        if CustomUser.objects.filter(mobile_number=mobile).exists():
            raise forms.ValidationError(
                "A user with this mobile number already exists."
            )
        return mobile

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]  # Use email as username
        user.email = self.cleaned_data["email"]

        # Split full name into first and last name
        full_name = self.cleaned_data["full_name"].strip()
        name_parts = full_name.split(" ", 1)
        user.first_name = name_parts[0]
        user.last_name = name_parts[1] if len(name_parts) > 1 else ""

        user.mobile_number = self.cleaned_data["mobile_number"]
        user.gender = self.cleaned_data["gender"]
        user.date_of_birth = self.cleaned_data["date_of_birth"]

        if commit:
            user.save()
        return user


# --- LoginForm (Updated for 2FA compatibility) ---
# We now inherit from AuthenticationForm to work with the 2FA view.
# We keep your logic for logging in with an email address instead of a username.


class LoginForm(AuthenticationForm):
    # Override the default username field to accept an email
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(
            attrs={"autofocus": True, "placeholder": "Enter your email"}
        ),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "placeholder": "Enter your password",
            }
        ),
    )

    # This code takes the submitted email, finds the corresponding CustomUser in the database, gets their actual username (user_obj.username), and puts it back into self.cleaned_data["username"].
    def clean(self):
        # The 'username' field from the form now contains the user's email
        email = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if email and password:
            # We need to find the user by email first, as 'authenticate' uses the username field
            try:
                user_obj = CustomUser.objects.get(email=email)
                # Then, we pass the actual username to the parent class's authentication logic
                self.cleaned_data["username"] = user_obj.username
            except CustomUser.DoesNotExist:
                # Raise a generic error to avoid user enumeration
                raise forms.ValidationError(
                    self.error_messages["invalid_login"],
                    code="invalid_login",
                    params={"username": self.username_field.verbose_name},
                )

        # Call the parent's clean method to perform the actual authentication
        return super().clean()


# --- OTPForm (New form required for the 2FA process) ---
# This form is for the second step of the login.

# This inherits from the most basic forms.Form.It's not connected to any database model. It's just a temporary container for one piece of data: the One-Time Password (OTP) that the user enters. 
class OTPForm(forms.Form):
    otp = forms.CharField(
        max_length=6,
        required=True,
        label="OTP Code",
        widget=forms.TextInput(attrs={"placeholder": "123456"}),
    )
