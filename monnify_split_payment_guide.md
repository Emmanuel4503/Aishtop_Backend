# 💳 Monnify Split Payment Setup Guide (1% Developer VAT)

This guide walks you through how to configure and run transaction splitting on your Monnify integration to route the **1% developer VAT/fee** to your OPay wallet, and the remaining **99%** to the business owner's main account.

---

## 1. How Split Payment Works in the System

When a customer pays for booking services or funds their wallet:
1. The backend triggers a request to the Monnify API to initialize a checkout session.
2. The payload includes an `incomeSplitConfig` block:
   * **Developer Sub-account**: Gets **1%** of the transaction amount.
   * **Owner Account**: Gets the remaining **99%** of the transaction amount.
3. Once payment is completed, Monnify automatically splits and routes the funds directly to the respective settlement destinations.

---

## 2. Your Account Configuration Details

To register your account as the developer destination:
* **Account Name**: `Ajani Isaiah olubunmi`
* **Bank**: `OPay` (Registered as **PAYCOM** in Monnify's banking index)
* **Bank Code**: `999992`
* **Account Number**: `8116711916`

---

## 3. Step-by-Step Integration Guide

There are **two ways** to set up the sub-account code. Either let the application register it automatically via API, or configure it manually from the Monnify Dashboard.

### Option A: Automatic Registration (Recommended & Easiest)
The system is built to dynamically register your account as a sub-account on the fly if it is not already present.

1. **Open your backend `.env` file** and configure the variables under the developer section:
   ```env
   # Developer Split Account (1% VAT / fee)
   MONNIFY_DEV_API_KEY='MK_PROD_...'          # Your Developer Api Key
   MONNIFY_DEV_SECRET_KEY='...'               # Your Developer Secret Key
   MONNIFY_DEV_CONTRACT_CODE='...'            # Your Developer Contract Code
   MONNIFY_DEV_WALLET_ACCOUNT='8116711916'
   MONNIFY_DEV_BANK_CODE='999992'
   MONNIFY_DEV_ACCOUNT_NAME='Ajani Isaiah olubunmi'
   MONNIFY_DEV_SUB_ACCOUNT_CODE=''            # Leave empty for auto-registration
   ```
2. **Leave `MONNIFY_DEV_SUB_ACCOUNT_CODE` empty (`''`)**.
3. When the first transaction is initialized, the system will:
   * Call the Monnify `POST /api/v1/sub-accounts` API using your OPay details.
   * Obtain the generated **Sub Account Code** (starting with `MFY_SUB_...`).
   * Automatically cache and reuse this code for all subsequent transaction splits.

---

### Option B: Manual Registration & Dashboard Code Retrieval
If you want to register the sub-account yourself on your Monnify Merchant portal and paste the code directly, follow these steps:

1. **Log in to Monnify**: Go to the [Monnify Dashboard](https://monnify.com).
2. **Navigate to Sub Accounts**: In the left sidebar, click on **Sub Accounts**.
3. **Add New Sub Account**: Click the **Create Sub Account** or **Add Sub Account** button.
4. **Enter Bank Information**:
   * **Account Name**: `Ajani Isaiah olubunmi`
   * **Bank**: Select `OPay` (If OPay isn't listed, look for `Paycom (OPay)` or `Paycom`).
   * **Account Number**: `8116711916`
   * **Split Percentage**: Set to `1.0` (this is the default fallback, but the code dynamically overrides this per transaction).
5. **Create**: Submit the form. Monnify will verify the account number and generate the sub-account.
6. **Copy Sub Account Code**: Locate your new sub-account in the list, and copy the **Sub Account Code** (e.g. `MFY_SUB_8907316744`).
7. **Configure `.env`**: Paste this code into your `.env` file:
   ```env
   MONNIFY_DEV_SUB_ACCOUNT_CODE='MFY_SUB_8907316744'
   ```

---

## 4. Verification Check

To confirm the splitting works:
1. Initiate a small payment (e.g., funding ₦1,000 to the wallet).
2. Complete the payment.
3. Log in to your **Monnify Merchant Dashboard** and check your transactions history. You should see a split icon next to the transaction, showing the breakdown:
   * **₦990** routed to the merchant wallet.
   * **₦10** (1% VAT) routed to your developer OPay sub-account.
