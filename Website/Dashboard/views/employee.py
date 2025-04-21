from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from ..decorators import role_required
from .. import models
from django.utils import timezone
from datetime import datetime
from django.db import connection
import os
from django.http import JsonResponse
from django.utils.timezone import localdate

DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@login_required(login_url='login')
@role_required('employee')
def employee_home(request):
    user = models.Personnels.objects.filter(user=request.user).first()
    presence_data = get_presence_data(datetime.now().date(), personnel_id=user.id)

    context = {
        'presence_data': presence_data,
    }
    
    return render(request, 'employee/dashboard.html', context)

def presence_history(request):
    user = models.Personnels.objects.filter(user=request.user).first()
    date_str = request.GET.get('date')  # Ambil parameter tanggal dari frontend

    if date_str:
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            date = None
    else:
        date = None  # Tidak ada filter tanggal

    presence_data = get_presence_data(date, personnel_id=user.id)

    context = {
        'presence_data': presence_data,
        'selected_date': date_str if date else None,  # Kirim tanggal ke template
    }

    return render(request, 'employee/presence_history.html', context)


def get_presence_data(date=None, personnel_id=None):
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
            AND presence_status IN ('ONTIME', 'LATE')
            ORDER BY timestamp DESC 
            LIMIT 1
            ) AS attendance_image,
            (SELECT d.image 
            FROM dashboard_personnel_entries AS d 
            WHERE d.personnel_id = p.id 
            AND presence_status = 'LEAVE'
            ORDER BY timestamp DESC 
            LIMIT 1
            ) AS leaving_image
        FROM 
            dashboard_personnel_entries AS d
        JOIN 
            dashboard_personnels AS p ON p.id = d.personnel_id
    '''
    
    params = []

    # Tambahkan filter tanggal jika ada
    if date:
        query += " WHERE DATE(d.timestamp) = %s"
        params.append(date)

    # Tambahkan filter personnel jika ada
    if personnel_id:
        query += " AND p.id = %s" if date else " WHERE p.id = %s"
        params.append(personnel_id)

    # Group by agar satu entri per orang
    query += " GROUP BY p.id"

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        entries = cursor.fetchall()

    presence_data = []
    for entry in entries:
        attended_time = entry[2].strftime('%H:%M:%S') if entry[2] else '-'
        leaving_time = entry[3].strftime('%H:%M:%S') if entry[3] else '-'

        attendance_image_path = os.path.relpath(entry[7], start=DIR) if entry[7] else 'No image'
        leaving_image_path = os.path.relpath(entry[8], start=DIR) if entry[8] else 'No image'

        presence_data.append({
            'id': entry[0],
            'name': entry[1],
            'date': entry[2].date() if entry[2] else '-',
            'attended': attended_time,
            'leave': leaving_time,
            'status': entry[4],
            'work_hours': entry[5] or 'Still Working',
            'notes': entry[6] or 'No notes',
            'attendance_image_path': attendance_image_path,
            'leaving_image_path': leaving_image_path,
        })

    return presence_data


@login_required(login_url='login')
@role_required('employee')
def take_image(request):
    employee = models.Personnels.objects.get(user=request.user)
    name = employee.name
    return render(request, 'employee/take_image.html', {'name':name})


