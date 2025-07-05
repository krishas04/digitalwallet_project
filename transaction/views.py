import os
import requests
from django.shortcuts import redirect
from django.contrib import messages
from django.db import transaction as db_transaction
from django.db.models import F
from .models import Transaction

# Khalti API URLs
KHALTI_LOOKUP_URL = "https://dev.khalti.com/api/v2/epayment/lookup/"
KHALTI_SECRET_KEY = os.getenv("KHALTI_SECRET_KEY")


def khalti_payment_callback(request):
    """
    Handles the callback from Khalti after the user has attempted payment.
    Verifies the transaction status with Khalti's server.
    """
    # Get the pidx from the URL parameters sent by Khalti
    pidx = request.GET.get("pidx")
    if not pidx:
        messages.error(
            request, "Invalid callback received from Khalti. Payment ID missing."
        )
        return redirect("wallet:dashboard")

    try:
        headers = {
            "Authorization": f"key {KHALTI_SECRET_KEY}",
            "Content-Type": "application/json",
        }
        payload = {"pidx": pidx}

        # Make the server-to-server verification call to Khalti
        response = requests.post(KHALTI_LOOKUP_URL, json=payload, headers=headers)
        response_data = response.json()

        status = response_data.get("status")

        # --- START OF CORRECTED LOGIC ---

        # Find our original transaction record using the pidx, which we saved earlier.
        transaction = Transaction.objects.filter(khalti_pidx=pidx).first()

        # --- END OF CORRECTED LOGIC ---

        if not transaction:
            # This error should not happen with the corrected logic.
            # It's here as a safeguard.
            messages.error(request, "Could not find the original transaction record.")
            return redirect("wallet:dashboard")

        # Check if we have already processed this transaction to prevent double-crediting money.
        if transaction.status != "PENDING":
            messages.warning(request, "This payment has already been processed.")
            return redirect("wallet:dashboard")

        # Use an atomic block to ensure the database updates happen all at once or not at all.
        with db_transaction.atomic():
            if status == "Completed":
                # --- SUCCESS CASE ---
                # 1. Update our transaction record to 'Completed'.
                transaction.status = Transaction.TransactionStatus.COMPLETED
                transaction.description = f"Wallet loaded successfully. Khalti Txn ID: {response_data.get('transaction_id')}"
                transaction.save()

                # 2. Update the user's wallet balance.
                wallet = transaction.wallet
                # Use F() expression for a safe, atomic database update.
                wallet.balance = F("balance") + transaction.amount
                wallet.save()

                # 3. Inform the user of their success.
                messages.success(
                    request,
                    f"Rs. {transaction.amount} loaded into your wallet successfully!",
                )
            else:
                # --- FAILURE CASE ---
                # 1. Mark our transaction as 'Failed'.
                transaction.status = Transaction.TransactionStatus.FAILED
                transaction.description = (
                    f"Khalti payment failed or was canceled. Status: {status}"
                )
                transaction.save()

                # 2. Inform the user of the failure.
                messages.error(
                    request, f"Payment was not successful. Status from Khalti: {status}"
                )

    except requests.exceptions.RequestException as req_err:
        messages.error(
            request,
            f"Could not connect to Khalti for verification. Please contact support. Error: {req_err}",
        )
    except Exception as e:
        messages.error(
            request, f"An unexpected error occurred during payment verification: {e}"
        )

    # Redirect to the dashboard in all cases. The user will see the success/error message there.
    return redirect("wallet:dashboard")
