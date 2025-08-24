from django.contrib import admin
from .models import Event, Hold, Booking, Metrics


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'total_seats', 'available_seats', 'held_seats', 'booked_seats', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    def available_seats(self, obj):
        return obj.available_seats
    available_seats.short_description = 'Available Seats'
    
    def held_seats(self, obj):
        return obj.held_seats
    held_seats.short_description = 'Held Seats'
    
    def booked_seats(self, obj):
        return obj.booked_seats
    booked_seats.short_description = 'Booked Seats'


@admin.register(Hold)
class HoldAdmin(admin.ModelAdmin):
    list_display = ['id', 'event', 'qty', 'status', 'expires_at', 'created_at']
    list_filter = ['status', 'created_at', 'expires_at']
    search_fields = ['event__name', 'payment_token']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('event')


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['id', 'booking_id', 'hold', 'created_at']
    list_filter = ['created_at']
    search_fields = ['booking_id', 'hold__id']
    readonly_fields = ['id', 'booking_id', 'created_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('hold', 'hold__event')


@admin.register(Metrics)
class MetricsAdmin(admin.ModelAdmin):
    list_display = ['id', 'event', 'total_holds', 'total_bookings', 'total_expiries', 'updated_at']
    list_filter = ['updated_at']
    search_fields = ['event__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('event')
