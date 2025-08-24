from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
import uuid
import logging

logger = logging.getLogger(__name__)


class Event(models.Model):
    """Event model representing a ticketing event"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    total_seats = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'events'
        indexes = [
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.name} ({self.total_seats} seats)"

    @property
    def available_seats(self):
        """Calculate available seats (total - held - booked)"""
        held_seats = self.holds.filter(status=Hold.Status.ACTIVE).aggregate(
            total=models.Sum('qty')
        )['total'] or 0
        booked_seats = self.holds.filter(booking__isnull=False).aggregate(
            total=models.Sum('qty')
        )['total'] or 0
        return max(0, self.total_seats - held_seats - booked_seats)

    @property
    def held_seats(self):
        """Calculate currently held seats"""
        return self.holds.filter(status=Hold.Status.ACTIVE).aggregate(
            total=models.Sum('qty')
        )['total'] or 0

    @property
    def booked_seats(self):
        """Calculate booked seats"""
        return self.holds.filter(booking__isnull=False).aggregate(
            total=models.Sum('qty')
        )['total'] or 0


class Hold(models.Model):
    """Hold model for temporary seat reservations"""
    
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        EXPIRED = 'EXPIRED', 'Expired'
        BOOKED = 'BOOKED', 'Booked'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='holds')
    qty = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    expires_at = models.DateTimeField()
    payment_token = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'holds'
        indexes = [
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['payment_token']),
            models.Index(fields=['event', 'status']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(qty__gt=0),
                name='hold_qty_positive'
            ),
        ]

    def __str__(self):
        return f"Hold {self.id} for {self.event.name} ({self.qty} seats)"

    @property
    def is_expired(self):
        """Check if hold has expired"""
        return timezone.now() > self.expires_at

    def expire(self):
        """Mark hold as expired"""
        if self.status == self.Status.ACTIVE:
            self.status = self.Status.EXPIRED
            self.save(update_fields=['status', 'updated_at'])
            logger.info(f"Hold {self.id} expired for event {self.event.id}")


class Booking(models.Model):
    """Booking model for confirmed seat reservations"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hold = models.OneToOneField(Hold, on_delete=models.CASCADE, related_name='booking')
    booking_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bookings'
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['booking_id']),
        ]

    def __str__(self):
        return f"Booking {self.booking_id} for hold {self.hold.id}"

    def save(self, *args, **kwargs):
        if not self.booking_id:
            self.booking_id = f"BK-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


class Metrics(models.Model):
    """Metrics model for tracking system statistics"""
    id = models.AutoField(primary_key=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='metrics')
    total_holds = models.PositiveIntegerField(default=0)  # Number of hold records
    total_bookings = models.PositiveIntegerField(default=0)  # Number of booking records
    total_expiries = models.PositiveIntegerField(default=0)  # Number of expired hold records
    total_held_seats = models.PositiveIntegerField(default=0)  # Total quantity of held seats
    total_booked_seats = models.PositiveIntegerField(default=0)  # Total quantity of booked seats
    total_expired_seats = models.PositiveIntegerField(default=0)  # Total quantity of expired seats
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'metrics'
        indexes = [
            models.Index(fields=['event', 'created_at']),
        ]

    def __str__(self):
        return f"Metrics for {self.event.name}"

    @classmethod
    def get_or_create_for_event(cls, event):
        """Get or create metrics for an event"""
        metrics, created = cls.objects.get_or_create(event=event)
        return metrics

    def update_metrics(self):
        """Update metrics based on current data"""
        # Count total holds (number of hold records)
        self.total_holds = self.event.holds.count()
        
        # Count total bookings (number of booking records)
        self.total_bookings = self.event.holds.filter(booking__isnull=False).count()
        
        # Count total expiries (number of expired hold records)
        self.total_expiries = self.event.holds.filter(status=Hold.Status.EXPIRED).count()
        
        # Calculate total quantities
        self.total_held_seats = self.event.holds.filter(status=Hold.Status.ACTIVE).aggregate(
            total=models.Sum('qty')
        )['total'] or 0
        
        self.total_booked_seats = self.event.holds.filter(booking__isnull=False).aggregate(
            total=models.Sum('qty')
        )['total'] or 0
        
        self.total_expired_seats = self.event.holds.filter(status=Hold.Status.EXPIRED).aggregate(
            total=models.Sum('qty')
        )['total'] or 0
        
        self.save(update_fields=[
            'total_holds', 'total_bookings', 'total_expiries', 
            'total_held_seats', 'total_booked_seats', 'total_expired_seats', 
            'updated_at'
        ])
