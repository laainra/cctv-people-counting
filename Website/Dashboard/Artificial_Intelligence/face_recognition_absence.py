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
import pickle

# Initialize paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURED_IMG_DIR = os.path.join(BASE_DIR, 'static', 'img', 'extracted_faces', 'raw')
PERSONNEL_PICS_DIR = os.path.join(BASE_DIR, 'static', 'img', 'personnel_pics')
PREDICTED_ABSENCE_DIR = os.path.join(BASE_DIR, 'static', 'img', 'extracted_faces', 'predicted_faces', 'absence')
# PREDICTED_NOT_SAVED_DIR = os.path.join(BASE_DIR, 'static', 'img', 'extracted_faces', 'predicted_faces', 'not_saved') 
PREDICTED_UNKNOWN_DIR = os.path.join(BASE_DIR, 'static', 'img', 'extracted_faces', 'predicted_faces', 'unknown')
PREDICTED_BLURRY_DIR = os.path.join(BASE_DIR, 'static', 'img', 'extracted_faces', 'predicted_faces', 'blurry')
JSON_PATH = os.path.join(BASE_DIR, 'static', 'attendance' , 'attendance.json')
EMBEDDINGS_PATH = os.path.join(BASE_DIR, 'static', 'embeddings', 'personnel_embeddings.pkl')

# Create directories if not exist
for dir_path in [PREDICTED_ABSENCE_DIR, 
                #  PREDICTED_NOT_SAVED_DIR, 
                 PREDICTED_UNKNOWN_DIR, 
                 PREDICTED_BLURRY_DIR, 
                 CAPTURED_IMG_DIR]:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

# Initialize model
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
resnet = InceptionResnetV1(pretrained='vggface2').eval().to(device)

# Ensure embeddings directory exists
os.makedirs(os.path.dirname(EMBEDDINGS_PATH), exist_ok=True)

def extract_datetime_from_filename(filename):
    try:
        # Remove file extension
        filename = os.path.splitext(filename)[0]
        
        # Split string based on underscore
        parts = filename.split('_')
        
        date_str = None
        time_str = None

        for part in parts:
            if len(part) == 8 and part.isdigit():  # YYYYMMDD
                date_str = part
            elif len(part) == 6 and part.isdigit():  # HHMMSS
                time_str = part

        if date_str and time_str:
            datetime_str = f"{date_str}_{time_str}"
            return datetime.strptime(datetime_str, '%Y%m%d_%H%M%S')
        return None
        
    except Exception as e:
        print(f"Error parsing datetime from filename {filename}: {str(e)}")
        return None

def get_embedding(img_path):
    # Read image using OpenCV
    img = cv2.imread(img_path)
    if img is None:
        return None
    
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # Resize image to 160x160 (expected input size)
    img = cv2.resize(img, (160, 160))
    
    # Normalize image
    img = img.transpose((2, 0, 1))
    img = torch.from_numpy(img).float()
    img = img.unsqueeze(0)  # Add batch dimension
    
    # Normalize pixel values
    img = (img - 127.5) / 128.0
    
    # Move to appropriate device (CPU/GPU)
    img = img.to(device)
    
    # Get embedding
    with torch.no_grad():
        embedding = resnet(img).detach().cpu().numpy()
    return embedding[0]

def save_embeddings(database):
    """
    Save embeddings database to file
    """
    with open(EMBEDDINGS_PATH, 'wb') as f:
        pickle.dump(database, f)
    print(f"Embeddings saved to: {EMBEDDINGS_PATH}")

def load_embeddings():
    """
    Load embeddings from file if exists
    """
    if os.path.exists(EMBEDDINGS_PATH):
        with open(EMBEDDINGS_PATH, 'rb') as f:
            return pickle.load(f)
    return None

