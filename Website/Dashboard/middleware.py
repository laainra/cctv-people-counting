from django.utils.deprecation import MiddlewareMixin

class CamIdMiddleware(MiddlewareMixin):
    def process_request(self, request, *args):
        if hasattr(request, 'session'):
            request.cam_id = request.session.get('cam_id', 1)
        else:
            request.cam_id = 1
    