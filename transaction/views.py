import os
import uuid
import requests

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.db import transaction as db_transaction
from django.db.models import F
from django.contrib import messages

# Local application imports needed for Load Money
from .models import Transaction

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger



# --- Constants for Khalti API ---
KHALTI_INITIATE_URL = "https://dev.khalti.com/api/v2/epayment/initiate/"
KHALTI_LOOKUP_URL = "https://dev.khalti.com/api/v2/epayment/lookup/"
KHALTI_SECRET_KEY = os.getenv("KHALTI_SECRET_KEY")


# ==============================================================================
# --- LOAD MONEY SERVICE VIEWS ---
# ==============================================================================

@login_required
def load_money_view(request):
    """ Renders the page where users can enter an amount to load. """
    return render(request, "transaction/load_money.html")


@login_required
def initiate_khalti_payment(request):
    """
    Receives the amount from the form, creates a PENDING transaction,
    and redirects the user to Khalti's payment page.
    """
    if request.method == "POST":
        try:
            amount = int(float(request.POST.get("amount")))
            if amount < 10:
                messages.error(request, "Amount must be at least Rs. 10.")
                return redirect("transaction:load_money")

            user = request.user
            purchase_order_id = f"webpay-{user.username}-{uuid.uuid4()}"

            # Create a pending transaction record
            pending_transaction = Transaction.objects.create(
                wallet=user.wallet,
                transaction_type=Transaction.TransactionType.LOAD,
                amount=amount,
                status=Transaction.TransactionStatus.PENDING,
                description="Load money initiation via Khalti",
                purchase_order_id=purchase_order_id,
            )

            # Prepare data for Khalti API
            payload = {
                "return_url": request.build_absolute_uri(reverse("transaction:khalti_callback")),
                "website_url": request.build_absolute_uri(reverse("wallet:dashboard")),
                "amount": amount * 100,
                "purchase_order_id": purchase_order_id,
                "purchase_order_name": f"Load Wallet for {user.username}",
                "customer_info": {
                    "name": user.get_full_name() or user.username,
                    "email": user.email,
                    "phone": user.mobile_number or "9800000000"
                },
            }
            headers = { "Authorization": f"key {KHALTI_SECRET_KEY}", "Content-Type": "application/json" }

            # Call Khalti API
            response = requests.post(KHALTI_INITIATE_URL, json=payload, headers=headers)
            response_data = response.json()

            if response.status_code == 200 and "pidx" in response_data:
                # If successful, save the pidx and redirect user
                pidx_from_khalti = response_data.get('pidx')
                pending_transaction.khalti_pidx = pidx_from_khalti
                pending_transaction.save()
                return redirect(response_data['payment_url'])
            else:
                # If failed, delete the pending record and show error
                pending_transaction.delete()
                messages.error(request, f"Khalti Error: {response_data.get('detail', 'Failed to initiate payment.')}")
                return redirect("transaction:load_money")

        except Exception as e:
            messages.error(request, f"An unexpected error occurred: {e}")
            return redirect("transaction:load_money")
            
    return redirect("transaction:load_money")


def khalti_payment_callback(request):
    """
    Handles the callback from Khalti. Verifies the transaction status and updates
    the user's wallet and transaction record accordingly.
    """
    pidx = request.GET.get("pidx")
    if not pidx:
        messages.error(request, "Invalid callback received. Payment ID missing.")
        return redirect("wallet:dashboard")

    try:
        headers = { "Authorization": f"key {KHALTI_SECRET_KEY}", "Content-Type": "application/json" }
        payload = {"pidx": pidx}
        response = requests.post(KHALTI_LOOKUP_URL, json=payload, headers=headers)
        response_data = response.json()
        status = response_data.get("status")

        transaction = Transaction.objects.filter(khalti_pidx=pidx).first()
        if not transaction:
            messages.error(request, "Could not find the original transaction record.")
            return redirect("wallet:dashboard")

        if transaction.status != "PENDING":
            messages.warning(request, "This payment has already been processed.")
            return redirect("wallet:dashboard")

        with db_transaction.atomic():
            if status == "Completed":
                transaction.status = Transaction.TransactionStatus.COMPLETED
                transaction.description = f"Wallet loaded successfully. Khalti Txn ID: {response_data.get('transaction_id')}"
                transaction.save()
                
                wallet = transaction.wallet
                wallet.balance = F("balance") + transaction.amount
                wallet.save()
                
                messages.success(request, f"Rs. {transaction.amount} loaded into your wallet successfully!")
            else:
                transaction.status = Transaction.TransactionStatus.FAILED
                transaction.description = f"Khalti payment failed or was canceled. Status: {status}"
                transaction.save()
                messages.error(request, f"Payment was not successful. Status from Khalti: {status}")

    except Exception as e:
        messages.error(request, f"An error occurred during payment verification: {e}")
        
    return redirect("wallet:dashboard")


@login_required
def transaction_history_view(request):
    """
    Fetches and displays the complete transaction history for the logged-in user
    with pagination.
    """
    # Fetch all transaction objects for the current user, ordered by most recent first.
    # This is now a base queryset that we will paginate.
    transaction_list = Transaction.objects.filter(user=request.user).order_by('-timestamp')
    
    # Set up the Paginator: 25 transactions per page.
    paginator = Paginator(transaction_list, 25) 
    
    # Get the page number from the GET request's 'page' parameter.
    # e.g., /transactions/?page=2
    page_number = request.GET.get('page')
    
    try:
        # Get the Page object for the requested page number.
        transactions_on_page = paginator.page(page_number)
    except PageNotAnInteger:
        # If the 'page' parameter is not an integer, show the first page.
        transactions_on_page = paginator.page(1)
    except EmptyPage:
        # If the page is out of range (e.g., page 9999), show the last page.
        transactions_on_page = paginator.page(paginator.num_pages)
    
    # The context now passes the 'Page' object to the template.
    # The template loop will iterate over the transactions on this specific page.
    context = {
        'transactions': transactions_on_page
    }
    
    return render(request, 'transaction/transaction_history.html', context)