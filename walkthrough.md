# Booking Service and Monnify Split Payment Walkthrough

This document outlines the architecture, database models, APIs, and verification results for the completed Booking Service and Admin Dashboard.

---

## 1. Summary of Changes

### Database & User Profile Enhancements
- Added the **`MembershipLevel`** model dynamically managed by the owner (`accounts/models.py`).
- Enhanced **`CustomUser`** with fields for `wallet_balance`, `total_deposited`, and `worker_status` (`available` / `busy`), and dynamically resolved membership level benefits/discounts based on deposit thresholds.
- Updated `UserSerializer` to expose the new fields in JSON payloads (`accounts/serializers.py`).

### New 'bookings' Application
- Created the **`bookings`** app to hold models, serializers, views, and urls for general client operations.
- Implemented models:
  - `ServiceCategory`: Categorizes salon services (e.g. Haircut, Wig Services, Pedicure).
  - `Service`: Holds details for specific salon offerings, prices, and durations.
  - `Booking`: Manages the lifecycle of walk-in/scheduled tickets, payment references, guest/customer profiles, and pricing calculations.
  - `WalletTransaction`: Logs wallet deposit/spend activities.
- Implemented Monnify integration library (`bookings/monnify.py`):
  - Dynamic bearer token generation using basic auth.
  - **Dynamic transaction splitting**: Automatically registers the developer's wallet (`4756256291` under Wema Bank `035`) as a sub-account if not present, and uses `incomeSplitConfig` to route 1% to the developer subaccount (displayed as VAT) and 99% to the business account. Allows direct override via setting `MONNIFY_DEV_SUB_ACCOUNT_CODE`.
  - Secure webhook receiver with HMAC-SHA512 header verification to confirm payments and wallets.
- Created worker endpoints (`bookings/views.py`):
  - Ticket verification.
  - Service start/complete lifecycle.
  - **Queue auto-assignment**: When a worker completes a service, the system automatically assigns the oldest waiting paid walk-in booking to them, updating their status to `busy` and the booking status to `assigned`.

### New 'admin_dashboard' Application
- Created the **`admin_dashboard`** app specifically for salon owner capabilities (`role = 'owner'`).
- Implemented owner permission restrictions (`admin_dashboard/permissions.py`).
- Implemented owner views (`admin_dashboard/views.py`):
  - CRUD operations over Service Categories, Services, and Membership Levels.
  - Queue management (rescheduling appointments and cancelling bookings).
  - Analytics and metrics (Daily/Weekly/Monthly/Overall revenues, Customer spending and visit history, Worker job counts and revenue generation).

---

## 2. Default Seeded Data

Running `python manage.py seed_services` populates the database with:
- **Membership Levels**:
  - **Silver** (Min Deposit ₦10,000): 5% discount
  - **Gold** (Min Deposit ₦50,000): 10% discount
  - **VIP** (Min Deposit ₦100,000): 15% discount
- **Service Categories & Services**:
  - **Hair Cut & Dye**: Barbing cut and dye (₦5,000), Barbing (₦3,000)
  - **Hair Locking**: Relocking (₦20,000), Dread (₦40,000)
  - **Wig Services**: Swiss lace Installation (₦15,000), HD Lace Installation (₦25,000), Wig styling (₦15,000), Revamping & styling (₦15,000)
  - **Pedicure**: Male Pedicure (₦15,000), Female Pedicure (₦10,000)

---

## 3. Verification & Test Results

A comprehensive unit test suite has been implemented across the apps:
- `bookings/tests.py`: 8 new tests verifying services listing, guest/registered booking, pricing discounts, Monnify checkout, webhook handling, wallet deposit, and worker queue assignment.
- `admin_dashboard/tests.py`: 8 new tests verifying owner CRUD operations, analytics reports, cancel/reschedule actions, and customer/worker role authorization blocks.

### Test Execution Output

```powershell
.venv\Scripts\python manage.py test
```

```text
Found 28 test(s).
System check identified no issues (0 silenced).
............................
----------------------------------------------------------------------
Ran 28 tests in 244.544s

OK
Destroying test database for alias 'default'...
```

All 28 tests executed and passed successfully.
