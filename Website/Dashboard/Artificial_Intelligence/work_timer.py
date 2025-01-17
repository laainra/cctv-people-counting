
import cv2
import os
import numpy as np
from datetime import datetime
import torch
from facenet_pytorch import InceptionResnetV1
import pickle
import concurrent.futures
from sklearn.metrics.pairwise import cosine_similarity

class RecognitionVariable:
    # Global Variable for known faces features
    known_features = {}

    # Model for face detector
    face_detector = cv2.FaceDetectorYN.create(os.path.join(os.path.dirname(__file__), 'models', 'face_detection_yunet_2023mar.onnx'), '', (0, 0))
    face_detector.setScoreThreshold(0.8)

    root_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'img', 'personnel_pics')

    def set_personnel_known_faces(personnel_name):
        embeddings = []
        dir_path = os.path.join(RecognitionVariable.root_path, personnel_name)

        for file in np.array(os.listdir(dir_path)):
            if file.endswith('.txt'):
                continue
            
            img = cv2.imread(os.path.join(dir_path, file))
            feats, _ = RecognitionVariable.get_feature(img)
            if len(feats) == 0:
                print('No face detected in', file)
                os.remove(os.path.join(dir_path, file))
            else:
                embeddings.append(feats[0])
        
        if len(embeddings) != 0: 
            RecognitionVariable.known_features[personnel_name] = embeddings

    def set_all_known_faces():
        if not os.path.exists(RecognitionVariable.root_path):
            os.mkdir(RecognitionVariable.root_path)

        for dir_name in os.listdir(RecognitionVariable.root_path):
            RecognitionVariable.set_personnel_known_faces(dir_name)

    def get_feature(img):
        RecognitionVariable.face_detector.setInputSize((img.shape[1], img.shape[0]))
        _, faces = RecognitionVariable.face_detector.detect(img)
        faces = faces if faces is not None else []
        features = []

        for face in faces:
            aligned_face = img[int(face[1]):int(face[1] + face[3]), int(face[0]):int(face[0] + face[2])]
            aligned_face = cv2.resize(aligned_face, (112, 112))  # Resize to the required size
            features.append(aligned_face)

        return features, faces

