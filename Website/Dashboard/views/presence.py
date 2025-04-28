from django.utils.timezone import localtime
from datetime import date
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
    # print("Starting Read Attendance JSON data...")
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
        
        # print("Attendance JSON data read successfully.")
        return data_list

    except json.JSONDecodeError as e:
        print("Error reading JSON file: Invalid JSON format:", e)
        return []
    except Exception as e:
        print("Error reading JSON file:", e)
        return []


# Insert presence data into the database
def insert_presence(cam_id, personnel_id, detected_time, status, image_path):
    # print(f"Starting insert presence data for {personnel_id}...")

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

def process_attendance_entry(data):
    # print("Starting proccess attendance entry...")
    name = data.get('name')
    datetime_str = data.get('datetime')
    image_path = data.get('image_path')
    cam_id= data.get('camera_id') 
    # cam_id = cam.lstrip('cam') 
    # cam_id = int(cam) 
    print(cam_id)
    detected_time = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')

    try:
        personnel = models.Personnels.objects.get(name=name)
        personnel_id = personnel.id
    except models.Personnels.DoesNotExist:
        print(f"Personnel '{name}' not found.")
        return

    # Ambil pengaturan kamera
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT attendance_time_start, attendance_time_end, leaving_time_start, leaving_time_end 
            FROM dashboard_camera_settings 
            WHERE id = %s AND role_camera IN ('P_IN', 'P_OUT')
        """, [cam_id])
        camera = cursor.fetchone()
    
    if not camera:
        print("Camera settings not found or not a P_IN/P_OUT camera.")
        return


    print("DEBUG: Isi camera sebelum parsing waktu:", camera)
    current_time = detected_time.time()


    try:
        attendance_start = datetime.strptime(camera[0], '%H:%M:%S').time() if camera[0] else None
        attendance_end = datetime.strptime(camera[1], '%H:%M:%S').time() if camera[1] else None
        leaving_start = datetime.strptime(camera[2], '%H:%M:%S').time() if camera[2] else None
        leaving_end = datetime.strptime(camera[3], '%H:%M:%S').time() if camera[3] else None
    except (TypeError, ValueError):
        print("Invalid camera time format detected.")
        return

    # Tentukan status berdasarkan waktu yang terdeteksi
    if attendance_start and attendance_end and attendance_start <= current_time <= attendance_end:
        status = 'ONTIME'
    elif leaving_start and leaving_end and leaving_start <= current_time <= leaving_end:
        status = 'LEAVE'
    else:
        if attendance_end and leaving_start and attendance_end < current_time < leaving_start:
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
    return True
    
# Main function to process presence
def presence_process():
    # print(f"Starting Process Presence for {cam_id}...")
    data_list = read_attendance_data()
    
    # Process each entry
    for data in data_list:
        process_attendance_entry(data)
        
    # print("Presence data processed successfully.")
    # delete_attendance_file()
    return {'status': 'success', 'message': 'Attendance data processed successfully'}

def get_presence_data(date, personnel_id=None, company=None):
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
            AND presence_status IN ('ONTIME', 'LATE')
            ORDER BY timestamp DESC 
            LIMIT 1
            ) AS attendance_image_path,
            (SELECT d.image 
            FROM dashboard_personnel_entries AS d 
            WHERE d.personnel_id = p.id 
            AND DATE(d.timestamp) = %s
            AND presence_status = 'LEAVE'
            ORDER BY timestamp DESC 
            LIMIT 1
            ) AS leaving_image_path
        FROM 
            dashboard_personnel_entries AS d
        JOIN 
            dashboard_personnels AS p ON p.id = d.personnel_id
        WHERE 
            DATE(d.timestamp) = %s
    '''
    
    params = [date, date, date, date]

    if personnel_id:
        query += " AND p.id = %s"
        params.append(personnel_id)
    
    if company:
        query += " AND p.company_id = %s"  # Assuming company_id is the foreign key in the personnels table
        params.append(company.id)  # Use company.id to filter by the company

    query += " GROUP BY p.id"

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        entries = cursor.fetchall()

    presence_data = []
    for entry in entries:
        attended_time = entry[2].strftime('%H:%M:%S') if entry[2] else '-'
        leaving_time = entry[3].strftime('%H:%M:%S') if entry[3] else '-'

        work_hours = entry[5] or 'Still Working'
        dashboard_dir = os.path.join(DIR, 'Dashboard')
        attendance_image_path = os.path.relpath(entry[7], start=dashboard_dir) if entry[7] else 'No image'
        leaving_image_path = os.path.relpath(entry[8], start=dashboard_dir) if entry[8] else 'No image'

        presence_data.append({
            'id': entry[0],
            'name': entry[1],
            'attended': attended_time,
            'leave': leaving_time,
            'status': entry[4],
            'work_hours': work_hours,
            'notes': entry[6] or 'No notes',
            'attendance_image_path': attendance_image_path,
            'leaving_image_path': leaving_image_path,
        })
    
    print("Presence data retrieved successfully: ", presence_data)
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



def get_active_cam_ids():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id FROM dashboard_camera_settings 
            WHERE cam_is_active = 1 
            AND role_camera IN ('p_in', 'p_out')
        """)
        active_cam_ids = cursor.fetchall()
        return [cam_id[0] for cam_id in active_cam_ids] 

