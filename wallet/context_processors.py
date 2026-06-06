from transaction.models import Transaction

def wallet_context(request):
    context = {
        'wallet_balance': 0,
        'recent_transactions': None,
    }

    if request.user.is_authenticated:
        try:
            wallet_balance = request.user.wallet.balance
            
            # Follow the relationship from Transaction -> wallet -> user
            recent_transactions = Transaction.objects.filter(
                wallet__user=request.user
            ).order_by('-timestamp')[:5]

            context['wallet_balance'] = wallet_balance
            context['recent_transactions'] = recent_transactions
        
        except AttributeError:
            pass
    
    return context