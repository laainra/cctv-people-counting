import json
import os
from datetime import datetime, timedelta
import time
from django.views.decorators.csrf import csrf_exempt
from django.db import connection
from django.utils import timezone
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from threading import Thread
from .. import models
from django.shortcuts import render
from django.http import HttpRequest, HttpResponse, JsonResponse
from xlsxwriter.workbook import Workbook
from io import BytesIO
from django.contrib.auth.decorators import login_required
from ..decorators import role_required



# Directory paths
DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURED_IMG_DIR = os.path.join(DIR, 'static', 'img', 'extracted_faces', 'raw')
JSON_DIR = os.path.join(DIR, 'static', 'attendance')
JSON_PATH = os.path.join(DIR, 'static', 'attendance' , 'attendance.json')


def read_attendance_data():
    # Mendapatkan tanggal kemarin dan hari ini
    attendance_date_yesterday = (datetime.now() - timedelta(days=1)).date()
    attendance_date_today = datetime.now().date()

    yesterday_json_path = os.path.join(DIR, 'static', 'attendance', f'{attendance_date_yesterday}.json')
    today_json_path = os.path.join(DIR, 'static', 'attendance', f'{attendance_date_today}.json')
    
    # print("JSON_PATH:", JSON_PATH)
    # print("File exists:", os.path.isfile(JSON_PATH))

    try:
        # Cek apakah file untuk tanggal kemarin ada, jika ada hapus
        if os.path.isfile(yesterday_json_path):
            # print(f"File untuk {attendance_date_yesterday} ditemukan, menghapus file lama.")
            os.remove(yesterday_json_path)

        # Membuat file baru untuk tanggal hari ini
        if not os.path.isfile(today_json_path):
            # print(f"File untuk {attendance_date_today} tidak ditemukan, membuat file baru.")
            with open(today_json_path, 'w') as file:
                json.dump([], file)  # Inisialisasi dengan array kosong
        
        # Baca data dari file JSON hari ini
        if os.path.getsize(today_json_path) == 0:
            print("JSON file is empty.")
            return []

        # Baca data JSON
        with open(today_json_path, 'r') as file:
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

    if not cam_id or not personnel_id or not detected_time or not status:
        # print("Invalid data detected, skipping insertion.")
        return

    with connection.cursor() as cursor:
        cursor.execute(
            '''
            INSERT INTO dashboard_personnel_entries (camera_id, personnel_id, timestamp, presence_status, image)
            VALUES (%s, %s, %s, %s, %s)
            ''',
            [cam_id, personnel_id, detected_time, status, image_path]
        )
    print(f"Presence saved as {status} for personnel ID {personnel_id} at {detected_time}")


       
