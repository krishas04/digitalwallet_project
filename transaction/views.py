# Standard library imports
import os
import uuid
import json
from decimal import Decimal

# Third-party imports
import requests

# Django imports
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.db import transaction as db_transaction
from django.db.models import F
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.hashers import check_password  # For checking the PIN

# Local application imports
from .models import Transaction
from users.models import CustomUser
from .aes_cipher import encrypt, decrypt  # For the encryption demo


# --- Constants for Khalti API ---
KHALTI_INITIATE_URL = "https://dev.khalti.com/api/v2/epayment/initiate/"
KHALTI_LOOKUP_URL = "https://dev.khalti.com/api/v2/epayment/lookup/"
KHALTI_SECRET_KEY = os.getenv("KHALTI_SECRET_KEY")


# ==============================================================================
# --- LOAD MONEY SERVICE VIEWS (No Change) ---
# ==============================================================================


@login_required
def load_money_view(request):
    """Renders the page where users can enter an amount to load."""
    return render(request, "transaction/load_money.html")


# (Your existing initiate_khalti_payment and khalti_payment_callback views go here, unchanged)
# ...
@login_required
def initiate_khalti_payment(request):
    # This function remains exactly as you provided it.
    if request.method == "POST":
        try:
            amount = int(float(request.POST.get("amount")))
            if amount < 10:
                messages.error(request, "Amount must be at least Rs. 10.")
                return redirect("transaction:load_money")

            user = request.user
            purchase_order_id = f"webpay-{user.username}-{uuid.uuid4()}"

            pending_transaction = Transaction.objects.create(
                wallet=user.wallet,
                transaction_type=Transaction.TransactionType.LOAD,
                amount=amount,
                status=Transaction.TransactionStatus.PENDING,
                description="Load money initiation via Khalti",
            )
            payload = {
                "return_url": request.build_absolute_uri(
                    reverse("transaction:khalti_callback")
                ),
                "website_url": request.build_absolute_uri(reverse("wallet:dashboard")),
                "amount": amount * 100,
                "purchase_order_id": purchase_order_id,
                "purchase_order_name": f"Load Wallet for {user.username}",
                "customer_info": {
                    "name": user.get_full_name() or user.username,
                    "email": user.email,
                    "phone": "9800000000",
                },
            }
            headers = {
                "Authorization": f"key {KHALTI_SECRET_KEY}",
                "Content-Type": "application/json",
            }
            response = requests.post(KHALTI_INITIATE_URL, json=payload, headers=headers)
            response_data = response.json()

            if response.status_code == 200 and "pidx" in response_data:
                pending_transaction.save()
                return redirect(response_data["payment_url"])
            else:
                pending_transaction.delete()
                messages.error(
                    request,
                    f"Khalti Error: {response_data.get('detail', 'Failed to initiate payment.')}",
                )
                return redirect("transaction:load_money")
        except Exception as e:
            messages.error(request, f"An unexpected error occurred: {e}")
            return redirect("transaction:load_money")
    return redirect("transaction:load_money")


def khalti_payment_callback(request):
    # This function remains exactly as you provided it.
    pidx = request.GET.get("pidx")
    if not pidx:
        messages.error(request, "Invalid callback received. Payment ID missing.")
        return redirect("wallet:dashboard")
    try:
        headers = {
            "Authorization": f"key {KHALTI_SECRET_KEY}",
            "Content-Type": "application/json",
        }
        payload = {"pidx": pidx}
        response = requests.post(KHALTI_LOOKUP_URL, json=payload, headers=headers)
        response_data = response.json()
        status = response_data.get("status")
        transaction = Transaction.objects.filter(
            status="PENDING", transaction_type="LOAD"
        ).latest("timestamp")
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
                messages.success(
                    request,
                    f"Rs. {transaction.amount} loaded into your wallet successfully!",
                )
            else:
                transaction.status = Transaction.TransactionStatus.FAILED
                transaction.description = (
                    f"Khalti payment failed or was canceled. Status: {status}"
                )
                transaction.save()
                messages.error(
                    request, f"Payment was not successful. Status from Khalti: {status}"
                )
    except Exception as e:
        messages.error(request, f"An error occurred during payment verification: {e}")
    return redirect("wallet:dashboard")


# ==============================================================================
# --- TRANSFER MONEY SERVICE VIEWS (PIN-based, AES Demo included) ---
# ==============================================================================


@login_required
def transfer_dispatcher_view(request):
    """
    Checks if a user has a PIN.
    - If YES, redirects to the transfer form.
    - If NO, redirects to the PIN creation page first.
    """
    if request.user.transaction_pin:
        return redirect("transaction:transfer_money_initiate")
    else:
        create_pin_url = reverse("users:create_pin")
        next_url = reverse("transaction:transfer_money_initiate")
        messages.info(
            request, "Please create a Transaction PIN before making a transfer."
        )
        return redirect(f"{create_pin_url}?next={next_url}")


