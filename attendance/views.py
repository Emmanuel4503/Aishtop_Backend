from datetime import datetime
import zoneinfo

from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import WorkerAttendance
from .serializers import WorkerAttendanceSerializer

User = get_user_model()
WAT = zoneinfo.ZoneInfo("Africa/Lagos")


def _wat_now():
    """Return current date and time in West Africa Time (UTC+1)."""
    now = datetime.now(tz=WAT)
    return now.date(), now.time().replace(microsecond=0)


# ---------------------------------------------------------------------------
# Public endpoints (used by the QR-code attendance page)
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([AllowAny])
def list_workers_for_attendance(request):
    """
    Returns all active workers so the attendance page can show the picker.
    """
    workers = User.objects.filter(role='worker', is_active=True).order_by('full_name')
    data = [
        {
            'id': w.id,
            'name': w.full_name,
            'email': w.email,
            'worker_role': w.worker_role or '',
        }
        for w in workers
    ]
    return Response({'status': 'success', 'data': data})


@api_view(['POST'])
@permission_classes([AllowAny])
def record_attendance(request):
    """
    Record a sign-in or sign-out for a worker.
    Body: { "worker_id": <int>, "action": "sign_in" | "sign_out" }
    Time is taken from the server clock in WAT.
    """
    worker_id = request.data.get('worker_id')
    action = request.data.get('action')

    if not worker_id or action not in ('sign_in', 'sign_out'):
        return Response(
            {'status': 'error', 'message': 'worker_id and action (sign_in | sign_out) are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        worker = User.objects.get(id=worker_id, role='worker', is_active=True)
    except User.DoesNotExist:
        return Response(
            {'status': 'error', 'message': 'Worker not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    today, now_time = _wat_now()
    record, _ = WorkerAttendance.objects.get_or_create(worker=worker, date=today)

    if action == 'sign_in':
        if record.sign_in_time:
            time_str = record.sign_in_time.strftime('%I:%M %p')
            return Response(
                {'status': 'error', 'message': f'{worker.full_name} already signed in today at {time_str}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        record.sign_in_time = now_time
        record.save()
        return Response({
            'status': 'success',
            'message': f'Sign-in recorded for {worker.full_name}.',
            'data': {
                'worker_name': worker.full_name,
                'action': 'sign_in',
                'time': now_time.strftime('%I:%M %p'),
                'date': str(today),
            },
        })

    else:  # sign_out
        if not record.sign_in_time:
            return Response(
                {'status': 'error', 'message': f'{worker.full_name} has not signed in today yet.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if record.sign_out_time:
            time_str = record.sign_out_time.strftime('%I:%M %p')
            return Response(
                {'status': 'error', 'message': f'{worker.full_name} already signed out today at {time_str}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        record.sign_out_time = now_time
        record.save()
        return Response({
            'status': 'success',
            'message': f'Sign-out recorded for {worker.full_name}.',
            'data': {
                'worker_name': worker.full_name,
                'action': 'sign_out',
                'time': now_time.strftime('%I:%M %p'),
                'date': str(today),
            },
        })


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_attendance_by_date(request):
    """
    Returns attendance records for a given date, with a row for every
    active worker (absent workers appear with null times).
    Query param: ?date=YYYY-MM-DD  (defaults to today WAT)
    """
    if request.user.role not in ('owner', 'front_desk'):
        return Response({'status': 'error', 'message': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

    date_str = request.query_params.get('date')
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'status': 'error', 'message': 'Invalid date format. Use YYYY-MM-DD.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        target_date, _ = _wat_now()

    workers = User.objects.filter(role='worker', is_active=True).order_by('full_name')
    records = {
        r.worker_id: r
        for r in WorkerAttendance.objects.filter(date=target_date).select_related('worker')
    }

    rows = []
    for w in workers:
        rec = records.get(w.id)
        rows.append({
            'worker_id': w.id,
            'worker_name': w.full_name,
            'sign_in_time': rec.sign_in_time.strftime('%I:%M %p') if rec and rec.sign_in_time else None,
            'sign_out_time': rec.sign_out_time.strftime('%I:%M %p') if rec and rec.sign_out_time else None,
            'hours_worked': rec.hours_worked if rec else None,
        })

    return Response({
        'status': 'success',
        'data': {
            'date': str(target_date),
            'records': rows,
        },
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_worker_attendance_history(request, worker_id):
    """
    Returns the attendance history for a specific worker.
    Query params: ?from=YYYY-MM-DD&to=YYYY-MM-DD  (optional)
    """
    if request.user.role not in ('owner', 'front_desk'):
        return Response({'status': 'error', 'message': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        worker = User.objects.get(id=worker_id, role='worker')
    except User.DoesNotExist:
        return Response({'status': 'error', 'message': 'Worker not found.'}, status=status.HTTP_404_NOT_FOUND)

    qs = WorkerAttendance.objects.filter(worker=worker).order_by('-date')

    from_str = request.query_params.get('from')
    to_str = request.query_params.get('to')
    if from_str:
        try:
            qs = qs.filter(date__gte=datetime.strptime(from_str, '%Y-%m-%d').date())
        except ValueError:
            pass
    if to_str:
        try:
            qs = qs.filter(date__lte=datetime.strptime(to_str, '%Y-%m-%d').date())
        except ValueError:
            pass

    rows = [
        {
            'date': str(r.date),
            'sign_in_time': r.sign_in_time.strftime('%I:%M %p') if r.sign_in_time else None,
            'sign_out_time': r.sign_out_time.strftime('%I:%M %p') if r.sign_out_time else None,
            'hours_worked': r.hours_worked,
        }
        for r in qs
    ]

    return Response({
        'status': 'success',
        'data': {
            'worker_id': worker.id,
            'worker_name': worker.full_name,
            'records': rows,
        },
    })
