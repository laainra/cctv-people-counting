import os
import cv2
import numpy as np

# Global Variable for each camera
class GlobalVariable:
    def __init__(self):
        # Model outputs
        self.feats = []
        self.face_coordinates = []
        self.person_bboxes = []
        self.genders = []
        self.detection_times = {} 

        # Face recognition result
        self.names = np.array(["Unknown", "Unknown"])

        # DB Variables
        self.total_enter = 0
        self.total_exit = 0
        self.unknown_enter = 0
        self.female_enter = 0
        self.male_enter = 0
        self.exit = 0
        self.occupancy = 0

# Global Variable for all camera
class RecognitionVariable:
    # Global Variable for known faces features
    known_features = {}

    # Model for face recognition
    face_recognizer = cv2.FaceRecognizerSF.create(os.path.join(os.path.dirname(__file__), 'models/face_recognizer_fast.onnx'), '')

    # Model for face detector
    face_detector = cv2.FaceDetectorYN.create(os.path.join(os.path.dirname(__file__), 'models/face_detection_yunet_2023mar.onnx'), '', (0,0))
    face_detector.setScoreThreshold(0.8)

    root_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'img', 'personnel_pics')

    def set_personnel_known_faces(personnel_name):
        embeddings = []
        dir_path = os.path.join(RecognitionVariable.root_path, personnel_name)

        for file in np.array(os.listdir(dir_path)):

            if file.endswith('.txt'):
                continue
            
            img = cv2.imread(os.path.join(dir_path, file))
            feats, _= RecognitionVariable.get_feature(img)
            if len(feats) == 0:
                print('no face detected in', file)
                os.remove(os.path.join(dir_path, file))
            else:
                embeddings.append(feats[0])
        
        if len(embeddings) != 0: 
            RecognitionVariable.known_features[personnel_name] = embeddings

    # Function to set all known faces from the folder
    def set_all_known_faces():
        if not os.path.exists(RecognitionVariable.root_path):
            os.mkdir(RecognitionVariable.root_path)

        for dir_name in os.listdir(RecognitionVariable.root_path):

            RecognitionVariable.set_personnel_known_faces(dir_name)

    # Function to get features from image
    def get_feature(img):
        RecognitionVariable.face_detector.setInputSize((img.shape[1], img.shape[0]))

        _, faces = RecognitionVariable.face_detector.detect(img)

        faces = faces if faces is not None else []
        features = []

        for face in faces:
            aligned_face = RecognitionVariable.face_recognizer.alignCrop(img, face)
            
            feat = RecognitionVariable.face_recognizer.feature(aligned_face)
            features.append(feat)

        return features, faces