import cv2
import os
import numpy as np
from django.db import connection
from datetime import datetime, timedelta
from django.utils import timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
dataset_folder = os.path.join(BASE_DIR, 'static', 'img', 'personnel_pics')
model_path = 'model_lbph.xml'
static_folder = os.path.join(BASE_DIR, 'static')
label_to_name_path = os.path.join(static_folder, 'label_to_name.json')

# Global variables
is_face_detected = False
detection_times = {}
last_detection_time = {}
last_save_time = datetime.now()

def save_or_update_database(name, total_time, camera_url):
    """Save or update the detection time in the Work_Timer table using raw SQL."""
    print(f"Start Saving detection time for {name}: {total_time} seconds") 
    current_time = timezone.now()

    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM dashboard_personnels WHERE name = %s", [name])
        personnel_id = cursor.fetchone()

        if personnel_id:
            cursor.execute("SELECT id FROM dashboard_camera_settings WHERE feed_src = %s AND cam_is_active = TRUE", [camera_url])
            camera_id = cursor.fetchone()

            if camera_id:
                cursor.execute("""
                    INSERT INTO dashboard_work_timer (personnel, camera, type, datetime, timer)
                    VALUES (%s, %s, %s, %s, %s)
                """, [personnel_id[0], camera_id[0], 'FACE_DETECTED', current_time, int(total_time)])
            else:
                print(f"No active camera found for URL: {camera_url}")
        else:
            print(f"No personnel found with name: {name}")

def recognize_face():
    print("Starting face recognition thread...")
    global is_face_detected
    global detection_times
    global last_detection_time
    global last_save_time
    
    # Fetch camera URLs using raw SQL
    with connection.cursor() as cursor:
        cursor.execute("SELECT feed_src FROM dashboard_camera_settings WHERE cam_is_active = TRUE AND role_camera = 'T'")
        camera_urls = [row[0] for row in cursor.fetchall()]

    if not camera_urls:
        print("No active cameras found.")
        return  # Exit if no active cameras are found

    # Initialize the recognizer and load the model
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    if not os.path.exists(model_path):
        print({'status': 'error', 'message': 'Model not available, please train the model first.'})
        return  # Exit if the model is not available
    recognizer.read(model_path)

    label_to_name = {}
    for face_folder in os.listdir(dataset_folder):
        face_folder_path = os.path.join(dataset_folder, face_folder)
        if os.path.isdir(face_folder_path):
            for file_name in os.listdir(face_folder_path):
                if file_name.endswith('.jpg'):
                    label = int(file_name.split('_')[1])
                    extracted_name = file_name.split('_')[2]
                    label_to_name[label] = extracted_name

    # Try to use active cameras first
    for camera_url in camera_urls:
        print(f"Start to open camera: {camera_url}")
        
        cap = cv2.VideoCapture(camera_url)  # Use the camera URL
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
                        save_or_update_database(name, detection_times[name], camera_url)  # Save to database
                        last_save_time = current_time  # Update the last save time
                        print(f"Saving detection time for {name}: {detection_times[name]} seconds") 
                else:
                    is_face_detected = False
                    
                total_time_recognized = int(detection_times.get(name, 0))
                timer_text = f'Timer: {total_time_recognized}s'
                
                print(f'Name: {name}  ({confidence:.2f}), {timer_text}')
                # Draw a rectangle around the face
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
                cv2.putText(frame, f'Name: {name}  ({confidence:.2f}), {timer_text}', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Yield the frame for streaming
            ret, jpeg = cv2.imencode('.jpg', frame)
            if not ret:
                break

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')

        cap.release()  # Release the camera when done

    # If no active cameras were found or all failed, use the webcam
    print("No active cameras found or all failed. Using the webcam.")
    cap = cv2.VideoCapture(0)  # Open the default webcam
    if not cap.isOpened():
        print("Failed to open the webcam .")
        return  # Exit if the webcam cannot be opened

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to read frame from webcam.")
            break  # Exit the loop if frame reading fails
        
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
                    save_or_update_database(name, detection_times[name], "Webcam")  # Save to database with "Webcam" as camera URL
                    last_save_time = current_time  # Update the last save time
                    print(f"Saving detection time for {name}: {detection_times[name]} seconds") 
            else:
                is_face_detected = False
                
            total_time_recognized = int(detection_times.get(name, 0))
            timer_text = f'Timer: {total_time_recognized}s'
            
            print(f'Name: {name}  ({confidence:.2f}), {timer_text}')
            # Draw a rectangle around the face
            cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
            cv2.putText(frame, f'Name: {name}  ({confidence:.2f}), {timer_text}', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # Yield the frame for streaming
        ret, jpeg = cv2.imencode('.jpg', frame)
        if not ret:
            break

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')

    cap.release()

if __name__ == "__main__":
    print("Starting Face Recognition Service...")
    recognize_face()