from django.db import connection
import cv2
import os
import json
import numpy as np
from django.shortcuts import render
from django.http import JsonResponse, StreamingHttpResponse
from .. import models
from .var import var
from django.conf import settings  # Import settings to access static files
from datetime import datetime, timedelta
from django.utils import timezone 
# from .presence import process_attendance_entry
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.shortcuts import redirect

from .. camera import camera_instance

# Initialize Haar Cascade for face detection
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
dataset_folder = var.personnel_path
model_path = 'model_lbph.xml'
static_folder = os.path.join(settings.BASE_DIR, 'Dashboard', 'static')  # Path to the static folder
label_to_name_path = os.path.join(static_folder, 'label_to_name.json')  # Path to the JSON file

# Global variables to track detection time
detection_times = {}
last_detection_time = {}
is_face_detected = False
last_save_time = datetime.now()

if not os.path.exists(dataset_folder):
    os.makedirs(dataset_folder)

if not os.path.exists(static_folder):
    os.makedirs(static_folder)


def load_label_to_name(file_path=label_to_name_path):
    """Load label-to-name mapping from a JSON file. Create the file if it does not exist."""
    if not os.path.exists(file_path):
        with open(file_path, 'w') as f:
            json.dump({}, f)  # Write an empty dictionary to the file
        return {}

    with open(file_path, 'r') as f:
        return json.load(f)

def save_label_to_name(label_to_name, file_path=label_to_name_path):
    """Save label-to-name mapping to a JSON file."""
    with open(file_path, 'w') as f:
        json.dump(label_to_name, f)

def capture_page(request):

    user = models.Personnels.objects.filter(user_id=request.user).first()
    name = user.name
    return render(request, 'employee/capture.html', {'name': name})

def capture_faces(request):
    user = models.Personnels.objects.filter(user_id=request.user).first()
    
    if user:
        face_id = user.id
        face_name = user.name
        face_folder = os.path.join(var.personnel_path, face_name)
        if not os.path.exists(face_folder):
            os.makedirs(face_folder)

        if not face_id:
            return JsonResponse({'status': 'error', 'message': 'Face ID is required.'})

        cap = cv2.VideoCapture(1, cv2.CAP_DSHOW) # DirectShow (Windows)
        if not cap.isOpened():
            cap = cv2.VideoCapture(1, cv2.CAP_MSMF)  # Media Foundation (Windows)
        if not cap.isOpened():
            cap = cv2.VideoCapture(1, cv2.CAP_V4L2)  # Video4Linux (Linux)
    
        if not cap.isOpened():
            return JsonResponse({'status': 'error', 'message': 'Failed to open camera.'})

        count = len(os.listdir(face_folder))  # Count existing images in the folder
        captured_faces = 0  # Count of faces captured in this session

        while captured_faces < 50:  # Capture up to 50 new faces
            ret, frame = cap.read()
            if not ret:
                break  # Stop if frame reading fails

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces_detected = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

            for (x, y, w, h) in faces_detected:
                face = gray[y:y + h, x:x + w]
                count += 1
                file_name = os.path.join(face_folder, f"face_{face_id}_{face_name}_{count}.jpg")
                cv2.imwrite(file_name, face)
                captured_faces += 1  # Count the saved faces
                

                if captured_faces >= 50:  # Break if we have captured 50 faces
                    break

        cap.release()
        cv2.destroyAllWindows()

        return JsonResponse({'status': 'success', 'message': 'Face capture completed.'})

    return JsonResponse({'status': 'error', 'message': 'User  not found.'})

