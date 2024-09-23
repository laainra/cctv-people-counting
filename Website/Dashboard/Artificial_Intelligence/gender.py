import cv2
import os
import torch
import numpy as np
import concurrent.futures
from torchvision import transforms

class GenderDetection:
    def __init__(self, model):
        # # Gender detection model | if device using CPU
        self.MODEL_MEAN_VALUES = (78.4263377603, 87.7689143744, 114.895847746)
        self.GENDER_MODEL = os.path.join(os.path.dirname(__file__), 'models/deploy_gender.prototxt')
        self.GENDER_PROTO = os.path.join(os.path.dirname(__file__), 'models/gender_net.caffemodel')
        self.gender_net = cv2.dnn.readNetFromCaffe(self.GENDER_MODEL, self.GENDER_PROTO)

        # Trained CNN model for gender detection | if device using GPU
        self.model = model
        
        # # Model for face recognition
        self.face_recognizer = cv2.FaceRecognizerSF.create(os.path.join(os.path.dirname(__file__), 'models/face_recognizer_fast.onnx'), '')

        # # Model for face detector
        self.face_detector = cv2.FaceDetectorYN.create(os.path.join(os.path.dirname(__file__), 'models/face_detection_yunet_2023mar.onnx'), '', (0,0))
        self.face_detector.setScoreThreshold(0.8)

        # Change device if gpu is available
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Transform image to tensor and resize based on the model
        self.transform = transforms.Compose([transforms.ToTensor(), transforms.Resize((640, 640), antialias=True)])

        # Classification classes
        self.classes = ['Male', 'Female']

        # Font variables
        self.font = cv2.FONT_HERSHEY_DUPLEX
        self.font_thickness = 1
        self.font_size = 0.7

        # Genders value
        self.genders = []
        self.face_coordinates = []

        # Images size variables
        self.img_ori_size = ()
        self.img_resized_size = ()

    # Function to detect gender based on cropped face image
    def detect_gender(self, img, face):
        fy = 1/(self.img_resized_size[0]/self.img_ori_size[0])
        fx = 1/(self.img_resized_size[1]/self.img_ori_size[1])

        for i in range(0, 14, 2): face[i] = face[i] * fx
        
        for i in range(1, 14, 2): face[i] = face[i] * fy

        aligned_face = self.face_recognizer.alignCrop(img, face)

        if self.device == torch.device('cuda'):
            if self.model == None:
                raise ValueError("Gender Detection model has not been set yet")

            aligned_face = self.transform(aligned_face)
            pred = self.model(aligned_face.unsqueeze(0).to(self.device)).squeeze(0)
            gender = self.classes[np.argmax(pred.cpu().detach().numpy())]
            gender_score = max(pred.cpu().detach().numpy())
        else:
            blob = cv2.dnn.blobFromImage(image=aligned_face, scalefactor=1.0, size=(227, 227), mean=self.MODEL_MEAN_VALUES, swapRB=False, crop=False)
            self.gender_net.setInput(blob)
            gender_preds = self.gender_net.forward()
            max_idx = gender_preds[0].argmax()
            gender = self.classes[max_idx]
            gender_score = max(gender_preds[0])

        x1, y1, w, h = list(map(int, face[:4]))
        x2, y2 = x1 + w, y1 + h
        center_x = int(x1 + w/2)
        center_y = int(y1 + h/2)

        return [[[x1, y1, x2, y2, w, h], center_x, center_y], [gender, gender_score]]
    
    # Get the genders of all detected faces
    def get_genders(self, img):
        self.img_ori_size = img.shape

        img_resized = cv2.resize(img, (600, 300), interpolation=cv2.INTER_AREA)

        self.img_resized_size = img_resized.shape

        self.face_detector.setInputSize((img_resized.shape[1], img_resized.shape[0]))

        _, faces = self.face_detector.detect(img_resized)

        faces = faces if faces is not None else []

        face_data = [i for i in concurrent.futures.ThreadPoolExecutor().map(self.detect_gender, [img]*len(faces), faces)]

        coordinates = [row[0:1][0] for row in face_data]
        genders = [row[1:2][0] for row in face_data]

        return coordinates, genders
    
    # Extract gender and store it to the global variables
    def extract_genders(self, img):
        self.face_coordinates, self.genders = self.get_genders(img)