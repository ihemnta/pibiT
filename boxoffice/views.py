from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db import transaction, models
from django.utils import timezone
from django.conf import settings
import logging
import time
import psutil
import os

from .models import Event, Hold, Booking, Metrics
from .serializers import (
    EventSerializer, EventDetailSerializer, HoldCreateSerializer, 
    HoldResponseSerializer, BookingCreateSerializer, BookingResponseSerializer,
    MetricsSerializer, SystemMetricsSerializer
)
from .utils import RedisLock, set_hold_expiry, clear_hold_expiry, increment_metric, get_metric

logger = logging.getLogger(__name__)


class EventViewSet(viewsets.ModelViewSet):
    """ViewSet for Event operations"""
    
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return EventDetailSerializer
        return EventSerializer
    
    def create(self, request, *args, **kwargs):
        """Create a new event"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = serializer.save()
        
        # Create metrics record for the event
        Metrics.get_or_create_for_event(event)
        
        # Increment metrics
        increment_metric('events_created')
        
        logger.info(
            f"Event created: {event.id}",
            extra={
                'correlation_id': getattr(request, 'correlation_id', None),
                'event_id': str(event.id),
                'event_name': event.name,
                'total_seats': event.total_seats,
            }
        )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def retrieve(self, request, *args, **kwargs):
        """Get event details with seat counts"""
        event = self.get_object()
        serializer = self.get_serializer(event)
        
        logger.info(
            f"Event details retrieved: {event.id}",
            extra={
                'correlation_id': getattr(request, 'correlation_id', None),
                'event_id': str(event.id),
            }
        )
        
        return Response(serializer.data)


class HoldView(APIView):
    """View for creating holds with concurrency control"""
    
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        """Create a hold on seats"""
        serializer = HoldCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        event = serializer.validated_data['event_id']
        qty = serializer.validated_data['qty']
        ttl_minutes = serializer.validated_data.get('ttl_minutes', settings.HOLD_EXPIRY_MINUTES)
        
        # Use Redis lock for concurrency control
        lock_name = f"event_hold:{event.id}"
        
        try:
            with RedisLock(lock_name, timeout=10):
                # Double-check availability within the lock
                available_seats = event.available_seats
                if qty > available_seats:
                    return Response({
                        'error': 'Insufficient seats',
                        'details': f"Requested: {qty}, Available: {available_seats}",
                        'correlation_id': getattr(request, 'correlation_id', None),
                    }, status=status.HTTP_409_CONFLICT)
                
                # Create the hold
                hold = serializer.save()
                
                # Set expiry in Redis
                expiry_seconds = ttl_minutes * 60
                set_hold_expiry(str(hold.id), expiry_seconds)
                
                # Schedule the expire_holds task to run at the exact expiry time
                try:
                    from boxoffice.tasks import expire_specific_hold
                    expire_specific_hold.apply_async(
                        args=[str(hold.id)],
                        eta=hold.expires_at
                    )
                    logger.info(f"Scheduled expiry task for hold {hold.id} at {hold.expires_at}")
                except Exception as e:
                    logger.error(f"Failed to schedule expiry task for hold {hold.id}: {str(e)}", exc_info=True)
                
                # Increment metrics
                increment_metric('holds_created')
                increment_metric(f'holds_created_event_{event.id}')
                
                response_serializer = HoldResponseSerializer(hold)
                
                logger.info(
                    f"Hold created: {hold.id}",
                    extra={
                        'correlation_id': getattr(request, 'correlation_id', None),
                        'hold_id': str(hold.id),
                        'event_id': str(event.id),
                        'qty': qty,
                        'expires_at': hold.expires_at.isoformat(),
                    }
                )
                
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(
                f"Failed to create hold: {str(e)}",
                extra={
                    'correlation_id': getattr(request, 'correlation_id', None),
                    'event_id': str(event.id),
                    'qty': qty,
                }
            )
            return Response({
                'error': 'Failed to create hold',
                'details': str(e),
                'correlation_id': getattr(request, 'correlation_id', None),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BookingView(APIView):
    """View for creating bookings with idempotency"""
    
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        """Create a booking from a hold"""
        serializer = BookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        hold = serializer.validated_data['hold']
        
        # Use database transaction for atomicity
        with transaction.atomic():
            # Check if already booked (idempotency)
            if hasattr(hold, 'booking'):
                response_serializer = BookingResponseSerializer(hold.booking)
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            
            # Create booking
            booking = Booking.objects.create(hold=hold)
            
            # Update hold status
            hold.status = Hold.Status.BOOKED
            hold.save(update_fields=['status', 'updated_at'])
            
            # Clear expiry from Redis
            clear_hold_expiry(str(hold.id))
            
                             # The scheduled expiry task will be ignored since hold status is now BOOKED
            
            # Update metrics
            metrics = Metrics.get_or_create_for_event(hold.event)
            metrics.update_metrics()
            
            # Increment metrics
            increment_metric('bookings_created')
            increment_metric(f'bookings_created_event_{hold.event.id}')
            
            response_serializer = BookingResponseSerializer(booking)
            
            logger.info(
                f"Booking created: {booking.booking_id}",
                extra={
                    'correlation_id': getattr(request, 'correlation_id', None),
                    'booking_id': booking.booking_id,
                    'hold_id': str(hold.id),
                    'event_id': str(hold.event.id),
                }
            )
            
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class MetricsView(APIView):
    """View for system metrics"""
    
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        """Get system-wide metrics"""
        # Get database metrics
        total_events = Event.objects.count()
        total_active_holds = Hold.objects.filter(status=Hold.Status.ACTIVE).count()
        total_bookings = Booking.objects.count()
        total_expiries = Hold.objects.filter(status=Hold.Status.EXPIRED).count()
        
        # Get quantity-based metrics
        total_held_seats = Hold.objects.filter(status=Hold.Status.ACTIVE).aggregate(
            total=models.Sum('qty')
        )['total'] or 0
        
        total_booked_seats = Hold.objects.filter(booking__isnull=False).aggregate(
            total=models.Sum('qty')
        )['total'] or 0
        
        total_expired_seats = Hold.objects.filter(status=Hold.Status.EXPIRED).aggregate(
            total=models.Sum('qty')
        )['total'] or 0
        
        # Get Redis metrics
        redis_holds_created = get_metric('holds_created')
        redis_bookings_created = get_metric('bookings_created')
        redis_events_created = get_metric('events_created')
        
        # Calculate system uptime
        process = psutil.Process(os.getpid())
        uptime_seconds = time.time() - process.create_time()
        uptime_hours = int(uptime_seconds // 3600)
        uptime_minutes = int((uptime_seconds % 3600) // 60)
        system_uptime = f"{uptime_hours}h {uptime_minutes}m"
        
        metrics_data = {
            'total_events': total_events,
            'total_active_holds': total_active_holds,
            'total_bookings': total_bookings,
            'total_expiries': total_expiries,
            'total_held_seats': total_held_seats,
            'total_booked_seats': total_booked_seats,
            'total_expired_seats': total_expired_seats,
            'system_uptime': system_uptime,
            'redis_metrics': {
                'holds_created': redis_holds_created,
                'bookings_created': redis_bookings_created,
                'events_created': redis_events_created,
            }
        }
        
        serializer = SystemMetricsSerializer(data=metrics_data)
        serializer.is_valid(raise_exception=True)
        
        logger.info(
            f"Metrics retrieved",
            extra={
                'correlation_id': getattr(request, 'correlation_id', None),
                'total_events': total_events,
                'total_active_holds': total_active_holds,
                'total_bookings': total_bookings,
            }
        )
        
        return Response(serializer.data)


class EventMetricsView(APIView):
    """View for event-specific metrics"""
    
    permission_classes = [permissions.AllowAny]
    
    def get(self, request, event_id):
        """Get metrics for a specific event"""
        event = get_object_or_404(Event, id=event_id)
        metrics = Metrics.get_or_create_for_event(event)
        metrics.update_metrics()
        
        serializer = MetricsSerializer(metrics)
        
        logger.info(
            f"Event metrics retrieved: {event.id}",
            extra={
                'correlation_id': getattr(request, 'correlation_id', None),
                'event_id': str(event.id),
            }
        )
        
        return Response(serializer.data)
