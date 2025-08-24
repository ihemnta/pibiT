import uuid
import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class CorrelationIdMiddleware(MiddlewareMixin):
    """
    Middleware to add correlation IDs to requests for tracking
    """
    
    def process_request(self, request):
        # Generate correlation ID if not present
        correlation_id = request.META.get('HTTP_X_CORRELATION_ID')
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        
        # Add to request for use in views
        request.correlation_id = correlation_id
        
        # Add to META for logging
        request.META['HTTP_X_CORRELATION_ID'] = correlation_id
        
        # Log request with correlation ID
        logger.info(
            f"Request started",
            extra={
                'correlation_id': correlation_id,
                'method': request.method,
                'path': request.path,
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            }
        )
    
    def process_response(self, request, response):
        # Add correlation ID to response headers
        if hasattr(request, 'correlation_id'):
            response['X-Correlation-ID'] = request.correlation_id
            
            # Log response with correlation ID
            logger.info(
                f"Request completed",
                extra={
                    'correlation_id': request.correlation_id,
                    'status_code': response.status_code,
                    'method': request.method,
                    'path': request.path,
                }
            )
        
        return response
