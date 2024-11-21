import json
import os
from datetime import datetime, timedelta
import time
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import connection
from django.utils import timezone
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from threading import Thread
from .. import models
from django.shortcuts import render
from django.http import HttpRequest


# Directory paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURED_IMG_DIR = os.path.join(BASE_DIR, 'static', 'img', 'extracted_faces', 'raw')
JSON_DIR = os.path.join(BASE_DIR, 'static', 'attendance')
JSON_PATH = os.path.join(BASE_DIR, 'static', 'attendance' , 'attendance.json')

def read_attendance_data():
    print("JSON_PATH:", JSON_PATH)
    print("File exists:", os.path.isfile(JSON_PATH))
    
    try:
        # Buat file JSON jika belum ada
        if not os.path.isfile(JSON_PATH):
            print("File JSON tidak ditemukan, membuat file baru.")
            with open(JSON_PATH, 'w') as file:
                json.dump([], file)  # Inisialisasi dengan array kosong

        # Cek apakah file kosong
        if os.path.getsize(JSON_PATH) == 0:
            print("JSON file is empty.")
            return []

        # Baca data JSON
        with open(JSON_PATH, 'r') as file:
            data = file.read().strip()
            if not data:
                print("JSON file has no content.")
                return []
            data_list = json.loads(data)
        return data_list
    except json.JSONDecodeError as e:
        print("Error reading JSON file: Invalid JSON format:", e)
        return []
    except Exception as e:
        print("Error reading JSON file:", e)
        return []


