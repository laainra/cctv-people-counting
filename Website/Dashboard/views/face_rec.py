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

        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # DirectShow (Windows)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0, cv2.CAP_MSMF)  # Media Foundation (Windows)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0, cv2.CAP_V4L2)  # Video4Linux (Linux)
    
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
        camera_url = 0  
    else:
        camera_url = cam.feed_src
        
        
    camera_name = cam.cam_name


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
        print(f"Start to open camera: {camera_name} {camera_url}")
        cap = cv2.VideoCapture(camera_url)
            
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
                            if not camera_url == 0:
                                save_or_update_database(name, detection_times[name], camera_url)
                            last_save_time = current_time  # Update the last save time
                            print(f"Saving detection time for {name}: {detection_times[name]} seconds") 
                else:
                    is_face_detected = False
                    

                
                # Draw a rectangle around the face
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
                if request.path == '/presence_stream/':
                    # Display only name and confidence
                    cv2.putText(frame, f'Name: {name} ({confidence:.2f})', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                elif request.path == '/tracking_stream/':
                    # Assuming timer_text is defined and updated elsewhere in your code
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
        cap = cv2.VideoCapture(0)  # Open the default camera
        while True:
            success, frame = cap.read()  # Read a frame from the camera
            if not success:
                break
            else:
                # Encode the frame in JPEG format
                ret, buffer = cv2.imencode('.jpg', frame)
                frame = buffer.tobytes()  # Convert to bytes
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    return StreamingHttpResponse(generate_frames(), content_type='multipart/x-mixed-replace; boundary=frame')

def predict_video(request, cam_id=None):
    """View for streaming video with object detection."""
    
    if cam_id == 0:
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