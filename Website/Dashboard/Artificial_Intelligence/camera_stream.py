import cv2
import os
import time
import threading
import torch
import numpy as np
from ultralytics import YOLO
from ..Artificial_Intelligence.recognition import FaceRecognition 
from ..Artificial_Intelligence.gender import GenderDetection
from ..Artificial_Intelligence.people_counting import PeopleCounting
from ..Artificial_Intelligence.variables import GlobalVariable
from ..Artificial_Intelligence.freshest_frame import FreshestFrame
from .. import models
from datetime import datetime

class CameraStream:
    def __init__(self, camera, ID):
        # Change device if gpu is available
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Import yolo model
        model_yolo = YOLO(os.path.join(os.path.dirname(__file__), 'models/yolov8n.pt'), task='detect')
        model_yolo.to(self.device)

        # Import CNN model
        model_gender = torch.load(os.path.join(os.path.dirname(__file__), 'models/gender.pt'), map_location=self.device)
        model_gender.eval()  # Set model ke mode evaluasi

        # Set classes
        self.GV = GlobalVariable()
        self.FR = FaceRecognition()
        self.GD = GenderDetection(model_gender)
        self.PC = PeopleCounting(model_yolo, self.GV)

        self.streaming = False

        # Poly coordinates
        self.poly = np.array([[0,0], [0,0], [0,0], [0,0], [0,0], [0,0], [0,0], [0,0]])

        # Set camera source
        self.camera = camera

        # Processed frame
        self.frame = []

        # Predicted frame
        self.pred_frame = []

        self.fr_active = True
        self.gd_active = True

        self.stream_paused = False

        self.time_range = ['00:00:00', '00:00:00']

        self.ID = ID

        self.max_width = 2500

        # Tambahkan folder untuk menyimpan wajah yang diekstrak
        self.face_folder = os.path.join(os.path.dirname(__file__), '..', 'static', 'img', 'extracted_faces', 'raw')
        if not os.path.exists(self.face_folder):
            os.makedirs(self.face_folder)

    def check_time_range(self, time_range):
        time_start = int(time_range[0].replace(':', ''))
        time_stop = int(time_range[1].replace(':', ''))
        time_now = int(datetime.now().strftime('%H%M%S'))

        if time_now > time_start and time_now < time_stop:
            return True
        else:
            return False

    # Function to run each models
    def run_models(self):
        while self.streaming:
            if len(self.frame) != 0 and self.frame is not None:
                img = self.frame

                start = time.time()

                # Run gender and face recognition model
                if self.gd_active:
                    self.GD.extract_genders(img)
                
                if self.fr_active:
                    self.FR.extract_features(img)

                # Run people counting model
                self.PC.extract_bboxes(img)

                self.PC.detectSpeed = time.time() - start

                if not self.gd_active:
                    self.GD.genders = [['Unknown', 0] for _ in self.FR.feats]
                
                if not self.fr_active:
                    self.FR.feats = [['Unknown', 1, []] for _ in self.GD.genders]

                # Store recieved variables to global variable
                self.GV.person_bboxes = self.PC.person_bboxes
                self.GV.feats = self.FR.feats
                self.GV.genders = self.GD.genders

                if self.fr_active:
                    self.GV.face_coordinates = self.FR.face_coordinates
                else:
                    self.GV.face_coordinates = self.GD.face_coordinates

                # Ekstrak dan simpan wajah
                self.extract_and_save_faces(img)

    def extract_and_save_faces(self, img):
        for idx, ((x1, y1, x2, y2, w, h), _, _) in enumerate(self.GV.face_coordinates):
            face = img[y1:y2, x1:x2]
            if face.size > 0:  # Pastikan wajah tidak kosong
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"face_{timestamp}_{idx}_cam{self.ID}.jpg"
                filepath = os.path.join(self.face_folder, filename)
                cv2.imwrite(filepath, face)

    # Function to read camera footage
    def start_stream(self):
        # For changing polygon coordinates from terminal
        # threading.Thread(target=self.change_poly, daemon=True).start()

        print(self.device)
        
        self.streaming = True
        
        # Open camera
        cap = cv2.VideoCapture(self.camera)
        cap.set(cv2.CAP_PROP_FPS, 30)
        # cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        # cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        # Wrap it
        self.fresh = FreshestFrame(cap)

        # Run models in separate thread
        threading.Thread(target=self.run_models, daemon=True).start()

        prev_hour = -1
        prev_minute = datetime.now().strftime('%M')

        data = models.Counted_Instances.objects.filter(camera_id=self.ID)

        start_time = time.time()

        prev_image = []

        if len(data) != 0:
            latest_data = models.Counted_Instances.objects.filter(camera_id=self.ID)[len(data)-1]

            latest_hour = str(latest_data.timestamp).split('-')[1].split(':')[0]
            latest_date = str(latest_data.timestamp).split('-')[0].split('/')[1]

            total_male_enter = [int(model.male_entries) for model in data if str(model.timestamp).split('-')[0] == datetime.now().strftime('%D')]
            total_female_enter = [int(model.female_entries) for model in data if str(model.timestamp).split('-')[0] == datetime.now().strftime('%D')]
            total_unknown_enter = [int(model.unknown_gender_entries) for model in data if str(model.timestamp).split('-')[0] == datetime.now().strftime('%D')]
            total_exit = [int(model.people_exits) for model in data if str(model.timestamp).split('-')[0] == datetime.now().strftime('%D')]

            if latest_hour == datetime.now().strftime('%H') and latest_date == datetime.now().strftime('%d'):
                self.GV.total_enter = int(sum(total_male_enter[:-1]) + sum(total_female_enter[:-1]) + sum(total_unknown_enter[:-1]))
                self.GV.total_exit = int(sum(total_exit[:-1]))
                
                self.GV.unknown_enter = int(latest_data.unknown_gender_entries)
                self.GV.female_enter = int(latest_data.female_entries) 
                self.GV.male_enter = int(latest_data.male_entries)
                self.GV.exit = int(latest_data.people_exits) 
                self.GV.occupancy = int(latest_data.people_inside)
                prev_hour = datetime.now().strftime('%H')
            else:
                self.GV.total_enter = int(sum(total_male_enter) + sum(total_female_enter) + sum(total_unknown_enter))
                self.GV.total_exit = int(sum(total_exit))
                

        # Get pred frame
        while self.streaming:
            try:
                ret, frame = self.fresh.read()

                if self.check_time_range(self.time_range):
                    self.stream_paused = False
                    
                    if datetime.now().strftime('%M') != prev_minute:
                        counted_data = models.Counted_Instances.objects.filter(camera_id=self.ID)
                        counted_data = counted_data[len(counted_data)-1]
                        
                        counted_data.male_entries = self.GV.male_enter
                        counted_data.female_entries = self.GV.female_enter
                        counted_data.unknown_gender_entries = self.GV.unknown_enter
                        counted_data.people_exits = self.GV.exit
                        counted_data.people_inside = self.GV.occupancy
                        counted_data.save()

                        prev_minute = datetime.now().strftime('%M')

                    if datetime.now().strftime('%H') != prev_hour:
                        cam = models.Camera_Settings.objects.get(id=self.ID)

                        self.GV.total_enter += self.GV.female_enter + self.GV.male_enter + self.GV.unknown_enter
                        self.GV.total_exit += self.GV.exit

                        self.GV.unknown_enter = 0
                        self.GV.female_enter = 0 
                        self.GV.male_enter = 0
                        self.GV.exit = 0

                        models.Counted_Instances.objects.create(camera = cam, 
                                                                male_entries=self.GV.male_enter, 
                                                                female_entries=self.GV.female_enter, 
                                                                unknown_gender_entries=self.GV.unknown_enter, 
                                                                people_exits=self.GV.exit, 
                                                                people_inside=self.GV.occupancy,
                                                                timestamp = datetime.now().strftime('%D-%H:%M:%S'))

                        prev_hour = datetime.now().strftime('%H')

                    if (frame.shape[1] > self.max_width):
                        resize_val = self.max_width/frame.shape[1]
                        self.frame = cv2.resize(frame, None, fx=resize_val, fy=resize_val)
                    else:  
                        self.frame = cv2.resize(frame, None, fx=1, fy=1)

                    self.pred_frame = self.PC.people_count(self.frame, self.GV.person_bboxes, self.GV.face_coordinates, self.GV.feats, self.GV.genders, self.poly, self.ID)
                else:
                    prev_hour = -1
                    prev_minute = datetime.now().strftime('%M')
                    
                    self.GV.unknown_enter = 0
                    self.GV.female_enter = 0 
                    self.GV.male_enter = 0
                    self.GV.exit = 0
                    self.GV.occupancy = 0

                    if (frame.shape[1] > self.max_width):
                        resize_val = self.max_width/frame.shape[1]
                        self.frame = cv2.resize(frame, None, fx=resize_val, fy=resize_val)
                        self.pred_frame = cv2.resize(frame, None, fx=resize_val, fy=resize_val)
                    else:  
                        self.frame = cv2.resize(frame, None, fx=1, fy=1)
                        self.pred_frame = cv2.resize(frame, None, fx=1, fy=1)

                    self.stream_paused = True
            except Exception as e:
                print('ERROR: ', e)
                pass

    # Function to stop streaming  
    def stop_stream(self):
        if self.streaming:
            cam = models.Camera_Settings.objects.get(id=self.ID)
            cam.cam_is_active = False
            cam.save()

            self.streaming = False
            self.fresh.release()