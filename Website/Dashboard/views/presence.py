import json
from datetime import datetime, timedelta
import pytz
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.db import connection
from django.utils import timezone
import os
import shutil
from ..Artificial_Intelligence.face_recognition_absence import process_attendance
from .. import models
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from django.http import HttpRequest
from threading import Thread


# Inisialisasi path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURED_IMG_DIR = os.path.join(
    BASE_DIR, 'static', 'img', 'extracted_faces', 'raw')
PERSONNEL_PICS_DIR = os.path.join(BASE_DIR, 'static', 'img', 'personnel_pics')
PREDICTED_ABSENCE_DIR = os.path.join(
    BASE_DIR, 'static', 'img', 'extracted_faces', 'predicted_faces', 'absence')
PREDICTED_NOT_SAVED_DIR = os.path.join(
    BASE_DIR, 'static', 'img', 'extracted_faces', 'predicted_faces', 'not_saved')
PREDICTED_UNKNOWN_DIR = os.path.join(
    BASE_DIR, 'static', 'img', 'extracted_faces', 'predicted_faces', 'unknown')
JSON_PATH = os.path.join(BASE_DIR, 'static', 'attendance', 'attendance.json')


@csrf_exempt
def presence(request):
    print("Presence process starting...")
    data_list = process_attendance()
    print("data attendance retrieved: ", data_list)

    for data in data_list:
        image_path = data['image_path']
        new_filename = data['new_filename']
        rec_status = data['rec_status']
        predicted_name = data['name']
        detected_time = data['datetime']

        detected_time = datetime.strptime(
            data['datetime'], '%Y-%m-%d %H:%M:%S')

        cam_id = request.session.get('cam_id')
        print("cam_id: ", cam_id)

        try:
            personnel = models.Personnels.objects.get(name=predicted_name)
            personnel_id = personnel.id
        except models.Personnels.DoesNotExist:
            personnel_id = None

        if personnel_id is None:
            print("Personnel not found; skipping database insertion.")
            new_filename = f"unknown_{
                detected_time.strftime('%Y%m%d_%H%M%S')}.jpg"
            new_path = os.path.join(PREDICTED_UNKNOWN_DIR, new_filename)
            shutil.move(image_path, new_path)
            print(f"file berhasil dipindahkan ke {new_path} ")

        print("personnel_id: ", personnel_id)

        # check apakah status nya tidak unknown
        if rec_status != "Unknown":
            # Check if there are records for this person today
            check_personnel_db = models.Personnel_Entries.objects.filter(
                personnel_id=personnel_id)
            current_date = detected_time.date()
            current_date_str = current_date.strftime('%Y-%m-%d')

            # Filter records for today based on date and personnel name
            today_records = [record for record in check_personnel_db if record.timestamp.date(
            ).strftime('%Y-%m-%d') == current_date_str]
            person_today = [
                record for record in today_records if record.personnel.name == predicted_name]

            if not person_today:
                # Create folder based on the date in the absence directory
                date_folder = os.path.join(
                    PREDICTED_ABSENCE_DIR, detected_time.strftime('%Y%m%d'))
                if not os.path.exists(date_folder):
                    os.makedirs(date_folder)

                new_filename = f"{predicted_name}_{
                    detected_time.strftime('%Y%m%d_%H%M%S')}.jpg"
                new_path = os.path.join(date_folder, new_filename)
                shutil.move(image_path, new_path)
                print(f"file berhasil dipindahkan ke {new_path} ")
            else:
                # If no matching record today, save as unknown
                new_filename = f"unknown_{
                    detected_time.strftime('%Y%m%d_%H%M%S')}.jpg"
                new_path = os.path.join(PREDICTED_UNKNOWN_DIR, new_filename)
                shutil.move(image_path, new_path)
                print(f"file berhasil dipindahkan ke {new_path} ")
        else:
            # If status is "Unknown", save as unknown
            new_filename = f"unknown_{
                detected_time.strftime('%Y%m%d_%H%M%S')}.jpg"
            new_path = os.path.join(PREDICTED_UNKNOWN_DIR, new_filename)
            shutil.move(image_path, new_path)
            print(f"file berhasil dipindahkan ke {new_path} ")

        try:

            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT attendance_time_start, attendance_time_end, leaving_time_start, leaving_time_end FROM dashboard_camera_settings WHERE id = %s', [cam_id])
                camera = cursor.fetchone()

                if not camera:
                    return JsonResponse({'status': 'error', 'message': 'Camera not found.'})

            attendance_start, attendance_end, leaving_start, leaving_end = camera

            # Convert string times to datetime.time objects
            attendance_start = datetime.strptime(
                attendance_start, '%H:%M:%S').time()
            attendance_end = datetime.strptime(
                attendance_end, '%H:%M:%S').time()
            leaving_start = datetime.strptime(leaving_start, '%H:%M:%S').time()
            leaving_end = datetime.strptime(leaving_end, '%H:%M:%S').time()


            current_time = detected_time.time()
            status = 'UNKNOWN'

            # Determine initial attendance status
            if attendance_start <= current_time <= attendance_end:
                status = 'ONTIME'
            elif leaving_start <= current_time <= leaving_end:
                status = 'LEAVE'
            else:
                status = 'LATE'

            # Use raw SQL to check existing statuses using SELECT IF
            query = '''
                SELECT
                    IF(EXISTS(SELECT 1 FROM dashboard_personnel_entries WHERE personnel_id = %s AND DATE(timestamp) = %s AND presence_status = 'ONTIME'), 1, 0) AS has_ontime,
                    IF(EXISTS(SELECT 1 FROM dashboard_personnel_entries WHERE personnel_id = %s AND DATE(timestamp) = %s AND presence_status = 'LATE'), 1, 0) AS has_late,
                    IF(EXISTS(SELECT 1 FROM dashboard_personnel_entries WHERE personnel_id = %s AND DATE(timestamp) = %s AND presence_status = 'LEAVE'), 1, 0) AS has_leave
            '''
            with connection.cursor() as cursor:
                cursor.execute(query, [personnel_id, detected_time.date(
                ), personnel_id, detected_time.date(), personnel_id, detected_time.date()])
                result = cursor.fetchone()

            has_ontime, has_late, has_leave = result

            # Logic for determining status based on existing entries
            if status == "ONTIME":
                if has_ontime:
                    return JsonResponse({'status': 'ignored', 'message': 'ONTIME status already exists for this person today.'})
            elif status == 'LATE':
                if has_ontime:
                    return JsonResponse({'status': 'ignored', 'message': 'Entry ignored; ONTIME status already exists for this person today.'})
                if has_late:
                    return JsonResponse({'status': 'ignored', 'message': 'Entry ignored; LATE status already exists for this person today.'})
            elif status == 'LEAVE':
                if has_leave:
                    return JsonResponse({'status': 'ignored', 'message': 'LEAVE status already exists for this person today.'})

            print("status: " + status)

            # Insert the new status entry if valid
            with connection.cursor() as cursor:
                cursor.execute(
                    '''
                    INSERT INTO dashboard_personnel_entries (camera_id, personnel_id, timestamp, presence_status, image)
                    VALUES (%s, %s, %s, %s, %s)
                    ''',
                    [cam_id, personnel_id, detected_time, status, new_path]
                )
            print("Presence saved to DB successfully")
            # return JsonResponse({'status': 'success', 'message': f'Entry saved as {status}.', 'time': detected_time.strftime('%Y-%m-%d %H:%M:%S')})

        except Exception as e:
            print("Error inserting presence data:", e)
            continue

    if request.method == "POST":
        if request.POST["command"] == "presence-data":
            date = data.get('date', timezone.now().date().strftime('%Y-%m-%d'))
            print("Date for presence data:", date)

            try:
                query = '''
                    SELECT 
                        p.id AS personnel_id,
                        p.name,
                        MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END) AS attended_time,
                        MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END) AS leaving_time,
                        (SELECT presence_status 
                        FROM dashboard_personnel_entries 
                        WHERE personnel_id = p.id 
                        ORDER BY timestamp DESC 
                        LIMIT 1) AS latest_status,
                        TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), 
                                MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END)) AS work_hours,
                        CASE 
                            WHEN TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END)) > '08:00:00' 
                            THEN CONCAT('Overtime ', HOUR(TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END))) - 9, ' hours')
                            WHEN TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END)) < '08:00:00' 
                            THEN CONCAT('Less time ', 9 - HOUR(TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END))), ' hours')
                            ELSE 'Standard Time'
                        END AS notes
                    FROM 
                        dashboard_personnel_entries AS d
                    JOIN 
                        dashboard_personnels AS p ON p.id = d.personnel_id
                    WHERE 
                        DATE(d.timestamp) = %s
                    GROUP BY 
                        p.id
                '''

                with connection.cursor() as cursor:
                    cursor.execute(query, [date])
                    entries = cursor.fetchall()

                # Prepare presence data
                presence_data = []
                for entry in entries:
                    attended_time = entry[2].strftime(
                        '%H:%M:%S') if entry[2] else '-'
                    leaving_time = entry[3].strftime(
                        '%H:%M:%S') if entry[3] else '-'
                    presence_data.append({
                        'id': entry[0],
                        'name': entry[1],
                        'attended': attended_time,
                        'leave': leaving_time,
                        'status': entry[4],
                        'work_hours': entry[5] or '-',
                        'notes': entry[6] or 'No notes',
                        'image': entry[7] or 'No image',
                    })

                # Return data in JSON format for AJAX
                return JsonResponse({'status': 'success', 'presence_data': presence_data})

            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)})

    if request.method == 'GET':
        try:
            # Get date filter from the frontend, or use today's date as default
            today = request.GET.get(
                'date', timezone.now().date().strftime('%Y-%m-%d'))
            print("today: " + today)

            query = '''
                SELECT 
                    p.id AS personnel_id,
                    p.name,
                    MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END) AS attended_time,
                    MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END) AS leaving_time,
                    (SELECT presence_status 
                    FROM dashboard_personnel_entries 
                    WHERE personnel_id = p.id 
                    ORDER BY timestamp DESC 
                    LIMIT 1) AS latest_status,
                    TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), 
                            MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END)) AS work_hours,
                    CASE 
                        WHEN TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END)) > '08:00:00' 
                        THEN CONCAT('Overtime ', HOUR(TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END))) - 9, ' hours')
                        WHEN TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END)) < '08:00:00' 
                        THEN CONCAT('Less time ', 9 - HOUR(TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END))), ' hours')
                        ELSE 'Standard Time'
                    END AS notes,
                    d.image AS image_path  -- Include image path here
                FROM 
                    dashboard_personnel_entries AS d
                JOIN 
                    dashboard_personnels AS p ON p.id = d.personnel_id
                WHERE 
                    DATE(d.timestamp) = %s
                GROUP BY 
                    p.id
            '''

            with connection.cursor() as cursor:
                cursor.execute(query, [today])
                entries = cursor.fetchall()

            # Prepare context for rendering in the template
            # Prepare presence data
            presence_data = []
            for entry in entries:
                # Format timestamps for attended and leaving times
                attended_time = entry[2].strftime(
                    '%H:%M:%S') if entry[2] else '-'
                leaving_time = entry[3].strftime(
                    '%H:%M:%S') if entry[3] else '-'

                # Calculate work hours if both attended and leaving times are available
                if entry[2] and entry[3]:
                    # Convert to datetime objects if they aren't already
                    attended_dt = entry[2]
                    leaving_dt = entry[3]

                    # Calculate the time difference
                    work_duration = leaving_dt - attended_dt

                    # Format the work hours as hours and minutes
                    hours_worked = work_duration.seconds // 3600  # Total hours
                    minutes_worked = (work_duration.seconds %
                                      3600) // 60  # Total minutes
                    work_hours = f"{hours_worked} hours, {
                        minutes_worked} minutes"
                else:

                    work_hours = 'Still Working'

                STATIC_DIR = os.path.join(BASE_DIR, 'static')
                full_image_path = entry[7]
                relative_image_path = os.path.relpath(
                    full_image_path, start=STATIC_DIR)

                presence_data.append({
                    'id': entry[0],
                    'name': entry[1],
                    'attended': attended_time,
                    'leave': leaving_time,
                    'status': entry[4],
                    'work_hours': work_hours,
                    'notes': entry[6] or 'No notes',
                    'image_path': relative_image_path or 'No image'
                })

            print(presence_data)

            # Render the presence data in the template
            return render(request, 'presence.html', {'presence_data': presence_data, 'today': today, 'Page': "Presence"})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

# Handler for file system events


class FileHandler(FileSystemEventHandler):

    def on_created(self, event):
        request = HttpRequest()
        request.method = 'GET'
        request.session = {}
        if event.is_directory:
            return
        # When a new file is created in the folder, process attendance
        print(f"New file detected: {event.src_path}")
        presence(request)

# Start the watchdog observer


def start_watching():
    # Check for files already present in the directory
    files_in_directory = os.listdir(CAPTURED_IMG_DIR)
    if files_in_directory:
        # If files are already present, trigger the presence function
        print("Files found, triggering presence...")
        request = HttpRequest()
        request.method = 'GET'
        request.session = {}
        presence(request)

    # Set up the watchdog to monitor new files
    event_handler = FileHandler()
    observer = Observer()
    observer.schedule(event_handler, path=CAPTURED_IMG_DIR, recursive=False)
    observer.start()

    try:
        while True:
            pass
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


def run_watchdog():
    thread = Thread(target=start_watching)
    thread.start()
