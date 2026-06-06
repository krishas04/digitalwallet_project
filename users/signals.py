from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser
# This import might fail if the wallet app isn't set up correctly.
# If it does, please provide your wallet/models.py file.
from wallet.models import Wallet

@receiver(post_save, sender=CustomUser)
def create_user_wallet(sender, instance, created, **kwargs):
    """
    Creates a Wallet for a user as soon as they are created.
    This will now only be registered ONCE by Django.
    """
    if created:
        # Check if a wallet already exists, just in case.
        if not Wallet.objects.filter(user=instance).exists():
            Wallet.objects.create(user=instance)