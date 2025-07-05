import os
import uuid
import requests
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.db import transaction as db_transaction
from django.contrib import messages
from transaction.models import Transaction
from .models import Wallet

# Khalti API URLs for the new method
KHALTI_INITIATE_URL = "https://dev.khalti.com/api/v2/epayment/initiate/"
KHALTI_SECRET_KEY = os.getenv("KHALTI_SECRET_KEY")

# --- VIEWS FOR STATIC PAGES (UNCHANGED) ---
def index(request):
    return render(request, "wallet/index.html")

def aboutus(request):
    return render(request, "wallet/aboutus.html")

def services(request):
    return render(request, "wallet/services.html")

def contact(request):
    return render(request, "wallet/contact.html")

def policies(request):
    return render(request, "wallet/policies.html")

def help(request):
    return render(request, "wallet/help.html")


# --- CORE APPLICATION VIEWS (CORRECTED) ---

@login_required
def dashboard_view(request):
    """
    Renders the main dashboard and fetches recent transactions.
    """
    recent_transactions = Transaction.objects.filter(
        wallet__user=request.user
    ).order_by('-timestamp')[:5]

    context = {
        'recent_transactions': recent_transactions,
    }
    return render(request, "wallet/dashboard.html", context)


@login_required
def load_money_view(request):
    """
    Renders the page where users can enter an amount.
    """
    return render(request, "wallet/load_money.html")


@login_required
def initiate_khalti_payment(request):
    """
    This is the new view that initiates the payment with Khalti's server.
    """
    if request.method == "POST":
        try:
            amount_str = request.POST.get("amount")
            if not amount_str:
                messages.error(request, "Amount is required.")
                return redirect("wallet:load_money")

            amount = int(float(amount_str))

            if amount < 10:
                messages.error(request, "Amount must be at least Rs. 10.")
                return redirect("wallet:load_money")

            user = request.user
            purchase_order_id = f"webpay-{user.username}-{uuid.uuid4()}"
            purchase_order_name = f"Load Wallet for {user.username}"
            return_url = request.build_absolute_uri(reverse("wallet:khalti_callback"))

            # --- START OF CORRECTED LOGIC ---

            # 1. Create the transaction record first, keeping it in a variable.
            #    This is the ONLY time we create it.
            pending_transaction = Transaction.objects.create(
                wallet=user.wallet,
                transaction_type=Transaction.TransactionType.LOAD,
                amount=amount,
                status=Transaction.TransactionStatus.PENDING,
                description="Load money initiation via Khalti",
                purchase_order_id=purchase_order_id,
            )

            # 2. Prepare the payload for Khalti's API.
            payload = {
                "return_url": return_url,
                "website_url": request.build_absolute_uri(reverse("wallet:dashboard")),
                "amount": amount * 100,  # Convert to Paisa
                "purchase_order_id": purchase_order_id,
                "purchase_order_name": purchase_order_name,
                "customer_info": {
                    "name": user.get_full_name() or user.username,
                    "email": user.email,
                    "phone": user.mobile_number or "9800000000", # Use a fallback
                },
            }

            headers = {
                "Authorization": f"key {KHALTI_SECRET_KEY}",
                "Content-Type": "application/json",
            }

            # 3. Make the API call to Khalti.
            response = requests.post(KHALTI_INITIATE_URL, json=payload, headers=headers)
            response_data = response.json()

            # 4. Check if the API call was successful.
            if response.status_code == 200 and "pidx" in response_data:
                # 5. Get the pidx and SAVE it to our transaction record.
                pidx_from_khalti = response_data.get('pidx')
                pending_transaction.khalti_pidx = pidx_from_khalti
                pending_transaction.save()
                
                # 6. Redirect the user to Khalti's payment page.
                return redirect(response_data['payment_url'])
            else:
                # If initiation fails, delete the pending record we created to keep the database clean.
                pending_transaction.delete()
                error_message = response_data.get("detail", "Failed to initiate payment. Please try again.")
                messages.error(request, f"Khalti Error: {error_message}")
                return redirect("wallet:load_money")

            # --- END OF CORRECTED LOGIC ---

        except Exception as e:
            messages.error(request, f"An unexpected error occurred: {e}")
            return redirect("wallet:load_money")

    return redirect("wallet:load_money")