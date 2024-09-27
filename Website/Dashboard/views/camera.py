import os
import cv2
import numpy as np

# Backend Library
from .var import var
from django.shortcuts import render, redirect, HttpResponse
from django.contrib.auth.decorators import login_required
from django.http.response import StreamingHttpResponse, JsonResponse
from .. import forms, models

# Artificial Intelligence Library
from ..Artificial_Intelligence.variables import RecognitionVariable as RV
from ..Artificial_Intelligence.multi_camera import MultiCamera as MC

# ================================================== CAMERA DASHBOARD ================================================== #


@login_required(login_url='login')
def camera(request):
    frame_shape = (0.1, 0.1)
    data = models.Camera_Settings.objects.all()

    if len(data) == 0:
        active_cam = None
    else:
        for cam in data:
            status = MC.get_camera_status(cam.id) 

            cam.cam_is_active = status
            cam.save()

        try:
            active_cam = models.Camera_Settings.objects.get(id=request.session['cam_id'])
        except:
            active_cam = models.Camera_Settings.objects.first()
            request.session['cam_id'] = active_cam.id

        while active_cam.cam_is_active:
            try:
                frame, _ = MC.get_frame(request.session['cam_id'])
                frame_shape = (frame.shape[0], frame.shape[1])
                break
            except:
                pass
    
        if status:
            cam = active_cam
            poly = np.array([[cam.x1, cam.y1], [cam.x2, cam.y2], [cam.x3, cam.y3], [cam.x4, cam.y4], 
                             [cam.x8, cam.y8], [cam.x7, cam.y7], [cam.x6, cam.y6], [cam.x5, cam.y5]])
            poly = poly.astype(int)

            MC.set_polygon(request.session['cam_id'], poly)

    if request.method == "POST":
        if request.POST['command'] == 'open_settings':
            request.session['toggle_polygon'] = True
        elif request.POST['command'] == 'close_settings':
            request.session['toggle_polygon'] = False
        elif request.POST['command'] == 'select_camera':
            request.session['cam_id'] = int(request.POST['id'])
            request.session['toggle_polygon'] = False
        elif request.POST['command'] == 'reset_status':
            request.session['status'] = 'none'
        elif request.POST['command'] == 'get_camera':
            cam  = models.Camera_Settings.objects.get(id=request.POST['id'])
            return JsonResponse({'cam_name':cam.cam_name,
                                 'feed_src':cam.feed_src,
                                 'cam_start':cam.cam_start,
                                 'cam_stop':cam.cam_stop,
                                 'gender_detection':cam.gender_detection,
                                 'face_detection':cam.face_detection})

        return HttpResponse("Success")
    else:

        try: 
            request.session['toggle_polygon']
        except:
            request.session['toggle_polygon'] = False

        return render(request, 'camera.html', {'Cams':data,
                                               'Active_Cam':active_cam, 
                                               'Frame_X':frame_shape[1], 
                                               'Frame_Y':frame_shape[0], 
                                               'Toggle_Settings':request.session['toggle_polygon'],
                                               'Page':"Camera"})

@login_required
def start_stream(request):
    cam = models.Camera_Settings.objects.get(id=request.session['cam_id'])
    cam.cam_is_active = True
    cam.save()

    poly = np.array([[cam.x1, cam.y1], [cam.x2, cam.y2], [cam.x3, cam.y3], [cam.x4, cam.y4], 
                     [cam.x8, cam.y8], [cam.x7, cam.y7], [cam.x6, cam.y6], [cam.x5, cam.y5]])
    poly = poly.astype(int)

    try:
        cap = cv2.VideoCapture(int(cam.feed_src))
    except:
        cap = cv2.VideoCapture(cam.feed_src)

    # Check if feed source is valid
    if cap.isOpened():
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

        # Add camera
        MC.add_camera(cam.id, cam.feed_src)
        
        # Set polygon coordinates
        MC.set_polygon(cam.id, poly)

        # Set activated model
        MC.set_model(cam.id, cam.face_detection, cam.gender_detection)

        # Set AI time range
        MC.set_time_range(cam.id, cam.cam_start, cam.cam_stop)

        # Stop stream if camera is already running
        MC.stop_cam(cam.id)

        # Start stream
        MC.start_cam(cam.id)
        
        request.session['status'] = 'stream_success'
    else:
        request.session['status'] = 'stream_error'

    return redirect('camera')

@login_required
def change_camera(request):
    request.session['cam_id'] = int(request.POST['cam_number'])

    return redirect('camera')

