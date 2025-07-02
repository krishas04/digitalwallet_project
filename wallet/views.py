from django.shortcuts import render
# from django.http import HttpResponse
from django.contrib.auth.decorators import login_required


def index(request):
    #  return HttpResponse('<h1>Welcome to Homepage</h1>')
    return render(request,'wallet/index.html')

def aboutus(request):
    return render(request,'wallet/aboutus.html')

def services(request):
    return render(request,'wallet/services.html')

def contact(request):
    return render(request,'wallet/contact.html')

def policies(request):
    return render(request,'wallet/policies.html')

def help(request):
    return render(request,'wallet/help.html')

@login_required
def dashboard_view(request):
    return render(request, "wallet/dashboard.html", {"user": request.user})
