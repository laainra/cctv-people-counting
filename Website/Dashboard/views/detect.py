import cv2
from django.http import StreamingHttpResponse
from ..Artificial_Intelligence.object import detect_objects
from django.shortcuts import render

def generate_frames():
    """
    Generator untuk streaming frame video dengan deteksi objek.
    """
    cap = cv2.VideoCapture(0)  # 0 untuk kamera default
    if not cap.isOpened():
        raise Exception("Cannot open camera")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Deteksi objek pada frame
        annotated_frame, detected_classes, results = detect_objects(frame)

        # Simpan gambar jika objek tertentu terdeteksi
        for i, label in enumerate(results[0].boxes.cls):
            detected_class = detected_classes[int(label)]
            if detected_class == 'ID-card':  # Ganti dengan class yang sesuai
                # Simpan gambar ke file atau database jika perlu
                pass

        # Encode frame sebagai JPEG
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        if not ret:
            continue

        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    cap.release()

def predict_video(request):
    """
    View untuk streaming video dengan deteksi objek.
    """
    return StreamingHttpResponse(generate_frames(), content_type='multipart/x-mixed-replace; boundary=frame')


def live_detection_page(request):
    """
    View untuk merender halaman dengan live video stream.
    """
    return render(request, 'live_detection.html')