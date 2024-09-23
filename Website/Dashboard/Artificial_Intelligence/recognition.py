import cv2
import os
import concurrent.futures
from ..Artificial_Intelligence.variables import RecognitionVariable as RV

class FaceRecognition:
    def __init__(self):
        # Model for face recognition
        self.face_recognizer = cv2.FaceRecognizerSF.create(os.path.join(os.path.dirname(__file__), 'models/face_recognizer_fast.onnx'), '')

        # Model for face detector
        self.face_detector = cv2.FaceDetectorYN.create(os.path.join(os.path.dirname(__file__), 'models/face_detection_yunet_2023mar.onnx'), '', (0,0))
        self.face_detector.setScoreThreshold(0.8)

        # Recognition minimum score
        self.THRESHOLD = 0.5

        # Font variables
        self.font = cv2.FONT_HERSHEY_DUPLEX
        self.font_thickness = 1
        self.font_size = 0.7

        # Face data
        self.face_coordinates = []
        self.feats = []

        # Images size variables
        self.img_ori_size = ()
        self.img_resized_size = ()

    # Function to match detected feature with known features
    def match(self, feature1):
        best_score = 0
        best_id = None

        known_features = RV.known_features.copy()

        for user_id, feature_list in zip(known_features.keys(), known_features.values()):
            best = max([i for i in concurrent.futures.ThreadPoolExecutor().map(self.face_recognizer.match, [feature1]*len(feature_list), feature_list, [cv2.FaceRecognizerSF_FR_COSINE]*len(feature_list))])

            if best >= best_score and best > self.THRESHOLD:
                best_score = best
                best_id = user_id

        return best_id, best_score
    
    # Function to get features from image
    def get_feature(self, img):
        self.img_ori_size = img.shape

        img_resized = cv2.resize(img, (600, 300), interpolation=cv2.INTER_AREA)

        self.img_resized_size = img_resized.shape

        self.face_detector.setInputSize((img_resized.shape[1], img_resized.shape[0]))

        _, faces = self.face_detector.detect(img_resized)

        faces = faces if faces is not None else []
        
        features = [i for i in concurrent.futures.ThreadPoolExecutor().map(self.detect_features, [img]*len(faces), faces)]

        return features, faces
    
    # Function to detect feature from a single face
    def detect_features(self, img, face):
        fy = 1/(self.img_resized_size[0]/self.img_ori_size[0])
        fx = 1/(self.img_resized_size[1]/self.img_ori_size[1])

        for i in range(0, 14, 2): face[i] = face[i] * fx
        
        for i in range(1, 14, 2): face[i] = face[i] * fy

        aligned_face = self.face_recognizer.alignCrop(img, face)

        feat = self.face_recognizer.feature(aligned_face)
        
        return feat

    # Function to extract feature and store it to global variables
    def extract_features(self, img):
        feats, faces = self.get_feature(img)

        face_data = [i for i in concurrent.futures.ThreadPoolExecutor().map(self.get_face_data, feats, faces)]

        self.face_coordinates = [row[0:1][0] for row in face_data]
        self.feats = [row[1:2][0] for row in face_data]

    def get_face_data(self, feat, face):
        name, score = self.match(feat)

        x1, y1, w, h = list(map(int, face[:4]))
        x2, y2 = x1 + w, y1 + h
        center_x = int(x1 + w/2)
        center_y = int(y1 + h/2)

        return [[[x1, y1, x2, y2, w, h], center_x, center_y], [name, score, feat]]


    
