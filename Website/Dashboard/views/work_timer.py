# views.py
import cv2
from datetime import datetime, timedelta
from django.http import JsonResponse, StreamingHttpResponse
from .. import models
from ..Artificial_Intelligence.face_rec_haar import recognize_face
from django.shortcuts import render
# Global variables to track detection times
detection_times = {}
last_detection_time = {}
last_save_time = datetime.now()

def work_timer():
    """Continuously process frames from multiple RTSP cameras."""
    global detection_times, last_detection_time, last_save_time

    # Retrieve camera URLs from the database where role_camera is True
    camera_urls = models.Camera_Settings.objects.filter(cam_is_active = True, role_camera="T").values_list('feed_src', flat=True)

    while True:
        for camera_url in camera_urls:
            # print(f"Processing camera: {camera_url}")  # Print the current camera URL
            cap = cv2.VideoCapture(camera_url)

            if not cap.isOpened():
                # print(f"Failed to open camera: {camera_url}")
                continue  # Skip to the next camera if it fails to open

            recognized_faces = recognize_face(cap)

            current_time = datetime.now()
            for name, bbox in recognized_faces:
                print(f"Recognized face: {name}")  # Print the recognized name

                if name != "Unknown":
                    if name in last_detection_time:
                        elapsed_time = (current_time - last_detection_time[name]).total_seconds()
                        detection_times[name] += elapsed_time
                        print(f"Elapsed time for {name}: {elapsed_time:.2f} seconds")  # Print elapsed time
                    else:
                        detection_times[name] = 0

                    last_detection_time[name] = current_time

                    # Check if a minute has passed to save to the database
                    if (current_time - last_save_time) >= timedelta(minutes=1):
                        print(f"Saving detection time for {name}: {detection_times[name]} seconds")  # Print before saving
                        save_or_update_database(name, detection_times[name], camera_url)
                        last_save_time = current_time  # Update the last save time
                else:
                    print("No recognized face.")  # Print if no face is recognized

            cap.release()

def save_or_update_database(name, total_time,camera_url):
    """Save or update the detection time in the Work_Timer table."""
    try:
        personnel = models.Personnels.objects.get(name=name)  # Get the personnel object
        camera = models.Camera_Settings.objects.get(feed_src=camera_url)  # Get the personnel object
        
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
                camera_id=camera,  # Replace with the actual camera ID
                type='FACE_DETECTED',
                datetime=datetime.now(),
                timer=int(total_time)
            )
        
    except models.Personnels.DoesNotExist:
        print(f"Personnel with name {name} does not exist.")
        

def stream_timer_video(camera_url):
    """Stream video and display bounding boxes with names and timers."""
    cap = cv2.VideoCapture(camera_url)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        recognized_faces = recognize_face(frame)

        for name, bbox in recognized_faces:
            x, y, w, h = bbox
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
            timer_text = f'Timer: {detection_times.get(name, 0)} seconds'
            cv2.putText(frame, f'Name: {name}, {timer_text}', (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        ret, jpeg = cv2.imencode('.jpg', frame)
        if not ret:
            break

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')

    cap.release()

def video_feed_timer(request, cam_id):
    """View to stream video from a specific camera."""
    camera_url = models.Camera_Settings.objects.get(id=cam_id).feed_src
    return StreamingHttpResponse(stream_timer_video(camera_url), content_type='multipart/x-mixed-replace; boundary=frame')

def work_time_report(request):
    """View to display the work time report."""
    return render(request, 'work_time_report.html')