def train_model(request):
    faces = []
    labels = []
    target_size = (200, 200)
    label_to_name = {}
    user = models.Personnels.objects.filter(user_id=request.user).first()
    
    if user:
        face_id = user.id
        face_name = user.name
        face_folder = os.path.join(var.personnel_path)  # Ensure this path is correct

        # Check if the face folder exists
        if not os.path.exists(face_folder):
            return JsonResponse({'status': 'error', 'message': 'Face folder does not exist.'})

        for name_folder in os.listdir(face_folder):
            name_folder_path = os.path.join(face_folder, name_folder)  # Construct full path
            # Check if the name_folder_path is a directory
            if os.path.isdir(name_folder_path):
                for file_name in os.listdir(name_folder_path):
                    if file_name.endswith('.jpg'):
                        img_path = os.path.join(name_folder_path, file_name)  # Use the full path
                        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                        img = cv2.resize(img, target_size)
                        label = int(file_name.split('_')[1])  # Extract ID from filename
                        faces.append(img)
                        labels.append(np.int32(label))
                        extracted_name = file_name.split('_')[2]  # Extract name from filename
                        label_to_name[label] = extracted_name  # Map label to name

    if len(faces) > 0:
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.train(np.array(faces), np.array(labels))
        recognizer.save(model_path)

        return JsonResponse({'status': 'success', 'message': 'Model successfully trained and saved.'})
    else:
        return JsonResponse({'status': 'error', 'message': 'No face data to train.'})
  
