import json
from datetime import datetime, timedelta
import pytz
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.db import connection
from django.utils import timezone
import base64  
from django.core.files import File  # For handling file operations
from django.conf import settings  # To access settings
import os


@csrf_exempt
def presence(request):
    presence_path = os.path.join(settings.BASE_DIR, 'dashboard', 'static', 'img', 'presence_folder')
    if request.method == 'POST':
        data = json.loads(request.body)
        personnel_id = data.get('personnel_id')
        camera_id = data.get('camera_id')
        timestamp_str = data.get('timestamp')
        command = data.get('command')
        image_data = data.get('image')
        
        image_path = None

        if image_data:
            try:
                # Decode the base64 image data
                header, encoded = image_data.split(',', 1)
                image = base64.b64decode(encoded)

                # Define the image filename
                image_filename = f"{personnel_id}_{timestamp_str.replace(' ', '_')}.jpg"
                image_path = os.path.join(presence_path, image_filename)

                # Save the image file
                with open(image_path, 'wb') as f:
                    f.write(image)

            except Exception as e:
                return JsonResponse({'status': 'error', 'message': f'Image save error: {str(e)}'})

        if command == "presence-data":
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
                    attended_time = entry[2].strftime('%H:%M:%S') if entry[2] else '-'
                    leaving_time = entry[3].strftime('%H:%M:%S') if entry[3] else '-'
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
            
            


        # Convert timestamp string from AI to timezone-aware datetime object
        local_tz = pytz.timezone('Asia/Jakarta')
        try:
            detected_time = local_tz.localize(
                datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S'))
        except ValueError:
            return JsonResponse({'status': 'error', 'message': 'Invalid timestamp format. Use YYYY-MM-DD HH:MM:SS.'})

        try:
            # Get camera settings (simplified)
            with connection.cursor() as cursor:
                cursor.execute(
                    'SELECT attendance_time_start, attendance_time_end, leaving_time_start, leaving_time_end FROM dashboard_camera_settings WHERE id = %s', [camera_id])
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

            current_time = detected_time.time()  # Get only the time from detected_time
            status = 'UNKNOWN'  # Default status

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

            # Insert the new status entry if valid
            with connection.cursor() as cursor:
                cursor.execute(
                    '''
                    INSERT INTO dashboard_personnel_entries (camera_id, personnel_id, timestamp, presence_status, image)
                    VALUES (%s, %s, %s, %s)
                    ''',
                    [camera_id, personnel_id, detected_time, status,image_path]
                )
            return JsonResponse({'status': 'success', 'message': f'Entry saved as {status}.', 'time': detected_time.strftime('%Y-%m-%d %H:%M:%S')})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

    elif request.method == 'GET':
        try:
            # Get date filter from the frontend, or use today's date as default
            today = request.GET.get('date', timezone.now().date().strftime('%Y-%m-%d'))
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
                attended_time = entry[2].strftime('%H:%M:%S') if entry[2] else '-'
                leaving_time = entry[3].strftime('%H:%M:%S') if entry[3] else '-'

                # Calculate work hours if both attended and leaving times are available
                if entry[2] and entry[3]:
                    # Convert to datetime objects if they aren't already
                    attended_dt = entry[2]
                    leaving_dt = entry[3]
                    
                    # Calculate the time difference
                    work_duration = leaving_dt - attended_dt

                    # Format the work hours as hours and minutes
                    hours_worked = work_duration.seconds // 3600  # Total hours
                    minutes_worked = (work_duration.seconds % 3600) // 60  # Total minutes
                    work_hours = f"{hours_worked} hours, {minutes_worked} minutes"
                else:
                
                    work_hours = 'Still Working'

                presence_data.append({
                    'id': entry[0],
                    'name': entry[1],
                    'attended': attended_time,
                    'leave': leaving_time,
                    'status': entry[4],
                    'work_hours': work_hours,
                    'notes': entry[6] or 'No notes',
                    'image_path': entry[7] or 'No image'
                })

            print(presence_data)

            # Render the presence data in the template
            return render(request, 'presence.html', {'presence_data': presence_data, 'today': today, 'Page': "Presence"})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})
