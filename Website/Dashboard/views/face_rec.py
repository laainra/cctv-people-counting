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

# Global variables to track detection time
detection_times = {}
last_detection_time = {}
is_face_detected = False

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

        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # Initialize camera
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
        face_folder = os.path.join(var.personnel_path, face_name)

    for file_name in os.listdir(face_folder):
        if file_name.endswith('.jpg'):
            img_path = os.path.join(face_folder, file_name)
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

def recognize_face(request):
    global is_face_detected
    global detection_times
    global last_detection_time
    global last_save_time

    cap = cv2.VideoCapture(0)  
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

    def save_or_update_database(name, total_time):
        """Save or update the detection time in the Work_Timer table."""
        personnel = models.Personnels.objects.get(name=name)  # Get the personnel object
        
        # Check if a record already exists for this personnel
        try:
            work_timer_entry = models.Work_Timer.objects.get(personnel=personnel, type='FACE_DETECTED', datetime__date=datetime.now().date())
            # Update the existing record
            work_timer_entry.timer += int(total_time)  # Add the new time to the existing time
            work_timer_entry.save()
        except models.Work_Timer.DoesNotExist:
            # Create a new record if it doesn't exist
            models.Work_Timer.objects.create(
                personnel=personnel,
                camera_id=1,  # Replace with the actual camera ID
                type='FACE_DETECTED',
                datetime=datetime.now(),
                timer=int(total_time)
            )

    def generate_frames():
        global is_face_detected
        global detection_times
        global last_detection_time
        global last_save_time

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces_detected = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

            for (x, y, w, h) in faces_detected:
                face = cv2.resize(gray[y:y+h, x:x+w], (200, 200))
                label, confidence = recognizer.predict(face)

                name = label_to_name.get(label, "Unknown")
                
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

                    # Check if a minute has passed to save to the database
                    if (current_time - last_save_time) >= timedelta(minutes=1):
                        save_or_update_database(name, detection_times[name])
                        last_save_time = current_time  # Update the last save time
                else:
                    is_face_detect = False

                # Calculate the total time recognized
                total_time_recognized = int(detection_times.get(name, 0))
                timer_text = f'Timer: {total_time_recognized}s'

                # Draw a rectangle around the face
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
                cv2.putText(frame, f'Name: {name}  ({confidence:.2f}), {timer_text}', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            ret, jpeg = cv2.imencode('.jpg', frame)
            if not ret:
                break

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')

        cap.release()

    return StreamingHttpResponse(generate_frames(), content_type='multipart/x-mixed-replace; boundary=frame')

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

def predict_video(request):
    """View for streaming video with object detection."""
    return recognize_face(request)

def dataset(request):
    images = []
    user = models.Personnels.objects.filter(user_id=request.user).first()
    
    if user:
        face_id = user.id
        face_name = user.name
        face_folder = os.path.join(var.personnel_path, face_name)
    if os.path.exists(dataset_folder):
        for file_name in os.listdir(face_folder):
            if file_name.endswith('.jpg'):
                images.append({
                    'url': f'img/personnel_pics/{face_name}/{file_name}',  
                })
    return render(request, 'employee/dataset.html', {'images': images, 'name': face_name, 'detection_times': detection_times})  