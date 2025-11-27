from django.urls import path
from . import views

app_name = "transaction"

urlpatterns = [
    
    path("load-money/", views.load_money_view, name="load_money"),
    path("initiate-khalti/", views.initiate_khalti_payment, name="initiate_khalti"),
    path("khalti-callback/", views.khalti_payment_callback, name="khalti_callback"),
    
    # The new entry point from the dashboard, it decides where to send the user.
    path("transfer/", views.transfer_dispatcher_view, name="transfer_dispatcher"),
    # 1: The page where user enters recipient/amount.
    path(
        "transfer/initiate/",
        views.transfer_money_initiate_view,
        name="transfer_money_initiate",
    ),
    # 2: The page where user enters their PIN to confirm.
    path(
        "transfer/confirm/",
        views.transfer_money_confirm_view,
        name="transfer_money_confirm",
    ),
    # Transaction History
    path("history/", views.transaction_history_view, name="transaction-history"),
]
