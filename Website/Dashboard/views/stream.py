
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
import cv2  # OpenCV for video capture
import threading
from .face_rec import predict_video
# Artificial Intelligence Library
# from ..Artificial_Intelligence.work_timer import Work_Timer as WT
from ..Artificial_Intelligence.multi_camera import MultiCamera as MC
from ..Artificial_Intelligence.variables import RecognitionVariable as RV
import logging
from django.db.models import Q


logger = logging.getLogger(__name__)

# presence_stream
camera_feed = None
streaming = False
camera_feeds = {}
streaming_status = {}
detection_times = {}

@login_required(login_url='login')
@role_required('admin')
def stream(request, cam_id):
    company = models.Company.objects.get(user=request.user)
    cam = models.Camera_Settings.objects.get(id=cam_id)
    return render(request, 'admin/stream.html', {'company': company, 'cam': cam})

@login_required(login_url='login')
@role_required('admin')
def presence_stream(request):
    company = models.Company.objects.get(user=request.user)
    cams = models.Camera_Settings.objects.filter(role_camera__in=['P_IN', 'P_OUT'], company=company)
    return render(request, 'admin/presence_stream.html', {'company': company, 'cams': cams})

def start_presence_stream(request, cam_id):
    global camera_feed, streaming
    
    # Initialize the session variable if it doesn't exist
    if 'cams' not in request.session:
        request.session['cams'] = []

    # Check if the camera is already active
    if cam_id in request.session['cams']:
        return JsonResponse({'status': 'error', 'message': 'Camera is already active'})

    cam = get_object_or_404(models.Camera_Settings, id=cam_id)
    
    # Attempt to open the camera feed
    camera_feed = cv2.VideoCapture(cam.feed_src) # Assuming feed_src is a valid URL or path

    if camera_feed.isOpened():
        print(f"Start RTSP stream from: {cam.cam_name}")
        request.session['cams'].append(cam_id)  # Add cam_id to the session list
        request.session.modified = True  # Mark the session as modified
        streaming = True
        
        # Update camera status
        cam.cam_is_active = True
        cam.save()
        
        # Start camera management
        MC.add_camera(cam.id, cam.feed_src)
        MC.stop_cam(cam.id)  # Stop any existing camera stream
        MC.start_cam(cam.id)  # Start the new camera stream
        
        # Start the stream in a separate thread
        threading.Thread(target=predict_video, args=(cam_id,)).start() 
        
        return redirect('presence_stream')
    else:
        print("Failed to open camera stream")
        return redirect('presence_stream')


def stop_presence_stream(request, cam_id):
    global camera_feed, streaming

    streaming = False
    camera_feed = None
    
    request.session['cams'].remove(cam_id)
    request.session.modified = True  
    
    cam = get_object_or_404(models.Camera_Settings, id=cam_id)
    cam.cam_is_active = False
    cam.save()
    
    MC.stop_cam(cam.id)
    
    print(f"Cam with id: {cam_id} stopped successfully")
    
    return redirect('presence_stream')
    
@login_required(login_url='login')
@role_required('admin')
def tracking_stream(request):
    company = models.Company.objects.get(user=request.user)
    tracking_cameras = models.Camera_Settings.objects.filter(company=company, role_camera='T')  # Get tracking cameras
    default_camera = tracking_cameras.first() if tracking_cameras.exists() else None  # Set a default camera if available
    return render(request, 'admin/tracking_stream.html', {
        'company': company,
        'tracking_cameras': tracking_cameras,
        'default_camera': default_camera
    })

@login_required(login_url='login')
@role_required('admin')
def presence_cam_stream(request):
    company = models.Company.objects.get(user=request.user)
    presence_cameras = models.Camera_Settings.objects.filter(
        Q(role_camera='P_IN') | Q(role_camera='P_OUT'),
        company=company
    ) # Get presence cameras
    default_camera = presence_cameras.first() if presence_cameras.exists() else None  # Set a default camera if available
    
    print("presence camera:",presence_cameras)
    print("default camera:", default_camera)
    return render(request, 'admin/presence_cam_stream.html', {
        'company': company,
        'presence_cameras': presence_cameras,
        'default_camera': default_camera
    })
    
@login_required(login_url='login')
@role_required('admin')
def tracking_cam_stream(request):
    company = models.Company.objects.get(user=request.user)
    tracking_cameras = models.Camera_Settings.objects.filter(company=company, role_camera='T')  # Get presence cameras
    default_camera = tracking_cameras.first() if tracking_cameras.exists() else None  # Set a default camera if available
    
    print("tracking camera:",tracking_cameras)
    print("default camera:", default_camera)
    return render(request, 'admin/tracking_cam_stream.html', {        'company': company,
        'tracking_cameras': tracking_cameras,
        'default_camera': default_camera})

# Global variables
camera_feeds = {}
streaming_status = {}

def start_tracking_stream(request, cam_id):
    # Initialize the session variable if it doesn't exist
    if 'cams' not in request.session:
        request.session['cams'] = []
    if 'streaming_status' not in request.session:
        request.session['streaming_status'] = {}

    # Check if the camera is already active
    if cam_id in request.session['cams']:
        return JsonResponse({'status': 'error', 'message': 'Camera is already active'})

    # Check if the camera is already streaming
    if request.session['streaming_status'].get(cam_id, False):
        return JsonResponse({'status': 'error', 'message': 'Streaming is already in progress'})

    cam = get_object_or_404(models.Camera_Settings, id=cam_id)
    camera_feed = cv2.VideoCapture(cam.feed_src)  # Assuming feed_src is a valid URL or path

    if camera_feed.isOpened():
        print(f"Start RTSP stream from: {cam.feed_src}")
        request.session['cams'].append(cam_id)  # Add cam_id to the session list
        request.session.modified = True  # Mark the session as modified
        request.session['streaming_status'][cam_id] = True  # Mark this camera as streaming
        cam.cam_is_active = True
        cam.save()
        MC.add_camera(cam.id, cam.feed_src)

        MC.stop_cam(cam.id)

        # Start stream
        MC.start_cam(cam.id)

        # Start the stream in a separate thread
        threading.Thread(target=predict_video, args=(cam_id,)).start() 
        
        return redirect('tracking_stream')
    else:
        print("Failed to open camera stream")
        return redirect('tracking_stream')

    
def stop_tracking_stream(request, cam_id):
    global camera_feed, streaming

    streaming = False
    camera_feed = None
    
    request.session['cams'].remove(cam_id)
    request.session.modified = True  
    
    cam = get_object_or_404(models.Camera_Settings, id=cam_id)
    cam.cam_is_active = False
    cam.save()
    
    MC.stop_cam(cam.id)
    
    print(f"Cam with id: {cam_id} stopped successfully")
    
    return redirect('tracking_stream')

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
            return redirect('stream')

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)