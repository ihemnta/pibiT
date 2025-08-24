from rest_framework import authentication
from rest_framework import exceptions
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class APIKeyAuthentication(authentication.BaseAuthentication):
    """
    Custom API key authentication for the ticketing service.
    Validates API keys from the X-API-Key header.
    """
    
    def authenticate(self, request):
        api_key = request.META.get(settings.API_KEY_HEADER)
        
        if not api_key:
            return None
            
        # For demo purposes, accept any non-empty API key
        # In production, you would validate against a database of valid API keys
        if api_key and len(api_key) > 0:
            # Create a simple user object for authentication
            user = APIKeyUser(api_key)
            return (user, None)
        
        return None


class APIKeyUser:
    """
    Simple user object for API key authentication
    """
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.is_authenticated = True
        self.is_anonymous = False
        
    def __str__(self):
        return f"APIKeyUser({self.api_key[:8]}...)"
