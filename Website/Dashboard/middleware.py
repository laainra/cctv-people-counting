from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect

class RedirectIfLoggedInMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Cek apakah pengguna sudah login
        if request.user.is_authenticated:
            # Redirect berdasarkan role
            if request.path == '/login':  # Ganti '/login/' dengan URL login Anda
                if request.user.is_superadmin:
                    return redirect('superadmin_home')
                elif request.user.is_admin:
                    return redirect('admin_home')
                elif request.user.is_employee:
                    return redirect('employee_home')
        
        response = self.get_response(request)
        return response
class RoleRedirectMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Check if the user is authenticated
        if request.user.is_authenticated:
            # Only redirect if the user is accessing the root URL
            if request.path == '/' or request.path == '':
                # Check the user's role and redirect accordingly
                if request.user.role == 'employee':
                    return redirect('employee_home')  # Redirect to employee home
                elif request.user.role == 'superadmin':
                    return redirect('superadmin_home')  # Redirect to superadmin home
                # If the role is 'admin', do not redirect
        return None 
class CamIdMiddleware(MiddlewareMixin):
    def process_request(self, request, *args):
        if hasattr(request, 'session'):
            request.cam_id = request.session.get('cam_id', 1)
        else:
            request.cam_id = 1
    