def get_presence_data(date):
    query = '''
        SELECT 
            p.id AS personnel_id,
            p.name,
            MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END) AS attended_time,
            MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END) AS leaving_time,
            CASE 
                WHEN EXISTS (
                    SELECT 1 
                    FROM dashboard_personnel_entries AS sub 
                    WHERE sub.personnel_id = p.id 
                    AND DATE(sub.timestamp) = %s 
                    AND presence_status = 'LEAVE'
                ) THEN 'LEAVING'
                ELSE MAX(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN presence_status END)
            END AS latest_status,
            TIMESTAMPDIFF(HOUR, 
                MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END),
                MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END)
            ) AS work_hours,
            CASE 
                WHEN TIMESTAMPDIFF(HOUR, 
                    MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END),
                    MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END)
                ) > 8 THEN CONCAT('Overtime ', TIMESTAMPDIFF(HOUR, 
                    MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END),
                    MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END)
                ) - 8, ' hours')
                WHEN TIMESTAMPDIFF(HOUR, 
                    MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END),
                    MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END)
                ) < 8 THEN CONCAT('Less time ', 8 - TIMESTAMPDIFF(HOUR, 
                    MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END),
                    MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END)
                ), ' hours')
                ELSE 'Standard Time'
            END AS notes,
            (SELECT d.image 
            FROM dashboard_personnel_entries AS d 
            WHERE d.personnel_id = p.id 
            AND DATE(d.timestamp) = %s
            AND (
                (presence_status = 'LEAVE') OR
                (presence_status IN ('ONTIME', 'LATE') 
                    AND NOT EXISTS (
                        SELECT 1
                        FROM dashboard_personnel_entries AS sub
                        WHERE sub.personnel_id = p.id
                        AND DATE(sub.timestamp) = %s
                        AND sub.presence_status = 'LEAVE'
                    ))
            )
            ORDER BY timestamp DESC 
            LIMIT 1
            ) AS image_path
        FROM 
            dashboard_personnel_entries AS d
        JOIN 
            dashboard_personnels AS p ON p.id = d.personnel_id
        WHERE 
            DATE(d.timestamp) = %s
        GROUP BY 
            p.id
    '''
    params = [date, date, date, date]

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        entries = cursor.fetchall()

    presence_data = []
    for entry in entries:
        attended_time = entry[2].strftime('%H:%M:%S') if entry[2] else '-'
        leaving_time = entry[3].strftime('%H:%M:%S') if entry[3] else '-'

        work_hours = entry[5] or 'Still Working'
        relative_image_path = os.path.relpath(entry[7], start=DIR) if entry[7] else 'No image'

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
    return presence_data

def get_presence_by_status(date, status=None):
    query = '''
        SELECT 
            p.id AS personnel_id,
            p.name,
            MIN(CASE WHEN presence_status IN ('ONTIME', 'LATE') THEN timestamp END) AS attended_time,
            MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END) AS leaving_time
        FROM 
            dashboard_personnel_entries AS d
        JOIN 
            dashboard_personnels AS p ON p.id = d.personnel_id
        WHERE 
            DATE(d.timestamp) = %s
    '''
    params = [date]
    if status:
        query += " AND d.presence_status = %s"
        params.append(status)

    query += " GROUP BY p.id"

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchall()

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
    if attendance_start <= current_time <= attendance_end:
        status = 'ONTIME'
    elif leaving_start <= current_time <= leaving_end:
        status = 'LEAVE'
    else:
        if attendance_end < current_time < leaving_start:
            status = 'LATE'
        else:
            status = 'LEAVE'

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

    # Jika belum ada ONTIME atau LATE, tolak entri LEAVE
    if status == 'LEAVE' and not (has_ontime or has_late):
        # print(f"Skipping LEAVE entry for {name} on {detected_time.date()} due to no ONTIME or LATE status.")
        return

    # Jika status sudah ada di database, abaikan duplikat
    if (status == 'ONTIME' and has_ontime) or (status == 'LATE' and (has_ontime or has_late)) or (status == 'LEAVE' and has_leave):
        # print(f"Duplicate entry found for {name} on {detected_time.date()} with status {status}. Skipping insert.")
        return

    # Jika statusnya 'LATE' dan sudah ada ONTIME, maka ubah menjadi 'LEAVE'
    if status == 'LATE' and has_ontime:
        status = 'LEAVE'

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

