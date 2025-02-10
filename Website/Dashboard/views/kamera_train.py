import cv2
import os
import numpy as np
from django.shortcuts import render
from django.http import JsonResponse, StreamingHttpResponse

# Inisialisasi Haar Cascade untuk deteksi wajah
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
dataset_folder = 'dataset_wajah'
model_path = 'model_lbph.xml'

if not os.path.exists(dataset_folder):
    os.makedirs(dataset_folder)

def capture_faces(request):
    if request.method == 'POST':
        face_id = request.POST.get('face_id')
        if not face_id:
            return JsonResponse({'status': 'error', 'message': 'ID wajah diperlukan.'})

        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # Inisialisasi kamera
        if not cap.isOpened():
            return JsonResponse({'status': 'error', 'message': 'Gagal membuka kamera.'})

        count = 0  # Inisialisasi variabel count
        captured_faces = 0  # Menghitung jumlah wajah yang disimpan

        while captured_faces < 10:
            ret, frame = cap.read()
            if not ret:
                break  # Jika gagal membaca frame, hentikan proses

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces_detected = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

            for (x, y, w, h) in faces_detected:
                face = gray[y:y + h, x:x + w]
                count += 1
                file_name = os.path.join(dataset_folder, f"face_{face_id}_{count}.jpg")
                cv2.imwrite(file_name, face)
                captured_faces += 1  # Hitung wajah yang sudah disimpan

            # Tampilkan frame (Opsional untuk debugging)
            cv2.imshow("Capturing Faces", frame)
            cv2.waitKey(1)  # Tunggu sebentar untuk menghindari error

        cap.release()
        cv2.destroyAllWindows()

        return JsonResponse({'status': 'success', 'message': 'Pengambilan gambar selesai.'})

    return render(request, 'employee/capture.html')

def train_model(request):
    faces = []
    labels = []
    target_size = (200, 200)

    for file_name in os.listdir(dataset_folder):
        if file_name.endswith('.jpg'):
            img_path = os.path.join(dataset_folder, file_name)
            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            img = cv2.resize(img, target_size)
            label = int(file_name.split('_')[1])  # Ekstraksi ID wajah dari nama file
            faces.append(img)
            labels.append(np.int32(label))  # Pastikan label dalam format numpy int32

    if len(faces) > 0:
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.train(np.array(faces), np.array(labels))
        recognizer.save(model_path)
        return JsonResponse({'status': 'success', 'message': 'Model berhasil dilatih dan disimpan.'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Tidak ada data wajah untuk dilatih.'})

def recognize_face(request):
    cap = cv2.VideoCapture(0)  # Inisialisasi ulang setiap permintaan
    recognizer = cv2.face.LBPHFaceRecognizer_create()

    if not os.path.exists(model_path):
        return JsonResponse({'status': 'error', 'message': 'Model belum tersedia, latih model terlebih dahulu.'})

    recognizer.read(model_path)

    def generate_frames():
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces_detected = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

            for (x, y, w, h) in faces_detected:
                face = cv2.resize(gray[y:y+h, x:x+w], (200, 200))  # Resize sesuai ukuran saat pelatihan
                label, confidence = recognizer.predict(face)

                # Gambar kotak di sekitar wajah
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
                cv2.putText(frame, f'Label: {label} ({confidence:.2f})', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            ret, jpeg = cv2.imencode('.jpg', frame)
            if not ret:
                break

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')

        cap.release()

    return StreamingHttpResponse(generate_frames(), content_type='multipart/x-mixed-replace; boundary=frame')

def predict_video(request):
    """View untuk streaming video dengan deteksi objek."""
    return recognize_face(request)

def dataset(request):
    images = []
    if os.path.exists(dataset_folder):
        for file_name in os.listdir(dataset_folder):
            if file_name.endswith('.jpg'):
                images.append({
                    'url': f'/media/{file_name}',  # Sesuaikan dengan konfigurasi MEDIA_URL
                    'face_id': file_name.split('_')[1]  # Ambil ID dari nama file
                })
    return render(request, 'employee/dataset.html', {'images': images})
