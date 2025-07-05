from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction as db_transaction
from decimal import Decimal
import requests
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import Transaction

# Import your new conversion function and the form
from .services import create_paypal_order, capture_paypal_payment, convert_usd_to_npr
from wallet.models import Wallet
from .forms import LoadMoneyForm # <-- IMPORT THE FORM

# View 1: Show the form to load money (UPDATED)
@login_required
def load_money_view(request):
    if request.method == 'POST':
        # Use the Django Form for validation
        form = LoadMoneyForm(request.POST)
        if form.is_valid():
            amount_usd = form.cleaned_data['amount'] # This is the amount in USD
            
            # Build the full URLs for PayPal
            return_url = request.build_absolute_uri(reverse('transactions:paypal-capture'))
            cancel_url = request.build_absolute_uri(reverse('transactions:paypal-cancel'))
            
            try:
                # Create the PayPal order with the USD amount
                order_id, approval_link = create_paypal_order(amount_usd, return_url, cancel_url)
                
                if approval_link:
                    # Store the USD amount in the session
                    request.session['paypal_order_id'] = order_id
                    request.session['load_amount_usd'] = str(amount_usd) # Store USD amount
                    return redirect(approval_link)
                else:
                    messages.error(request, "Could not connect to PayPal. Please try again.")

            except requests.exceptions.HTTPError as e:
                # Catch specific PayPal API errors
                messages.error(request, f"PayPal error: {e.response.text}")
            except Exception as e:
                messages.error(request, f"An error occurred: {e}")
        
        # If form is not valid, it will fall through and re-render with errors
    else:
        form = LoadMoneyForm()
    
    # Notice the redirect now uses the namespace
    return render(request, 'transactions/load_money.html', {'form': form})


# View 2: Handle the return from PayPal after approval (UPDATED)
@login_required
def paypal_capture_view(request):
    order_id = request.session.get('paypal_order_id')
    amount_usd_str = request.session.get('load_amount_usd')
    
    if not order_id or not amount_usd_str:
        # Handle if something went wrong before this
        return redirect('transactions:load-money')

    try:
        # Step 3: Get the proof/receipt from PayPal that the money was sent.
        # This confirms the user's PayPal account has been DEDUCTED.
        capture_data = capture_paypal_payment(order_id)
        
        # Check if the receipt says "COMPLETED"
        if capture_data.get("status") == "COMPLETED":
            
            # This is the amount that was deducted from the user's PayPal
            amount_usd = Decimal(amount_usd_str)
            
            # Convert it for your wallet
            amount_npr = convert_usd_to_npr(amount_usd)
            
            with db_transaction.atomic():
                # Find the user's wallet in your database
                wallet = get_object_or_404(Wallet, user=request.user)
                
                # Step 4: INCREASE the wallet balance in your database.
                wallet.balance += amount_npr
                wallet.save()
                
                # Create a record of this successful deposit
                Transaction.objects.create(
                    user=request.user,
                    transaction_type='DEPOSIT',
                    amount=amount_npr,
                    status='COMPLETED',
                    paypal_order_id=order_id
                )
            
            messages.success(request, "Your wallet has been loaded successfully!")
            
            # Clean up and send the user to their dashboard
            del request.session['paypal_order_id']
            del request.session['load_amount_usd']
            return redirect('wallet:dashboard') # Redirect to the wallet dashboard
        else:
            # The receipt did not say "COMPLETED", so we don't increase the wallet balance.
            messages.error(request, "PayPal payment was not completed.")
            return redirect('transactions:load-money')

    except Exception as e:
        # An error happened, so we don't increase the wallet balance.
        messages.error(request, f"An error occurred: {e}")
        return redirect('transactions:load-money')
    
# View 3: Handle the cancellation (UPDATED)
@login_required
def paypal_cancel_view(request):
    messages.warning(request, "The payment process was cancelled.")
    # Clean up session
    if 'paypal_order_id' in request.session:
        del request.session['paypal_order_id']
    if 'load_amount_usd' in request.session:
        del request.session['load_amount_usd']
    return redirect('transactions:load-money') # Use namespace

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
    
    return render(request, 'transactions/transaction_history.html', context)