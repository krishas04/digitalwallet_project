from django.urls import path
from . import views
from transaction.views import khalti_payment_callback  # Import the callback view

app_name = "wallet"

urlpatterns = [
    path("", views.index, name="index"),
    path("aboutus/", views.aboutus, name="aboutus"),
    path("services/", views.services, name="services"),
    path("contact/", views.contact, name="contact"),
    path("policies/", views.policies, name="policies"),
    path("help/", views.help, name="help"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
]
