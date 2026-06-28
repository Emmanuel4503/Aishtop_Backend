from django.shortcuts import render
from django.conf import settings
from django.utils import timezone
from rest_framework import status, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from decimal import Decimal
import logging
import json
from django.db.models import Q

from accounts.models import CustomUser
from accounts.serializers import UserSerializer
from .models import ServiceCategory, Service, Booking, WalletTransaction
from .serializers import (
    ServiceCategorySerializer,
    ServiceSerializer,
    BookingSerializer,
    WalletTransactionSerializer
)
from .monnify import (
    initialize_monnify_payment,
    verify_monnify_webhook_signature,
    verify_monnify_payment
)

logger = logging.getLogger(__name__)


def auto_assign_worker_for_booking(booking):
    """
    Check if there are any available workers. If so, assign the oldest available
    worker to this booking, update status to 'assigned', and set worker status to 'busy'.
    Now supports multiple workers in booking.workers ManyToManyField.
    """
    if booking.service_status == 'waiting' and booking.payment_status == 'paid':
        # If workers are explicitly selected/assigned to this booking:
        assigned_workers = list(booking.workers.all())
        if assigned_workers:
            booking.service_status = 'assigned'
            booking.save()
            for worker in assigned_workers:
                worker.worker_status = 'busy'
                worker.save()
            return True

        if booking.worker:
            booking.service_status = 'assigned'
            booking.save()
            booking.worker.worker_status = 'busy'
            booking.worker.save()
            booking.workers.add(booking.worker)
            return True

        if booking.booking_type == 'walk_in':
            available_worker = CustomUser.objects.filter(
                role='worker',
                worker_status='available',
                is_active=True
            ).first()
            
            if available_worker:
                booking.worker = available_worker
                booking.workers.add(available_worker)
                booking.service_status = 'assigned'
                booking.save()
                
                available_worker.worker_status = 'busy'
                available_worker.save()
                return True
    return False


def assign_next_waiting_booking(worker):
    """
    Search for the oldest paid walk_in booking in 'waiting' state,
    assign it to this worker, update status, and set worker status to 'busy'.
    """
    booking = Booking.objects.filter(
        booking_type='walk_in',
        service_status='waiting',
        payment_status='paid'
    ).order_by('created_at').first()
    
    if booking:
        booking.worker = worker
        booking.service_status = 'assigned'
        booking.save()
        
        worker.worker_status = 'busy'
        worker.save()
        return booking
    return None


