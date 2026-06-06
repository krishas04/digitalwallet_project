# transactions/urls.py
from django.urls import path
from . import views

# Add this line for better URL management (Good Practice!)
app_name = 'transactions'

urlpatterns = [
    # CHANGE THIS LINE: Ensure the path is 'load-money/' and the name is 'load-money'
    path('load-money/', views.load_money_view, name='load-money'),
    
    # These should be correct from the previous step
    path('paypal/capture/', views.paypal_capture_view, name='paypal-capture'),
    path('paypal/cancel/', views.paypal_cancel_view, name='paypal-cancel'),

    path('history/', views.transaction_history_view, name='transaction-history'),
]