@login_required
def stop_stream(request):
    cam = models.Camera_Settings.objects.get(id=request.session['cam_id'])
    cam.cam_is_active = False
    cam.save()

    MC.stop_cam(cam.id)

    return redirect('camera')

@login_required
def delete_camera(request, id):
    models.Camera_Settings.objects.get(id=id).delete()
    try:
        models.Counted_Instances.objects.filter(camera=id).delete()
    except:
        pass

    MC.stop_cam(id)

    MC.delete_cam(id)

    first_cam = models.Camera_Settings.objects.first()

    if str(id) == str(request.session['cam_id']):
        if first_cam != None:
            request.session['cam_id'] = int(first_cam.id)

    if str(id) == str(request.session['home_cam_num']):
        if first_cam != None:
            request.session['home_cam_num'] = int(first_cam.id)

    request.session['status'] = 'camera_deleted'

    return redirect('camera')

@login_required
def add_camera(request):
    if request.method == 'POST':
        form = forms.AddCameraForm(request.POST)
        if form.is_valid():
            form.save()
            cam = models.Camera_Settings.objects.last()

            MC.add_camera(cam.id, cam.feed_src)

            MC.set_time_range(cam.id, cam.cam_start, cam.cam_stop)

            request.session['status'] = 'adding_success'

            return redirect('camera')
        else:
            request.session['status'] = 'adding_error'
            
    return render(request,'add_camera.html', {'Active_Cam':None})

@login_required
def edit_camera(request, id):
    form = forms.AddCameraForm()
    active_cam = models.Camera_Settings.objects.get(id=id)

    if request.method == 'POST':
        form = forms.AddCameraForm(request.POST)
        if form.is_valid():
            if active_cam.feed_src != form.cleaned_data['feed_src']:
                MC.stop_cam(active_cam.id)
                MC.add_camera(active_cam.id, form.cleaned_data['feed_src'])
                active_cam.cam_is_active = False

            active_cam.feed_src = form.cleaned_data['feed_src']
            active_cam.cam_name = form.cleaned_data['cam_name']
            active_cam.gender_detection = form.cleaned_data['gender_detection']
            active_cam.face_detection = form.cleaned_data['face_detection']
            active_cam.cam_start = form.cleaned_data['cam_start']
            active_cam.cam_stop = form.cleaned_data['cam_stop']
            active_cam.save()

            try:
                MC.set_model(active_cam.id, bool(active_cam.face_detection), bool(active_cam.gender_detection))
                MC.set_time_range(active_cam.id, active_cam.cam_start, active_cam.cam_stop)
            except:
                pass

            request.session['status'] = 'edit_success'
            return redirect('camera')
        else:
            print(form.errors)
            request.session['status'] = 'edit_error'
            
    return render(request,'add_camera.html', {'Active_Cam':active_cam})

def gen(request):
    request.session['stream_running'] = True

    while request.session['stream_running']:
        try:
            frame, pred_frame = MC.get_frame(request.session['cam_id'])
        except:
            continue

        buffer = cv2.imencode('.jpg',pred_frame)[1]
        pred_frame = buffer.tobytes()

        yield(b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + pred_frame + b'\r\n\r\n')

@login_required(login_url='login')
def video_feed(request):
    return StreamingHttpResponse(gen(request), content_type='multipart/x-mixed-replace; boundary=frame')

@login_required
def save_coordinates(request):
    cam = models.Camera_Settings.objects.get(id=request.session['cam_id'])
    cam.x1=request.POST['x1']
    cam.y1=request.POST['y1']
    cam.x2=request.POST['x2']
    cam.y2=request.POST['y2']
    cam.x3=request.POST['x3']
    cam.y3=request.POST['y3']
    cam.x4=request.POST['x4']
    cam.y4=request.POST['y4']
    cam.x5=request.POST['x5']
    cam.y5=request.POST['y5']
    cam.x6=request.POST['x6']
    cam.y6=request.POST['y6']
    cam.x7=request.POST['x7']
    cam.y7=request.POST['y7']
    cam.x8=request.POST['x8']
    cam.y8=request.POST['y8']
    cam.save()

    poly = np.array([[cam.x1, cam.y1], [cam.x2, cam.y2], [cam.x3, cam.y3], [cam.x4, cam.y4], 
                     [cam.x8, cam.y8], [cam.x7, cam.y7], [cam.x6, cam.y6], [cam.x5, cam.y5]])
        
    poly = poly.astype(int)

    MC.set_polygon(cam.id, poly)

    return HttpResponse("Success")

