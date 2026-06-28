import base64
import hmac
import hashlib
import requests
import logging
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

def get_monnify_token():
    """
    Authenticate with Monnify and get an access token.
    Uses Basic Auth with apiKey and secretKey.
    """
    cache_key = "monnify_access_token"
    token = cache.get(cache_key)
    if token:
        return token

    url = f"{settings.MONNIFY_BASE_URL.rstrip('/')}/api/v1/auth/login"
    
    # Base64 encode credentials
    credentials = f"{settings.MONNIFY_API_KEY}:{settings.MONNIFY_SECRET_KEY}"
    base64_creds = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {base64_creds}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, headers=headers, timeout=15)
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get("requestSuccessful"):
            token = response_data["responseBody"]["accessToken"]
            expires_in = response_data["responseBody"].get("expiresIn", 86400)
            
            # Cache the token, leaving a 5-minute buffer
            cache_time = max(60, expires_in - 300)
            cache.set(cache_key, token, cache_time)
            return token
        else:
            logger.error(f"Monnify auth failed: {response_data}")
            return None
    except Exception as e:
        logger.exception(f"Error fetching Monnify token: {str(e)}")
        return None


def get_or_create_developer_subaccount():
    """
    Retrieves or creates the developer sub-account for transaction splitting.
    Developer account details:
      Bank Code: 035 (Wema Bank)
      Account Number: settings.MONNIFY_DEV_WALLET_ACCOUNT
    """
    # If the sub-account code is pre-configured, use it immediately
    if getattr(settings, 'MONNIFY_DEV_SUB_ACCOUNT_CODE', None):
        return settings.MONNIFY_DEV_SUB_ACCOUNT_CODE

    token = get_monnify_token()
    if not token:
        # Fallback to mock subaccount code if API auth fails (useful for local development without credentials)
        return "MFY_SUB_DEV_MOCK_1"


    cache_key = "monnify_dev_subaccount_code"
    subaccount_code = cache.get(cache_key)
    if subaccount_code:
        return subaccount_code

    base_url = settings.MONNIFY_BASE_URL.rstrip('/')
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 1. Check if the sub-account already exists
    try:
        list_url = f"{base_url}/api/v1/sub-accounts"
        response = requests.get(list_url, headers=headers, timeout=15)
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get("requestSuccessful"):
            subaccounts = response_data.get("responseBody", [])
            for sub in subaccounts:
                if sub.get("accountNumber") == settings.MONNIFY_DEV_WALLET_ACCOUNT:
                    sub_code = sub.get("subAccountCode")
                    cache.set(cache_key, sub_code, 86400)  # Cache for 24h
                    return sub_code
    except Exception as e:
        logger.warning(f"Failed to fetch Monnify sub-accounts: {str(e)}")

    # 2. If not found, create a new sub-account
    create_url = f"{base_url}/api/v1/sub-accounts"
    payload = [
        {
            "currencyCode": "NGN",
            "accountNumber": settings.MONNIFY_DEV_WALLET_ACCOUNT,
            "bankCode": getattr(settings, "MONNIFY_DEV_BANK_CODE", "035"),
            "email": "developer@oratech.com.ng",
            "defaultSplitPercentage": 1.0,
            "accountName": getattr(settings, "MONNIFY_DEV_ACCOUNT_NAME", "Developer Split Account")
        }
    ]
    
    try:
        response = requests.post(create_url, json=payload, headers=headers, timeout=15)
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get("requestSuccessful"):
            created_accounts = response_data.get("responseBody", [])
            if created_accounts:
                sub_code = created_accounts[0].get("subAccountCode")
                cache.set(cache_key, sub_code, 86400)
                return sub_code
        logger.error(f"Failed to create developer sub-account in Monnify: {response_data}")
    except Exception as e:
        logger.exception(f"Exception during sub-account creation: {str(e)}")
        
    return "MFY_SUB_DEV_MOCK_1"


def initialize_monnify_payment(amount, reference, email, name, description, redirect_url=None):
    """
    Initialize a checkout payment session on Monnify.
    Sets up dynamic splitting where 1% goes to the developer's sub-account.
    """
    token = get_monnify_token()
    if not token:
        raise ValueError("Failed to authenticate with Monnify payment gateway. Please verify API credentials.")
    
    # Default redirect fallback url
    if not redirect_url:
        redirect_url = "http://localhost:8000/api/payments/monnify-webhook/"

    subaccount_code = get_or_create_developer_subaccount()

    # Split: 1% to developer sub-account, remainder to main business account
    # Omit split configuration if developer sub-account is not successfully created
    income_split_config = []
    if subaccount_code and subaccount_code != "MFY_SUB_DEV_MOCK_1":
        income_split_config = [
            {
                "subAccountCode": subaccount_code,
                "feePercentage": 0.0,
                "splitPercentage": 1.0,
                "feeBearer": False
            }
        ]

    payload = {
        "amount": float(amount),
        "customerName": name,
        "customerEmail": email,
        "paymentReference": reference,
        "paymentDescription": description,
        "currencyCode": "NGN",
        "contractCode": settings.MONNIFY_CONTRACT_CODE,
        "redirectUrl": redirect_url,
        "paymentMethods": ["CARD", "ACCOUNT_TRANSFER", "USSD"],
        "incomeSplitConfig": income_split_config
    }

    url = f"{settings.MONNIFY_BASE_URL.rstrip('/')}/api/v1/merchant/transactions/init-transaction"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get("requestSuccessful"):
            return {
                "checkoutUrl": response_data["responseBody"]["checkoutUrl"],
                "transactionReference": response_data["responseBody"]["transactionReference"]
            }
        else:
            logger.error(f"Monnify payment initialization failed: {response_data}")
            error_msg = response_data.get("responseMessage", "Unknown error occurred on Monnify.")
            raise ValueError(f"Monnify payment initialization failed: {error_msg}")
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        logger.exception(f"Error initializing Monnify payment: {str(e)}")
        raise ValueError(f"Monnify payment gateway error: {str(e)}")


def verify_monnify_webhook_signature(raw_body_bytes, signature):
    """
    Verify the signature sent in Monnify webhook header.
    HMAC-SHA512 of request body using client secret key.
    """
    if not signature:
        return False
    
    key = settings.MONNIFY_SECRET_KEY.encode('utf-8')
    computed_hash = hmac.new(key, raw_body_bytes, hashlib.sha512).hexdigest()
    
    return hmac.compare_digest(computed_hash, signature)


def verify_monnify_payment(payment_reference):
    """
    Query Monnify API to get the current status of a payment.
    """
    token = get_monnify_token()
    if not token:
        logger.error("Failed to get Monnify token for verification")
        return None

    url = f"{settings.MONNIFY_BASE_URL.rstrip('/')}/api/v2/merchant/transactions/query"
    params = {"paymentReference": payment_reference}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response_data = response.json()
        if response.status_code == 200 and response_data.get("requestSuccessful"):
            return response_data.get("responseBody")
        else:
            logger.error(f"Monnify transaction query failed: {response_data}")
            return None
    except Exception as e:
        logger.exception(f"Error querying Monnify transaction {payment_reference}: {str(e)}")
        return None
