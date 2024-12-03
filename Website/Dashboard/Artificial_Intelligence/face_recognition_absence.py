import os
import warnings
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  
warnings.filterwarnings('ignore')
import cv2
import numpy as np
# import pandas as pd
from datetime import datetime
import shutil
# from deepface import DeepFace
import torch
from facenet_pytorch import InceptionResnetV1
import glob
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import json

# Inisialisasi path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURED_IMG_DIR = os.path.join(BASE_DIR, 'static', 'img', 'extracted_faces', 'raw')
PERSONNEL_PICS_DIR = os.path.join(BASE_DIR, 'static', 'img', 'personnel_pics')
PREDICTED_ABSENCE_DIR = os.path.join(BASE_DIR, 'static', 'img', 'extracted_faces', 'predicted_faces', 'absence')
PREDICTED_NOT_SAVED_DIR = os.path.join(BASE_DIR, 'static', 'img', 'extracted_faces', 'predicted_faces', 'not_saved') 
PREDICTED_UNKNOWN_DIR = os.path.join(BASE_DIR, 'static', 'img', 'extracted_faces', 'predicted_faces', 'unknown')
JSON_PATH = os.path.join(BASE_DIR, 'static', 'attendance' , 'attendance.json')

# Membuat direktori jika belum ada
for dir_path in [PREDICTED_ABSENCE_DIR, PREDICTED_NOT_SAVED_DIR, PREDICTED_UNKNOWN_DIR, CAPTURED_IMG_DIR]:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

# Inisialisasi model FaceNet
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
resnet = InceptionResnetV1(pretrained='vggface2').eval().to(device)

def extract_datetime_from_filename(filename):
    try:
        # Hapus ekstensi file
        filename = os.path.splitext(filename)[0]
        
        # Memisahkan string berdasarkan underscore
        parts = filename.split('_')
        
        # Ambil dua bagian terakhir dari nama file
        if len(parts) < 2:
            return None
        
        # Ambil bagian terakhir dan kedua terakhir
        date_str = parts[-2]
        time_str = parts[-1]
        
        # Periksa apakah bagian terakhir adalah format tanggal (YYYYMMDD) dan waktu (HHMMSS)
        if len(date_str) == 8 and date_str.isdigit() and len(time_str) == 6 and time_str.isdigit():
            datetime_str = f"{date_str}_{time_str}"
            return datetime.strptime(datetime_str, '%Y%m%d_%H%M%S')
        
        return None
        
    except Exception as e:
        print(f"Error parsing datetime from filename {filename}: {str(e)}")
        return None

def get_embedding(img_path):
    # Baca dan resize gambar ke ukuran yang diharapkan oleh InceptionResnetV1 (160x160)
    img = cv2.imread(img_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (160, 160))
    
    # Konversi ke tensor dan normalisasi
    img = torch.from_numpy(img.transpose((2, 0, 1))).float()
    img = img.unsqueeze(0)  # Tambahkan dimensi batch
    img = img / 255.0  # Normalisasi ke range [0,1]
    
    # Pindahkan ke device yang sama dengan model
    img = img.to(device)
    
    # Dapatkan embedding
    with torch.no_grad():
        embedding = resnet(img).detach().cpu().numpy()
    return embedding[0]

def load_database():
    database = {}
    for person_dir in os.listdir(PERSONNEL_PICS_DIR):
        person_path = os.path.join(PERSONNEL_PICS_DIR, person_dir)
        if os.path.isdir(person_path):
            embeddings = []
            for img_path in glob.glob(os.path.join(person_path, "*.jpg")):
                embedding = get_embedding(img_path)
                if embedding is not None:
                    embeddings.append(embedding)
            if embeddings:
                database[person_dir] = np.array(embeddings)
    return database

def cosine_similarity(embedding1, embedding2):
    return np.dot(embedding1, embedding2) / (np.linalg.norm(embedding1) * np.linalg.norm(embedding2))

def predict_face(img_path, database):
    embedding = get_embedding(img_path)
    if embedding is None:
        return None, 0
    
    max_similarity = 0
    predicted_person = None
    
    for person, person_embeddings in database.items():
        similarities = [cosine_similarity(embedding, ref_embedding) for ref_embedding in person_embeddings]
        avg_similarity = np.mean(similarities)
        
        if avg_similarity > max_similarity:
            max_similarity = avg_similarity
            predicted_person = person
            
    return predicted_person, max_similarity


