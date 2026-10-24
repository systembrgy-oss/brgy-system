import qrcode
import io
import base64
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from .models import AuditLog

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip or "127.0.0.1"

def log_action(request, action, module):
    """Logs system security and operational events for auditability."""
    user = request.user if request.user.is_authenticated else None
    AuditLog.objects.create(
        UserID=user,
        Action=action,
        Module=module,
        IPAddress=get_client_ip(request)
    )

def generate_qr_base64(data_text):
    """Generates an embedded base64 QR code image."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(data_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="white")
    
    buffer = io.BytesIO()
    img.save(buffer)
    img_b64 = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_b64}"

def role_required(allowed_roles):
    """Decorator to enforce RBAC based on user role."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            # Superusers always have full access
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
                
            role_name = request.user.RoleID.RoleName if request.user.RoleID else None
            if role_name not in allowed_roles:
                messages.error(request, "Access Denied: You do not have permission to access this module.")
                return redirect('dashboard')
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
