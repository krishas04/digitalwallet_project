from .models import Wallet


def wallet_context(request):
    if request.user.is_authenticated:
        try:
            wallet = Wallet.objects.get(user=request.user)
            return {"wallet_balance": wallet.balance}
        except Wallet.DoesNotExist:
            return {"wallet_balance": 0.00}
    return {}
