# wallet/context_processors.py

from transactions.models import Transaction

def wallet_context(request):
    # This function will run for every request
    
    # Initialize context with default values for anonymous users
    context = {
        'wallet_balance': 0,
        'recent_transactions': None,
    }

    # Check if the user is logged in
    if request.user.is_authenticated:
        try:
            # Get the wallet balance. The '.wallet' related_name is key here!
            wallet_balance = request.user.wallet.balance
            
            # Get the 5 most recent completed transactions for the user
            recent_transactions = Transaction.objects.filter(
                user=request.user,
            ).order_by('-timestamp')[:5]

            # Update the context for authenticated users
            context['wallet_balance'] = wallet_balance
            context['recent_transactions'] = recent_transactions
        
        except AttributeError:
            # This handles the rare case where a user might not have a wallet
            # (e.g., if the signal failed or for very old users).
            pass
    
    return context