def load_database():
    # Try to load existing embeddings
    database = load_embeddings()
    if database is not None:
        print(f"Loaded existing embeddings for {len(database)} personnel")
        
        # Check if there are changes in the personnel directory
        need_update = False
        for person_dir in os.listdir(PERSONNEL_PICS_DIR):
            person_path = os.path.join(PERSONNEL_PICS_DIR, person_dir)
            if os.path.isdir(person_path):
                if person_dir not in database:
                    need_update = True
                    break
                # Cek jumlah file di folder
                n_files = len([f for f in os.listdir(person_path) if f.endswith(('.jpg', '.png'))])
                if len(database[person_dir]) != n_files:
                    need_update = True
                    break
        
        if not need_update:
            return database
        print("Changes detected in personnel directory, updating embeddings...")
    
    # If no embeddings or need update, regenerate
    database = {}
    for person_dir in os.listdir(PERSONNEL_PICS_DIR):
        person_path = os.path.join(PERSONNEL_PICS_DIR, person_dir)
        if os.path.isdir(person_path):
            print(f"Generating embeddings for: {person_dir}")
            embeddings = []
            for img_path in glob.glob(os.path.join(person_path, "*.jpg")) + glob.glob(os.path.join(person_path, "*.png")):
                embedding = get_embedding(img_path)
                if embedding is not None:
                    embeddings.append(embedding)
            if embeddings:
                database[person_dir] = np.array(embeddings)
    
    # Save new embeddings
    save_embeddings(database)
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
        max_sim = np.max(similarities)
        
        if max_sim > max_similarity:
            max_similarity = max_sim
            predicted_person = person
            
    return predicted_person, max_similarity

# Blur Detection
def is_image_blurry(image_path, threshold=100):
    """
    Mengecek apakah gambar blur menggunakan Laplacian variance.
    Args:
        image_path: Path ke file gambar
        threshold: Nilai ambang batas untuk menentukan blur (default: 100)
    Returns:
        Boolean: True jika gambar blur, False jika tidak
    """
    image = cv2.imread(image_path)
    if image is None:
        return True
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    print(f"Laplacian variance: {laplacian_var}")
    return laplacian_var < threshold

