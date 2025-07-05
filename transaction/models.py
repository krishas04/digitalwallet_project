import uuid
from django.db import models
from wallet.models import Wallet


class Transaction(models.Model):
    class TransactionStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    class TransactionType(models.TextChoices):
        LOAD = "LOAD", "Load"
        TRANSFER = "TRANSFER", "Transfer"
        PAYMENT = "PAYMENT", "Payment"

    transaction_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    wallet = models.ForeignKey(
        Wallet, on_delete=models.CASCADE, related_name="transactions"
    )
    transaction_type = models.CharField(max_length=10, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=10,
        choices=TransactionStatus.choices,
        default=TransactionStatus.PENDING,
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=255, blank=True)

    # Fields for Khalti integration
    purchase_order_id = models.CharField(
        max_length=255, unique=True, null=True, blank=True
    )
    khalti_pidx = models.CharField(max_length=255, unique=True, null=True, blank=True)

    def __str__(self):
        return f"{self.transaction_type} - {self.status} - {self.amount}"