@login_required
def transfer_money_initiate_view(request):
    """Step 1 of Transfer: User enters recipient's email and amount."""
    # This view is unchanged and correct.
    if request.method == "POST":
        recipient_email = request.POST.get("recipient_email")
        try:
            amount = Decimal(request.POST.get("amount"))
        except (ValueError, TypeError):
            messages.error(request, "Invalid amount entered.")
            return render(request, "transaction/transfer_money.html")

        sender = request.user
        if not recipient_email:
            messages.error(request, "Recipient email is required.")
        elif recipient_email == sender.email:
            messages.error(request, "You cannot transfer money to yourself.")
        elif amount <= 0:
            messages.error(request, "Transfer amount must be positive.")
        elif sender.wallet.balance < amount:
            messages.error(request, "You have insufficient funds.")
        elif not CustomUser.objects.filter(email=recipient_email).exists():
            messages.error(
                request, f"No user found with the email '{recipient_email}'."
            )
        else:
            request.session["transfer_data"] = {
                "recipient_email": recipient_email,
                "amount": str(amount),
            }
            return redirect("transaction:transfer_money_confirm")

        return render(request, "transaction/transfer_money.html")

    return render(request, "transaction/transfer_money.html")


@login_required
@db_transaction.atomic
def transfer_money_confirm_view(request):
    """Step 2 of Transfer: User enters PIN to authorize the transaction."""
    transfer_data = request.session.get("transfer_data")
    if not transfer_data:
        messages.warning(
            request, "Your session has expired. Please start the transfer again."
        )
        return redirect("transaction:transfer_money_initiate")

    recipient_email = transfer_data["recipient_email"]
    amount = Decimal(transfer_data["amount"])

    if request.method == "POST":
        pin = request.POST.get("pin")
        sender = request.user

        if check_password(pin, sender.transaction_pin):
            # --- PIN IS CORRECT, PROCEED ---
            recipient = CustomUser.objects.get(email=recipient_email)

            if sender.wallet.balance < amount:
                messages.error(
                    request, "Your balance became insufficient. Transaction cancelled."
                )
                del request.session["transfer_data"]
                return redirect("wallet:dashboard")

            # ======================================================================
            # ## --- AES DEMO ADDED BACK IN --- ##
            # ======================================================================
            print("\n--- AES-256 ENCRYPTION & DECRYPTION DEMO ---")
            transaction_details = {
                "from": sender.email,
                "to": recipient.email,
                "amount": str(amount),
                "currency": "NPR",
            }
            plaintext = json.dumps(transaction_details).encode("utf-8")
            aes_key = os.getenv("AES_ENCRYPTION_KEY").encode("utf-8")

            if len(aes_key) == 32:
                encrypted_data = encrypt(plaintext, aes_key)
                decrypted_bytes = decrypt(encrypted_data, aes_key)
                print(f"Original Data   : {plaintext.decode()}")
                print(f"Encrypted (Hex) : {encrypted_data.hex()}")
                print(f"Decrypted Data  : {decrypted_bytes.decode()}")
            else:
                print(
                    "\nFATAL ERROR: AES_ENCRYPTION_KEY is not 32 bytes. Skipping demo.\n"
                )
            print("--- END OF DEMO ---\n")
            # ======================================================================

            # Perform the database changes
            sender.wallet.balance -= amount
            sender.wallet.save()
            recipient.wallet.balance += amount
            recipient.wallet.save()

            # Log transactions
            Transaction.objects.create(
                wallet=sender.wallet,
                transaction_type=Transaction.TransactionType.TRANSFER,
                amount=-amount,
                status=Transaction.TransactionStatus.COMPLETED,
                description=f"Transferred to {recipient.username}",
            )
            Transaction.objects.create(
                wallet=recipient.wallet,
                transaction_type=Transaction.TransactionType.TRANSFER,
                amount=amount,
                status=Transaction.TransactionStatus.COMPLETED,
                description=f"Received from {sender.username}",
            )

            # Clean up and redirect
            del request.session["transfer_data"]
            messages.success(
                request,
                f"Successfully transferred Rs. {amount} to {recipient.username}.",
            )
            return redirect("wallet:dashboard")
        else:
            messages.error(request, "Incorrect PIN. Please try again.")

    context = {"recipient_email": recipient_email, "amount": amount}
    return render(request, "transaction/transfer_money_confirm.html", context)


# ==============================================================================
# --- TRANSACTION HISTORY VIEW (No Change) ---
# ==============================================================================


@login_required
def transaction_history_view(request):
    # This function remains exactly as you provided it.
    transactions_list = Transaction.objects.filter(wallet__user=request.user).order_by(
        "-timestamp"
    )
    paginator = Paginator(transactions_list, 10)
    page = request.GET.get("page")
    try:
        transactions = paginator.page(page)
    except PageNotAnInteger:
        transactions = paginator.page(1)
    except EmptyPage:
        transactions = paginator.page(paginator.num_pages)
    context = {"transactions": transactions}
    return render(request, "transaction/transaction_history.html", context)
