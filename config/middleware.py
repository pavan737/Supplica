"""
Custom middleware for handling CSRF and API authentication.
"""

from django.utils.deprecation import MiddlewareMixin
from django.conf import settings


class CSRFExemptAPIMiddleware(MiddlewareMixin):
    """
    Exempt API endpoints from CSRF protection.
    
    JWT-based APIs don't need CSRF tokens because:
    1. JWT tokens are in the Authorization header, not cookies
    2. Cross-site requests cannot read the Authorization header (same-origin policy)
    3. CSRF attacks rely on cookies being automatically sent with requests
    
    This middleware exempts paths that use JWT authentication.
    """
    
    EXEMPT_PATHS = [
        '/api/',
    ]
    
    def process_request(self, request):
        """Check if the request path should be exempt from CSRF."""
        for path in self.EXEMPT_PATHS:
            if request.path.startswith(path):
                # Mark request as CSRF exempt
                request._dont_enforce_csrf_checks = True
                break
        return None
