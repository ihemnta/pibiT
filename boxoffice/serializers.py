from rest_framework import serializers
from .models import Event, Hold, Booking, Metrics
from django.utils import timezone
from django.conf import settings
import uuid


class EventSerializer(serializers.ModelSerializer):
    """Serializer for Event model"""
    
    class Meta:
        model = Event
        fields = ['id', 'name', 'total_seats', 'created_at']
        read_only_fields = ['id', 'created_at']


class EventDetailSerializer(serializers.ModelSerializer):
    """Serializer for detailed event information including seat counts"""
    
    total = serializers.IntegerField(source='total_seats', read_only=True)
    available = serializers.IntegerField(source='available_seats', read_only=True)
    held = serializers.IntegerField(source='held_seats', read_only=True)
    booked = serializers.IntegerField(source='booked_seats', read_only=True)
    
    class Meta:
        model = Event
        fields = ['id', 'name', 'total', 'available', 'held', 'booked', 'created_at']
        read_only_fields = ['id', 'total', 'available', 'held', 'booked', 'created_at']


class HoldCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating holds"""
    
    event_id = serializers.UUIDField(write_only=True)
    qty = serializers.IntegerField(min_value=1)
    ttl_minutes = serializers.IntegerField(
        min_value=1, 
        max_value=settings.MAX_HOLD_TTL_MINUTES,
        default=settings.HOLD_EXPIRY_MINUTES,
        required=False
    )
    
    class Meta:
        model = Hold
        fields = ['event_id', 'qty', 'ttl_minutes']
    
    def validate_event_id(self, value):
        """Validate that event exists"""
        try:
            event = Event.objects.get(id=value)
            return event
        except Event.DoesNotExist:
            raise serializers.ValidationError("Event not found")
    
    def validate(self, data):
        """Validate hold request"""
        event = data['event_id']  # This is now the Event instance
        qty = data['qty']
        
        # Check if enough seats are available
        available_seats = event.available_seats
        if qty > available_seats:
            raise serializers.ValidationError(
                f"Not enough seats available. Requested: {qty}, Available: {available_seats}"
            )
        
        return data
    
    def create(self, validated_data):
        """Create hold with proper expiry time"""
        event = validated_data['event_id']
        qty = validated_data['qty']
        ttl_minutes = validated_data.get('ttl_minutes', settings.HOLD_EXPIRY_MINUTES)
        
        # Calculate expiry time
        expires_at = timezone.now() + timezone.timedelta(minutes=ttl_minutes)
        
        # Generate payment token
        payment_token = str(uuid.uuid4())
        
        # Create hold
        hold = Hold.objects.create(
            event=event,
            qty=qty,
            expires_at=expires_at,
            payment_token=payment_token
        )
        
        return hold


class HoldResponseSerializer(serializers.ModelSerializer):
    """Serializer for hold response"""
    
    hold_id = serializers.UUIDField(source='id', read_only=True)
    expires_at = serializers.DateTimeField(read_only=True)
    payment_token = serializers.CharField(read_only=True)
    
    class Meta:
        model = Hold
        fields = ['hold_id', 'expires_at', 'payment_token']


class BookingCreateSerializer(serializers.Serializer):
    """Serializer for creating bookings"""
    
    hold_id = serializers.UUIDField()
    payment_token = serializers.CharField()
    
    def validate(self, data):
        """Validate booking request"""
        hold_id = data['hold_id']
        payment_token = data['payment_token']
        
        try:
            hold = Hold.objects.get(id=hold_id)
        except Hold.DoesNotExist:
            raise serializers.ValidationError("Hold not found")
        
        # Check if hold is active
        if hold.status != Hold.Status.ACTIVE:
            raise serializers.ValidationError("Hold is not active")
        
        # Check if hold has expired
        if hold.is_expired:
            raise serializers.ValidationError("Hold has expired")
        
        # Check payment token
        if hold.payment_token != payment_token:
            raise serializers.ValidationError("Invalid payment token")
        
        # Check if already booked
        if hasattr(hold, 'booking'):
            raise serializers.ValidationError("Hold is already booked")
        
        data['hold'] = hold
        return data


class BookingResponseSerializer(serializers.ModelSerializer):
    """Serializer for booking response"""
    
    booking_id = serializers.CharField(read_only=True)
    
    class Meta:
        model = Booking
        fields = ['booking_id']


class MetricsSerializer(serializers.ModelSerializer):
    """Serializer for metrics"""
    
    event_name = serializers.CharField(source='event.name', read_only=True)
    
    class Meta:
        model = Metrics
        fields = [
            'event_name', 'total_holds', 'total_bookings', 'total_expiries',
            'total_held_seats', 'total_booked_seats', 'total_expired_seats', 'updated_at'
        ]
        read_only_fields = [
            'total_holds', 'total_bookings', 'total_expiries',
            'total_held_seats', 'total_booked_seats', 'total_expired_seats', 'updated_at'
        ]


class SystemMetricsSerializer(serializers.Serializer):
    """Serializer for system-wide metrics"""
    
    total_events = serializers.IntegerField()
    total_active_holds = serializers.IntegerField()
    total_bookings = serializers.IntegerField()
    total_expiries = serializers.IntegerField()
    total_held_seats = serializers.IntegerField()
    total_booked_seats = serializers.IntegerField()
    total_expired_seats = serializers.IntegerField()
    system_uptime = serializers.CharField()
