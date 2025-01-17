from django.http import HttpResponseForbidden
from django.shortcuts import redirect
def role_required(role):
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_authenticated:
                if request.user.role != role:
                    return HttpResponseForbidden("You are not authorized to access this page.")
                
                if role == 'superadmin':
                    return view_func(request, *args, **kwargs)
                
                if role == 'admin':
                    # Admin logic - check if associated with a company
                    if not hasattr(request.user, 'company'):
                        return HttpResponseForbidden("Admin does not have an associated company.")
                    return view_func(request, *args, **kwargs)
                
                if role == 'employee':
                    # Employee logic - check if associated with a company
                    if not hasattr(request.user, 'company'):
                        return HttpResponseForbidden("Employee does not have an associated company.")
                    return view_func(request, *args, **kwargs)
            return redirect('login')
        return _wrapped_view
    return decorator