# Insert presence data into the database
def insert_presence(cam_id, personnel_id, detected_time, status, image_path):
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            INSERT INTO dashboard_personnel_entries (camera_id, personnel_id, timestamp, presence_status, image)
            VALUES (%s, %s, %s, %s, %s)
            ''',
            [cam_id, personnel_id, detected_time, status, image_path]
        )
    print(f"Presence saved as {status} for personnel ID {personnel_id} at {detected_time}")


def process_attendance_entry(data, cam_id):
    name = data.get('name')
    datetime_str = data.get('datetime')
    image_path = data.get('image_path')
    detected_time = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')

    try:
        personnel = models.Personnels.objects.get(name=name)
        personnel_id = personnel.id
    except models.Personnels.DoesNotExist:
        print(f"Personnel '{name}' not found.")
        return

    # Ambil pengaturan kamera
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT attendance_time_start, attendance_time_end, leaving_time_start, leaving_time_end FROM dashboard_camera_settings WHERE id = %s',
            [cam_id]
        )
        camera = cursor.fetchone()
        if not camera:
            print("Camera settings not found.")
            return

    # Parse waktu dari pengaturan kamera
    attendance_start, attendance_end, leaving_start, leaving_end = map(lambda t: datetime.strptime(t, '%H:%M:%S').time(), camera)
    current_time = detected_time.time()

    # Tentukan status berdasarkan waktu yang terdeteksi
    # Penanganan waktu lebih dari satu rentang (misalnya jika waktu mulai lebih besar dari waktu berakhir)
    if attendance_start <= current_time <= attendance_end:
        status = 'ONTIME'
    elif leaving_start <= current_time <= leaving_end:
        status = 'LEAVE'
    else:
        # Cek apakah waktu yang terdeteksi berada di luar rentang `attendance_time_end` dan `leaving_time_start`
        if attendance_end < current_time < leaving_start:
            status = 'LATE'
        else:
            status = 'LEAVE'  # Status 'LEAVE' jika berada di luar range yang valid, bisa disesuaikan

    # Query untuk cek entri yang sudah ada untuk tanggal dan status tertentu
    query = '''
        SELECT
            IF(EXISTS(SELECT 1 FROM dashboard_personnel_entries WHERE personnel_id = %s AND DATE(timestamp) = %s AND presence_status = 'ONTIME'), 1, 0) AS has_ontime,
            IF(EXISTS(SELECT 1 FROM dashboard_personnel_entries WHERE personnel_id = %s AND DATE(timestamp) = %s AND presence_status = 'LATE'), 1, 0) AS has_late,
            IF(EXISTS(SELECT 1 FROM dashboard_personnel_entries WHERE personnel_id = %s AND DATE(timestamp) = %s AND presence_status = 'LEAVE'), 1, 0) AS has_leave
    '''
    with connection.cursor() as cursor:
        cursor.execute(query, [personnel_id, detected_time.date(), personnel_id, detected_time.date(), personnel_id, detected_time.date()])
        has_ontime, has_late, has_leave = cursor.fetchone()

    # Jika sudah ada ONTIME atau statusnya sudah ada pada tanggal yang sama, jangan insert
    if (status == "ONTIME" and has_ontime) or (status == 'LATE' and (has_ontime or has_late)) or (status == 'LEAVE' and has_leave):
        print(f"Duplicate entry found for {name} on {detected_time.date()} with status {status}. Skipping insert.")
        return  # Skip duplicate entries

    # Jika statusnya 'LATE' dan sudah ada ONTIME, maka statusnya diubah menjadi 'LEAVING'
    if status == 'LATE' and has_ontime:
        status = 'LEAVE'  # Update status to LEAVE if there's an ONTIME entry for the same person on that day

    # Fungsi untuk menyimpan entri ke database
    insert_presence(cam_id, personnel_id, detected_time, status, image_path)
    print(f"Inserted {status} entry for {name} at {detected_time}")

    
# Main function to process presence
def presence_process(cam_id):
    data_list = read_attendance_data()
    
    # Process each entry
    for data in data_list:
        process_attendance_entry(data, cam_id)
    
    # delete_attendance_file()
    return {'status': 'success', 'message': 'Attendance data processed successfully'}

def get_cam_id(request: HttpRequest):
    return request.session.get('cam_id', 1) 

@csrf_exempt
def presence(request):
    if request.method == "POST":
        cam_id = request.session.get('cam_id')
        if not cam_id:
            return JsonResponse({'status': 'error', 'message': 'Camera ID not found in session'})
        
        # Check the command for fetching presence data
        if request.POST.get("command") == "presence-data":
            date = request.POST.get('date', timezone.now().date().strftime('%Y-%m-%d'))
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
                            THEN CONCAT('Overtime ', HOUR(TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END))) - 8, ' hours')
                            WHEN TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END)) < '08:00:00' 
                            THEN CONCAT('Less time ', 8 - HOUR(TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END))), ' hours')
                            ELSE 'Standard Time'
                        END AS notes,
                        d.image AS image_path
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

                presence_data = []
                for entry in entries:
                    attended_time = entry[2].strftime('%H:%M:%S') if entry[2] else '-'
                    leaving_time = entry[3].strftime('%H:%M:%S') if entry[3] else '-'
                    
                    work_hours = entry[5] or 'Still Working'
                    STATIC_DIR = os.path.join(BASE_DIR)
                    relative_image_path = os.path.relpath(entry[7], start=STATIC_DIR) if entry[7] else 'No image'
                    
                    presence_data.append({
                        'id': entry[0],
                        'name': entry[1],
                        'attended': attended_time,
                        'leave': leaving_time,
                        'status': entry[4],
                        'work_hours': work_hours,
                        'notes': entry[6] or 'No notes',
                        'image_path': relative_image_path,
                    })

                return JsonResponse({'status': 'success', 'presence_data': presence_data})

            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)})

        result = presence_process(cam_id)
        return JsonResponse(result)

    elif request.method == 'GET':
        try:
            today = request.GET.get('date', timezone.now().date().strftime('%Y-%m-%d'))
            
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
                        THEN CONCAT('Overtime ', HOUR(TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END))) - 8, ' hours')
                        WHEN TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END)) < '08:00:00' 
                        THEN CONCAT('Less time ', 8 - HOUR(TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END))), ' hours')
                        ELSE 'Standard Time'
                    END AS notes,
                    d.image AS image_path
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

            presence_data = []
            for entry in entries:
                attended_time = entry[2].strftime('%H:%M:%S') if entry[2] else '-'
                leaving_time = entry[3].strftime('%H:%M:%S') if entry[3] else '-'
                work_hours = entry[5] or 'Still Working'
                STATIC_DIR = os.path.join(BASE_DIR)
                relative_image_path = os.path.relpath(entry[7], start=STATIC_DIR) if entry[7] else 'No image'
                
                presence_data.append({
                    'id': entry[0],
                    'name': entry[1],
                    'attended': attended_time,
                    'leave': leaving_time,
                    'status': entry[4],
                    'work_hours': work_hours,
                    'notes': entry[6] or 'No notes',
                    'image_path': relative_image_path,
                })

            return render(request, 'presence.html', {'presence_data': presence_data, 'today': today, 'Page': "Presence"})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})



        
# Watchdog handler for directory monitoring
class AttendanceHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
    
    def on_created(self, event):
        cam_id = 1 
        print("File created, running presence process.")
        presence_process(cam_id)

    def on_modified(self, event):
        cam_id = 1 
        print("File modified, running presence process.")
        presence_process(cam_id)


# Watchdog observer setup
def start_watching():
    observer = Observer()
    observer.schedule(AttendanceHandler(), path=JSON_DIR, recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1) 
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    print(f"Monitoring directory: {JSON_DIR}")
    


# import json
# from datetime import datetime, timedelta
# import pytz
# from django.http import JsonResponse
# from django.shortcuts import render
# from django.views.decorators.csrf import csrf_exempt
# from django.db import connection
# from django.utils import timezone
# import os
# import shutil
# from ..Artificial_Intelligence.face_recognition_absence import process_attendance
# from .. import models
# from watchdog.observers import Observer
# from watchdog.events import FileSystemEventHandler
# from django.http import HttpRequest
# from threading import Thread


# # Inisialisasi path
# BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# CAPTURED_IMG_DIR = os.path.join(
#     BASE_DIR, 'static', 'img', 'extracted_faces', 'raw')
# PERSONNEL_PICS_DIR = os.path.join(BASE_DIR, 'static', 'img', 'personnel_pics')
# PREDICTED_ABSENCE_DIR = os.path.join(
#     BASE_DIR, 'static', 'img', 'extracted_faces', 'predicted_faces', 'absence')
# PREDICTED_NOT_SAVED_DIR = os.path.join(
#     BASE_DIR, 'static', 'img', 'extracted_faces', 'predicted_faces', 'not_saved')
# PREDICTED_UNKNOWN_DIR = os.path.join(
#     BASE_DIR, 'static', 'img', 'extracted_faces', 'predicted_faces', 'unknown')
# JSON_PATH = os.path.join(BASE_DIR, 'static', 'attendance', 'attendance.json')


# @csrf_exempt
# def presence(request):
#     print("Presence process starting...")
    
#     try:
#         with open(JSON_PATH, 'r') as file:
#             data_list = json.load(file)
#         print("Data attendance retrieved: ", data_list)
#     except Exception as e:
#         print("Error reading JSON file:", e)
#         return JsonResponse({'status': 'error', 'message': 'Error reading JSON file'})

#     for data in data_list:
#         try:
#             name = data.get('name')
#             datetime_str = data.get('datetime')
#             image_path = data.get('image_path')
#             detected_time = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')

#             # Get camera ID from session
#             cam_id = request.session.get('cam_id')
#             # cam_id = 1
#             print("cam_id: ", cam_id)

#             # Fetch personnel
#             try:
#                 personnel = models.Personnels.objects.get(name=name)
#                 personnel_id = personnel.id
#             except models.Personnels.DoesNotExist:
#                 personnel_id = None
#                 print("Personnel not found; skipping database insertion.")
#                 continue

#             # Attendance time settings from camera
#             with connection.cursor() as cursor:
#                 cursor.execute(
#                     'SELECT attendance_time_start, attendance_time_end, leaving_time_start, leaving_time_end FROM dashboard_camera_settings WHERE id = %s', [cam_id]
#                 )
#                 camera = cursor.fetchone()
#                 if not camera:
#                     return JsonResponse({'status': 'error', 'message': 'Camera not found.'})
                
#             attendance_start, attendance_end, leaving_start, leaving_end = camera
#             attendance_start = datetime.strptime(attendance_start, '%H:%M:%S').time()
#             attendance_end = datetime.strptime(attendance_end, '%H:%M:%S').time()
#             leaving_start = datetime.strptime(leaving_start, '%H:%M:%S').time()
#             leaving_end = datetime.strptime(leaving_end, '%H:%M:%S').time()

#             # Determine attendance status
#             current_time = detected_time.time()
#             status = 'UNKNOWN'
#             if attendance_start <= current_time <= attendance_end:
#                 status = 'ONTIME'
#             elif leaving_start <= current_time <= leaving_end:
#                 status = 'LEAVE'
#             else:
#                 status = 'LATE'

#             # Check for existing status in the database
#             query = '''
#                 SELECT
#                     IF(EXISTS(SELECT 1 FROM dashboard_personnel_entries WHERE personnel_id = %s AND DATE(timestamp) = %s AND presence_status = 'ONTIME'), 1, 0) AS has_ontime,
#                     IF(EXISTS(SELECT 1 FROM dashboard_personnel_entries WHERE personnel_id = %s AND DATE(timestamp) = %s AND presence_status = 'LATE'), 1, 0) AS has_late,
#                     IF(EXISTS(SELECT 1 FROM dashboard_personnel_entries WHERE personnel_id = %s AND DATE(timestamp) = %s AND presence_status = 'LEAVE'), 1, 0) AS has_leave
#             '''
#             with connection.cursor() as cursor:
#                 cursor.execute(query, [personnel_id, detected_time.date(), personnel_id, detected_time.date(), personnel_id, detected_time.date()])
#                 result = cursor.fetchone()

