from django.shortcuts import render
from django.utils import timezone
from django.db.models import Sum, Count, Q
from rest_framework import status, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from decimal import Decimal

from accounts.models import CustomUser, MembershipLevel
from accounts.serializers import UserSerializer
from bookings.models import ServiceCategory, Service, Booking, WalletTransaction
from bookings.serializers import (
    ServiceCategorySerializer,
    ServiceSerializer,
    BookingSerializer,
    WalletTransactionSerializer
)
from .permissions import IsOwner
from .serializers import MembershipLevelSerializer, RescheduleBookingRequestSerializer


# --- Category CRUD Endpoints ---

@swagger_auto_schema(
    method='get',
    responses={200: ServiceCategorySerializer(many=True)},
    operation_description="List all service categories (Owner only)."
)
@swagger_auto_schema(
    method='post',
    request_body=ServiceCategorySerializer,
    responses={
        201: ServiceCategorySerializer(),
        400: "Validation Error"
    },
    operation_description="Create a new service category (Owner only)."
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsOwner])
def admin_category_list_create(request):
    """
    List and create service categories.
    """
    if request.method == 'GET':
        categories = ServiceCategory.objects.all().prefetch_related('services')
        serializer = ServiceCategorySerializer(categories, many=True)
        return Response({
            'status': 'success',
            'message': 'Service categories retrieved successfully.',
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    elif request.method == 'POST':
        serializer = ServiceCategorySerializer(data=request.data)
        if serializer.is_valid():
            category = serializer.save()
            return Response({
                'status': 'success',
                'message': f"Category '{category.name}' created successfully.",
                'data': ServiceCategorySerializer(category).data
            }, status=status.HTTP_201_CREATED)
        return Response({
            'status': 'error',
            'message': 'Failed to create category.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    responses={200: ServiceCategorySerializer(), 404: "Category not found"},
    operation_description="Retrieve a service category detail (Owner only)."
)
@swagger_auto_schema(
    method='put',
    request_body=ServiceCategorySerializer,
    responses={200: ServiceCategorySerializer(), 400: "Validation error", 404: "Category not found"},
    operation_description="Update a service category (Owner only)."
)
@swagger_auto_schema(
    method='delete',
    responses={200: "Deleted successfully", 404: "Category not found"},
    operation_description="Delete a service category (Owner only)."
)
@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated, IsOwner])
def admin_category_detail(request, pk):
    """
    Retrieve, update or delete a service category.
    """
    try:
        category = ServiceCategory.objects.get(pk=pk)
    except ServiceCategory.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Category not found.'
        }, status=status.HTTP_404_NOT_FOUND)
        
    if request.method == 'GET':
        serializer = ServiceCategorySerializer(category)
        return Response({
            'status': 'success',
            'message': 'Category retrieved successfully.',
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    elif request.method == 'PUT':
        serializer = ServiceCategorySerializer(category, data=request.data, partial=True)
        if serializer.is_valid():
            category = serializer.save()
            return Response({
                'status': 'success',
                'message': 'Category updated successfully.',
                'data': ServiceCategorySerializer(category).data
            }, status=status.HTTP_200_OK)
        return Response({
            'status': 'error',
            'message': 'Failed to update category.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
    elif request.method == 'DELETE':
        name = category.name
        category.delete()
        return Response({
            'status': 'success',
            'message': f"Category '{name}' deleted successfully."
        }, status=status.HTTP_200_OK)


# --- Service CRUD Endpoints ---

@swagger_auto_schema(
    method='get',
    responses={200: ServiceSerializer(many=True)},
    operation_description="List all services with pricing and details (Owner only)."
)
@swagger_auto_schema(
    method='post',
    request_body=ServiceSerializer,
    responses={
        201: ServiceSerializer(),
        400: "Validation Error"
    },
    operation_description="Create a new service (Owner only)."
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsOwner])
def admin_service_list_create(request):
    """
    List and create services.
    """
    if request.method == 'GET':
        services = Service.objects.all().order_by('category__name', 'name')
        serializer = ServiceSerializer(services, many=True)
        return Response({
            'status': 'success',
            'message': 'Services retrieved successfully.',
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    elif request.method == 'POST':
        serializer = ServiceSerializer(data=request.data)
        if serializer.is_valid():
            service = serializer.save()
            return Response({
                'status': 'success',
                'message': f"Service '{service.name}' created successfully.",
                'data': ServiceSerializer(service).data
            }, status=status.HTTP_201_CREATED)
        return Response({
            'status': 'error',
            'message': 'Failed to create service.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    responses={200: ServiceSerializer(), 404: "Service not found"},
    operation_description="Retrieve a service detail (Owner only)."
)
@swagger_auto_schema(
    method='put',
    request_body=ServiceSerializer,
    responses={200: ServiceSerializer(), 400: "Validation error", 404: "Service not found"},
    operation_description="Update a service (Owner only)."
)
@swagger_auto_schema(
    method='delete',
    responses={200: "Deleted successfully", 404: "Service not found"},
    operation_description="Delete a service (Owner only)."
)
@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated, IsOwner])
def admin_service_detail(request, pk):
    """
    Retrieve, update or delete a service.
    """
    try:
        service = Service.objects.get(pk=pk)
    except Service.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Service not found.'
        }, status=status.HTTP_404_NOT_FOUND)
        
    if request.method == 'GET':
        serializer = ServiceSerializer(service)
        return Response({
            'status': 'success',
            'message': 'Service retrieved successfully.',
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    elif request.method == 'PUT':
        serializer = ServiceSerializer(service, data=request.data, partial=True)
        if serializer.is_valid():
            service = serializer.save()
            return Response({
                'status': 'success',
                'message': 'Service updated successfully.',
                'data': ServiceSerializer(service).data
            }, status=status.HTTP_200_OK)
        return Response({
            'status': 'error',
            'message': 'Failed to update service.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
    elif request.method == 'DELETE':
        name = service.name
        service.delete()
        return Response({
            'status': 'success',
            'message': f"Service '{name}' deleted successfully."
        }, status=status.HTTP_200_OK)


# --- Membership Level CRUD Endpoints ---

@swagger_auto_schema(
    method='get',
    responses={200: MembershipLevelSerializer(many=True)},
    operation_description="List all membership levels (Owner only)."
)
@swagger_auto_schema(
    method='post',
    request_body=MembershipLevelSerializer,
    responses={
        201: MembershipLevelSerializer(),
        400: "Validation Error"
    },
    operation_description="Create a new membership level (Owner only)."
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsOwner])
def admin_membership_list_create(request):
    """
    List and create membership levels.
    """
    if request.method == 'GET':
        levels = MembershipLevel.objects.all().order_by('min_deposit_amount')
        serializer = MembershipLevelSerializer(levels, many=True)
        return Response({
            'status': 'success',
            'message': 'Membership levels retrieved successfully.',
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    elif request.method == 'POST':
        serializer = MembershipLevelSerializer(data=request.data)
        if serializer.is_valid():
            level = serializer.save()
            return Response({
                'status': 'success',
                'message': f"Membership level '{level.name}' created successfully.",
                'data': MembershipLevelSerializer(level).data
            }, status=status.HTTP_201_CREATED)
        return Response({
            'status': 'error',
            'message': 'Failed to create membership level.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    responses={200: MembershipLevelSerializer(), 404: "Membership level not found"},
    operation_description="Retrieve a membership level detail (Owner only)."
)
@swagger_auto_schema(
    method='put',
    request_body=MembershipLevelSerializer,
    responses={200: MembershipLevelSerializer(), 400: "Validation error", 404: "Membership level not found"},
    operation_description="Update a membership level (Owner only)."
)
@swagger_auto_schema(
    method='delete',
    responses={200: "Deleted successfully", 404: "Membership level not found"},
    operation_description="Delete a membership level (Owner only)."
)
@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated, IsOwner])
def admin_membership_detail(request, pk):
    """
    Retrieve, update or delete a membership level.
    """
    try:
        level = MembershipLevel.objects.get(pk=pk)
    except MembershipLevel.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Membership level not found.'
        }, status=status.HTTP_404_NOT_FOUND)
        
    if request.method == 'GET':
        serializer = MembershipLevelSerializer(level)
        return Response({
            'status': 'success',
            'message': 'Membership level retrieved successfully.',
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    elif request.method == 'PUT':
        serializer = MembershipLevelSerializer(level, data=request.data, partial=True)
        if serializer.is_valid():
            level = serializer.save()
            return Response({
                'status': 'success',
                'message': 'Membership level updated successfully.',
                'data': MembershipLevelSerializer(level).data
            }, status=status.HTTP_200_OK)
        return Response({
            'status': 'error',
            'message': 'Failed to update membership level.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
    elif request.method == 'DELETE':
        name = level.name
        level.delete()
        return Response({
            'status': 'success',
            'message': f"Membership level '{name}' deleted successfully."
        }, status=status.HTTP_200_OK)


# --- Queue & Bookings Management Endpoints ---

@swagger_auto_schema(
    method='get',
    manual_parameters=[
        openapi.Parameter('service_status', openapi.IN_QUERY, description="Filter by service status (e.g. waiting, assigned, in_progress, completed, cancelled)", type=openapi.TYPE_STRING),
        openapi.Parameter('payment_status', openapi.IN_QUERY, description="Filter by payment status (e.g. pending, paid)", type=openapi.TYPE_STRING),
        openapi.Parameter('booking_type', openapi.IN_QUERY, description="Filter by booking type (e.g. walk_in, scheduled)", type=openapi.TYPE_STRING),
    ],
    responses={200: BookingSerializer(many=True)},
    operation_description="List all salon bookings and queue states with optional filtering (Owner only)."
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOwner])
def admin_list_bookings(request):
    """
    List all bookings/tickets in the system.
    """
    bookings = Booking.objects.filter(payment_status='paid').order_by('-created_at')
    
    # Apply filters
    service_status_filter = request.query_params.get('service_status')
    payment_status_filter = request.query_params.get('payment_status')
    booking_type_filter = request.query_params.get('booking_type')
    
    if service_status_filter:
        bookings = bookings.filter(service_status=service_status_filter)
    if payment_status_filter:
        bookings = bookings.filter(payment_status=payment_status_filter)
    if booking_type_filter:
        bookings = bookings.filter(booking_type=booking_type_filter)
        
    serializer = BookingSerializer(bookings, many=True)
    return Response({
        'status': 'success',
        'message': 'Bookings retrieved successfully.',
        'data': serializer.data
    }, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='post',
    request_body=RescheduleBookingRequestSerializer,
    responses={200: BookingSerializer(), 400: "Validation/Status Error", 404: "Booking not found"},
    operation_description="Reschedule a booking to a new date and time (Owner only)."
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOwner])
def admin_reschedule_booking(request, ticket_id):
    """
    Reschedule an appointment.
    """
    try:
        booking = Booking.objects.get(ticket_id=ticket_id)
    except Booking.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Booking not found.'
        }, status=status.HTTP_404_NOT_FOUND)
        
    if booking.service_status in ['completed', 'cancelled']:
        return Response({
            'status': 'error',
            'message': f'Cannot reschedule a booking that is already {booking.service_status}.'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    serializer = RescheduleBookingRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'status': 'error',
            'message': 'Validation failed.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
    booking.scheduled_date = serializer.validated_data['scheduled_date']
    booking.scheduled_time = serializer.validated_data['scheduled_time']
    booking.booking_type = 'scheduled'  # Force type to scheduled
    booking.save()
    
    return Response({
        'status': 'success',
        'message': f"Booking '{ticket_id}' successfully rescheduled to {booking.scheduled_date} at {booking.scheduled_time}.",
        'data': BookingSerializer(booking).data
    }, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='post',
    responses={200: BookingSerializer(), 400: "Status Error", 404: "Booking not found"},
    operation_description="Cancel a booking. Reassings newly available workers if needed (Owner only)."
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOwner])
def admin_cancel_booking(request, ticket_id):
    """
    Cancel a booking. If a worker was actively busy on this service,
    re-enable them to 'available' and try to assign the next waiting walk-in ticket.
    """
    try:
        booking = Booking.objects.get(ticket_id=ticket_id)
    except Booking.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Booking not found.'
        }, status=status.HTTP_404_NOT_FOUND)
        
    if booking.service_status in ['completed', 'cancelled']:
        return Response({
            'status': 'error',
            'message': f'Booking is already {booking.service_status}.'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    # Free up all assigned workers
    all_assigned_workers = list(booking.workers.all())
    if booking.worker and booking.worker not in all_assigned_workers:
        all_assigned_workers.append(booking.worker)

    booking.service_status = 'cancelled'
    booking.save()

    for w in all_assigned_workers:
        if w.worker_status == 'busy':
            active_bookings = Booking.objects.filter(
                Q(worker=w) | Q(workers=w),
                service_status__in=['assigned', 'in_progress']
            ).exclude(id=booking.id).exists()
            
            if not active_bookings:
                w.worker_status = 'available'
                w.save()
                
                # Try to auto-assign next waiting walk-in
                from bookings.views import assign_next_waiting_booking
                assign_next_waiting_booking(w)
            
    return Response({
        'status': 'success',
        'message': f"Booking '{ticket_id}' successfully cancelled.",
        'data': BookingSerializer(booking).data
    }, status=status.HTTP_200_OK)


# --- Analytics & Metrics Endpoints ---

@swagger_auto_schema(
    method='get',
    responses={
        200: openapi.Response(
            description="Success - Returns revenue aggregates",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'status': openapi.Schema(type=openapi.TYPE_STRING, example="success"),
                    'message': openapi.Schema(type=openapi.TYPE_STRING),
                    'data': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'daily_revenue': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'weekly_revenue': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'monthly_revenue': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'overall_revenue': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'wallet_payments': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'monnify_payments': openapi.Schema(type=openapi.TYPE_NUMBER),
                        }
                    )
                }
            )
        )
    },
    operation_description="Get daily, weekly, monthly, overall revenues, and payment type breakdown (Owner only)."
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOwner])
def admin_revenue_metrics(request):
    """
    Retrieve revenue analytical reports.
    """
    now = timezone.now()
    today = now.date()
    start_of_week = now - timezone.timedelta(days=7)
    start_of_month = now - timezone.timedelta(days=30)
    
    # Calculate revenues of confirmed bookings
    paid_bookings = Booking.objects.filter(payment_status='paid')
    
    daily_rev = paid_bookings.filter(created_at__date=today).aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
    weekly_rev = paid_bookings.filter(created_at__gte=start_of_week).aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
    monthly_rev = paid_bookings.filter(created_at__gte=start_of_month).aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
    overall_rev = paid_bookings.aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
    
    # Breakdown
    wallet_pay = paid_bookings.filter(payment_method='wallet').aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
    monnify_pay = paid_bookings.filter(payment_method='monnify').aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
    
    # Calculate successful wallet deposits (credit transactions)
    monthly_wallet_deps = WalletTransaction.objects.filter(
        transaction_type='deposit',
        payment_status='success',
        created_at__gte=start_of_month
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    return Response({
        'status': 'success',
        'message': 'Revenue analytics calculated successfully.',
        'data': {
            'daily_revenue': float(daily_rev),
            'weekly_revenue': float(weekly_rev),
            'monthly_revenue': float(monthly_rev),
            'overall_revenue': float(overall_rev),
            'wallet_payments': float(wallet_pay),
            'monnify_payments': float(monnify_pay),
            'monthly_wallet_deposits': float(monthly_wallet_deps)
        }
    }, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='get',
    responses={
        200: openapi.Response(
            description="Success - Returns customer profile list with stats",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'status': openapi.Schema(type=openapi.TYPE_STRING, example="success"),
                    'message': openapi.Schema(type=openapi.TYPE_STRING),
                    'data': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'user': openapi.Schema(type=openapi.TYPE_OBJECT),
                                'total_bookings': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'total_spent': openapi.Schema(type=openapi.TYPE_NUMBER)
                            }
                        )
                    )
                }
            )
        )
    },
    operation_description="Retrieve all registered customer spending history, booking counts, and current wallet details (Owner only)."
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOwner])
def admin_customer_metrics(request):
    """
    Retrieve registered customers and their spending metrics.
    """
    customers = CustomUser.objects.filter(role='customer').order_by('-date_joined')
    customer_list = []
    
    for customer in customers:
        # Aggregate stats
        cust_bookings = Booking.objects.filter(user=customer)
        total_bookings = cust_bookings.count()
        total_spent = cust_bookings.filter(payment_status='paid').aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
        
        customer_list.append({
            'user': UserSerializer(customer).data,
            'total_bookings': total_bookings,
            'total_spent': float(total_spent)
        })
        
    return Response({
        'status': 'success',
        'message': 'Customer metrics retrieved successfully.',
        'data': customer_list
    }, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='get',
    responses={
        200: openapi.Response(
            description="Success - Returns worker details with completed job stats",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'status': openapi.Schema(type=openapi.TYPE_STRING, example="success"),
                    'message': openapi.Schema(type=openapi.TYPE_STRING),
                    'data': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'worker': openapi.Schema(type=openapi.TYPE_OBJECT),
                                'completed_jobs': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'revenue_generated': openapi.Schema(type=openapi.TYPE_NUMBER)
                            }
                        )
                    )
                }
            )
        )
    },
    operation_description="Retrieve details of all workers, their availability status, completed job counts, and revenue generated (Owner only)."
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOwner])
def admin_worker_metrics(request):
    """
    Retrieve worker performance metrics.
    """
    workers = CustomUser.objects.filter(role='worker').order_by('full_name')
    worker_list = []
    
    for worker in workers:
        completed_bookings = Booking.objects.filter(worker=worker, service_status='completed')
        completed_jobs = completed_bookings.count() + worker.jobs_completed_override
        rev_gen = (completed_bookings.aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')) + worker.revenue_generated_override
        
        worker_list.append({
            'worker': UserSerializer(worker).data,
            'completed_jobs': completed_jobs,
            'revenue_generated': float(rev_gen)
        })
        
    return Response({
        'status': 'success',
        'message': 'Worker metrics retrieved successfully.',
        'data': worker_list
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOwner])
def admin_create_worker(request):
    """
    Create a new worker user (Owner only).
    """
    email = request.data.get('email')
    full_name = request.data.get('full_name')
    phone_number = request.data.get('phone_number', '')
    password = request.data.get('password')
    worker_status = request.data.get('worker_status', 'available')
    worker_role = request.data.get('worker_role', '')
    jobs_completed_override = request.data.get('jobs_completed_override', 0)
    revenue_generated_override = request.data.get('revenue_generated_override', 0.00)

    if not email or not full_name or not password:
         return Response({
            'status': 'error',
            'message': 'Email, full name, and password are required.'
        }, status=status.HTTP_400_BAD_REQUEST)

    if CustomUser.objects.filter(email=email).exists():
        return Response({
            'status': 'error',
            'message': 'A user with this email already exists.'
        }, status=status.HTTP_400_BAD_REQUEST)

    worker = CustomUser.objects.create_user(
        email=email,
        full_name=full_name,
        password=password,
        phone_number=phone_number,
        role='worker'
    )
    worker.is_verified = True
    worker.worker_status = worker_status
    worker.worker_role = worker_role
    worker.jobs_completed_override = int(jobs_completed_override)
    worker.revenue_generated_override = Decimal(str(revenue_generated_override))
    worker.save()

    return Response({
        'status': 'success',
        'message': f"Worker {full_name} successfully created.",
        'data': UserSerializer(worker).data
    }, status=status.HTTP_201_CREATED)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated, IsOwner])
