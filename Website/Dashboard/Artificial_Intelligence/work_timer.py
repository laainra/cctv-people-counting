import cv2
import os
import time
import numpy as np
from datetime import datetime
from django.shortcuts import render, redirect, HttpResponse
from django.contrib.auth.decorators import login_required
from django.http.response import StreamingHttpResponse, JsonResponse
from face_recognition import face_encodings, compare_faces, face_locations, load_image_file
from ..models import Camera_Settings, Personnels, Work_Timer, Counted_Instances


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTURED_IMG_DIR = os.path.join(BASE_DIR, 'static', 'img', 'extracted_faces', 'raw')
PERSONNEL_PICS_DIR = os.path.join(BASE_DIR, 'static', 'img', 'personnel_pics')

class Work_Timer:
    def __init__(self, camera, ID):
        self.streaming = False
        self.camera = camera
        self.ID = ID
        self.frame = []
        self.pred_frame = []
        self.time_range = ['00:00:00', '00:00:00']
        self.known_faces = {}
        self.load_known_faces()
        self.detection_times = {}

    def load_known_faces(self):
        """Load known faces and their encodings from stored images."""
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        PERSONNEL_PICS_DIR = os.path.join(BASE_DIR, 'static', 'img', 'personnel_pics')

        # Ensure the directory exists
        if not os.path.exists(PERSONNEL_PICS_DIR):
            os.makedirs(PERSONNEL_PICS_DIR)

        for personnel_name in os.listdir(PERSONNEL_PICS_DIR):
            encodings = []
            dir_path = os.path.join(PERSONNEL_PICS_DIR, personnel_name)
            for file in os.listdir(dir_path):
                if file.endswith('.jpg') or file.endswith('.png'):
                    img = load_image_file(os.path.join(dir_path, file))
                    face_enc = face_encodings(img)
                    if face_enc:
                        encodings.append(face_enc[0])
            if encodings:
                self.known_faces[personnel_name] = np.mean(encodings, axis=0)

    def check_time_range(self, time_range):
        """Check if the current time is within the specified range."""
        time_start = int(time_range[0].replace(':', ''))
        time_stop = int(time_range[1].replace(':', ''))
        time_now = int(datetime.now().strftime('%H%M%S'))
        return time_start <= time_now <= time_stop

    def run_models(self):
        """Detect faces in the frame and identify personnel."""
        img = self.frame
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        locations = face_locations(img_rgb)
        encodings = face_encodings(img_rgb, locations)

        for face_encoding, bbox in zip(encodings, locations):
            name = "Unknown"
            min_dist = float('inf')

            for known_name, known_encoding in self.known_faces.items():
                dist = np.linalg.norm(face_encoding - known_encoding)
                if dist < min_dist and dist <= 0.6:  # Adjust threshold as needed
                    min_dist = dist
                    name = known_name

            self.update_detection_time(name)
            self.save_detection_time(name)
            self.draw_bounding_box(img, bbox, name)

        self.pred_frame = img

    def update_detection_time(self, name):
        """Update detection time for a recognized person."""
        current_time = datetime.now()
        if name in self.detection_times:
            start_time, duration = self.detection_times[name]
            elapsed_time = (current_time - start_time).total_seconds()
            updated_duration = duration + elapsed_time
            self.detection_times[name] = (current_time, updated_duration)
        else:
            self.detection_times[name] = (current_time, 0)

    def save_detection_time(self, name):
        """Save detection time to the database."""
        if name in self.detection_times:
            start_time, duration = self.detection_times[name]
            if name != "Unknown":
                personnel = Personnels.objects.get(name=name)
                Work_Timer.objects.create(
                    personnel=personnel,
                    camera_id=self.ID,
                    type='FACE_DETECTED',
                    datetime=start_time,
                    timer=int(duration)
                )

    def draw_bounding_box(self, img, bbox, name):
        """Draw a bounding box and name label on the detected face."""
        top, right, bottom, left = bbox
        cv2.rectangle(img, (left, top), (right, bottom), (255, 252, 46), 3)
        timer_text = ""
        if name in self.detection_times:
            _, duration = self.detection_times[name]
            seconds = int(duration)
            timer_text = f"{seconds // 3600:02}:{(seconds % 3600) // 60:02}:{seconds % 60:02}"
        cv2.putText(img, f"{name} {timer_text}", (left, top - 10), cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255), 1)

    def start_stream(self):
        """Start streaming and processing frames."""
        self.streaming = True
        cap = cv2.VideoCapture(self.camera)
        cap.set(cv2.CAP_PROP_FPS, 10)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)

        while self.streaming:
            ret, frame = cap.read()
            if not ret:
                continue

            if self.check_time_range(self.time_range):
                self.frame = frame
                self.run_models()

        cap.release()

    def stop_stream(self):
        """Stop the streaming process."""
        self.streaming = False