#             has_ontime, has_late, has_leave = result

#             # Finalize status based on existing entries
#             if status == "ONTIME" and has_ontime:
#                 continue
#             elif status == 'LATE' and (has_ontime or has_late):
#                 continue
#             elif status == 'LEAVE' and has_leave:
#                 continue

#             # Insert attendance record if valid
#             with connection.cursor() as cursor:
#                 cursor.execute(
#                     '''
#                     INSERT INTO dashboard_personnel_entries (camera_id, personnel_id, timestamp, presence_status, image)
#                     VALUES (%s, %s, %s, %s, %s)
#                     ''',
#                     [cam_id, personnel_id, detected_time, status, image_path]
#                 )
#             print(f"Presence saved as {status} for {name} at {detected_time}")

#         except Exception as e:
#             print("Error processing attendance data:", e)
#             continue

#         return JsonResponse({'status': 'success', 'message': 'Attendance data processed successfully'})

#     if request.method == "POST":
#         if request.POST["command"] == "presence-data":
#             date = data.get('date', timezone.now().date().strftime('%Y-%m-%d'))
#             print("Date for presence data:", date)

#             try:
#                 query = '''
#                     SELECT 
#                         p.id AS personnel_id,
#                         p.name,
#                         MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END) AS attended_time,
#                         MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END) AS leaving_time,
#                         (SELECT presence_status 
#                         FROM dashboard_personnel_entries 
#                         WHERE personnel_id = p.id 
#                         ORDER BY timestamp DESC 
#                         LIMIT 1) AS latest_status,
#                         TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), 
#                                 MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END)) AS work_hours,
#                         CASE 
#                             WHEN TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END)) > '08:00:00' 
#                             THEN CONCAT('Overtime ', HOUR(TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END))) - 9, ' hours')
#                             WHEN TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END)) < '08:00:00' 
#                             THEN CONCAT('Less time ', 9 - HOUR(TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END))), ' hours')
#                             ELSE 'Standard Time'
#                         END AS notes
#                     FROM 
#                         dashboard_personnel_entries AS d
#                     JOIN 
#                         dashboard_personnels AS p ON p.id = d.personnel_id
#                     WHERE 
#                         DATE(d.timestamp) = %s
#                     GROUP BY 
#                         p.id
#                 '''

