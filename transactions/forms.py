# transactions/forms.py

from django import forms
from decimal import Decimal

class LoadMoneyForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        min_value=Decimal('1.00'), # Set a minimum amount, e.g., $1
        label="Amount to Load (in USD)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 50.00'})
    )