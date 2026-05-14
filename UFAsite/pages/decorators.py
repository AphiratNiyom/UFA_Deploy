from functools import wraps
from django.shortcuts import redirect


def admin_required(view_func):
    """
    Decorator ตรวจสอบว่า session มี 'is_admin_logged_in' = True
    ถ้าไม่มี redirect ไปหน้า login
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('is_admin_logged_in'):
            return redirect('admin_login')
        return view_func(request, *args, **kwargs)
    return wrapper
