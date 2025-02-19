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
from datetime import datetime, timedelta

class CameraStream:
    def __init__(self, camera, ID):
        # Change device if gpu is available
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Import yolo model
        model_path = os.path.join(os.path.dirname(__file__), 'models/yolo11n.pt')
        # model_path = os.path.join(os.path.dirname(__file__), 'models/yolov8n.pt')
        model_yolo = YOLO(model_path, verbose=False, task='detect')
        
        # Optimize model untuk GPU
        if torch.cuda.is_available():
            # Convert to FP32 first before optimization
            model_yolo = model_yolo.to(self.device).float()
             
            # Export to format engine
            engine_path = model_path.replace('.pt', '.engine')
            if not os.path.exists(engine_path):
                model_yolo.export(
                    format="engine",
                    device=0,  # GPU device id
                    half=True, 
                    simplify=True,
                    workspace=4,
                    verbose=False
                )
            
            # Logging
            print(f"Model berhasil dikonversi ke TensorRT engine: {engine_path}")
            
            # Load engine model
            model_yolo = YOLO(engine_path)
        
        self.model = model_yolo

        # Import and optimize gender model
        model_gender = torch.load(
            os.path.join(os.path.dirname(__file__), 'models/gender.pt'),
            map_location=self.device
        )
        model_gender = model_gender.float().eval()  # Use FP32
        
        if torch.cuda.is_available():
            model_gender = torch.jit.trace(model_gender, torch.randn(1, 3, 224, 224).to(self.device))
            model_gender = torch.jit.freeze(model_gender)
        
        self.model_gender = model_gender

        # Set classes
        self.GV = GlobalVariable()
        self.FR = FaceRecognition()
        self.GD = GenderDetection(self.model_gender)
        self.PC = PeopleCounting(self.model, self.GV)

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
        self.fc_active = True

        self.stream_paused = False

        self.time_range = ['00:00:00', '00:00:00']

        self.ID = ID

        self.max_width = 2000

        # Add folder for saving extracted faces
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

                # Use torch.no_grad() to save memory
                with torch.no_grad():
                    # Run gender and face recognition model
                    if self.gd_active:
                        self.GD.extract_genders(img)
                    
                    if self.fr_active:
                        self.FR.extract_features(img)
                        for name in self.FR.names:
                            self.FR.update_detection_time(name)       

                    # Run people counting model
                    self.PC.extract_bboxes(img)

                self.PC.detectSpeed = time.time() - start

                if not self.gd_active:
                    self.GD.genders = [['Unknown', 0] for _ in self.FR.feats]
                
                if not self.fr_active:
                    self.FR.feats = [['Unknown', 1, []] for _ in self.GD.genders]

                # Store received variables to global variable
                self.GV.person_bboxes = self.PC.person_bboxes
                self.GV.feats = self.FR.feats
                self.GV.genders = self.GD.genders

                if self.fr_active:
                    self.GV.face_coordinates = self.FR.face_coordinates
                else:
                    self.GV.face_coordinates = self.GD.face_coordinates

                if self.fc_active:
                    self.extract_and_save_faces(img)
                 
                for name, duration in self.FR.detection_times.items():
                    try:
                        personnel = models.Personnels.objects.get(name=name)
                        # work_timer, created = models.Work_Timer.objects.get_or_create(
                        #     personnel=personnel,
                        #     camera=self.ID,
                        #     type='FACE_DETECTED',
                        #     defaults={'datetime': datetime.now(), 'timer': 0}
                        # )
                        
                        # if not created:
                        #     if isinstance(duration, timedelta):
                        #         work_timer.timer += duration.total_seconds()
                        #     else:
                        #         print(f"Error: duration is not a timedelta object for {name}")
                        #     work_timer.datetime = datetime.now()
                        #     work_timer.save()
                    except models.Personnels.DoesNotExist:
                        # print(f"Personnel '{name}' not found in the database. Marking as 'Unknown'.")
                        # Assign "Unknown" to bounding box or handle the detection accordingly
                        name = "Unknown"

    def extract_and_save_faces(self, img):
        for idx, ((x1, y1, x2, y2, w, h), _, _) in enumerate(self.GV.face_coordinates):
            face = img[y1:y2, x1:x2]
            if face.size > 0:  # Ensure face is not empty
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"face_{timestamp}_{idx}_cam{self.ID}.png"
                filepath = os.path.join(self.face_folder, filename)
                
                cv2.imwrite(filepath, face, [cv2.IMWRITE_PNG_COMPRESSION, 0])

    # Function to read camera footage
    def start_stream(self):
        # For changing polygon coordinates from terminal
        # threading.Thread(target=self.change_poly, daemon=True).start()

        print(self.device)
        
        self.streaming = True
        
        # Open camera
        cap = cv2.VideoCapture(self.camera)
        cap.set(cv2.CAP_PROP_FPS, 10)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
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

                # Process only the latest frame
                if not ret:
                    continue

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