def admin_edit_worker(request, pk):
    """
    Update worker user details (Owner only).
    """
    try:
        worker = CustomUser.objects.get(pk=pk, role='worker')
    except CustomUser.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Worker not found.'
        }, status=status.HTTP_404_NOT_FOUND)

    data = request.data
    if 'email' in data:
        email = data['email']
        if CustomUser.objects.filter(email=email).exclude(pk=pk).exists():
            return Response({
                'status': 'error',
                'message': 'A user with this email already exists.'
            }, status=status.HTTP_400_BAD_REQUEST)
        worker.email = email

    if 'full_name' in data:
        worker.full_name = data['full_name']
    if 'phone_number' in data:
        worker.phone_number = data['phone_number']
    if 'password' in data and data['password']:
        worker.set_password(data['password'])
    if 'worker_status' in data:
        worker.worker_status = data['worker_status']
    if 'worker_role' in data:
        worker.worker_role = data['worker_role']
    if 'jobs_completed_override' in data:
        worker.jobs_completed_override = int(data['jobs_completed_override'])
    if 'revenue_generated_override' in data:
        worker.revenue_generated_override = Decimal(str(data['revenue_generated_override']))

    worker.save()
    return Response({
        'status': 'success',
        'message': f"Worker {worker.full_name} successfully updated.",
        'data': UserSerializer(worker).data
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsOwner])
def admin_delete_worker(request, pk):
    """
    Delete a worker user (Owner only).
    """
    try:
        worker = CustomUser.objects.get(pk=pk, role='worker')
    except CustomUser.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Worker not found.'
        }, status=status.HTTP_404_NOT_FOUND)

    name = worker.full_name
    worker.delete()
    return Response({
        'status': 'success',
        'message': f"Worker {name} successfully deleted."
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOwner])
def admin_assign_worker(request, ticket_id):
    """
    Manually assign workers to a booking (Owner/Admin only).
    Accepts 'worker_ids' (list of IDs) or 'worker_id' (single ID).
    """
    try:
        booking = Booking.objects.get(ticket_id=ticket_id)
    except Booking.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Booking not found.'
        }, status=status.HTTP_404_NOT_FOUND)

    worker_ids = request.data.get('worker_ids')
    worker_id = request.data.get('worker_id')

    # Standardize input to list of worker IDs
    ids_list = []
    if isinstance(worker_ids, list):
        ids_list = worker_ids
    elif worker_id:
        ids_list = [worker_id]
        
    if not ids_list:
        return Response({
            'status': 'error',
            'message': 'At least one worker ID is required.'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Get new workers
    new_workers = CustomUser.objects.filter(id__in=ids_list, role='worker')
    if not new_workers.exists():
        return Response({
            'status': 'error',
            'message': 'No valid workers found with the provided IDs.'
        }, status=status.HTTP_404_NOT_FOUND)

    # Keep track of old workers to free them up
    old_workers = list(booking.workers.all())
    if booking.worker and booking.worker not in old_workers:
        old_workers.append(booking.worker)

    # Assign new workers
    new_workers_list = list(new_workers)
    booking.workers.set(new_workers_list)
    booking.worker = new_workers_list[0]  # Set primary worker for legacy views
    booking.service_status = 'assigned'
    booking.save()

    # Set new workers to busy
    for worker in new_workers_list:
        worker.worker_status = 'busy'
        worker.save()

    # Free up old workers who are no longer assigned to this booking
    for old_w in old_workers:
        if old_w not in new_workers_list:
            # Check if this worker is busy on any other active bookings
            is_still_busy = Booking.objects.filter(
                Q(worker=old_w) | Q(workers=old_w),
                service_status__in=['assigned', 'in_progress']
            ).exclude(id=booking.id).exists()
            
            if not is_still_busy:
                old_w.worker_status = 'available'
                old_w.save()

    worker_names = ", ".join([w.full_name for w in new_workers_list])
    return Response({
        'status': 'success',
        'message': f"Workers ({worker_names}) successfully assigned to booking {ticket_id}.",
        'data': BookingSerializer(booking).data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOwner])
def admin_wallet_metrics(request):
    """
    Retrieve all customer wallet transactions and aggregated wallet metrics for admin dashboard.
    """
    transactions = WalletTransaction.objects.all().order_by('-created_at')
    serializer = WalletTransactionSerializer(transactions, many=True)
    
    # Also calculate total balance and metrics
    from django.contrib.auth import get_user_model
    User = get_user_model()
    customers = User.objects.filter(role='customer')
    total_balance = sum(c.wallet_balance for c in customers)
    active_wallets = sum(1 for c in customers if c.wallet_balance > 0)
    
    return Response({
        'status': 'success',
        'message': 'Admin wallet metrics retrieved successfully.',
        'data': {
            'transactions': serializer.data,
            'total_balance': float(total_balance),
            'total_customers': customers.count(),
            'active_wallets': active_wallets
        }
    }, status=status.HTTP_200_OK)
