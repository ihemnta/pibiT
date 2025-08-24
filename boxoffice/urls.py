from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EventViewSet, HoldView, BookingView, MetricsView, EventMetricsView

# Create router for ViewSets
router = DefaultRouter()
router.register(r'events', EventViewSet)

urlpatterns = [
    # Include router URLs
    path('', include(router.urls)),
    
    # Custom API endpoints
    path('holds/', HoldView.as_view(), name='holds'),
    path('book/', BookingView.as_view(), name='book'),
    path('metrics/', MetricsView.as_view(), name='metrics'),
    path('events/<uuid:event_id>/metrics/', EventMetricsView.as_view(), name='event-metrics'),
]
