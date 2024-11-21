from django.utils.deprecation import MiddlewareMixin

class CamIdMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.cam_id = request.session.get('cam_id', 1) 
