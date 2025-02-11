import cv2
import os
import numpy as np
from datetime import datetime
from django.shortcuts import render
from django.http import JsonResponse
from Dashboard import models
class Work_Timer:
    def __init__(self, camera, ID):
        self.streaming = False
        self.camera = camera
        self.ID = ID
        self.frame = []
        self.detection_times = {}  # To track detection times for each personnel
        self.last_detection_time = {}  # To track the last time a face was detected
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'models/haarcascade_frontalface_default.xml')
        self.known_faces = self.load_known_faces()  # Load known faces

    def load_known_faces(self):
        """Load known faces from stored images."""
        known_faces = {}
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        PERSONNEL_PICS_DIR = os.path.join(BASE_DIR, 'static', 'img', 'personnel_pics')

        # Ensure the directory exists
        if not os.path.exists(PERSONNEL_PICS_DIR):
            os.makedirs(PERSONNEL_PICS_DIR)

        for personnel_name in os.listdir(PERSONNEL_PICS_DIR):
            dir_path = os.path.join(PERSONNEL_PICS_DIR, personnel_name)
            if os.path.isdir(dir_path):
                known_faces[personnel_name] = dir_path  # Store the directory path for each personnel

        return known_faces

    def run_models(self):
        """Detect faces in the frame and identify personnel."""
        img = self.frame
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)  # Convert to grayscale for Haar Cascade
        faces_detected = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

        for (x, y, w, h) in faces_detected:
            # Draw a rectangle around the detected face
            cv2.rectangle(img, (x, y), (x + w, y + h), (255, 252, 46), 3)

            # Here you would typically implement face recognition logic
            name = self.recognize_face(gray[y:y + h, x:x + w])  # Implement this method to recognize the face

            self.update_detection_time(name)
            self.draw_bounding_box(img, (x, y, w, h), name)

        self.pred_frame = img

    def recognize_face(self, face):
        """Simulate face recognition. Replace this with actual recognition logic."""
        # For now, we will return "Unknown" as a placeholder
        # You can implement your recognition logic here
        return "Unknown"

    def update_detection_time(self, name):
        """Update detection time for a recognized person."""
        current_time = datetime.now()
        if name != "Unknown":
            if name in self.last_detection_time:
                # If the name was detected previously, calculate the elapsed time
                elapsed_time = (current_time - self.last_detection_time[name]).total_seconds()
                self.detection_times[name] += elapsed_time
            else:
                # If it's the first detection, initialize the timer
                self.detection_times[name] = 0

            # Update the last detection time
            self.last_detection_time[name] = current_time

    def save_detection_time(self):
        """Save detection time to the database at the end of the day or when the application stops."""
        for name, total_time in self.detection_times.items():
            if name != "Unknown":
                personnel = models.Personnels.objects.get(name=name)
                models.Work_Timer.objects.create(
                    personnel=personnel,
                    camera_id=self.ID,
                    type='FACE_DETECTED',
                    datetime=datetime.now(),
                    timer=int(total_time)
                )

    def draw_bounding_box(self, img, bbox, name):
        """Draw a bounding box and name label on the detected face."""
        x, y, w, h = bbox
        cv2.rectangle(img, (x, y), (x + w, y + h), (255, 252, 46), 3)
        timer_text = ""
        if name in self.detection_times:
            seconds = int(self.detection_times[name])
            timer_text = f"{seconds // 3600:02}:{(seconds % 3600) // 60:02}:{seconds % 60:02}"
        cv2.putText(img, f"{name} {timer_text}", (x, y - 10), cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255), 1)

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

            self.frame = frame
            self.run_models()

        cap.release()
        self.save_detection_time()  # Save detection times when streaming stops

    def stop_stream(self):
        """Stop the streaming process."""
        self.streaming = False