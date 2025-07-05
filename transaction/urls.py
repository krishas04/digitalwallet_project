from django.urls import path
from . import views

app_name = "transaction"

urlpatterns = [
    # URLs for Loading Money
    path("load-money/", views.load_money_view, name="load_money"),
    path("initiate-khalti/", views.initiate_khalti_payment, name="initiate_khalti"),
    path("khalti-callback/", views.khalti_payment_callback, name="khalti_callback"),
    # URL for Transferring Money

     path('history/', views.transaction_history_view, name='transaction-history'),
]
