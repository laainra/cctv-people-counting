from datetime import datetime

# Misalkan attendance_start dan attendance_end adalah waktu dalam format datetime.time
attendance_start = datetime.strptime('08:00:00', '%H:%M:%S').time()
attendance_end = datetime.strptime('09:00:00', '%H:%M:%S').time()
leaving_start = datetime.strptime('17:00:00', '%H:%M:%S').time()
leaving_end = datetime.strptime('18:00:00', '%H:%M:%S').time()

# Waktu yang terdeteksi, yang juga merupakan objek datetime.time
current_time = datetime.strptime('08:30:00', '%H:%M:%S').time()

# Tentukan status berdasarkan waktu yang terdeteksi
if attendance_start <= current_time <= attendance_end:
    status = 'ONTIME'
elif leaving_start <= current_time <= leaving_end:
    status = 'LEAVE'
else:
    status = 'LATE'

print(status)
