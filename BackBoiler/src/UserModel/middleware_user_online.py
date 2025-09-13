from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()

class UserOnlineMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Track activity for authenticated users
        if request.user.is_authenticated:
            # Update activity timestamp
            User.objects.filter(id=request.user.id).update(
                last_activity_at=timezone.now()
            )
            
            # Also store in session for additional tracking
            request.session['last_activity_at'] = timezone.now().isoformat()
        
        response = self.get_response(request)
        return response