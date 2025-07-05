import requests
from django.conf import settings
from decimal import Decimal

# 1. Function to get an Access Token

def get_paypal_access_token():
    """Get access token from PayPal."""
    # REVERT BACK TO THIS ORIGINAL CODE
    auth = (settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET)
    
    headers = {"Accept": "application/json", "Accept-Language": "en_US"}
    data = {"grant_type": "client_credentials"}
    
    url = f"{settings.PAYPAL_API_BASE_URL}/v1/oauth2/token"
    
    response = requests.post(url, auth=auth, headers=headers, data=data)
    response.raise_for_status()
    return response.json()["access_token"]

# 2. Function to create a PayPal Order
def create_paypal_order(amount, return_url, cancel_url):
    """Create a PayPal order and return the approval link."""
    access_token = get_paypal_access_token()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }
    
    # The payload for creating an order
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "amount": {
                    "currency_code": "USD", # Change if needed
                    "value": str(amount)
                }
            }
        ],
        "application_context": {
            "return_url": return_url,
            "cancel_url": cancel_url,
            "brand_name": "My Digital Wallet", # Your app name
            "user_action": "PAY_NOW",
        }
    }

    url = f"{settings.PAYPAL_API_BASE_URL}/v2/checkout/orders"
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    
    order_data = response.json()
    
    # Find the approval link
    approval_link = None
    for link in order_data.get("links", []):
        if link.get("rel") == "approve":
            approval_link = link["href"]
            break
            
    return order_data["id"], approval_link


# 3. Function to Capture the Payment
def capture_paypal_payment(order_id):
    """Capture payment for a given PayPal order ID."""
    access_token = get_paypal_access_token()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    url = f"{settings.PAYPAL_API_BASE_URL}/v2/checkout/orders/{order_id}/capture"
    response = requests.post(url, headers=headers)
    response.raise_for_status()
    
    capture_data = response.json()
    return capture_data

# New function to convert USD to NPR
def convert_usd_to_npr(amount_usd):
    """Convert USD amount to NPR using a fixed exchange rate."""
    # In a real app, get this from an API. For now, a fixed rate is fine.
    exchange_rate = Decimal('133.50') 
    return (amount_usd * exchange_rate).quantize(Decimal('0.01'))