#                 with connection.cursor() as cursor:
#                     cursor.execute(query, [date])
#                     entries = cursor.fetchall()

#                 # Prepare presence data
#                 presence_data = []
#                 for entry in entries:
#                     attended_time = entry[2].strftime(
#                         '%H:%M:%S') if entry[2] else '-'
#                     leaving_time = entry[3].strftime(
#                         '%H:%M:%S') if entry[3] else '-'
#                     presence_data.append({
#                         'id': entry[0],
#                         'name': entry[1],
#                         'attended': attended_time,
#                         'leave': leaving_time,
#                         'status': entry[4],
#                         'work_hours': entry[5] or '-',
#                         'notes': entry[6] or 'No notes',
#                         'image': entry[7] or 'No image',
#                     })

#                 # Return data in JSON format for AJAX
#                 return JsonResponse({'status': 'success', 'presence_data': presence_data})

#             except Exception as e:
#                 return JsonResponse({'status': 'error', 'message': str(e)})

#     if request.method == 'GET':
#         try:
#             # Get date filter from the frontend, or use today's date as default
#             today = request.GET.get(
#                 'date', timezone.now().date().strftime('%Y-%m-%d'))
#             print("today: " + today)

#             query = '''
#                 SELECT 
#                     p.id AS personnel_id,
#                     p.name,
#                     MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END) AS attended_time,
#                     MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END) AS leaving_time,
#                     (SELECT presence_status 
#                     FROM dashboard_personnel_entries 
#                     WHERE personnel_id = p.id 
#                     ORDER BY timestamp DESC 
#                     LIMIT 1) AS latest_status,
#                     TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), 
#                             MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END)) AS work_hours,
#                     CASE 
#                         WHEN TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END)) > '08:00:00' 
#                         THEN CONCAT('Overtime ', HOUR(TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END))) - 9, ' hours')
#                         WHEN TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END)) < '08:00:00' 
#                         THEN CONCAT('Less time ', 9 - HOUR(TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END))), ' hours')
#                         ELSE 'Standard Time'
#                     END AS notes,
#                     d.image AS image_path  -- Include image path here
#                 FROM 
#                     dashboard_personnel_entries AS d
#                 JOIN 
#                     dashboard_personnels AS p ON p.id = d.personnel_id
#                 WHERE 
#                     DATE(d.timestamp) = %s
#                 GROUP BY 
#                     p.id
#             '''