def process_attendance():
    print("="*50)
    print("Memulai proses attendance...")
    print(f"Checking directory: {CAPTURED_IMG_DIR}")
    
    # Load database foto wajah personnel
    database = load_database()
    if not database:
        print("Database kosong! Pastikan ada foto referensi di folder personnel_pics")
        return
    print(f"Database loaded with {len(database)} entries: {list(database.keys())}")
    
    # Membuat direktori untuk file JSON jika belum ada
    attendance_date = datetime.now().date()
    daily_json_path = os.path.join(BASE_DIR, 'static', 'attendance', f'{attendance_date}.json')

    # Membuat atau membaca JSON untuk hari ini
    if not os.path.exists(daily_json_path):
        attendance_data = []
        print(f"Membuat file JSON baru untuk {attendance_date}!")
    else:
        with open(daily_json_path, 'r') as f:
            content = f.read()
            if content:  # Memastikan file tidak kosong
                attendance_data = json.loads(content)
                print(f"Membaca JSON yang ada: {len(attendance_data)} records!")
            else:
                attendance_data = []
                print("File JSON kosong, membuat data baru!")
    
    # Memproses setiap gambar di folder raw
    raw_images = [f for f in os.listdir(CAPTURED_IMG_DIR) if f.endswith(('.jpg', '.jpeg', '.png'))]
    print(f"Ditemukan {len(raw_images)} gambar di folder raw!")
    
    for img_file in raw_images:
        print(f"\nMemproses gambar: {img_file}")
        img_path = os.path.join(CAPTURED_IMG_DIR, img_file)
        
        try:
            # Ekstrak datetime dari nama file
            detection_time = extract_datetime_from_filename(img_file)
            if detection_time is None:
                print(f"Format nama file tidak valid: {img_file}")
                new_filename = f"unknown_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                unknown_path = os.path.join(PREDICTED_UNKNOWN_DIR, new_filename)
                shutil.move(img_path, unknown_path)
                print(f"File dipindahkan ke: {unknown_path}")
                continue
            
            # Deteksi wajah dan dapatkan embedding
            embedding = get_embedding(img_path)
            if embedding is None:
                print(f"Tidak ada wajah terdeteksi dalam {img_file}")
                new_filename = f"unknown_{detection_time.strftime('%Y%m%d_%H%M%S')}.jpg"
                unknown_path = os.path.join(PREDICTED_UNKNOWN_DIR, new_filename)
                shutil.move(img_path, unknown_path)
                print(f"File dipindahkan ke: {unknown_path}")
                continue
            
            # Prediksi wajah
            predicted_name, confidence = predict_face(img_path, database)
            current_date = detection_time.date()
            
            # Definisikan status berdasarkan kondisi yang ada
            if confidence >= 0.70:
                # Cek apakah sudah ada data untuk orang ini hari ini
                current_date_str = current_date.strftime('%Y-%m-%d')
                today_records = [record for record in attendance_data 
                                if datetime.strptime(record['datetime'], '%Y-%m-%d %H:%M:%S').date().strftime('%Y-%m-%d') == current_date_str]
                person_today = [record for record in today_records if record['name'] == predicted_name]
                
                # if not person_today:
                    # Buat folder berdasarkan tanggal di absence
                date_folder = os.path.join(PREDICTED_ABSENCE_DIR, detection_time.strftime('%Y%m%d'))
                if not os.path.exists(date_folder):
                    os.makedirs(date_folder)
                
                # Format nama file baru: nama_YYYYMMDD_HHMMSS.jpg
                new_filename = f"{predicted_name}_{detection_time.strftime('%Y%m%d_%H%M%S')}.jpg"
                new_path = os.path.join(date_folder, new_filename)
                
                new_record = {
                    'name': predicted_name,
                    'datetime': detection_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'confidence': float(confidence),
                    'image_path': os.path.relpath(new_path, BASE_DIR).replace("\\", "/")
                }
                attendance_data.append(new_record)
                shutil.move(img_path, new_path)
                print(f"Absensi berhasil: {predicted_name} ({confidence:.2f})")
                print(f"File dipindahkan ke: {new_path}")
                # else:
                #     # Jika sudah ada data untuk hari yang sama
                #     print(f"Sudah absen hari ini: {predicted_name}")
                #     # Simpan file di not_saved
                #     date_folder = os.path.join(PREDICTED_NOT_SAVED_DIR, detection_time.strftime('%Y%m%d'))
                #     if not os.path.exists(date_folder):
                #         os.makedirs(date_folder)
                    
                #     new_filename = f"{predicted_name}_{detection_time.strftime('%Y%m%d_%H%M%S')}.jpg"
                #     new_path = os.path.join(date_folder, new_filename)
                #     shutil.move(img_path, new_path)
                #     print(f"File dipindahkan ke: {new_path}")
            else:
                # Confidence rendah, simpan sebagai unknown
                new_filename = f"unknown_{detection_time.strftime('%Y%m%d_%H%M%S')}.jpg"
                new_path = os.path.join(PREDICTED_UNKNOWN_DIR, new_filename)
                shutil.move(img_path, new_path)
                print(f"Wajah tidak dikenali (confidence: {confidence:.2f})")
                print(f"File dipindahkan ke: {new_path}")
                
        except Exception as e:
            print(f"Error memproses {img_file}: {str(e)}")
            new_filename = f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            unknown_path = os.path.join(PREDICTED_UNKNOWN_DIR, new_filename)
            shutil.move(img_path, unknown_path)
            print(f"File dipindahkan ke: {unknown_path}")
            continue
    
    # Simpan JSON harian
    with open(daily_json_path, 'w') as f:
        json.dump(attendance_data, f, indent=4)
    
    # Verifikasi folder raw
    remaining_files = os.listdir(CAPTURED_IMG_DIR)
    if remaining_files:
        print(f"Peringatan: Masih ada {len(remaining_files)} file di folder raw")
    else:
        print("Semua file berhasil diproses dan dipindahkan")

class ImageHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(('.jpg', '.jpeg', '.png')):
            process_attendance()

def run_face_recognition_service():
    print("="*50)
    print("Starting face recognition monitoring service...")
    print(f"Monitoring directory: {CAPTURED_IMG_DIR}")
    
    # Pastikan semua direktori yang diperlukan sudah ada
    for dir_path in [CAPTURED_IMG_DIR, PREDICTED_ABSENCE_DIR, PREDICTED_NOT_SAVED_DIR, PREDICTED_UNKNOWN_DIR]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

    # Set up file system observer
    event_handler = ImageHandler()
    observer = Observer()
    observer.schedule(event_handler, CAPTURED_IMG_DIR, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    print("Starting Face Recognition Service...")
    # Jalankan proses attendance pertama kali
    process_attendance()
    # Kemudian jalankan service monitoring
    run_face_recognition_service()