@swagger_auto_schema(
    method='get',
    responses={
        200: openapi.Response(
            description="Success - Returns list of service categories and nested services",
            schema=ServiceCategorySerializer(many=True)
        )
    },
    operation_description="Retrieve a list of all service categories and their respective services."
)
@api_view(['GET'])
@permission_classes([AllowAny])
def list_services(request):
    """
    Retrieve all service categories and their services.
    """
    categories = ServiceCategory.objects.all().prefetch_related('services')
    serializer = ServiceCategorySerializer(categories, many=True)
    return Response({
        'status': 'success',
        'message': 'Services retrieved successfully.',
        'data': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_service_detail(request, pk):
    """
    Retrieve details of a single service by ID.
    """
    try:
        service = Service.objects.get(pk=pk)
        serializer = ServiceSerializer(service)
        return Response({
            'status': 'success',
            'message': 'Service details retrieved successfully.',
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    except Service.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Service not found.'
        }, status=status.HTTP_404_NOT_FOUND)


class BookingCreateRequestSerializer(serializers.Serializer):
    service = serializers.IntegerField(help_text="ID of the Service to book")
    booking_type = serializers.ChoiceField(choices=['walk_in', 'scheduled'], help_text="walk_in (serve today) or scheduled")
    payment_method = serializers.ChoiceField(choices=['wallet', 'monnify'], help_text="wallet (registered users only) or monnify")
    scheduled_date = serializers.DateField(required=False, help_text="Required if booking_type is scheduled. Format: YYYY-MM-DD")
    scheduled_time = serializers.TimeField(required=False, help_text="Required if booking_type is scheduled. Format: HH:MM:SS")
    guest_name = serializers.CharField(required=False, help_text="Required for guest bookings")
    guest_email = serializers.EmailField(required=False, help_text="Required for guest bookings")
    guest_phone = serializers.CharField(required=False, help_text="Required for guest bookings")


@swagger_auto_schema(
    method='post',
    request_body=BookingCreateRequestSerializer,
    responses={
        201: openapi.Response(
            description="Booking created successfully",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'status': openapi.Schema(type=openapi.TYPE_STRING, example="success"),
                    'message': openapi.Schema(type=openapi.TYPE_STRING, example="Booking created successfully."),
                    'data': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'booking': openapi.Schema(type=openapi.TYPE_OBJECT, description="Serialized Booking details"),
                            'checkout_url': openapi.Schema(type=openapi.TYPE_STRING, description="Monnify checkout URL (for monnify payments)"),
                            'payment_reference': openapi.Schema(type=openapi.TYPE_STRING, description="Unique payment reference")
                        }
                    )
                }
            )
        ),
        400: 'Bad Request - Validation errors',
        402: 'Payment Required - Insufficient wallet balance'
    },
    operation_description="Create a booking/ticket for a service. Guest users must provide guest details. Registered users use wallet or Monnify."
)
@api_view(['POST'])
@permission_classes([AllowAny])
def create_booking(request):
    """
    Create a new booking/ticket.
    """
    data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
    
    if 'services' in data:
        services_list = data.get('services')
        if isinstance(services_list, list) and len(services_list) > 0:
            data['service'] = services_list[0]
            data['additional_services'] = services_list[1:]
        elif isinstance(services_list, list) and len(services_list) == 0:
            return Response({
                'status': 'error',
                'message': 'At least one service must be selected.'
            }, status=status.HTTP_400_BAD_REQUEST)

    serializer = BookingSerializer(data=data, context={'request': request})
    if not serializer.is_valid():
        return Response({
            'status': 'error',
            'message': 'Validation failed.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
    service = serializer.validated_data['service']
    additional_services = serializer.validated_data.pop('additional_services', [])
    booking_type = serializer.validated_data.get('booking_type', 'walk_in')
    payment_method = serializer.validated_data.get('payment_method', 'monnify')

    # Sum pricing across primary + additional services
    all_services = [service] + list(additional_services)
    base_price = sum(s.price for s in all_services)
    discount_applied = Decimal('0.00')

    # Check if registered user and apply discount
    is_authenticated = request.user and request.user.is_authenticated
    if is_authenticated:
        discount_pct = Decimal(str(request.user.discount_percentage))
        if discount_pct > 0:
            discount_applied = (base_price * discount_pct) / Decimal('100.00')

    net_price = base_price - discount_applied

    # Calculate 1% developer split (shown as VAT)
    vat_amount = net_price * Decimal('0.01')
    total_price = net_price + vat_amount

    # Retrieve and assign selected workers/worker if specified
    workers_input = request.data.get("workers", [])
    worker_id = request.data.get("worker")
    
    primary_worker = None
    worker_instances = []
    
    if isinstance(workers_input, list) and len(workers_input) > 0:
        for w_id in workers_input:
            try:
                w_user = CustomUser.objects.get(id=w_id, role="worker")
                worker_instances.append(w_user)
            except (CustomUser.DoesNotExist, ValueError):
                pass
        if worker_instances:
            primary_worker = worker_instances[0]
    elif worker_id and worker_id != "any":
        try:
            w_user = CustomUser.objects.get(id=worker_id, role="worker")
            primary_worker = w_user
            worker_instances.append(w_user)
        except (CustomUser.DoesNotExist, ValueError):
            pass

    # Create booking instance
    booking = serializer.save(
        user=request.user if is_authenticated else None,
        worker=primary_worker,
        base_price=base_price,
        discount_applied=discount_applied,
        vat_amount=vat_amount,
        total_price=total_price,
        payment_status='pending',
        service_status='waiting'
    )

    # Attach additional services via M2M
    if additional_services:
        booking.additional_services.set(additional_services)
    
    # Attach workers via M2M
    if worker_instances:
        booking.workers.set(worker_instances)
        
    booking.save()
    
    # Handle payments
    if payment_method == 'wallet':
        if not is_authenticated:
            booking.delete()
            return Response({
                'status': 'error',
                'message': 'Guest users cannot pay using wallet. Please register or choose Monnify.'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        user = request.user
        if user.wallet_balance < total_price:
            booking.delete()
            return Response({
                'status': 'error',
                'message': f'Insufficient wallet balance. You need ₦{total_price:,.2f} but only have ₦{user.wallet_balance:,.2f}.'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Deduct wallet balance
        user.wallet_balance -= total_price
        user.save()
        
        # Log wallet transaction
        WalletTransaction.objects.create(
            user=user,
            amount=total_price,
            transaction_type='spend',
            payment_method='wallet',
            payment_status='success',
            payment_reference=booking.payment_reference
        )
        
        booking.payment_status = 'paid'
        booking.save()
        
        # Trigger worker auto-assignment
        auto_assign_worker_for_booking(booking)
        
        # Reload booking to include updated fields
        booking.refresh_from_db()
        return Response({
            'status': 'success',
            'message': 'Booking paid successfully via wallet. Your ticket is confirmed!',
            'data': {
                'booking': BookingSerializer(booking).data
            }
        }, status=status.HTTP_201_CREATED)
        
    elif payment_method == 'monnify':
        # Initialize Monnify checkout payment
        email = request.user.email if is_authenticated else booking.guest_email
        name = request.user.full_name if is_authenticated else booking.guest_name
        all_service_names = ", ".join(s.name for s in all_services)
        description = f"Payment for: {all_service_names} (Ticket {booking.ticket_id})"

        if is_authenticated:
            redirect_url = f"{settings.FRONTEND_URL}/appointments"
        else:
            # No query params here — Monnify appends ?paymentReference=xxx itself.
            # If we put ?reference=xxx, Monnify appends ?paymentReference=xxx with another
            # '?' making the reference value "REF-xxx?paymentReference=REF-xxx".
            redirect_url = f"{settings.FRONTEND_URL}/booking-success"

        try:
            payment_details = initialize_monnify_payment(
                amount=total_price,
                reference=booking.payment_reference,
                email=email,
                name=name,
                description=description,
                redirect_url=redirect_url,
            )
            
            booking.monnify_transaction_reference = payment_details.get("transactionReference")
            booking.save()
            
            return Response({
                'status': 'success',
                'message': 'Booking initiated. Please complete payment using the checkout URL.',
                'data': {
                    'booking': BookingSerializer(booking).data,
                    'checkout_url': payment_details.get("checkoutUrl"),
                    'payment_reference': booking.payment_reference
                }
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            booking.delete()
            return Response({
                'status': 'error',
                'message': f"Failed to initialize Monnify payment: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    responses={
        200: openapi.Response(
            description="Success - Returns user's booking history",
            schema=BookingSerializer(many=True)
        ),
        401: 'Unauthorized - Missing token'
    },
    operation_description="Retrieve a list of bookings/tickets created by the logged-in user."
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_user_bookings(request):
    """
    Retrieve logged-in user's booking history.
    """
    bookings = Booking.objects.filter(user=request.user, payment_status='paid').order_by('-created_at')
    serializer = BookingSerializer(bookings, many=True)
    return Response({
        'status': 'success',
        'message': 'Booking history retrieved successfully.',
        'data': serializer.data
    }, status=status.HTTP_200_OK)


class WalletDepositRequestSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, help_text="Amount to deposit in Naira")


@swagger_auto_schema(
    method='get',
    responses={
        200: 'Success - Returns wallet transactions list',
        401: 'Unauthorized'
    },
    operation_description="Retrieve logged-in user's wallet transaction logs."
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_wallet_transactions(request):
    transactions = WalletTransaction.objects.filter(user=request.user).order_by('-created_at')
    serializer = WalletTransactionSerializer(transactions, many=True)
    return Response({
        'status': 'success',
        'message': 'Transactions retrieved successfully.',
        'data': {
            'transactions': serializer.data
        }
    }, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='post',
    request_body=WalletDepositRequestSerializer,
    responses={
        200: openapi.Response(
            description="Deposit initialized successfully",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'status': openapi.Schema(type=openapi.TYPE_STRING, example="success"),
                    'message': openapi.Schema(type=openapi.TYPE_STRING, example="Deposit transaction initiated."),
                    'data': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'checkout_url': openapi.Schema(type=openapi.TYPE_STRING, description="Monnify checkout page URL"),
                            'payment_reference': openapi.Schema(type=openapi.TYPE_STRING, description="Unique transaction reference")
                        }
                    )
                }
            )
        ),
        400: 'Bad Request - Validation error',
        401: 'Unauthorized'
    },
    operation_description="Initialize a wallet deposit transaction. Returns Monnify checkout URL."
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def init_wallet_deposit(request):
    """
    Initialize a wallet deposit.
    """
    serializer = WalletDepositRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'status': 'error',
            'message': 'Validation failed.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
    amount = serializer.validated_data['amount']
    if amount <= 0:
        return Response({
            'status': 'error',
            'message': 'Deposit amount must be greater than zero.'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    # Create WalletTransaction
    wallet_tx = WalletTransaction.objects.create(
        user=request.user,
        amount=amount,
        transaction_type='deposit',
        payment_method='monnify',
        payment_status='pending'
    )
    
    try:
        # Initialize Payment via Monnify
        payment_details = initialize_monnify_payment(
            amount=amount,
            reference=wallet_tx.payment_reference,
            email=request.user.email,
            name=request.user.full_name,
            description=f"Wallet Funding of ₦{amount:,.2f} for user: {request.user.email}",
            redirect_url=f"{settings.FRONTEND_URL}/wallet"
        )
        
        return Response({
            'status': 'success',
            'message': 'Wallet funding transaction initiated. Use checkout URL to complete payment.',
            'data': {
                'checkout_url': payment_details.get("checkoutUrl"),
                'payment_reference': wallet_tx.payment_reference
            }
        }, status=status.HTTP_200_OK)
    except Exception as e:
        wallet_tx.delete()
        return Response({
            'status': 'error',
            'message': f"Failed to initialize Monnify deposit: {str(e)}"
        }, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    responses={
        200: 'Webhook received and processed',
        400: 'Bad Request - Signature verification failure or bad data'
    },
    operation_description="Webhook endpoint for Monnify transaction completions. Handles booking payment and wallet deposits."
)
@api_view(['POST'])
@permission_classes([AllowAny])
def monnify_webhook(request):
    """
    Monnify Webhook callback for transaction verification.
    """
    # 1. Extract signature and raw body
    signature = request.headers.get('monnify-signature')
    raw_body = request.body
    
    # 2. Verify signature
    if not verify_monnify_webhook_signature(raw_body, signature):
        logger.error("Invalid Monnify signature received on Webhook")
        return Response({
            'status': 'error',
            'message': 'Unauthorized signature verification failed.'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    # 3. Parse data
    try:
        data = json.loads(raw_body)
    except Exception as e:
        return Response({
            'status': 'error',
            'message': 'Invalid JSON body.'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    event_data = data.get('eventData', {})
    payment_ref = event_data.get('paymentReference')
    payment_status = event_data.get('paymentStatus')
    transaction_ref = event_data.get('transactionReference')
    
    if not payment_ref:
        return Response({'status': 'success', 'message': 'Ignored empty reference'}, status=status.HTTP_200_OK)
        
    # Check if payment was successful
    # Monnify webhook status is usually 'PAID' or 'SUCCESS'
    is_success = payment_status in ['PAID', 'SUCCESS', 'SUCCESSFUL']
    
    # 4. Check if it matches a Booking
    try:
        booking = Booking.objects.get(payment_reference=payment_ref)
        if is_success:
            booking.payment_status = 'paid'
            booking.monnify_transaction_reference = transaction_ref
            booking.save()
            
            # Auto-assign worker
            auto_assign_worker_for_booking(booking)
            logger.info(f"Booking {booking.ticket_id} confirmed paid via Monnify webhook.")
        else:
            logger.info(f"Booking {booking.ticket_id} payment reported failed on Monnify.")
            
        return Response({'status': 'success', 'message': 'Booking updated successfully'}, status=status.HTTP_200_OK)
    except Booking.DoesNotExist:
        pass
        
    # 5. Check if it matches a WalletTransaction
    try:
        wallet_tx = WalletTransaction.objects.get(payment_reference=payment_ref)
        if is_success:
            if wallet_tx.payment_status != 'success':
                wallet_tx.payment_status = 'success'
                wallet_tx.save()
                
                # Update user wallet balance & deposits
                user = wallet_tx.user
                user.wallet_balance += wallet_tx.amount
                user.total_deposited += wallet_tx.amount
                user.save()
                
                logger.info(f"Wallet transaction of ₦{wallet_tx.amount} successful for user {user.email}.")
        else:
            wallet_tx.payment_status = 'failed'
            wallet_tx.save()
            logger.info(f"Wallet transaction for user {wallet_tx.user.email} failed on Monnify.")
            
        return Response({'status': 'success', 'message': 'Wallet transaction updated successfully'}, status=status.HTTP_200_OK)
    except WalletTransaction.DoesNotExist:
        pass
        
    return Response({'status': 'success', 'message': 'No matching transaction reference found'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def mock_payment_success(request):
    """
    Direct endpoint to simulate a successful Monnify payment callback locally.
    Accepts transaction reference (payment_reference) and marks it as paid.
    """
    payment_ref = request.data.get('payment_reference')
    if not payment_ref:
        return Response({
            'status': 'error',
            'message': 'payment_reference is required.'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    transaction_ref = f"MOCK-TX-{payment_ref}"
    
    # 1. Try Booking
    try:
        booking = Booking.objects.get(payment_reference=payment_ref)
        booking.payment_status = 'paid'
        booking.monnify_transaction_reference = transaction_ref
        booking.save()
        auto_assign_worker_for_booking(booking)
        return Response({
            'status': 'success',
            'message': f'Mock payment succeeded. Booking {booking.ticket_id} confirmed paid.'
        }, status=status.HTTP_200_OK)
    except Booking.DoesNotExist:
        pass
        
    # 2. Try WalletTransaction
    try:
        wallet_tx = WalletTransaction.objects.get(payment_reference=payment_ref)
        if wallet_tx.payment_status != 'success':
            wallet_tx.payment_status = 'success'
            wallet_tx.save()
            
            user = wallet_tx.user
            user.wallet_balance += wallet_tx.amount
            user.total_deposited += wallet_tx.amount
            user.save()
            
        return Response({
            'status': 'success',
            'message': f'Mock payment succeeded. Wallet transaction successful for user {wallet_tx.user.email}.'
        }, status=status.HTTP_200_OK)
    except WalletTransaction.DoesNotExist:
        pass
        
    return Response({
        'status': 'error',
        'message': f'Transaction with reference {payment_ref} not found.'
    }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([AllowAny])
def verify_payment(request):
    """
    Explicitly query Monnify API to check status of a transaction reference,
    and update database accordingly (marks as paid/success, credits wallet).
    """
    payment_ref = request.query_params.get('payment_reference')
    if not payment_ref:
        return Response({
            'status': 'error',
            'message': 'payment_reference query parameter is required.'
        }, status=status.HTTP_400_BAD_REQUEST)

    # 1. Query Monnify API
    monnify_data = verify_monnify_payment(payment_ref)
    if not monnify_data:
        return Response({
            'status': 'error',
            'message': 'Could not query transaction status on Monnify.'
        }, status=status.HTTP_400_BAD_REQUEST)

    payment_status = monnify_data.get('paymentStatus')
    transaction_ref = monnify_data.get('transactionReference')

    # 2. Check and update database if PAID or SUCCESSFUL
    if payment_status in ['PAID', 'SUCCESS']:
        # Case A: Booking
        try:
            booking = Booking.objects.get(payment_reference=payment_ref)
            if booking.payment_status != 'paid':
                booking.payment_status = 'paid'
                booking.monnify_transaction_reference = transaction_ref
                booking.save()
                auto_assign_worker_for_booking(booking)
            return Response({
                'status': 'success',
                'message': f'Payment verified successfully. Booking {booking.ticket_id} confirmed paid.',
                'data': {
                    'payment_status': 'paid',
                    'type': 'booking'
                }
            }, status=status.HTTP_200_OK)
        except Booking.DoesNotExist:
            pass

        # Case B: WalletTransaction
        try:
            wallet_tx = WalletTransaction.objects.get(payment_reference=payment_ref)
            if wallet_tx.payment_status != 'success':
                wallet_tx.payment_status = 'success'
                wallet_tx.save()
                
                user = wallet_tx.user
                user.wallet_balance += wallet_tx.amount
                user.total_deposited += wallet_tx.amount
                user.save()
                
            return Response({
                'status': 'success',
                'message': f'Payment verified successfully. Wallet funded for {wallet_tx.user.email}.',
                'data': {
                    'payment_status': 'success',
                    'type': 'wallet'
                }
            }, status=status.HTTP_200_OK)
        except WalletTransaction.DoesNotExist:
            pass

        return Response({
            'status': 'error',
            'message': 'Transaction reference paid on Monnify but not found in our system.'
        }, status=status.HTTP_404_NOT_FOUND)

    return Response({
        'status': 'pending',
        'message': f'Payment status on Monnify is {payment_status}.',
        'data': {
            'payment_status': payment_status
        }
    }, status=status.HTTP_200_OK)


# --- WORKER API VIEWS ---

class WorkerTicketActionRequestSerializer(serializers.Serializer):
    ticket_id = serializers.CharField(help_text="The Ticket ID of the booking (e.g. T-20260603-A7B8)")


@swagger_auto_schema(
    method='post',
    request_body=WorkerTicketActionRequestSerializer,
    responses={
        200: openapi.Response(
            description="Ticket verified successfully",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'status': openapi.Schema(type=openapi.TYPE_STRING, example="success"),
                    'message': openapi.Schema(type=openapi.TYPE_STRING, example="Ticket details retrieved."),
                    'data': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'customer_name': openapi.Schema(type=openapi.TYPE_STRING),
                            'service_name': openapi.Schema(type=openapi.TYPE_STRING),
                            'price': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'payment_status': openapi.Schema(type=openapi.TYPE_STRING),
                            'booking': openapi.Schema(type=openapi.TYPE_OBJECT, description="Full booking details")
                        }
                    )
                }
            )
        ),
        400: 'Bad Request - Validation error',
        404: 'Not Found - Ticket not found'
    },
    operation_description="Allows a worker/admin to input a Ticket ID and verify the customer details, service requested, and payment status."
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def worker_verify_ticket(request):
    """
    Worker ticket verification view.
    """
    # Guard: Must be worker, front_desk or owner
    if request.user.role not in ['worker', 'front_desk', 'owner']:
        return Response({
            'status': 'error',
            'message': 'Access denied. Only workers, front desk attendants, or owner can verify tickets.'
        }, status=status.HTTP_403_FORBIDDEN)
        
    serializer = WorkerTicketActionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'status': 'error',
            'message': 'Validation failed.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
    ticket_id = serializer.validated_data['ticket_id']
    try:
        booking = Booking.objects.get(ticket_id=ticket_id)
        if booking.payment_status != 'paid':
            return Response({
                'status': 'error',
                'message': f'Ticket code {ticket_id} cannot be verified because payment status is pending. Please complete payment first.'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        cust_name = booking.user.full_name if booking.user else booking.guest_name
        all_service_names = [booking.service.name] + [s.name for s in booking.additional_services.all()]
        return Response({
            'status': 'success',
            'message': 'Ticket verified successfully.',
            'data': {
                'customer_name': cust_name,
                'service_name': ", ".join(all_service_names),
                'service_count': len(all_service_names),
                'price': float(booking.total_price),
                'payment_status': booking.payment_status,
                'booking': BookingSerializer(booking).data
            }
        }, status=status.HTTP_200_OK)
    except Booking.DoesNotExist:
        return Response({
            'status': 'error',
            'message': f'Ticket code {ticket_id} is invalid or does not exist.'
        }, status=status.HTTP_404_NOT_FOUND)


@swagger_auto_schema(
    method='post',
    request_body=WorkerTicketActionRequestSerializer,
    responses={
        200: 'Success - Service started',
        400: 'Bad Request - Service cannot be started',
        403: 'Forbidden - User role is not worker'
    },
    operation_description="Allows assigned worker to start a service. Sets service status to in_progress and worker status to busy."
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def worker_start_service(request):
    """
    Worker starts performing the service.
    """
    if request.user.role != 'worker':
        return Response({
            'status': 'error',
            'message': 'Access denied. Only workers can perform services.'
        }, status=status.HTTP_403_FORBIDDEN)
        
    serializer = WorkerTicketActionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'status': 'error',
            'message': 'Validation failed.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
    ticket_id = serializer.validated_data['ticket_id']
    try:
        booking = Booking.objects.get(ticket_id=ticket_id)
        
        # Verify booking is paid
        if booking.payment_status != 'paid':
            return Response({
                'status': 'error',
                'message': 'Cannot start service for an unpaid ticket.'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Verify booking status is waiting/assigned
        if booking.service_status not in ['waiting', 'assigned']:
            return Response({
                'status': 'error',
                'message': f'Cannot start service. Booking is in {booking.service_status} state.'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Assign worker to booking if not already assigned
        if not booking.worker and not booking.workers.exists():
            booking.worker = request.user
            booking.workers.add(request.user)
            booking.save()
        elif booking.worker != request.user and request.user not in booking.workers.all():
            return Response({
                'status': 'error',
                'message': 'This service is assigned to other workers.'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        booking.service_status = 'in_progress'
        booking.save()
        
        # Update worker status to busy
        worker = request.user
        worker.worker_status = 'busy'
        worker.save()
        
        return Response({
            'status': 'success',
            'message': f'Service started for ticket {ticket_id}. Your status is now BUSY.',
            'data': BookingSerializer(booking).data
        }, status=status.HTTP_200_OK)
    except Booking.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Ticket does not exist.'
        }, status=status.HTTP_404_NOT_FOUND)


@swagger_auto_schema(
    method='post',
    request_body=WorkerTicketActionRequestSerializer,
    responses={
        200: 'Success - Service completed and next ticket assigned (if any)',
        400: 'Bad Request - Service cannot be completed',
        403: 'Forbidden - User role is not worker'
    },
    operation_description="Allows assigned worker to complete a service. Sets service status to completed, worker status to available, and auto-assigns next waiting walk-in."
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def worker_complete_service(request):
    """
    Worker completes the service. Sets status back to available,
    and tries to assign the next waiting booking to this worker.
    """
    if request.user.role != 'worker':
        return Response({
            'status': 'error',
            'message': 'Access denied. Only workers can complete services.'
        }, status=status.HTTP_403_FORBIDDEN)
        
    serializer = WorkerTicketActionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'status': 'error',
            'message': 'Validation failed.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
    ticket_id = serializer.validated_data['ticket_id']
    try:
        booking = Booking.objects.get(ticket_id=ticket_id)
        
        # Check ownership and state
        if booking.worker != request.user and request.user not in booking.workers.all():
            return Response({
                'status': 'error',
                'message': 'This service is not assigned to you.'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        if booking.service_status != 'in_progress':
            return Response({
                'status': 'error',
                'message': f'Cannot complete service. Service is in {booking.service_status} state.'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        booking.service_status = 'completed'
        booking.save()
        
        # Free up all workers assigned to this booking
        all_assigned_workers = list(booking.workers.all())
        if booking.worker and booking.worker not in all_assigned_workers:
            all_assigned_workers.append(booking.worker)
            
        for w in all_assigned_workers:
            # Check if this worker is busy on any other active bookings
            is_still_busy = Booking.objects.filter(
                Q(worker=w) | Q(workers=w),
                service_status__in=['assigned', 'in_progress']
            ).exclude(id=booking.id).exists()
            
            if not is_still_busy:
                w.worker_status = 'available'
                w.save()
                
                # Queue System: Check and auto-assign next waiting booking
                assign_next_waiting_booking(w)
                
        msg = f"Service completed for ticket {ticket_id}. You are now AVAILABLE."
        # If the current worker got auto-assigned a new booking, they are busy again.
        # Let's check their latest status to see if it's busy.
        worker_after = CustomUser.objects.get(id=request.user.id)
        if worker_after.worker_status == 'busy':
            # Find the new booking assigned to this worker
            next_booking = Booking.objects.filter(
                worker=request.user,
                service_status='assigned'
            ).order_by('-created_at').first()
            if next_booking:
                msg += f" You have been auto-assigned a new walk-in booking (Ticket: {next_booking.ticket_id})! Your status is BUSY."
            else:
                next_booking = None
        else:
            next_booking = None
            
        return Response({
            'status': 'success',
            'message': msg,
            'data': {
                'completed_booking': BookingSerializer(booking).data,
                'next_booking': BookingSerializer(next_booking).data if next_booking else None
            }
        }, status=status.HTTP_200_OK)
    except Booking.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Ticket does not exist.'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([AllowAny])
def list_membership_levels(request):
    """
    List all active membership levels for customers.
    """
    from accounts.models import MembershipLevel
    levels = MembershipLevel.objects.all().order_by('min_deposit_amount')
    data = []
    for level in levels:
        data.append({
            'id': level.id,
            'name': level.name,
            'min_deposit_amount': float(level.min_deposit_amount),
            'discount_percentage': float(level.discount_percentage),
            'description': level.description
        })
    return Response({
        'status': 'success',
        'message': 'Membership levels retrieved successfully.',
        'data': data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def list_public_workers(request):
    """
    List all active worker accounts for booking flow assignment.
    """
    workers = CustomUser.objects.filter(role='worker', is_active=True).order_by('full_name')
    data = []
    for w in workers:
        data.append({
            'id': w.id,
            'name': w.full_name,
            'phone_number': w.phone_number,
            'worker_status': w.worker_status,
            'initials': "".join([n[0] for n in w.full_name.split() if n]).upper() if w.full_name else "W",
            'rating': 4.8,
            'avatar': "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=150" if w.id % 2 == 0 else "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150",
            'specialties': ["Hair Styling", "Nail Art"] if w.id % 2 == 0 else ["Facials", "Massage Therapy"],
            'worker_role': w.worker_role
        })
    return Response({
        'status': 'success',
        'message': 'Workers retrieved successfully.',
        'data': data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def worker_list_jobs(request):
    """
    List bookings assigned to or completed by the logged-in worker.
    """
    if request.user.role != 'worker':
        return Response({
            'status': 'error',
            'message': 'Access denied. Only workers can view their jobs.'
        }, status=status.HTTP_403_FORBIDDEN)
        
    bookings = Booking.objects.filter(
        Q(worker=request.user) | Q(workers=request.user),
        payment_status='paid'
    ).distinct().order_by('-created_at')
    serializer = BookingSerializer(bookings, many=True)
    return Response({
        'status': 'success',
        'message': 'Jobs retrieved successfully.',
        'data': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def guest_booking_confirmation(request):
    """
    Public endpoint for guest users to retrieve their booking confirmation
    by payment_reference after a successful Monnify redirect.
    Verifies payment status with Monnify on every call so the guest sees
    the correct status even when the webhook hasn't fired (e.g. local dev).
    """
    reference = request.query_params.get('reference')
    if not reference:
        return Response({
            'status': 'error',
            'message': 'reference query parameter is required.'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        booking = Booking.objects.get(payment_reference=reference)
    except Booking.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Booking not found.'
        }, status=status.HTTP_404_NOT_FOUND)

    # If still pending, ask Monnify for the latest status and sync it.
    if booking.payment_status != 'paid':
        try:
            monnify_data = verify_monnify_payment(reference)
            if monnify_data and monnify_data.get('paymentStatus') in ('PAID', 'SUCCESS', 'SUCCESSFUL'):
                booking.payment_status = 'paid'
                if monnify_data.get('transactionReference'):
                    booking.monnify_transaction_reference = monnify_data['transactionReference']
                booking.save()
                auto_assign_worker_for_booking(booking)
        except Exception:
            pass  # If verification fails, return whatever status we have

    all_services = [booking.service.name] + [s.name for s in booking.additional_services.all()]

    return Response({
        'status': 'success',
        'message': 'Booking confirmation retrieved successfully.',
        'data': {
            'ticket_id': booking.ticket_id,
            'services': all_services,
            'total_price': float(booking.total_price),
            'payment_status': booking.payment_status,
            'service_status': booking.service_status,
            'booking_type': booking.booking_type,
            'scheduled_date': str(booking.scheduled_date) if booking.scheduled_date else None,
            'scheduled_time': str(booking.scheduled_time) if booking.scheduled_time else None,
            'guest_name': booking.guest_name,
            'payment_reference': booking.payment_reference,
        }
    }, status=status.HTTP_200_OK)

