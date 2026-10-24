from .models import BarangaySetting, Notification
from django.db.models import Q

def barangay_context(request):
    """
    Global context processor making Barangay identity, LGU hierarchy,
    and signatory officials accessible across all templates dynamically,
    along with role-based notifications.
    """
    try:
        settings = BarangaySetting.get_settings()
    except Exception:
        settings = None

    user_notifications = []
    unread_notif_count = 0

    if hasattr(request, 'user') and request.user.is_authenticated:
        user = request.user
        role_name = user.RoleID.RoleName if user.RoleID else "Admin"

        if role_name == 'Admin' or user.is_superuser:
            qs = Notification.objects.filter(
                Q(RecipientUser=user) | Q(TargetRole__in=['Admin', 'Staff', 'All'])
            )
        elif role_name == 'Staff':
            qs = Notification.objects.filter(
                Q(RecipientUser=user) | Q(TargetRole__in=['Staff', 'All'])
            )
        else: # People / Resident
            qs = Notification.objects.filter(
                Q(RecipientUser=user) | Q(TargetRole__in=['People', 'All'])
            )

        unread_notif_count = qs.filter(IsRead=False).count()
        user_notifications = list(qs.order_by('-CreatedAt')[:10])

    return {
        'barangay_info': settings,
        'user_notifications': user_notifications,
        'unread_notif_count': unread_notif_count,
    }
