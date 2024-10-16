import json
from datetime import datetime, timedelta
import pytz
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.db import connection
from django.utils import timezone


@csrf_exempt
def presence(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        personnel_id = data.get('personnel_id')
        camera_id = data.get('camera_id')
        timestamp_str = data.get('timestamp')

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
                    INSERT INTO dashboard_personnel_entries (camera_id, personnel_id, timestamp, presence_status)
                    VALUES (%s, %s, %s, %s)
                    ''',
                    [camera_id, personnel_id, detected_time, status]
                )
            return JsonResponse({'status': 'success', 'message': f'Entry saved as {status}.', 'time': detected_time.strftime('%Y-%m-%d %H:%M:%S')})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

    elif request.method == 'GET':
        try:
            # Get date filter from the frontend, or use today's date as default
            today = request.GET.get(
                'date', timezone.now().date().strftime('%Y-%m-%d'))

            # SQL query to fetch personnel entries for the given date
# SQL query to fetch personnel entries for the given date
            query = '''
            SELECT personnel_id, 
                DATE(timestamp) AS date, 
                MIN(CASE WHEN presence_status = 'ONTIME' OR presence_status = 'LATE' THEN TIME(timestamp) END) AS time_attend, 
                MAX(CASE WHEN presence_status = 'LEAVE' THEN TIME(timestamp) END) AS time_leaving, 
                TIMEDIFF(
                    MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), 
                    MIN(CASE WHEN presence_status = 'ONTIME' OR presence_status = 'LATE' THEN timestamp END)
                ) - INTERVAL 1 HOUR AS work_hours,
                MAX(presence_status) AS presence_status,
                CASE 
                    WHEN TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status = 'ONTIME' OR presence_status = 'LATE' THEN timestamp END)) > '08:00:00' 
                    THEN CONCAT('Overtime ', HOUR(TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status = 'ONTIME' OR presence_status = 'LATE' THEN timestamp END))) - 9, ' hours')
                    WHEN TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status = 'ONTIME' OR presence_status = 'LATE' THEN timestamp END)) < '08:00:00' 
                    THEN CONCAT('Less time ', 9 - HOUR(TIMEDIFF(MAX(CASE WHEN presence_status = 'LEAVE' THEN timestamp END), MIN(CASE WHEN presence_status = 'ONTIME' OR presence_status = 'LATE' THEN timestamp END))), ' hours')
                    ELSE 'Standard Time'
                END AS notes
            FROM dashboard_personnel_entries 
            WHERE DATE(timestamp) = %s
            GROUP BY personnel_id, DATE(timestamp)
            '''

            with connection.cursor() as cursor:
                cursor.execute(query, [today])
                entries = cursor.fetchall()

            # Prepare context for rendering in the template
            context = {
                'entries': entries,
                'today': today  # Pass the selected or default date
            }

            # Render the presence data in the template
            return render(request, 'presence.html', context)

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})