class FaceRecognition:
    def __init__(self):
        # Model for face recognition
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.face_recognizer = InceptionResnetV1(pretrained='vggface2').eval().to(device)

        # Model for face detector
        self.face_detector = cv2.FaceDetectorYN.create(os.path.join(os.path.dirname(__file__), 'models', 'face_detection_yunet_2023mar.onnx'), '', (0, 0))
        self.face_detector.setScoreThreshold(0.8)

        # Recognition minimum score
        self.THRESHOLD = 0.5

        # Face data
        self.face_coordinates = []
        self.feats = []
        self.names = []  # Added attribute for storing names

        # Detection time tracking
        self.detection_times = {}

    def match(self, feature1):
        best_score = 0
        best_id = None
        known_features = RecognitionVariable.known_features.copy()

        for user_id, feature_list in zip(known_features.keys(), known_features.values()):
            # Calculate cosine similarity for all known features
            scores = [cosine_similarity([feature1], [f])[0][0] for f in feature_list]
            best = max(scores)

            if best >= best_score and best > self.THRESHOLD:
                best_score = best
                best_id = user_id

        return best_id, best_score

    def get_feature(self, img):
        self.img_ori_size = img.shape
        img_resized = cv2.resize(img, (600, 300), interpolation=cv2.INTER_AREA)
        self.img_resized_size = img_resized.shape
        self.face_detector.setInputSize((img_resized.shape[1], img_resized.shape[0]))

        _, faces = self.face_detector.detect(img_resized)
        faces = faces if faces is not None else []
        
        features = [i for i in concurrent.futures.ThreadPoolExecutor().map(self.detect_features, [img]*len(faces), faces)]

        return features, faces
    
    def detect_features(self, img, face):
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        x, y, w, h = list(map(int, face[:4]))
        aligned_face = img[y:y+h, x:x+w]
        aligned_face = cv2.resize(aligned_face, (112, 112))  # Resize to the required size
        aligned_face = aligned_face.astype('float32') / 255.0  # Normalize if required

        feat = self.face_recognizer(torch.from_numpy(aligned_face).permute(2, 0, 1).unsqueeze(0).to(device)).detach().cpu().numpy()
        
        return feat

    def extract_features(self, img):
        feats, faces = self.get_feature(img)
        face_data = [i for i in concurrent.futures.ThreadPoolExecutor().map(self.get_face_data, feats, faces)]

        self.face_coordinates = [row[0][0] for row in face_data]
        self.feats = [row[1][0] for row in face_data]
        self.names = [row[1][1] for row in face_data]  # Store the names extracted

    def get_face_data(self, feat, face):
        name, score = self.match(feat)

        x1, y1, w, h = list(map(int, face[:4]))
        x2, y2 = x1 + w, y1 + h

        return [[[x1, y1, x2, y2, w, h], (x1 + x2) // 2, (y1 + y2) // 2], [name, score, feat]]

class WorkTimer:
    def __init__(self):
        self.timer_started = False
        self.detection_times = {}

    def start_timer(self, person_id):
        """Start a timer for a person"""
        self.detection_times[person_id] = datetime.now()
        self.timer_started = True

    def stop_timer(self, person_id):
        """Stop the timer for a person"""
        if person_id in self.detection_times:
            del self.detection_times[person_id]

    def get_time(self, person_id):
        """Get the time duration a face has been detected"""
        if person_id in self.detection_times:
            elapsed_time = datetime.now() - self.detection_times[person_id]
            return elapsed_time
        return None

    def update_detection_timer(self, img, detected_faces):
        """Update the timer for faces that are detected"""
        for face in detected_faces:
            name = face[1]
            bbox = face[0]

            if name == "Unknown":
                continue

            if name not in self.detection_times:
                self.start_timer(name)

            detection_duration = self.get_time(name)
            seconds = int(detection_duration.total_seconds()) if detection_duration else 0
            timer_text = f"{seconds}s"

            # Ensure bbox is iterable and has enough values
            if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                x1, y1 = bbox[:2]
                cv2.putText(img, timer_text, (x1, y1 - 30), cv2.FONT_HERSHEY_DUPLEX, 0.6, (0, 255, 0), 2)
            else:
                print(f"Invalid bounding box: {bbox}")

        return img


# # Initialize webcam
# cap = cv2.VideoCapture(0)  # 0 is typically the default webcam

# # Initialize the FaceRecognition class
# face_recognition = FaceRecognition()
# work_timer = WorkTimer()

# while True:
#     ret, frame = cap.read()
#     if not ret:
#         break

#     # Extract features and detect faces
#     face_recognition.extract_features(frame)

#     # Update the timer and display results
#     frame = work_timer.update_detection_timer(frame, face_recognition.face_coordinates)

#     # Draw bounding boxes and names for recognized faces
#     for face in zip(face_recognition.face_coordinates, face_recognition.names):
#         face_box = face[0][0]  # Extracting the bounding box [x1, y1, x2, y2, w, h]
#         name = face[1]

#         if isinstance(face_box, (list, tuple)) and len(face_box) == 6:
#             x1, y1, x2, y2, w, h = face_box
#         else:
#             print(f"Invalid face box: {face_box}")
#             continue

#         # Draw box in green
#         cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

#         if not name:
#             name = "Unknown"

#         cv2.putText(frame, name, (x1, y1 - 10), cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255), 2)

#     # Display the video feed with recognized faces and timers
#     cv2.imshow('Face Recognition', frame)

#     # Exit loop on pressing 'q'
#     if cv2.waitKey(1) & 0xFF == ord('q'):
#         break

# # Release the webcam and close all windows
# cap.release()
# cv2.destroyAllWindows()