def recognize_face(request, cam=None):
    print("Starting face recognition thread...")
    global is_face_detected
    global detection_times
    global last_detection_time
    global last_save_time
    
    if cam is None or cam.feed_src == 0:
        camera_url = 1 
    else:
        camera_url = cam.feed_src
        
        
    # camera_name = cam.cam_name


    # Initialize the recognizer and load the model
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    if not os.path.exists(model_path):
        return JsonResponse({'status': 'error', 'message': 'Model not available, please train the model first.'})
    recognizer.read(model_path)

    label_to_name = {}
    personnel_folder = var.personnel_path
    for face_folder in os.listdir(personnel_folder):
        face_folder_path = os.path.join(personnel_folder, face_folder)
        if os.path.isdir(face_folder_path):
            for file_name in os.listdir(face_folder_path):
                if file_name.endswith('.jpg'):
                    label = int(file_name.split('_')[1])
                    extracted_name = file_name.split('_')[2]
                    label_to_name[label] = extracted_name

    while True:
        print(f"Start to open camera: {camera_url}")
        cap = cv2.VideoCapture(camera_url)
            
        # if not cap.isOpened():
        #     cap = cv2.VideoCapture(camera_url, cv2.CAP_DSHOW) # DirectShow (Windows)
        # if not cap.isOpened():
        #     cap = cv2.VideoCapture(camera_url, cv2.CAP_MSMF)  # Media Foundation (Windows)
        # if not cap.isOpened():
        #     cap = cv2.VideoCapture(camera_url, cv2.CAP_V4L2)  # Video4Linux (Linux)
        if not cap.isOpened():
            print(f"Failed to open camera: {camera_url}")
            continue  # Try the next camera URL
        
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Failed to read frame from camera.")
                break  # Exit the inner loop if frame reading fails
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces_detected = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

            for (x, y, w, h) in faces_detected:
                face = cv2.resize(gray[y:y+h, x:x+w], (200, 200))
                label, confidence = recognizer.predict(face)

                name = label_to_name.get(label, "Unknown")
                
                if confidence >= 0.70:
                # Update detection time
                    if not camera_url == 0 or not camera_url == 1:
                        current_time = datetime.now()
                        if name != "Unknown":
                            if name in last_detection_time:
                                elapsed_time = (current_time - last_detection_time[name]).total_seconds()
                                detection_times[name] += elapsed_time
                            else:
                                detection_times[name] = 0

                            last_detection_time[name] = current_time
                            is_face_detected = True
                            
                            total_time_recognized = int(detection_times.get(name, 0))
                            timer_text = f'Timer: {total_time_recognized}s'
                            
                            print(f'Name: {name}  ({confidence:.2f}), {timer_text}')

                            # Check if a minute has passed to save to the database
                            if (current_time - last_save_time) >= timedelta(minutes=1):
                                if not camera_url == 0 or not camera_url == 1:
                                    save_or_update_database(name, detection_times[name], camera_url)
                                last_save_time = current_time  # Update the last save time
                                print(f"Saving detection time for {name}: {detection_times[name]} seconds") 
                else:
                    is_face_detected = False
                    
                
                # Draw a rectangle around the face
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
                # if request.path == '/presence_stream/':
                #     # Display only name and confidence
                #     cv2.putText(frame, f'Name: {name} ({confidence:.2f})', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                # elif request.path == '/tracking_stream/':
                #     # Assuming timer_text is defined and updated elsewhere in your code
                cv2.putText(frame, f'Name: {name} ({confidence:.2f}), Timer: {timer_text}', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Yield the frame for streaming
            ret, jpeg = cv2.imencode('.jpg', frame)
            if not ret:
                break

            yield (b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')

        cap.release()  # Release the camera after processing
            
def save_or_update_database(name, total_time, camera_url):
    """Save or update the detection time in the Work_Timer table."""
    print(f"Start Saving detection time for {name}: {total_time} seconds") 
    personnel = models.Personnels.objects.get(name=name)  # Get the personnel object
    camera = models.Camera_Settings.objects.filter(feed_src=camera_url, role_camera="T").first()
    
    # Use timezone.now() to get the current time as an aware datetime
    current_time = timezone.now()
    
    models.Work_Timer.objects.create(
        personnel=personnel,
        camera_id=camera.id,  # Replace with the actual camera ID
        type='FACE_DETECTED',
        datetime=current_time,  # Use the aware datetime
        timer=int(total_time)
    )


        
def capture_video(request):
    """View for streaming video with capture new dataset."""
    def generate_frames():
            while True:
                frame = camera_instance.get_frame()
                if frame is None:
                    continue

                # Optional: tambahkan facebox di sini (tanpa simpan)
                _, jpeg = cv2.imencode('.jpg', frame)
                yield (b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')

    return StreamingHttpResponse(generate_frames(), content_type='multipart/x-mixed-replace; boundary=frame')

def predict_video(request, cam_id=None):
    """View for streaming video with object detection."""
    
    if cam_id == 0 or cam_id == 1:
        # Handle the case for webcam
        return StreamingHttpResponse(recognize_face(request, cam=None), content_type='multipart/x-mixed-replace; boundary=frame')
    
    try:
        cam = models.Camera_Settings.objects.get(id=cam_id, cam_is_active=True)
        return StreamingHttpResponse(recognize_face(request, cam), content_type='multipart/x-mixed-replace; boundary=frame')
    except models.Camera_Settings.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Camera not found.'}, status=404)

def dataset(request, personnel_id=None):
    images = []
 
def dataset(request, personnel_id=None):
    images = []
    detection_times = []  # Ensure it's initialized

    # Determine personnel: If no ID, get by logged-in user
    if personnel_id is None:
        personnel = models.Personnels.objects.filter(user_id=request.user.id).first()
    else:
        personnel = models.Personnels.objects.filter(id=personnel_id).first()

    if not personnel:
        return render(request, 'employee/dataset.html', {
            'images': [],
            'name': "Unknown",
            'detection_times': [],
            'error': "No personnel found"
        })

    # Define face folder
    face_name = personnel.name
    face_folder = os.path.join(var.personnel_path, face_name)

    # Ensure the folder exists before listing files
    if os.path.exists(face_folder):
        for file_name in os.listdir(face_folder):
            if file_name.endswith('.jpg'):
                images.append({'url': f'img/personnel_pics/{face_name}/{file_name}'})

    return render(request, 'employee/dataset.html', {
        'images': images,
        'name': face_name,
        'detection_times': detection_times
    })
    
    
@csrf_exempt
def delete_images(request):
    if request.method == 'POST':
        images = request.POST.getlist('images_to_delete')
        
        for img_path in images:
            # img_path format: 'img/personnel_pics/Name/image.jpg'
            relative_path = img_path.replace('img/personnel_pics/', '')  # e.g. Name/image.jpg
            personnel_name, filename = relative_path.split('/', 1)

            # Bangun path absolut pakai var.personnel_path
            full_path = os.path.join(var.personnel_path, personnel_name, filename)

            if os.path.exists(full_path):
                os.remove(full_path)

        messages.success(request, "Selected images have been deleted.")
        
    return redirect(request.META.get('HTTP_REFERER', 'dataset'))


def presence_video_stream(request):
    def generate_frames():
        while True:
            frame = camera_instance.get_frame()
            if frame is None:
                continue

            # Optional: tambahkan facebox di sini (tanpa simpan)
            _, jpeg = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')

    return StreamingHttpResponse(generate_frames(), content_type='multipart/x-mixed-replace; boundary=frame')

@csrf_exempt
def capture_absence_from_webcam(request):
    """Process presence detection from the webcam feed."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method. Use POST.'})

    global detected_labels  # Use the global variable to track detected labels

    print("Starting presence detection...")

    # Get the active camera with role "P_IN"
    cam = models.Camera_Settings.objects.filter(role_camera='P', cam_is_active=True).first()
    if not cam:
        print("No active camera found.")
        return JsonResponse({'status': 'error', 'message': 'No camera with role P_IN or P_OUT found.'})

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    if not os.path.exists(model_path):
        print("Model path does not exist.")
        return JsonResponse({'status': 'error', 'message': 'Model not available, please train the model first.'})
    recognizer.read(model_path)

    label_to_name = {}
    personnel_folder = var.personnel_path

    # Load labels and names from personnel folder
    for face_folder in os.listdir(personnel_folder):
        face_folder_path = os.path.join(personnel_folder, face_folder)
        if os.path.isdir(face_folder_path):
            for file_name in os.listdir(face_folder_path):
                if file_name.endswith('.jpg'):
                    label = int(file_name.split('_')[1])
                    extracted_name = file_name.split('_')[2]
                    label_to_name[label] = extracted_name

    # cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)

    # if not cap.isOpened():
    #     print("Error: Camera could not be opened.")
    #     return JsonResponse({'status': 'error', 'message': 'Camera could not be opened.'})

    frame_count = 0  # To limit the number of frames processed
    max_frames = 100  # Set a maximum number of frames to process
    faces_detected = False  # Flag to track if any faces were detected

    while frame_count < max_frames:
        frame = camera_instance.get_frame()
        if frame is None:
            return JsonResponse({'status': 'error', 'message': 'No frame available from camera.'})


        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5)

        if len(faces) == 0:
            print("No faces detected in this frame.")
            frame_count += 1
            continue  # Skip to the next frame

        faces_detected = True  # Set the flag to True since we detected faces

        for (x, y, w, h) in faces:
            roi = gray[y:y + h, x:x + w]
            roi_resized = cv2.resize(roi, (200, 200))
            label, confidence = recognizer.predict(roi_resized)

            name = label_to_name.get(label, "Unknown")
            print(f"Detected face: {name} with confidence: {confidence}")

            now = datetime.now()
            # Define the directory for saving images
            save_directory = os.path.join(settings.BASE_DIR, 'Dashboard/static/img/extracted_faces/predicted_faces/absence', now.strftime('%Y%m%d'))
            
            # Check if the directory exists, if not, create it
            if not os.path.exists(save_directory):
                os.makedirs(save_directory)
                print(f"Created directory: {save_directory}")

            image_path = os.path.join(save_directory, f"{name}_{now.strftime('%H%M%S')}.jpg")
            
            success = cv2.imwrite(image_path, frame[y:y + h, x:x + w])
            if success:
                print(f"Image saved at: {image_path}")
            else:
                print(f"Failed to save image at: {image_path}")
                continue 

            relative_path = os.path.relpath(image_path, settings.BASE_DIR).replace("\\", "/")

            data = {
                'name': name,
                'datetime': now.strftime('%Y-%m-%d %H:%M:%S'),
                'image_path': relative_path,
                'camera_id': cam.id
            }

            # Directly insert attendance entry without checking for existing records
            # insert_presence(cam.id, data['name'], now, 'ONTIME', relative_path)
            result = process_attendance_entry(data)
            

            if result == 'success':
                print(f"Presence recorded for {name}.")
                return JsonResponse({'status': 'success', 'message': f'Presence recorded for {name}.'})
            elif result == 'already_present':
                print(f"{name} has already been marked present.")
                return JsonResponse({'status': 'info', 'message': f'{name}: Already Presence'})
            elif result == 'not_eligible_for_leave':
                return JsonResponse({'status': 'info', 'message': 'Cannot record LEAVE before ONTIME or LATE'})
            elif result == 'personnel_not_found':
                return JsonResponse({'status': 'error', 'message': 'Personnel not found'})
            elif result == 'invalid_camera':
                return JsonResponse({'status': 'error', 'message': 'Invalid or inactive camera'})

        frame_count += 1  # Increment the frame count

    # cap.release()

    # if not faces_detected:
    #     return JsonResponse({'status': 'info', 'message': 'No new presence detected after processing frames.'})

    return JsonResponse({'message': 'Processing completed without detecting new presence.'})

# Insert presence data into the database
def insert_presence(cam_id, personnel_id, detected_time, status, image_path):
    if not cam_id or not personnel_id or not detected_time or not status:
        return
    with connection.cursor() as cursor:
        cursor.execute('''
            INSERT INTO dashboard_personnel_entries (camera_id, personnel_id, timestamp, presence_status, image)
            VALUES (%s, %s, %s, %s, %s)
        ''', [cam_id, personnel_id, detected_time, status, image_path])
def process_attendance_entry(data):
    name = data.get('name')
    datetime_str = data.get('datetime')
    image_path = data.get('image_path')
    cam_id = data.get('camera_id')
    detected_time = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')

    try:
        personnel = models.Personnels.objects.get(name=name)
        personnel_id = personnel.id
    except models.Personnels.DoesNotExist:
        print(f"Personnel '{name}' not found.")
        return

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                attendance_time_start, 
                attendance_time_end, 
                leaving_time_start, 
                leaving_time_end,
                (SELECT COUNT(*) FROM dashboard_personnel_entries WHERE personnel_id = %s AND DATE(timestamp) = %s AND presence_status = 'ONTIME') AS has_ontime,
                (SELECT COUNT(*) FROM dashboard_personnel_entries WHERE personnel_id = %s AND DATE(timestamp) = %s AND presence_status = 'LATE') AS has_late,
                (SELECT COUNT(*) FROM dashboard_personnel_entries WHERE personnel_id = %s AND DATE(timestamp) = %s AND presence_status = 'LEAVE') AS has_leave
            FROM dashboard_camera_settings 
            WHERE id = %s AND role_camera IN ('P')
        """, [personnel_id, detected_time.date(), personnel_id, detected_time.date(), personnel_id, detected_time.date(), cam_id])
        
        result = cursor.fetchone()

    if not result:
        print("Camera settings not found or not a valid P camera.")
        return

    attendance_start = datetime.strptime(result[0], '%H:%M:%S').time() if result[0] else None
    attendance_end = datetime.strptime(result[1], '%H:%M:%S').time() if result[1] else None
    leaving_start = datetime.strptime(result[2], '%H:%M:%S').time() if result[2] else None
    leaving_end = datetime.strptime(result[3], '%H:%M:%S').time() if result[3] else None

    has_ontime = result[4]
    has_late = result[5]
    has_leave = result[6]
    current_time = detected_time.time()

    # Determine status
    status = None
    if attendance_start and attendance_end and attendance_start <= current_time <= attendance_end:
        status = 'ONTIME'
    elif leaving_start and leaving_end and leaving_start <= current_time <= leaving_end:
        status = 'LEAVE'
    else:
        if attendance_end and leaving_start and attendance_end < current_time < leaving_start:
            status = 'LATE'
        else:
            status = 'LEAVE'

    # Prevent duplicate entries
    if status == 'ONTIME' and has_ontime:
        print("ONTIME already recorded.")
        return 'already_present'
    if status == 'LATE':
        if has_ontime or has_late:
            print("Either ONTIME or LATE already recorded.")
            return 'already_present'
    if status == 'LEAVE':
        if has_leave:
            print("LEAVE already recorded.")
            return 'already_present'
        if not (has_ontime or has_late):
            print("Cannot record LEAVE without ONTIME or LATE.")
            return 'not_eligible_for_leave'

    if status == 'LATE' and has_ontime:
        status = 'LEAVE'
        if has_leave:
            print("LEAVE already recorded.")
            return 'already_present'

    # Save into DB
    insert_presence(cam_id, personnel_id, detected_time, status, image_path)
    print(f"Inserted {status} entry for {name} at {detected_time}")
    return True


def predict_presence_video(request, cam_id=None):
    """Streaming video feed to the client."""
    return StreamingHttpResponse(presence_video_stream(request), content_type='multipart/x-mixed-replace; boundary=frame')