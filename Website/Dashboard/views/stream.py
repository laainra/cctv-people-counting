
from django.shortcuts import render, get_object_or_404
import os
import cv2
import json
import numpy as np
from django.urls import reverse

# Backend Library
from .var import var
from django.shortcuts import render, redirect, HttpResponse
from django.contrib.auth.decorators import login_required
from django.http.response import StreamingHttpResponse, JsonResponse
from .. import forms, models
from ..decorators import role_required

# Artificial Intelligence Library
# from ..Artificial_Intelligence.work_timer import Work_Timer as WT
from ..Artificial_Intelligence.multi_camera import MultiCamera as MC
from ..Artificial_Intelligence.variables import RecognitionVariable as RV



@login_required(login_url='login')
@role_required('admin')
def stream(request):
    cam = models.Camera_Settings.objects.get(id=request.session['cam_id'])
    company = models.Company.objects.get(user=request.user)
    return render(request, 'admin/stream.html', {'company': company, 'cam': cam})

@login_required
def start_ai_stream(request):
    try:
        # Memulai dengan mengambil settingan kamera
        cam = models.Camera_Settings.objects.get(id=request.session['cam_id'])
        print(f"Camera settings retrieved: {cam}")

        poly = np.array([[cam.x1, cam.y1], [cam.x2, cam.y2], [cam.x3, cam.y3], [cam.x4, cam.y4],
                         [cam.x8, cam.y8], [cam.x7, cam.y7], [cam.x6, cam.y6], [cam.x5, cam.y5]])
        poly = poly.astype(int)
        print(f"Polygon points: {poly}")

        # Mencoba untuk membuka RTSP stream
        print(f"Attempting to open RTSP stream from: {cam.feed_src}")
        cap = cv2.VideoCapture(cam.feed_src)
        
        if not cap.isOpened():
            print("Failed to open RTSP stream, trying default camera")
            raise Exception("Failed to open RTSP stream")
    except Exception as e:
        print(f"Exception encountered: {e}")
        cap = cv2.VideoCapture(0)  # Coba dengan default camera
        if not cap.isOpened():
            print("Failed to open default camera as well")
            request.session['status'] = 'stream_error'
            return redirect('camera')

    # Jika kamera terbuka, lanjutkan proses
    if cap.isOpened():
        print("RTSP stream or default camera opened successfully")
        request.session['stream_running'] = False
        
                # Set known faces for face recognition
        if len(RV.known_features) == 0:
            RV.set_all_known_faces()
        else:
            for personnel_name in os.listdir(var.personnel_path):
                if RV.known_features.get(personnel_name) == None:
                    RV.set_personnel_known_faces(personnel_name)
                else:
                    if personnel_name == 'Unknown':
                        if len(RV.known_features[personnel_name]) != (len(os.listdir(os.path.join(var.personnel_path, personnel_name))) - 1):
                            RV.set_personnel_known_faces(personnel_name)
                    else:
                        if len(RV.known_features[personnel_name]) != len(os.listdir(os.path.join(var.personnel_path, personnel_name))):
                            RV.set_personnel_known_faces(personnel_name)


        ai_stream = WT(cam.feed_src, cam.id)
        print("AI Stream initialized")
        ai_stream.start_stream()
        # print("AI Stream started")
        
        MC.add_camera(cam.id, cam.feed_src)
        # Start stream
        MC.stop_cam(cam.id)
        MC.start_cam(cam.id)
        print(f"Started camera {cam.id}")

        # Update status kamera
        cam.cam_is_active = True
        cam.save()
        print(f"Camera status updated to active: {cam.cam_is_active}")

        request.session['status'] = 'stream_success'
        print(f"Session status set to 'stream_success'")
        
        return JsonResponse({'status': 'success', 'camera_active': cam.cam_is_active})
    else:
        print("Failed to open camera stream")
        request.session['status'] = 'stream_error'
        return JsonResponse({'status': 'error', 'message': 'Failed to open stream'})

 
@login_required
def stop_ai_stream(request):
    cam = models.Camera_Settings.objects.get(id=request.session['cam_id'])
    cam.cam_is_active = False
    cam.save()

    ai_stream = WT(cam.feed_src, cam.id)
    ai_stream.stop_stream()

    return JsonResponse({'status': 'success'})

def generate_ai_stream(request):
    request.session['stream_running'] = True

    while request.session['stream_running']:
        try:
            frame, pred_frame = MC.get_frame(request.session['cam_id'])
            print(f"Generated frame: {frame.shape}")
        except:
            continue

        buffer = cv2.imencode('.jpg', pred_frame)[1]
        pred_frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + pred_frame + b'\r\n\r\n')

@login_required(login_url='login')
def ai_video_feed(request):
    return StreamingHttpResponse(generate_ai_stream(request), content_type='multipart/x-mixed-replace; boundary=frame')

@login_required
def set_cam_id(request):
    if request.method == 'POST':
        try:
            # Mendapatkan cam_id dari body request
            data = json.loads(request.body)
            cam_id = data.get('cam_id')

            if not cam_id:
                return JsonResponse({'status': 'error', 'message': 'Camera ID not provided'}, status=400)

            # Logika untuk menyimpan cam_id di sesi atau database
            # Misalnya, menyimpan cam_id ke sesi
            request.session['cam_id'] = cam_id
            return JsonResponse({'status': 'success', 'message': 'Camera ID set successfully'})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)