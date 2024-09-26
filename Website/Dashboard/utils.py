# utils.py
from datetime import datetime, time
from .models import Personnel_Entries, AttendanceReport

def determine_attendance_status(personnel, date):
    """
    Determines the attendance status for a personnel on a given date.
    """
    # Define the time thresholds
    ontime_start = time(7, 30)
    ontime_end = time(8, 10)
    leave_time = time(17, 0)

    # Fetch all entries for the personnel on the given date
    entries = Personnel_Entries.objects.filter(
        name=personnel.name,
        timestamp__date=date
    ).order_by('timestamp')

    status = None
    time_detected = None

    if not entries.exists():
        # No entry detected; consider as Absent or handle accordingly
        return None

    first_entry = entries.first()
    first_entry_time = first_entry.time_in

    # Check if detected between 07:30 and 08:10
    if ontime_start <= first_entry_time <= ontime_end:
        status = 'ONTIME'
    elif first_entry_time > ontime_end and first_entry_time < leave_time:
        status = 'LATE'
    elif first_entry_time >= leave_time:
        status = 'LEAVE'

    if status:
        AttendanceReport.objects.update_or_create(
            personnel=personnel,
            date=date,
            status=status,
            defaults={'time_detected': first_entry_time}
        )

    return status

def generate_daily_attendance_report(date=None):
    """
    Generates attendance reports for all personnel for a given date.
    If date is None, defaults to today.
    """
    if date is None:
        date = datetime.now().date()

    personnel_list = Personnels.objects.all()

    for personnel in personnel_list:
        determine_attendance_status(personnel, date)