def get_active_cam_ids():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id FROM dashboard_camera_settings 
            WHERE cam_is_active = 1 
            AND role_camera IN ('p_in', 'p_out')
        """)
        active_cam_ids = cursor.fetchall()
        return [cam_id[0] for cam_id in active_cam_ids] 

@csrf_exempt
@login_required(login_url='login')
@role_required('admin')
def presence(request):
    if request.method == "POST":
        cam_id = request.POST.get("cam_id")  # Mengambil `cam_id` dari POST request
        if not cam_id:
            cam_id = get_active_cam_ids()
            if not cam_id:
                return JsonResponse({'status': 'error', 'message': 'No active camera found'})

        if request.POST.get("command") == "presence-data":
            date = request.POST.get('date', timezone.now().date().strftime('%Y-%m-%d'))
            try:
                presence_data = get_presence_data(date)
                return JsonResponse({'status': 'success', 'presence_data': presence_data})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)})

        result = presence_process(cam_id)
        return JsonResponse(result)

    elif request.method == 'GET':
        try:
            today = request.GET.get('date', timezone.now().date().strftime('%Y-%m-%d'))
            presence_data = get_presence_data(today)
            status = get_presence_by_status(today)
            return render(request, 'presence.html', {
                'presence_data': presence_data,
                'date': today,
                'status': status,
            })

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
 
def delete_and_create_json():
    while True:
        try:
            # Menghapus file JSON jika ada
            if os.path.exists(JSON_PATH):
                os.remove(JSON_PATH)
                print(f"File {JSON_PATH} telah dihapus.")

            # # Membuat file JSON baru
            # with open(JSON_PATH, 'w') as file:
            #     json.dump([], file)  # Menulis array kosong ke file baru
            # print(f"File {JSON_PATH} telah dibuat kembali.")
        except Exception as e:
            print(f"Error in delete_and_create_json: {e}")

        # Menunggu selama 10 menit (600 detik)
        time.sleep(600)

# Watchdog handler for directory monitoring
class AttendanceHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
    
    def on_created(self, event):
        # Retrieve active camera IDs with role 'p_in' and 'p_out'
        active_cam_ids = get_active_cam_ids()
        for cam_id in active_cam_ids:
            print(f"File created, running presence process for camera ID: {cam_id}")
            presence_process(cam_id)

    def on_modified(self, event):
        # Retrieve active camera IDs with role 'p_in' and 'p_out'
        active_cam_ids = get_active_cam_ids()
        for cam_id in active_cam_ids:
            print(f"File modified, running presence process for camera ID: {cam_id}")
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
    
    delete_and_create_json()
    
def download_presence_excel(request):
    """
    Generate an Excel file containing presence data.
    If a date is provided via request, filter data for that date using the 'timestamp' field.
    """
    from django.utils.timezone import make_aware
    from datetime import datetime

    # Retrieve the 'date' parameter from the request (if provided)
    date_str = request.GET.get('date')  # Date in the format 'YYYY-MM-DD'
    date = None

    # If the 'date' parameter is provided, try to parse it
    if date_str:
        try:
            # Convert the date string to a datetime object
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            # If the date format is incorrect, return an error or handle it accordingly
            return HttpResponse("Invalid date format. Please use YYYY-MM-DD.", status=400)

    # Create an in-memory output file for the workbook
    output = BytesIO()
    workbook = Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet("Presence Data")

    # Add headers to the worksheet
    headers = ["ID", "Name", "Role", "Timestamp", "Presence Status", "Camera ID"]
    for col_num, header in enumerate(headers):
        worksheet.write(0, col_num, header)

    # Filter presence data based on the provided date
    if date:
        # Filter by the date part of the timestamp
        presences = models.Personnel_Entries.objects.filter(timestamp__date=date)

    else:
        presences = models.Personnel_Entries.objects.all()

    # Add presence data to the worksheet
    for row_num, presence in enumerate(presences, start=1):
        worksheet.write(row_num, 0, presence.id)
        worksheet.write(row_num, 1, presence.personnel.name if presence.personnel else "Unknown")
        worksheet.write(row_num, 2, presence.personnel.employment_status if presence.personnel else "Unknown")
        worksheet.write(row_num, 3, presence.timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        worksheet.write(row_num, 4, presence.presence_status)
        worksheet.write(row_num, 5, presence.camera_id)

    # Close the workbook
    workbook.close()

    # Create an HTTP response with the Excel file
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    file_name = f"presence_data_{date if date else 'all'}.xlsx"
    response["Content-Disposition"] = f"attachment; filename={file_name}"

    # Write the Excel data to the response
    response.write(output.getvalue())
    return response
