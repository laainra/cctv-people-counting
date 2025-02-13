# Artificial_Intelligence/face_rec_haar.py

import cv2
import os
import numpy as np
from django.conf import settings

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
dataset_folder = os.path.join(BASE_DIR, 'static', 'img', 'personnel_pics')
model_path = '../model_lbph.xml'
static_folder = os.path.join(BASE_DIR, 'static')
label_to_name_path = os.path.join(static_folder, 'label_to_name.json')

def recognize_face(cap):
    """Process face recognition from the camera stream."""
    recognizer = cv2.face.LBPHFaceRecognizer_create()

    if not os.path.exists(model_path):
        print("Model not available, please train the model first.")
        return

    recognizer.read(model_path)

    label_to_name = {}
    personnel_folder = dataset_folder
    
    for face_folder in os.listdir(personnel_folder):
        face_folder_path = os.path.join(personnel_folder, face_folder)
        if os.path.isdir(face_folder_path):
            for file_name in os.listdir(face_folder_path):
                if file_name.endswith('.jpg'):
                    label = int(file_name.split('_')[1])
                    extracted_name = file_name.split('_')[2]
                    label_to_name[label] = extracted_name

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces_detected = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

        recognized_faces = []
        for (x, y, w, h) in faces_detected:
            face = cv2.resize(gray[y:y + h, x:x + w], (200, 200))
            label, confidence = recognizer.predict(face)
            name = label_to_name.get(label, "Unknown")
            recognized_faces.append((name, (x, y, w, h)))

        yield recognized_faces  # Yield recognized faces for further processing