def process_attendance():
    print("="*50)
    print("Starting attendance process...")
    print(f"Checking directory: {CAPTURED_IMG_DIR}")
    
    # Load database of personnel photos
    database = load_database()
    if not database:
        print("Database is empty! Make sure there are reference photos in personnel_pics folder")
        return
    print(f"Database loaded with {len(database)} entries: {list(database.keys())}")
    
    # Create directory for JSON file if not exist
    attendance_date = datetime.now().date()
    daily_json_path = os.path.join(BASE_DIR, 'static', 'attendance', f'{attendance_date}.json')

    # Create or read JSON for today
    if not os.path.exists(daily_json_path):
        attendance_data = []
        print(f"Creating new JSON file for {attendance_date}!")
    else:
        with open(daily_json_path, 'r') as f:
            content = f.read()
            if content: 
                attendance_data = json.loads(content)
                print(f"Reading existing JSON: {len(attendance_data)} records!")
            else:
                attendance_data = []
                print("Empty JSON file, creating new data!")
    
    # Process each image in the raw folder
    raw_images = [f for f in os.listdir(CAPTURED_IMG_DIR) if f.endswith(('.jpg', '.jpeg', '.png'))]
    print(f"Found {len(raw_images)} images in the raw folder!")
    
    for img_file in raw_images:
        print(f"\nProcessing image: {img_file}")
        img_path = os.path.join(CAPTURED_IMG_DIR, img_file)
        
        try:
            # Cek blur sebelum memproses gambar
            if is_image_blurry(img_path):
                print(f"Image {img_file} is too blurry, skipping...")
                # Pindahkan gambar blur ke folder blurry
                new_filename = f"blurry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                blurry_path = os.path.join(PREDICTED_BLURRY_DIR, new_filename)
                shutil.move(img_path, blurry_path)
                print(f"File moved to: {blurry_path}")
                continue
                
            # Extract datetime from file name
            detection_time = extract_datetime_from_filename(img_file)
            if detection_time is None:
                print(f"Invalid file name format: {img_file}")
                new_filename = f"unknown_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                unknown_path = os.path.join(PREDICTED_UNKNOWN_DIR, new_filename)
                shutil.move(img_path, unknown_path)
                print(f"File moved to: {unknown_path}")
                continue
            
            # Detect face and get embedding
            embedding = get_embedding(img_path)
            if embedding is None:
                print(f"No face detected in {img_file}")
                new_filename = f"unknown_{detection_time.strftime('%Y%m%d_%H%M%S')}.jpg"
                unknown_path = os.path.join(PREDICTED_UNKNOWN_DIR, new_filename)
                shutil.move(img_path, unknown_path)
                print(f"File moved to: {unknown_path}")
                continue
            
            # Predict face
            predicted_name, confidence = predict_face(img_path, database)
            current_date = detection_time.date()
            
            # Extract camera ID from the filename
            camera_id = img_file.split('_')[-1].split('.')[0]  # Assuming the camera ID is the last part of the filename
            
            # Define status based on the conditions
            if confidence >= 0.75:
                # Check if there is already data for this person today
                current_date_str = current_date.strftime('%Y-%m-%d')
                today_records = [record for record in attendance_data 
                                if datetime.strptime(record['datetime'], '%Y-%m-%d %H:%M:%S').date().strftime('%Y-%m-%d') == current_date_str]
                person_today = [record for record in today_records if record['name'] == predicted_name]
                
                # if not person_today:
                    # Create folder based on date in absence
                date_folder = os.path.join(PREDICTED_ABSENCE_DIR, detection_time.strftime('%Y%m%d'))
                if not os.path.exists(date_folder):
                    os.makedirs(date_folder)
                
                # Format new file name: name_YYYYMMDD_HHMMSS.jpg
                new_filename = f"{predicted_name}_{detection_time.strftime('%Y%m%d_%H%M%S')}.jpg"
                new_path = os.path.join(date_folder, new_filename)
                
                new_record = {
                    'name': predicted_name,
                    'datetime': detection_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'confidence': float(confidence),
                    'image_path': os.path.relpath(new_path, BASE_DIR).replace("\\", "/"),
                    'camera_id': camera_id
                }
                attendance_data.append(new_record)
                shutil.move(img_path, new_path)
                print(f"Attendance successful: {predicted_name} ({confidence:.2f})")
                print(f"File moved to: {new_path}")
                # else:
                #     # If there is already data for the same day
                #     print(f"Already attended today: {predicted_name}")
                #     # Save file in not_saved
                #     date_folder = os.path.join(PREDICTED_NOT_SAVED_DIR, detection_time.strftime('%Y%m%d'))
                #     if not os.path.exists(date_folder):
                #         os.makedirs(date_folder)
                    
                #     new_filename = f"{predicted_name}_{detection_time.strftime('%Y%m%d_%H%M:%S')}.jpg"
                #     new_path = os.path.join(date_folder, new_filename)
                #     shutil.move(img_path, new_path)
                #     print(f"File moved to: {new_path}")
            else:
                # Low confidence, save as unknown
                new_filename = f"unknown_{detection_time.strftime('%Y%m%d_%H%M')}.jpg"
                new_path = os.path.join(PREDICTED_UNKNOWN_DIR, new_filename)
                shutil.move(img_path, new_path)
                print(f"Face not recognized (confidence: {confidence:.2f})")
                print(f"File moved to: {new_path}")
                
        except Exception as e:
            print(f"Error processing {img_file}: {str(e)}")
            new_filename = f"error_{datetime.now().strftime('%Y%m%d_%H%M')}.jpg"
            unknown_path = os.path.join(PREDICTED_UNKNOWN_DIR, new_filename)
            shutil.move(img_path, unknown_path)
            print(f"File moved to: {unknown_path}")
            continue
    
    # Save daily JSON
    with open(daily_json_path, 'w') as f:
        json.dump(attendance_data, f, indent=4)
    
    # Verify raw folder
    remaining_files = os.listdir(CAPTURED_IMG_DIR)
    if remaining_files:
        print(f"Warning: There are still {len(remaining_files)} files in the raw folder")
    else:
        print("All files have been successfully processed and moved")

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
    
    # Update directory initialization
    for dir_path in [CAPTURED_IMG_DIR, PREDICTED_ABSENCE_DIR, 
                    #  PREDICTED_NOT_SAVED_DIR, 
                     PREDICTED_UNKNOWN_DIR, 
                     PREDICTED_BLURRY_DIR]:
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
    # Run attendance process for the first time
    process_attendance()
    # Then run the monitoring service
    run_face_recognition_service()

