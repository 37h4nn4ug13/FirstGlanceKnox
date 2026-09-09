from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def has_role(user, *roles):
    from operations.services import has_role as domain_has_role

    return domain_has_role(user, *roles)


def is_admin(user):
    return has_role(user, "Admin")


def staff_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not has_role(request.user, "Admin", "Salesperson", "Cleaner"):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    @staff_required
    def wrapped(request, *args, **kwargs):
        if not is_admin(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapped
