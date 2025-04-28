from django.shortcuts import render, get_object_or_404
import os
import cv2
import numpy as np
from django.urls import reverse

# Backend Library
from .var import var
from django.shortcuts import render, redirect, HttpResponse
from django.contrib.auth.decorators import login_required
from django.http.response import StreamingHttpResponse, JsonResponse
from .. import forms, models
from ..decorators import role_required
from datetime import datetime

# Artificial Intelligence Library
from ..Artificial_Intelligence.variables import RecognitionVariable as RV
from ..Artificial_Intelligence.multi_camera import MultiCamera as MC
# from ..Artificial_Intelligence.work_timer import Work_Timer as WT

# ================================================== CAMERA DASHBOARD ================================================== #


@login_required(login_url='login')
@role_required("admin")
def camera(request):
    company_id = models.Company.objects.get(user=request.user)
    frame_shape = (0.1, 0.1)
    data = models.Camera_Settings.objects.filter(company=company_id)

    if len(data) == 0:
        active_cam = None
    else:
        for cam in data:
            status = MC.get_camera_status(cam.id)

            cam.cam_is_active = status
            cam.save()

        try:
            active_cam = models.Camera_Settings.objects.get(
                id=request.session['cam_id'])
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
            cam = models.Camera_Settings.objects.get(id=request.POST['id'])
            return JsonResponse({'cam_name': cam.cam_name,
                                 'feed_src': cam.feed_src,
                                 'cam_start': cam.cam_start,
                                 'cam_stop': cam.cam_stop,
                                 'gender_detection': cam.gender_detection,
                                 'face_detection': cam.face_detection})

        return HttpResponse("Success")
    else:

        try:
            request.session['toggle_polygon']
        except:
            request.session['toggle_polygon'] = False

        return render(request, 'camera.html', {'Cams': data,
                                               'Active_Cam': active_cam,
                                               'Frame_X': frame_shape[1],
                                               'Frame_Y': frame_shape[0],
                                               'Toggle_Settings': request.session['toggle_polygon'],
                                               'Page': "Camera"})

@login_required
def start_stream(request):
    cam = models.Camera_Settings.objects.get(id=request.session['cam_id'])
    cam.cam_is_active = True
    cam.save()
    print(f"Camera settings retrieved: {cam}")

    poly = np.array([[cam.x1, cam.y1], [cam.x2, cam.y2], [cam.x3, cam.y3], [cam.x4, cam.y4],
                     [cam.x8, cam.y8], [cam.x7, cam.y7], [cam.x6, cam.y6], [cam.x5, cam.y5]])
    poly = poly.astype(int)
    print(f"Attempting to open RTSP stream from: {cam.feed_src}")
    
    try:
        cap = cv2.VideoCapture(int(cam.feed_src)) 
        if not cap.isOpened():
            raise Exception("Failed to open RTSP stream")
    except Exception as e:
        cap = cv2.VideoCapture(0) 
        if not cap.isOpened():
            request.session['status'] = 'stream_error'
            return redirect('stream')  

        # print("RTSP feed failed, switching to webcam")


    # Check if feed source is valid
    if cap.isOpened():
        request.session['stream_running'] = False
        
        print(f"Start RTSP stream from: {cam.feed_src}")

        # Set known faces for face recognition
        # if len(RV.known_features) == 0:
        #     RV.set_all_known_faces()
        # else:
        #     for personnel_name in os.listdir(var.personnel_path):
        #         if RV.known_features.get(personnel_name) == None:
        #             RV.set_personnel_known_faces(personnel_name)
        #         else:
        #             if personnel_name == 'Unknown':
        #                 if len(RV.known_features[personnel_name]) != (len(os.listdir(os.path.join(var.personnel_path, personnel_name))) - 1):
        #                     RV.set_personnel_known_faces(personnel_name)
        #             else:
        #                 if len(RV.known_features[personnel_name]) != len(os.listdir(os.path.join(var.personnel_path, personnel_name))):
        #                     RV.set_personnel_known_faces(personnel_name)
        # ai_stream = WT(cam.feed_src, cam.id)
        # print("AI Stream initialized")
        # ai_stream.start_stream()
        # Add camera
        MC.add_camera(cam.id, cam.feed_src)

        # Set polygon coordinates
        MC.set_polygon(cam.id, poly)

        # Set activated model
        MC.set_model(cam.id, cam.face_detection, cam.gender_detection, cam.face_capture)

        # Set AI time range
        MC.set_time_range(cam.id, cam.cam_start, cam.cam_stop)

        # Stop stream if camera is already running
        MC.stop_cam(cam.id)

        # Start stream
        MC.start_cam(cam.id)

        request.session['status'] = 'stream_success'
        print(f"Session status set to 'stream_success' {cam.feed_src}")
        return JsonResponse({'status': 'success', 'camera_active': cam.cam_is_active})
    else:
        request.session['status'] = 'stream_error'
        print("Failed to open camera stream")
        return JsonResponse({'status': 'error', 'message': 'Failed to open stream'})

@login_required
def change_camera(request):
    request.session['cam_id'] = int(request.POST['cam_number'])
    return redirect('camera')

@login_required(login_url='login')
def stop_stream(request):
    try:
        cam = models.Camera_Settings.objects.get(id=request.session['cam_id'])
        cam.cam_is_active = False
        cam.save()

        MC.stop_cam(cam.id)

        return JsonResponse({'status': 'success', 'camera_active': cam.cam_is_active})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@login_required
def delete_camera(request, id):
    if request.method == 'POST':
# Delete camera settings and counted instances associated with the camera
        models.Camera_Settings.objects.get(id=id).delete()
        try:
            models.Counted_Instances.objects.filter(camera=id).delete()
        except:
            pass

        # Stop and delete the camera using MC
        # MC.stop_cam(id)
        # MC.delete_cam(id)

        # Get the first camera setting
        first_cam = models.Camera_Settings.objects.first()

        # Check and update session for 'cam_id'
        if str(id) == str(request.session.get('cam_id')):
            if first_cam != None:
                request.session['cam_id'] = int(first_cam.id)

        # Check and update session for 'home_cam_num'
        if str(id) == str(request.session.get('home_cam_num')):
            if first_cam != None:
                request.session['home_cam_num'] = int(first_cam.id)

        # Set the status session variable to indicate the camera has been deleted
        request.session['status'] = 'camera_deleted'

    # Redirect to the camera page
        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

@login_required
def add_camera(request):
    if request.method == 'POST':
        form = forms.AddCameraForm(request.POST)
        if form.is_valid():
            company_id = models.Company.objects.get(user=request.user)
            camera = form.save(commit=False)  # Jangan langsung simpan
            camera.company = company_id   # Set ID perusahaan
            camera.cam_is_active = True  
            camera.save() 

            cam = models.Camera_Settings.objects.last()

            MC.add_camera(cam.id, cam.feed_src)

            MC.set_time_range(cam.id, cam.cam_start, cam.cam_stop)

            request.session['status'] = 'adding_success'

            return redirect('camera')
        else:
            request.session['status'] = 'adding_error'

    return render(request, 'add_camera.html', {'Active_Cam': None})

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
            active_cam.face_capture = form.cleaned_data['face_capture']
            active_cam.cam_start = form.cleaned_data['cam_start']
            active_cam.cam_stop = form.cleaned_data['cam_stop']
            active_cam.attendance_time_start = form.cleaned_data['attendance_time_start']
            active_cam.attendance_time_end = form.cleaned_data['attendance_time_end']
            active_cam.leaving_time_start = form.cleaned_data['leaving_time_start']
            active_cam.leaving_time_end = form.cleaned_data['leaving_time_end']
            active_cam.cam_is_active = True
            active_cam.save()

            try:
                # edit it when MC set time range change to attendance and leaving
                MC.set_model(active_cam.id, bool(
                    active_cam.face_detection), bool(active_cam.gender_detection), bool(active_cam.face_capture))
                MC.set_time_range(
                    active_cam.id, active_cam.cam_start, active_cam.cam_stop)
            except:
                pass

            request.session['status'] = 'edit_success'
            return redirect('camera')
        else:
            print(form.errors)
            request.session['status'] = 'edit_error'

    return render(request, 'edit_camera.html', {
        'Active_Cam': active_cam,
        # 'delete_camera_url': reverse('delete_camera', args=[id])  # Add this line
    })

def generate_stream(request):
    request.session['stream_running'] = True

    cam_id = request.session.get('cam_id')
    if not cam_id:
        print("Error: 'cam_id' not found in session")
        return

    print(f"Starting stream for cam_id: {cam_id}")

    while request.session['stream_running']:
        try:
            frame, pred_frame = MC.get_frame(cam_id)
            if pred_frame is None:
                print("No predicted frame available")
                continue

            if not isinstance(pred_frame, (np.ndarray, np.generic)):
                print(f"Invalid frame type: {type(pred_frame)}")
                continue

            buffer = cv2.imencode('.jpg', pred_frame)[1]
            pred_frame = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + pred_frame + b'\r\n\r\n')
            # print("Frame sent")
        except Exception as e:
            # print(f"Error getting frame: {e}")
            continue
    
@login_required(login_url='login')
def video_feed(request):
    return StreamingHttpResponse(generate_stream(request), content_type='multipart/x-mixed-replace; boundary=frame')

@login_required
def save_coordinates(request):
    cam = models.Camera_Settings.objects.get(id=request.session['cam_id'])
    
    # Check if we are resetting the polygon
    if request.POST['x1'] == '0' and request.POST['y1'] == '0':
        # Reset polygon coordinates to zero
        cam.x1 = 0
        cam.y1 = 0
        cam.x2 = 0
        cam.y2 = 0
        cam.x3 = 0
        cam.y3 = 0
        cam.x4 = 0
        cam.y4 = 0
        cam.x5 = 0
        cam.y5 = 0
        cam.x6 = 0
        cam.y6 = 0
        cam.x7 = 0
        cam.y7 = 0
        cam.x8 = 0
        cam.y8 = 0
        
        # Clear the session data for polygon points
        request.session.pop('polygon_data', None)  # Assuming 'polygon_data' holds your polygon points
    else:
        # Update existing coordinates
        cam.x1 = request.POST['x1']
        cam.y1 = request.POST['y1']
        cam.x2 = request.POST['x2']
        cam.y2 = request.POST['y2']
        cam.x3 = request.POST['x3']
        cam.y3 = request.POST['y3']
        cam.x4 = request.POST['x4']
        cam.y4 = request.POST['y4']
        cam.x5 = request.POST['x5']
        cam.y5 = request.POST['y5']
        cam.x6 = request.POST['x6']
        cam.y6 = request.POST['y6']
        cam.x7 = request.POST['x7']
        cam.y7 = request.POST['y7']
        cam.x8 = request.POST['x8']
        cam.y8 = request.POST['y8']
    
    cam.save()

    # Create the polygon array regardless of reset or update
    poly = np.array([[cam.x1, cam.y1], [cam.x2, cam.y2], [cam.x3, cam.y3], [cam.x4, cam.y4],
                     [cam.x8, cam.y8], [cam.x7, cam.y7], [cam.x6, cam.y6], [cam.x5, cam.y5]])

    poly = poly.astype(int)

    MC.set_polygon(cam.id, poly)

    return HttpResponse("Success")


def get_current_active_cam(request):
    # Get the camera ID from the session
    cam_id = request.session.get('cam_id', None)
    
    if cam_id is not None:
        try:
            # Check if the camera is active
            camera = models.Camera_Settings.objects.get(id=cam_id)
            if camera.cam_is_active:
                return cam_id
        except models.Camera_Settings.DoesNotExist:
            # If the camera does not exist, return None
            pass

    return None


@login_required
def add_tracking_camera(request):
    if request.method == 'POST':
        form = forms.AddTrackingCameraForm(request.POST)
        if form.is_valid():
            company = models.Company.objects.get(user=request.user)
            camera = form.save(commit=False) 
            camera.company = company 
            camera.cam_is_active = True
            camera.role_camera = "T"
            camera.save() 

            cam = models.Camera_Settings.objects.last()

            MC.add_camera(cam.id, cam.feed_src)

            request.session['status'] = 'adding_success'

            return JsonResponse({'status': 'success'})
        else:
            request.session['status'] = 'adding_error'

    return render(request, 'add_tracking_camera.html', {'Active_Cam': None})


@login_required
def edit_tracking_camera(request, id):
    try:
        active_cam = models.Camera_Settings.objects.get(id=id)
    except models.Camera_Settings.DoesNotExist:
        # Handle the case where the camera does not exist
        return redirect('camera')  # or render a "not found" page
    
    # Make sure you're passing the instance of Camera_Settings model to the form
    if request.method == 'POST':
        form = forms.AddTrackingCameraForm(request.POST, instance=active_cam)
        if form.is_valid():
            # Save the form first
            form.save()

            # Check if the feed source has changed and handle accordingly
            if active_cam.feed_src != form.cleaned_data['feed_src']:
                MC.stop_cam(active_cam.id)
                MC.add_camera(active_cam.id, form.cleaned_data['feed_src'])
                active_cam.cam_is_active = False
            
            # Update fields manually from cleaned data if needed
            active_cam.feed_src = form.cleaned_data['feed_src']
            active_cam.cam_name = form.cleaned_data['cam_name']
            active_cam.uniform_detection = form.cleaned_data['uniform_detection']
            active_cam.id_card_detection = form.cleaned_data['id_card_detection']
            active_cam.shoes_detection = form.cleaned_data['shoes_detection']
            active_cam.ciggerate_detection = form.cleaned_data['ciggerate_detection']
            active_cam.save()

            request.session['status'] = 'editing_success'
            return JsonResponse({'status': 'success'})
        else:
            request.session['status'] = 'editing_error'
    else:
        # Pass the existing instance of active_cam to the form
        form = forms.AddTrackingCameraForm(instance=active_cam)

    return render(request, 'edit_tracking_camera.html', {'Active_Cam': active_cam, 'form': form})

def format_time(time_str, default_time=None):
    """Convert 'HH:MM' to 'HH:MM:SS' format."""
    if not time_str:  # Check if the input is empty
        return default_time if default_time else datetime.strptime("00:00", "%H:%M").time()  # Return default time if input is empty

    try:
        return datetime.strptime(time_str, "%H:%M").time()  # Default seconds to 00
    except ValueError:
        print(f"Invalid time format: {time_str}. Returning default time.")
        return default_time if default_time else datetime.strptime("00:00", "%H:%M").time()  # Return default time on error
@login_required
def add_presence_camera(request):
    if request.method == 'POST':
        form = forms.AddPresenceCameraForm(request.POST)
        if form.is_valid():
            company = models.Company.objects.get(user=request.user)
            camera = form.save(commit=False)  # jgn save dulu

            # Set nilai default feed_src
            if not camera.feed_src:  # kalau belum diisi, set 1
                camera.feed_src = 1

            # Isi field lainnya
            camera.company = company
            camera.cam_is_active = True
            camera.role_camera = "P"  # kalau role diatur default juga

            # Format jam
            camera.attendance_time_start = format_time(request.POST['attendance_time_start'])
            camera.attendance_time_end = format_time(request.POST['attendance_time_end'])
            camera.leaving_time_start = format_time(request.POST['leaving_time_start'])
            camera.leaving_time_end = format_time(request.POST['leaving_time_end'])

            camera.save()
            return JsonResponse({'status': 'success'})
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Form tidak valid',
                'errors': form.errors.as_json()
            }, status=400)

    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=405)


@login_required
def edit_presence_camera(request, id):
    active_cam = models.Camera_Settings.objects.get(id=id)
    
    if request.method == 'POST':
        # Get the new values from the request
        cam_name = request.POST.get('cam_name', active_cam.cam_name)
        role_camera = request.POST.get('role_camera', active_cam.role_camera)
        feed_src = request.POST.get('feed_src', active_cam.feed_src)
        
        # Pass the existing values as default to format_time
        attendance_time_start = format_time(request.POST.get('attendance_time_start'), active_cam.attendance_time_start)
        attendance_time_end = format_time(request.POST.get('attendance_time_end'), active_cam.attendance_time_end)
        leaving_time_start = format_time(request.POST.get('leaving_time_start'), active_cam.leaving_time_start)
        leaving_time_end = format_time(request.POST.get('leaving_time_end'), active_cam.leaving_time_end)

        # Update the camera settings
        active_cam.cam_name = cam_name
        active_cam.role_camera = 'P'
        active_cam.feed_src = 1
        active_cam.attendance_time_start = attendance_time_start
        active_cam.attendance_time_end = attendance_time_end
        active_cam.leaving_time_start = leaving_time_start
        active_cam.leaving_time_end = leaving_time_end
        
        # Check if feed_src has changed
        if active_cam.feed_src != feed_src:
            MC.stop_cam(active_cam.id)
            MC.add_camera(active_cam.id, feed_src)
            active_cam.cam_is_active =  True

        active_cam.save()
        request.session['status'] = 'editing_success'
        return JsonResponse({'status': 'success'})

    return render(request, 'edit_presence_camera.html', {'Active_Cam': active_cam}) 

def get_edit_camera_url(request, camera_id):
    camera = models.Camera.objects.get(id=camera_id)  # Assuming you have a Camera model
    if camera.role_camera == 'T':
        return JsonResponse({'url': f'/edit_tracking_camera/{camera.id}/'})
    elif camera.role_camera in ['P_IN', 'P_OUT']:
        return JsonResponse({'url': f'/edit_presence_camera/{camera.id}/'})
    else:
        return JsonResponse({'url': ''}, status=400)
    
@login_required
def get_camera_data(request, id):
    try:
        camera = models.Camera_Settings.objects.get(id=id)
        camera_data = {
            'id': camera.id,
            'cam_name': camera.cam_name,
            'feed_src': camera.feed_src,
            'cam_is_active': camera.cam_is_active,
            'uniform_detection': camera.uniform_detection,
            'id_card_detection': camera.id_card_detection,
            'shoe_detection': camera.shoes_detection,
            'ciggerate_detection': camera.ciggerate_detection,
            'sit_detection': camera.sit_detection,
            'attendance_time_start': camera.attendance_time_start,
            'attendance_time_end': camera.attendance_time_end,
            'leaving_time_start': camera.leaving_time_start,
            'leaving_time_end': camera.leaving_time_end,
            'role_camera': camera.role_camera,
        }
        return JsonResponse({'status': 'success', 'data': camera_data})
    except models.Camera_Settings.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Camera not found'})