# @csrf_exempt
# @login_required(login_url='login')
# @role_required('admin')
# def presence(request):
#     try:
#         today = request.GET.get('date', timezone.now().date().strftime('%Y-%m-%d'))
#         personnel_id = request.GET.get('personnel_id')
#         presence_data = get_presence_data(today, personnel_id)
#         status = get_presence_by_status(today)
#         personnel_list = models.Personnels.objects.all()
#         print(presence_data)  # Debugging line
#         return JsonResponse({'presence_data': presence_data, 'date': today, 'status': status, 'personnel_list': list(personnel_list.values())})


#     except Exception as e:
#         print(f"Error: {str(e)}")  # Debugging line
#         return JsonResponse({'status': 'error', 'message': str(e)})
@csrf_exempt
@login_required(login_url='login')
@role_required('admin')
def presence(request):
    company = models.Company.objects.get(user=request.user)
    if request.method == "POST":
        cam_id = request.POST.get("cam_id")  # Get `cam_id` from POST request
        if not cam_id:
            cam_id = get_active_cam_ids()
            if not cam_id:
                return JsonResponse({'status': 'error', 'message': 'No active camera found'})

        if request.POST.get("command") == "presence-data":
            date = request.POST.get('date', timezone.now().date().strftime('%Y-%m-%d'))
            try:
                presence_data = get_presence_data(date, company)
                return JsonResponse({'status': 'success', 'presence_data': presence_data})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': str(e)})

        result = presence_process(cam_id)
        return JsonResponse(result)

    elif request.method == 'GET':
        try:
            today = request.GET.get('date', timezone.now().date().strftime('%Y-%m-%d'))
            filter_date = request.GET.get('filter_date', today)
            personnel_id = request.GET.get('personnel_id')
            presence_data = get_presence_data(filter_date, personnel_id, company=company)
            status = get_presence_by_status(today)
            company = models.Company.objects.get(user=request.user)
            personnel_list = models.Personnels.objects.filter(company=company)
            return render(request, 'admin/presence.html', {
                'presence_data': presence_data,
                'date': today,
                'status': status,
                'personnel_list': personnel_list,
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
        # active_cam_ids = get_active_cam_ids()
        # for cam_id in active_cam_ids:
        #     print(f"File created, running presence process for camera ID: {cam_id}")
        presence_process()
        print(f"Presence Proccess Executed Successfully")

    def on_modified(self, event):
        # Retrieve active camera IDs with role 'p_in' and 'p_out'
        # active_cam_ids = get_active_cam_ids()
        # for cam_id in active_cam_ids:
        #     print(f"File modified, running presence process for camera ID: {cam_id}")
        presence_process()
        print(f"Presence Proccess Executed Successfully ")

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

def get_today_presences(request):
    today = date.today()

    # The query from get_presence_data function
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
            AND presence_status IN ('ONTIME', 'LATE')
            ORDER BY timestamp DESC 
            LIMIT 1
            ) AS attendance_image_path,
            (SELECT d.image 
            FROM dashboard_personnel_entries AS d 
            WHERE d.personnel_id = p.id 
            AND DATE(d.timestamp) = %s
            AND presence_status = 'LEAVE'
            ORDER BY timestamp DESC 
            LIMIT 1
            ) AS leaving_image_path
        FROM 
            dashboard_personnel_entries AS d
        JOIN 
            dashboard_personnels AS p ON p.id = d.personnel_id
        WHERE 
            DATE(d.timestamp) = %s
        GROUP BY p.id
    '''
    
    params = [today, today, today, today]

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        entries = cursor.fetchall()

    presence_data = []
    for entry in entries:
        attended_time = entry[2].strftime('%H:%M:%S') if entry[2] else '-'
        leaving_time = entry[3].strftime('%H:%M:%S') if entry[3] else '-'

        work_hours = entry[5] or 'Still Working'
        dashboard_dir = os.path.join(DIR, 'Dashboard')
        attendance_image_path = os.path.relpath(entry[7], start=dashboard_dir) if entry[7] else 'No image'
        leaving_image_path = os.path.relpath(entry[8], start=dashboard_dir) if entry[8] else 'No image'

        presence_data.append({
            'id': entry[0],
            'name': entry[1],
            'attended': attended_time,
            'leave': leaving_time,
            'status': entry[4],
            'work_hours': work_hours,
            'notes': entry[6] or 'No notes',
            'attendance_image_path': attendance_image_path,
            'leaving_image_path': leaving_image_path,
        })
    
    print("Presence data retrieved successfully: ", presence_data)
    # del_img()
    return JsonResponse({'data': presence_data})

# def del_img():
#     today = date.today()

#     # The query to fetch image paths in the database
#     query = '''
#         SELECT 
#             d.image
#         FROM 
#             dashboard_personnel_entries AS d
#         WHERE 
#             DATE(d.timestamp) = %s
#         '''
#     params = [today]

#     with connection.cursor() as cursor:
#         cursor.execute(query, params)
#         # Fetch all image paths from the database
#         db_image_paths = [entry[0] for entry in cursor.fetchall()]

#     # Folder where images are stored
#     # dashboard_dir = os.path.join(DIR, 'Dashboard', 'static', 'img', 'extracted_faces',)
    
#     # Get all files in the directory
#     all_files = os.listdir(DIR)

#     # Remove files that are not in the database
#     for file in all_files:
#         file_path = os.path.join(DIR, file)
        
#         # Check if the file is not in the database list
#         if file not in db_image_paths:
#             try:
#                 # os.remove(file_path)  # Delete the file if not in the DB
#                 print(f"Deleted file: {file_path}")
#             except Exception as e:
#                 print(f"Error deleting file {file_path}: {str(e)}")

#     print("Deleted images in folder today")