#             with connection.cursor() as cursor:
#                 cursor.execute(query, [today])
#                 entries = cursor.fetchall()

#             # Prepare context for rendering in the template
#             # Prepare presence data
#             presence_data = []
#             for entry in entries:
#                 # Format timestamps for attended and leaving times
#                 attended_time = entry[2].strftime(
#                     '%H:%M:%S') if entry[2] else '-'
#                 leaving_time = entry[3].strftime(
#                     '%H:%M:%S') if entry[3] else '-'

#                 # Calculate work hours if both attended and leaving times are available
#                 if entry[2] and entry[3]:
#                     # Convert to datetime objects if they aren't already
#                     attended_dt = entry[2]
#                     leaving_dt = entry[3]

#                     # Calculate the time difference
#                     work_duration = leaving_dt - attended_dt

#                     # Format the work hours as hours and minutes
#                     hours_worked = work_duration.seconds // 3600  # Total hours
#                     minutes_worked = (work_duration.seconds %
#                                       3600) // 60  # Total minutes
#                     work_hours = f"{hours_worked} hours, {
#                         minutes_worked} minutes"
#                 else:

#                     work_hours = 'Still Working'

#                 STATIC_DIR = os.path.join(BASE_DIR)
#                 full_image_path = entry[7]
#                 relative_image_path = os.path.relpath(
#                     full_image_path, start=STATIC_DIR)

#                 presence_data.append({
#                     'id': entry[0],
#                     'name': entry[1],
#                     'attended': attended_time,
#                     'leave': leaving_time,
#                     'status': entry[4],
#                     'work_hours': work_hours,
#                     'notes': entry[6] or 'No notes',
#                     'image_path': relative_image_path or 'No image'
#                 })

#             print(presence_data)

#             # Render the presence data in the template
#             return render(request, 'presence.html', {'presence_data': presence_data, 'today': today, 'Page': "Presence"})

#         except Exception as e:
#             return JsonResponse({'status': 'error', 'message': str(e)})

#     return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

# # Handler for file system events


# class FileHandler(FileSystemEventHandler):

#     def on_created(self, event):
#         request = HttpRequest()
#         request.method = 'GET'
#         request.session = {}
#         if event.is_directory:
#             return
#         # When a new file is created in the folder, process attendance
#         print(f"New file detected: {event.src_path}")
#         presence(request)

# # Start the watchdog observer


# def start_watching():
#     # Check for files already present in the directory
#     files_in_directory = os.listdir(CAPTURED_IMG_DIR)
#     if files_in_directory:
#         # If files are already present, trigger the presence function
#         print("Files found, triggering presence...")
#         request = HttpRequest()
#         request.method = 'GET'
#         request.session = {}
#         presence(request)

#     # Set up the watchdog to monitor new files
#     event_handler = FileHandler()
#     observer = Observer()
#     observer.schedule(event_handler, path=CAPTURED_IMG_DIR, recursive=False)
#     observer.start()

#     try:
#         while True:
#             pass
#     except KeyboardInterrupt:
#         observer.stop()
#     observer.join()


# def run_watchdog():
#     thread = Thread(target=start_watching)
#     thread.start()
