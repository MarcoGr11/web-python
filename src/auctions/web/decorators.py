from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(role):
    """Require the caller to be authenticated and hold the given role.

    Unauthenticated users are redirected to login (302) by login_required.
    Authenticated users of the wrong role get PermissionDenied (403).
    """

    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            is_admin = request.user.is_staff
            if (role == "admin") != is_admin:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
