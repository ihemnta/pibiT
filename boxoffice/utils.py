from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError
from django.db import IntegrityError
import logging
import redis
from django.conf import settings

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler for consistent error responses
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    if response is not None:
        # Add correlation ID to error response
        request = context.get('request')
        if request and hasattr(request, 'correlation_id'):
            response.data['correlation_id'] = request.correlation_id
        
        # Log the error
        logger.error(
            f"API Error: {exc}",
            extra={
                'correlation_id': getattr(request, 'correlation_id', None),
                'view': context.get('view').__class__.__name__,
                'status_code': response.status_code,
            }
        )
        
        return response
    
    # Handle Django-specific exceptions
    if isinstance(exc, ValidationError):
        return Response({
            'error': 'Validation Error',
            'details': exc.message_dict if hasattr(exc, 'message_dict') else str(exc),
            'correlation_id': getattr(context.get('request'), 'correlation_id', None),
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if isinstance(exc, IntegrityError):
        return Response({
            'error': 'Database Integrity Error',
            'details': str(exc),
            'correlation_id': getattr(context.get('request'), 'correlation_id', None),
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Handle unexpected errors
    logger.error(
        f"Unexpected error: {exc}",
        extra={
            'correlation_id': getattr(context.get('request'), 'correlation_id', None),
            'view': context.get('view').__class__.__name__,
        }
    )
    
    return Response({
        'error': 'Internal Server Error',
        'details': 'An unexpected error occurred',
        'correlation_id': getattr(context.get('request'), 'correlation_id', None),
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RedisLock:
    """
    Distributed lock using Redis for concurrency control
    """
    
    def __init__(self, lock_name, timeout=10):
        self.lock_name = f"lock:{lock_name}"
        self.timeout = timeout
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.lock = None
    
    def __enter__(self):
        self.lock = self.redis_client.lock(
            self.lock_name,
            timeout=self.timeout,
            blocking_timeout=5
        )
        acquired = self.lock.acquire()
        if not acquired:
            raise Exception(f"Failed to acquire lock: {self.lock_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lock:
            try:
                self.lock.release()
            except:
                pass


def get_redis_client():
    """
    Get Redis client instance
    """
    return redis.from_url(settings.REDIS_URL)


def set_hold_expiry(hold_id, expiry_seconds):
    """
    Set hold expiry in Redis with TTL
    """
    redis_client = get_redis_client()
    key = f"hold_expiry:{hold_id}"
    redis_client.setex(key, expiry_seconds, hold_id)
    logger.info(f"Set hold expiry for {hold_id} with TTL {expiry_seconds}s")





def clear_hold_expiry(hold_id):
    """
    Clear hold expiry from Redis
    """
    redis_client = get_redis_client()
    key = f"hold_expiry:{hold_id}"
    redis_client.delete(key)
    logger.info(f"Cleared hold expiry for {hold_id}")


def increment_metric(metric_name, value=1):
    """
    Increment a metric counter in Redis
    """
    redis_client = get_redis_client()
    key = f"metric:{metric_name}"
    redis_client.incr(key, value)
    # Set expiry to prevent unlimited growth
    redis_client.expire(key, 86400)  # 24 hours


def get_metric(metric_name):
    """
    Get metric value from Redis
    """
    redis_client = get_redis_client()
    key = f"metric:{metric_name}"
    value = redis_client.get(key)
    return int(value) if value else 0
