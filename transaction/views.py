# Standard library imports
import os
import uuid
import json
from decimal import Decimal
import base64  # NEW: Added for Base64 encoding/decoding of encrypted bytes for storage

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
from django.utils import timezone # NEW: Added for getting current timestamp for transaction details

# Local application imports
from .models import Transaction
from users.models import CustomUser
from .aes_cipher import encrypt, decrypt  # Your custom AES functions

# Constants for Khalti API
KHALTI_INITIATE_URL = "https://dev.khalti.com/api/v2/epayment/initiate/" 
KHALTI_LOOKUP_URL = "https://dev.khalti.com/api/v2/epayment/lookup/"
KHALTI_SECRET_KEY = os.getenv("KHALTI_SECRET_KEY")


# LOAD MONEY SERVICE VIEWS 


@login_required
def load_money_view(request):
    """it renders the page where users can enter an amount to load."""
    return render(request, "transaction/load_money.html")


@login_required
def initiate_khalti_payment(request):
    
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
                description="Load money initiation via Khalti", # Description is plaintext for Khalti transactions
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
# --- TRANSFER MONEY SERVICE VIEWS (PIN-based, AES for Storage & Demo) ---
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
            # ## --- AES-256 ENCRYPTION FOR STORAGE & DEMO --- ##
            # ======================================================================
            print("\n--- AES-256 ENCRYPTION & DECRYPTION DEMO ---")
            
            # Prepare the ENTIRE transaction details dictionary for encryption
            full_transaction_details = {
                "from_email": sender.email, # NEW: Changed key for clarity
                "to_email": recipient.email, # NEW: Changed key for clarity
                "amount": str(amount), # Store as string to preserve decimal precision
                "currency": "NPR",
                "timestamp": str(timezone.now()), # NEW: Add timestamp for full detail
                "transaction_type": Transaction.TransactionType.TRANSFER, # NEW: Add transaction type
                "status": Transaction.TransactionStatus.COMPLETED, # NEW: Add status
                "original_description_for_console": f"Transferred to {recipient.username}", # NEW: For console demo clarity
            }
            
            # Convert dictionary to JSON string, then to bytes for encryption
            plaintext_bytes_sender = json.dumps(full_transaction_details).encode("utf-8") # NEW: Variable name for sender
            
            # --- Encryption Key Setup ---
            aes_key_str = os.getenv("AES_ENCRYPTION_KEY") # Get key as string from .env
            # NEW: Validate key length
            if not aes_key_str or len(aes_key_str.encode('utf-8')) != 32: # Check byte length
                print("\nFATAL ERROR: AES_ENCRYPTION_KEY is not 32 bytes (256-bit). Cannot encrypt/decrypt for demo or storage.\n")
                messages.error(request, "Encryption key is missing or invalid. Contact support.")
                return redirect("wallet:dashboard")
            
            # Convert key to bytes once
            aes_key_bytes = aes_key_str.encode("utf-8") # NEW: Convert key to bytes once

            # --- Perform Encryption and Decryption for Sender's Details (and Demo Output) ---
            # Encrypt
            encrypted_data_sender = encrypt(plaintext_bytes_sender, aes_key_bytes) # NEW: Use aes_key_bytes
            # Decrypt (for demo output to console)
            decrypted_bytes_sender = decrypt(encrypted_data_sender, aes_key_bytes) # NEW: Use aes_key_bytes

            print(f"SENDER Original Full Data:   {plaintext_bytes_sender.decode()}") # NEW: Updated print
            print(f"SENDER Encrypted (Hex): {encrypted_data_sender.hex()}") # NEW: Updated print
            print(f"SENDER Decrypted Full Data:  {decrypted_bytes_sender.decode()}") # NEW: Updated print
            
            # --- Prepare and Encrypt Recipient's Details (and Demo Output) ---
            # Tailor recipient's view of the transaction
            full_transaction_details_recipient = {
                "from_email": sender.email, # NEW: Changed key for clarity
                "to_email": recipient.email, # NEW: Changed key for clarity
                "amount": str(amount),
                "currency": "NPR",
                "timestamp": str(timezone.now()),
                "transaction_type": Transaction.TransactionType.TRANSFER,
                "status": Transaction.TransactionStatus.COMPLETED,
                "original_description_for_console": f"Received from {sender.username}", # NEW: For console demo clarity
            }
            plaintext_bytes_recipient = json.dumps(full_transaction_details_recipient).encode("utf-8") # NEW: Variable name
            encrypted_data_recipient = encrypt(plaintext_bytes_recipient, aes_key_bytes) # NEW: Use aes_key_bytes
            decrypted_bytes_recipient = decrypt(encrypted_data_recipient, aes_key_bytes) # For demo, NEW: Use aes_key_bytes

            print(f"RECIPIENT Original Full Data:   {plaintext_bytes_recipient.decode()}") # NEW: Updated print
            print(f"RECIPIENT Encrypted (Hex): {encrypted_data_recipient.hex()}") # NEW: Updated print
            print(f"RECIPIENT Decrypted Full Data:  {decrypted_bytes_recipient.decode()}") # NEW: Updated print
            
            print("--- END OF DEMO ---\n")
            # ======================================================================

            # Perform the database changes (balances)
            sender.wallet.balance -= amount
            sender.wallet.save()
            recipient.wallet.balance += amount
            recipient.wallet.save()

            # Log transactions - NOW STORING THE ENCRYPTED FULL DETAILS
            # We use base64.b64encode to store binary encrypted_data as a text string in the database
            # NEW: Store sender's encrypted details
            Transaction.objects.create(
                wallet=sender.wallet,
                transaction_type=Transaction.TransactionType.TRANSFER,
                amount=-amount,
                status=Transaction.TransactionStatus.COMPLETED,
                description=None, # NEW: Explicitly set original description to None as we're using encrypted_details
                encrypted_details=base64.b64encode(encrypted_data_sender).decode('utf-8'), # NEW: Store Base64 encoded ciphertext
            )
            # NEW: Store recipient's encrypted details
            Transaction.objects.create(
                wallet=recipient.wallet,
                transaction_type=Transaction.TransactionType.TRANSFER,
                amount=amount,
                status=Transaction.TransactionStatus.COMPLETED,
                description=None, # NEW: Explicitly set original description to None
                encrypted_details=base64.b64encode(encrypted_data_recipient).decode('utf-8'), # NEW: Store Base64 encoded ciphertext
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
# --- TRANSACTION HISTORY VIEW (DECRYPTION FOR DISPLAY) ---
# ==============================================================================
@login_required
def transaction_history_view(request):
    
    transactions_list = Transaction.objects.filter(wallet__user=request.user).order_by(
        "-timestamp"
    )

    aes_key_str = os.getenv("AES_ENCRYPTION_KEY") # NEW: Get key as string from .env
    # NEW: Validate key length
    if not aes_key_str or len(aes_key_str.encode('utf-8')) != 32:
        messages.error(request, "Encryption key is missing or invalid. Cannot display descriptions securely.")
        # If key is bad, we can't decrypt, so just set a placeholder description.
        for tx in transactions_list:
            tx.display_description = "[Encryption Key Error]"
    else:
        aes_key_bytes = aes_key_str.encode("utf-8") # NEW: Convert key to bytes once
        for tx in transactions_list:
            if tx.encrypted_details: # NEW: Check if encrypted_details field contains data
                try:
                    # Decode Base64 string from DB to bytes for decryption
                    ciphertext_bytes = base64.b64decode(tx.encrypted_details) # NEW: Use encrypted_details
                    decrypted_bytes = decrypt(ciphertext_bytes, aes_key_bytes) # NEW: Use aes_key_bytes
                    
                    # Decode the decrypted bytes into a JSON string, then parse to dictionary
                    decrypted_dict = json.loads(decrypted_bytes.decode('utf-8')) # NEW: Parse JSON
                    
                    # NEW: Construct a user-friendly description from the decrypted dictionary
                    # This logic helps make the history entry clear for the user viewing it.
                    if tx.transaction_type == Transaction.TransactionType.TRANSFER:
                        # For transfers, display 'Transferred to' or 'Received from' based on amount sign
                        if tx.amount < 0: # This is a debit from the current user's wallet
                            tx.display_description = f"Transferred to {decrypted_dict.get('to_email', 'Unknown User')}"
                        else: # This is a credit to the current user's wallet
                             tx.display_description = f"Received from {decrypted_dict.get('from_email', 'Unknown User')}"
                    elif tx.transaction_type == Transaction.TransactionType.LOAD:
                        # For Khalti loads, we might still use the original description if it was plaintext
                        # or display a generic one from the decrypted dict if it were encrypted.
                        # As per current load_money, description is plaintext.
                        tx.display_description = tx.description or f"Wallet Loaded via Khalti"
                    else:
                         tx.display_description = tx.description or f"{decrypted_dict.get('transaction_type', 'Transaction')} - {decrypted_dict.get('status', 'N/A')}"

                except (json.JSONDecodeError, Exception) as e: # NEW: Catch JSONDecodeError specifically
                    # Handle any decryption or JSON parsing errors
                    tx.display_description = "[Error: Decryption/Parsing Failed]"
                    print(f"Decryption/JSON error for transaction {tx.transaction_id}: {e}")
            else:
                # Fallback to the original plaintext description if encrypted_details is empty
                # This ensures Khalti transactions (or old ones) still display.
                tx.display_description = tx.description or "[No description available]" 


    paginator = Paginator(transactions_list, 10)
    page = request.GET.get("page")
    try:
        transactions = paginator.page(page)
    except PageNotAnInteger:
        transactions = paginator.page(1)
    except EmptyPage:
        transactions = paginator.page(paginator.num_pages)
    
    context = {"transactions": transactions} # Pass the transactions with decrypted descriptions
    return render(request, "transaction/transaction_history.html", context)