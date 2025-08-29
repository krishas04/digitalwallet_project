import os
import uuid
import requests
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.db import transaction as db_transaction
from django.contrib import messages
from transaction.models import Transaction
from .models import Wallet


# --- VIEWS FOR STATIC PAGES (UNCHANGED) ---
def index(request):
    return render(request, "wallet/index.html")

def aboutus(request):
    return render(request, "wallet/aboutus.html")

def services(request):
    return render(request, "wallet/services.html")

def contact(request):
    return render(request, "wallet/contact.html")

def policies(request):
    return render(request, "wallet/policies.html")

def help(request):
    return render(request, "wallet/help.html")


# --- CORE APPLICATION VIEWS (CORRECTED) ---

def support_view(request):
    return render(request, "wallet/support.html")

@login_required
def dashboard_view(request):
    return render(request, "wallet/dashboard.html", {"user": request.user})

@login_required
def all_services_view(request):
    """Renders the dedicated page listing all user services."""
    return render(request, "wallet/all_services.html")