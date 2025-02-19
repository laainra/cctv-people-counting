# views.py
import cv2
from datetime import datetime, timedelta
from django.http import JsonResponse, StreamingHttpResponse
from .. import models
# from ..Artificial_Intelligence.face_rec_haar import recognize_face
from .face_rec import recognize_face
from django.shortcuts import render
from django.utils import timezone
from collections import defaultdict
from datetime import timedelta
from django.db import connection

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
            print(f"Starting work time counting for {camera_url}")
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
    company = models.Company.objects.get(user=request.user)
    personnel_list = models.Personnels.objects.filter(company=company)

    # Get the date from the request, default to today if not provided
    filter_date = request.GET.get('filter_date', timezone.now().date())

    # Use a raw SQL query to fetch work time data for the selected date
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT wt.id, wt.datetime, wt.type, wt.timer, wt.camera_id, wt.personnel_id,
                p.name AS employee_name, p.division_id AS employee_division, c.cam_name AS camera_name
            FROM dashboard_work_timer wt
            JOIN dashboard_personnels p ON wt.personnel_id = p.id
            JOIN dashboard_camera_settings c ON wt.camera_id = c.id
            WHERE DATE(wt.datetime) = %s AND p.company_id = %s
        """, [filter_date, company.id])
        
        # Fetch all results
        work_time_data = cursor.fetchall()

    # Aggregate data
    aggregated_data = defaultdict(lambda: {
        'total_time_detected': timedelta(),
        'cctv_areas': set(),
        'employee_id': None,
        'employee_name': None,
        'division': None,
        'date': None,
    })

    for entry in work_time_data:
        # Assuming entry is a tuple: (id, datetime, type, timer, camera_id, personnel_id, employee_name, employee_division, camera_name)
        timer_seconds = entry[3]  # Assuming 'timer' is in seconds
        personnel_id = entry[5]
        employee_name = entry[6]
        employee_division = entry[7]
        camera_name = entry[8]

        # Calculate total time detected
        total_time = timedelta(seconds=timer_seconds)
        aggregated_data[personnel_id]['total_time_detected'] += total_time
        
        # Store employee details
        aggregated_data[personnel_id]['employee_id'] = personnel_id
        aggregated_data[personnel_id]['employee_name'] = employee_name
        aggregated_data[personnel_id]['division'] = employee_division
        aggregated_data[personnel_id]['cctv_areas'].add(camera_name)  # Collect CCTV areas
        aggregated_data[personnel_id]['date'] = entry[1].date()

    # Prepare data for rendering
    report_data = []
    for data in aggregated_data.values():
        total_seconds = int(data['total_time_detected'].total_seconds())  # Convert timedelta to total seconds
        total_hours = total_seconds // 3600  # Calculate hours
        total_minutes = (total_seconds % 3600) // 60  # Calculate remaining minutes

        report_data.append({
            'employee_id': data['employee_id'],
            'employee_name': data['employee_name'],
            'division': data['division'],
            'total_time_hours': total_hours if total_hours > 0 else 0,  # Show 0 if less than 1 hour
            'total_time_minutes': total_minutes if total_hours > 0 else total_seconds // 60,  # Show minutes if hours are 0
            'cctv_areas': ', '.join(data['cctv_areas']),  # Join CCTV areas
            'date': data['date'],
        })  

        
        print(report_data)

    return render(request, 'admin/work_time_report.html', {
        'personnel_list': personnel_list,
        'work_time_report': report_data,
        'filter_date': filter_date,  # Pass the selected filter date to the template
    })