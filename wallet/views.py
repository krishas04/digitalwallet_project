from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# We only need to import Transaction to display the history on the dashboard.
from transaction.models import Transaction


# --- VIEWS FOR STATIC PAGES ---
# These are fine here as they relate to the main user-facing 'wallet' site.
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


# --- CORE WALLET VIEW ---
# The ONLY core view that belongs in this file is the one that displays the dashboard.


def support_view(request):
    return render(request, "wallet/support.html")

@login_required
def dashboard_view(request):
<<<<<<< HEAD
    return render(request, "wallet/dashboard.html", {"user": request.user})

=======
    """
    Renders the main dashboard and fetches recent transactions to display.
    This view's only job is to SHOW information.
    """
    recent_transactions = Transaction.objects.filter(
        wallet__user=request.user
    ).order_by("-timestamp")[:5]

    context = {
        "recent_transactions": recent_transactions,
    }
    return render(request, "wallet/dashboard.html", context)


#
# The other views (`load_money_view`, `initiate_khalti_payment`, `transfer_money_view`)
# have been correctly moved to `transaction/views.py`.
#
>>>>>>> origin/feature/khalti_loadmoney3.0
