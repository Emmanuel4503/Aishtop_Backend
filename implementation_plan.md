# Select Multiple Services and Multiple Workers in Bookings

This plan outlines changes to allow customers to select multiple services and multiple workers during booking, and enables the admin to correct the selected workers from the admin dashboard.

## User Review Required

> [!IMPORTANT]
> - **Zero database breakage**: Instead of removing the original `service` and `worker` foreign key fields which would break existing database records and legacy queries, we are adding new ManyToMany fields and mapping layers.
> - **React Frontend simplified**: The React frontend only needs to send `services` (an array of service IDs) and `workers` (an array of worker IDs) to the standard booking endpoints.

---

## Proposed Changes

### Bookings App

#### [MODIFY] [models.py](file:///c:/Users/oladi/Documents/aishtop_server-main/bookings/models.py)
- Add `workers` ManyToManyField to the `Booking` model pointing to the custom user model (filtered by `role='worker'`).

#### [NEW] [0004_booking_workers.py](file:///c:/Users/oladi/Documents/aishtop_server-main/bookings/migrations/0004_booking_workers.py)
- Create migration file to add the `workers` ManyToManyField.

#### [MODIFY] [serializers.py](file:///c:/Users/oladi/Documents/aishtop_server-main/bookings/serializers.py)
- Add `services_details` field in `BookingSerializer` which returns the complete list of services (combining the primary service and any additional services).
- Add `workers` (writeable PrimaryKeyRelatedField list) and `workers_details` (nested serialized list) to `BookingSerializer` to support multiple workers.

#### [MODIFY] [views.py](file:///c:/Users/oladi/Documents/aishtop_server-main/bookings/views.py)
- Update `create_booking` view to accept `services` as an array of IDs and split them into `service` (the first element) and `additional_services` (the rest).
- Update `create_booking` to accept `workers` array of IDs and link them to the new `workers` relation.
- Update queue logic (`auto_assign_worker_for_booking`) to handle setting multiple workers to `busy`.
- Update worker action views (`worker_start_service` and `worker_complete_service`) so that workers assigned via the new ManyToMany field can start and complete tasks, and all associated workers are freed up (set to `available`) when the booking is completed.

---

### Admin Dashboard App

#### [MODIFY] [views.py](file:///c:/Users/oladi/Documents/aishtop_server-main/admin_dashboard/views.py)
- Update `admin_assign_worker` to accept a list of worker IDs (`worker_ids`) in addition to a single ID. It will assign all of them to the booking, set their statuses to `busy`, and free up any previously assigned workers.
- Update `admin_cancel_booking` to free up all workers currently associated with the cancelled booking.

---

## Verification Plan

### Automated Tests
We will perform standard Django checks to ensure the application compiles correctly:
- `python manage.py check` (if environment is set up by user)

### Manual Verification & React Integration Guide
We will provide a detailed React integration guide explaining:
1. **How to create a booking with multiple services and workers** (POST to `/api/bookings/`)
2. **How the admin updates/corrects the workers** (POST to `/api/admin/bookings/<ticket_id>/assign-worker/`)
3. **The payload structures** for requests and responses.
