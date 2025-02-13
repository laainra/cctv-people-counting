import cv2
import math
import numpy as np
import os
import random
import string
from .. import models
from datetime import datetime
from shapely.geometry import Point
from shapely.geometry.polygon import Polygon
from ..Artificial_Intelligence.variables import RecognitionVariable as RV
import torch

class PeopleCounting:
    def __init__(self, model, GV):
        # YOLOv8 model
        self.model = model

        # Set classes
        self.GV = GV

        # Font variables
        self.font = cv2.FONT_HERSHEY_DUPLEX
        self.font_thickness = 2
        self.font_size = 1

        # Counting variables
        self.green = np.array([])
        self.red = np.array([])
        self.id = {}

        # Bounding boxes
        self.person_bboxes = []

        self.isPolyMode = True

        self.detectSpeed = 0
        
        self.tracker_config = {
        'track_thresh': 0.5,
        'track_buffer': 30,
        'match_thresh': 0.8,
        'min_box_area': 100,
        'frame_rate': 30
    }
        # Detection times for each person
        self.detection_times = {}
        
        
    # Function to get distance between line and point
    def distance(self, x1, y1, x2, y2, x, y):
        A = x - x1
        B = y - y1
        C = x2 - x1
        D = y2 - y1

        dot = A * C + B * D
        len_sq = C * C + D * D
        param = -1
        if (len_sq != 0):
            param = dot / len_sq

        if (param < 0):
            xx = x1
            yy = y1
        elif (param > 1):
            xx = x2
            yy = y2
        else:
            xx = x1 + param * C
            yy = y1 + param * D

        dx = x - xx
        dy = y - yy

        return np.sqrt(dx * dx + dy * dy)

    # Function to get labelled image
    def get_label_img(self, img, bbox):
        (bbox_x1, bbox_y1, bbox_x2, bbox_y2), bbox_id, bbox_conf = bbox

        # text = f"{self.id[bbox_id]['name']} - {self.id[bbox_id]['gender']} ({bbox_conf:.2f})"
        text = f"{self.id[bbox_id]['name']} ({self.id[bbox_id].get('time', '0')})"

        (w, h), _ = cv2.getTextSize(text, self.font, self.font_size, self.font_thickness)

        # Create bounding box
        cv2.rectangle(img, (bbox_x1, bbox_y1), (bbox_x1 + w, bbox_y1 - h), (255, 252, 46), -1)
        cv2.rectangle(img, (bbox_x1, bbox_y1), (bbox_x2, bbox_y2), (255, 252, 46), 3)
        cv2.drawMarker(img, (int(bbox_x2), int(bbox_y2)), (0, 0, 255), thickness=1)
        cv2.putText(img, text, (bbox_x1, bbox_y1 - 10), self.font, self.font_size, (255, 255, 255), self.font_thickness)
        
        # Display timer
        detection_duration = self.detection_times.get(bbox_id, 0)
        seconds = int(detection_duration.total_seconds())
        timer_text = f"{seconds}s"
        cv2.putText(img, timer_text, (bbox_x1, bbox_y1 - 30), self.font, 0.6, (0, 255, 0), 2)

        return img

    # Function to get persons bounding box 
    def extract_bboxes(self, img):
        self.ori_img_size = img.shape
        
        # Resize image
        img_resized = cv2.resize(img, (360, 180))
        
        # Ensure the image is in uint8 format (0-255)
        if img_resized.dtype != np.uint8:
            img_resized = (img_resized * 255).astype(np.uint8)
        
        self.resized_img_size = img_resized.shape

        # Batch processing with the right settings
        try:
            for result in self.model.track(
                source=img_resized,
                persist=True,
                verbose=False,
                classes=[0],
                stream=True,
                device=0 if torch.cuda.is_available() else 'cpu',
                half=False,  # Use FP32
                tracker="bytetrack.yaml",  # Use ByteTracker with default configuration
                conf=0.3,  # Confidence threshold
                iou=0.5,   # NMS IOU threshold
            ):
                if result.boxes is not None:
                    self.person_bboxes = result.boxes.data.tolist()
                else:
                    self.person_bboxes = []
        except Exception as e:
            print(f"Error in tracking: {e}")
            self.person_bboxes = []

    # Function to count people with recieved datas
    def people_count(self, frame, bboxes, face_coordinates, feats, genders, poly_coordinates, cam_id):
        img = np.copy(frame)
        img_ori = np.copy(frame)

        if len(poly_coordinates) == 8:
            self.isPolyMode = True
        else:
            self.isPolyMode = False

        if len(bboxes) == 0:
            self.id.clear()

        # Save current time once
        current_time = datetime.now()

        # Loop through all bounding box
        for person_bbox in bboxes:

            if len(person_bbox) != 7:
                continue

            if person_bbox[6] != 0:
                continue

            bbox = np.copy(person_bbox)

            fy = 1/(self.resized_img_size[0]/self.ori_img_size[0])
            fx = 1/(self.resized_img_size[1]/self.ori_img_size[1])

            bbox[0] = bbox[0] * fx  # x1
            bbox[1] = bbox[1] * fy  # y1
            bbox[2] = bbox[2] * fx  # x2
            bbox[3] = bbox[3] * fy  # y2

            # Count center of bounding box
            bbox_x_center = bbox[0] + (bbox[2] - bbox[0]) / 2  # center x
            bbox_y_bottom = bbox[3]  # bottom y
            
            bbox_id = str(bbox[4])

            # Using dict.get() for checking
            person_data = self.id.get(bbox_id, {
                'name': 'Unknown',
                'gender': 'Unknown',
                'gender_score': 0,
                'prev_distRed': 0,
                'prev_distGreen': 0,
                'score': 0
            })
            
            self.id[bbox_id] = person_data
            
            if bbox_id not in self.detection_times:
                self.detection_times[bbox_id] = current_time
            else:
                # Calculate the duration of detection
                detection_duration = current_time - self.detection_times[bbox_id]
                self.detection_times[bbox_id] = detection_duration
                
            # Check which face belongs to which person bounding box
            for idx, (((ax1, ay1, ax2, ay2, w, h), center1, center2), (face_name, score, feat), (gender, gender_score)) in enumerate(zip(face_coordinates, feats, genders)):
                # print(len(feats), len(face_coordinates), len(genders))
                
                bx1 = bbox[0]
                by1 = bbox[1]
                bx2 = bbox[2]
                by2 = bbox[3]

                cx1 = max(min(ax1, ax2), min(bx1, bx2))
                cy1 = max(min(ay1, ay2), min(by1, by2))
                cx2 = min(max(ax1, ax2), max(bx1, bx2))
                cy2 = min(max(ay1, ay2), max(by1, by2))
                
                point_face = Point(center1, center2)
                polygon_bbox = Polygon([(bx1, by1), (bx2, by1), (bx2, by2), (bx1, by2)])

                if polygon_bbox.contains(point_face) and score >= self.id[bbox_id]['score'] and cx1<cx2 and cy1<cy2:
                    inter_area = (cx2-cx1)*(cy2-cy1)
                    if int(inter_area) == int(w*h) and center2 > by1:
                        if face_name != 'Unknown':
                            if face_name == None and self.id[bbox_id]['name'] == "Unknown":
                                # if w*h > 1000:
                                #     if not os.path.isdir(os.path.join(RV.root_path, 'Unknown')):
                                #         os.mkdir(os.path.join(RV.root_path, 'Unknown'))

                                #     # random_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
                                #     # filename = datetime.now().strftime('%Y-%m-%d_%H-%M-%S.jpg')
                                #     # while os.path.exists(os.path.join(RV.root_path, 'Unknown/' + filename)):
                                #     #     filename = datetime.now().strftime('%Y-%m-%d_%H-%M-') +  "{:02d}".format(int(datetime.now().strftime('%S')) + 1) + '.jpg'

                                #     x_expand = int(w/4)
                                #     y_expand = int(h/4)

                                #     new_x1 = int(ax1 - x_expand)
                                #     new_y1 = int(ay1 - y_expand)
                                #     new_x2 = int(ax2 + x_expand)
                                #     new_y2 = int(ay2 + y_expand)

                                #     if new_x1 < 0: new_x1 = 0
                                #     if new_y1 < 0: new_y1 = 0
                                #     if new_x2 > img.shape[1]: new_x2 = img.shape[1]
                                #     if new_y2 > img.shape[0]: new_y2 = img.shape[0]

                                #     cropped_img = img_ori[new_y1:new_y2, new_x1:new_x2]
                                    
                                #     detected_feats, _= RV.get_feature(cropped_img)
                                #     if len(detected_feats) != 0:
                                #         # cv2.imwrite(os.path.join(RV.root_path, 'Unknown/' + filename), cropped_img)

                                #         try:
                                #             RV.known_features['Unknown'].append(feat)
                                #         except:
                                #             RV.known_features['Unknown'] = [feat]

                                self.GV.feats[idx][-3] = 'Unknown'
                                face_name = 'Unknown'

                            self.id[bbox_id]['name'] = face_name
                            self.id[bbox_id]['score'] = score

                            del face_coordinates[idx]
                            del feats[idx]
                            del genders[idx]

                            if face_name != 'Unknown':
                                personnel = models.Personnels.objects.get(name=face_name)
                                saved_gender = 'Male' if personnel.gender == 'M' else 'Female'
                                self.id[bbox_id]['gender'] = saved_gender
                                self.id[bbox_id]['gender_score'] = 1
                            
                        if gender_score > self.id[bbox_id]['gender_score'] and face_name == 'Unknown':
                            self.id[bbox_id]['gender'] = gender
                            self.id[bbox_id]['gender_score'] = gender_score
                    
                        break

            # Get the distance of a point to green and red line
            if self.isPolyMode:
                x1, x2, x3, x4, x5, x6, x7, x8 = poly_coordinates[:,0]
                y1, y2, y3, y4, y5, y6, y7, y8 = poly_coordinates[:,1]
                
                distG1 = self.distance(x1, y1, x2, y2, bbox_x_center, bbox_y_bottom)
                distG2 = self.distance(x2, y2, x3, y3, bbox_x_center, bbox_y_bottom)
                distG3 = self.distance(x3, y3, x4, y4, bbox_x_center, bbox_y_bottom)

                distR1 = self.distance(x5, y5, x6, y6, bbox_x_center, bbox_y_bottom)
                distR2 = self.distance(x6, y6, x7, y7, bbox_x_center, bbox_y_bottom)
                distR3 = self.distance(x7, y7, x8, y8, bbox_x_center, bbox_y_bottom)

                distGreen = min(distG1, distG2, distG3)
                distRed = min(distR1, distR2, distR3)
            else:
                x1, x2, x3, x4 = poly_coordinates[:,0]
                y1, y2, y3, y4 = poly_coordinates[:,1]

                distGreen = self.distance(x1, y1, x2, y2, bbox_x_center, bbox_y_bottom)
                distRed = self.distance(x3, y3, x4, y4, bbox_x_center, bbox_y_bottom)

            # For polygon calculation | to detect whether the point is inside the polygon or not
            polygon = Polygon(poly_coordinates)
            point = Point(bbox_x_center, bbox_y_bottom)

            # If point is inside polygon
            if polygon.contains(point):
                if bbox_id not in self.green and bbox_id not in self.red:
                    if self.id[bbox_id]['prev_distGreen'] == 0 and self.id[bbox_id]['prev_distRed'] == 0:
                        if distGreen < distRed:
                            self.green = np.append(self.green, bbox_id)
                    elif self.id[bbox_id]['prev_distGreen'] < self.id[bbox_id]['prev_distRed']:
                        self.green = np.append(self.green, bbox_id)
                    else:
                        self.red = np.append(self.red, bbox_id)

            # If point is outside polygon
            else:
                if bbox_id in self.red:
                    if distRed > distGreen:
                        if self.id[bbox_id]['name'] != 'Unknown':
                            cam = models.Camera_Settings.objects.get(id=cam_id)
                            personnel = models.Personnels.objects.get(name=self.id[bbox_id]['name'])

                            models.Personnel_Entries.objects.create(
                                personnel=personnel,
                                camera=cam,
                                timestamp=datetime.now(),
                                presence_status= ''  
                            )
                        
                        if self.id[bbox_id]['gender'] == "Male":
                            self.GV.male_enter += 1
                        elif self.id[bbox_id]['gender'] == "Female":
                            self.GV.female_enter += 1
                        else:
                            self.GV.unknown_enter += 1
                   
                    self.red = np.delete(self.red, self.red==bbox_id)
                if bbox_id in self.green:
                    if distGreen > distRed:
                        self.GV.exit += 1

                    self.green = np.delete(self.green, self.green==bbox_id)

            self.id[bbox_id]['prev_distRed'] = distRed
            self.id[bbox_id]['prev_distGreen'] = distGreen

            img = self.get_label_img(img, [[int(data) for data in bbox[:4]], str(bbox[4]), bbox[5]])

        # Draw line based on polygon
        cv2.polylines(img, [poly_coordinates[:int(len(poly_coordinates)/2)]], False, (0, 255, 0), 2)
        cv2.polylines(img, [poly_coordinates[int(len(poly_coordinates)/2):]], False, (0, 0, 255), 2)

        # Create fill polygon
        alpha = 0.6
        overlay = img.copy()
        cv2.fillPoly(overlay, [poly_coordinates], (105, 105, 105))
        img = cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0)

        # Store occupancy
        self.GV.occupancy = (self.GV.female_enter + self.GV.male_enter + self.GV.unknown_enter + self.GV.total_enter) - (self.GV.exit + self.GV.total_exit) 
 
        if self.GV.occupancy < 0:
            self.GV.occupancy = 0

        # Print total count
        # cv2.putText(img, "Latest Update", (20, frame.shape[0] - 300), self.font, self.font_size, (255, 255, 255), self.font_thickness)
        # cv2.putText(img, "Undetected", (20, frame.shape[0] - 260), self.font, self.font_size, (255, 255, 255), self.font_thickness)
        # cv2.putText(img, "Female Enter", (20, frame.shape[0] - 220), self.font, self.font_size, (255, 255, 255), self.font_thickness)
        # cv2.putText(img, "Male Enter", (20, frame.shape[0] - 180), self.font, self.font_size, (255, 255, 255), self.font_thickness)
        # cv2.putText(img, "Occupancy", (20, frame.shape[0] - 140), self.font, self.font_size, (255, 255, 255), self.font_thickness)
        # cv2.putText(img, "Enter", (20, frame.shape[0] - 100), self.font, self.font_size, (255, 255, 255), self.font_thickness)
        # cv2.putText(img, "Exit", (20, frame.shape[0] - 60), self.font, self.font_size, (255, 255, 255), self.font_thickness)
        cv2.putText(img, "Detect Speed", (20, frame.shape[0] - 20), self.font, self.font_size, (255, 255, 255), self.font_thickness)

        # cv2.putText(img, ": " + str(self.GV.names[0]) + " enters at " + str(self.GV.names[1]), (250, frame.shape[0] - 300), self.font, self.font_size, (255, 255, 255), self.font_thickness)
        # cv2.putText(img, ": " + str(self.GV.unknown_enter), (250, frame.shape[0] - 260), self.font, self.font_size, (255, 255, 255), self.font_thickness)
        # cv2.putText(img, ": " + str(self.GV.female_enter), (250, frame.shape[0] - 220), self.font, self.font_size, (255, 255, 255), self.font_thickness)
        # cv2.putText(img, ": " + str(self.GV.male_enter), (250, frame.shape[0] - 180), self.font, self.font_size, (255, 255, 255), self.font_thickness)
        # cv2.putText(img, ": " + str(self.GV.occupancy), (250, frame.shape[0] - 140), self.font, self.font_size, (255, 255, 255), self.font_thickness)
        # cv2.putText(img, ": " + str((self.GV.female_enter + self.GV.male_enter + self.GV.unknown_enter)), (250, frame.shape[0] - 100), self.font, self.font_size, (255, 255, 255), self.font_thickness)
        # cv2.putText(img, ": " + str(self.GV.exit), (250, frame.shape[0] - 60), self.font, self.font_size, (255, 255, 255), self.font_thickness)
        cv2.putText(img, ": " + str("{:.2f}".format(self.detectSpeed)) + 's', (250, frame.shape[0] - 20), self.font, self.font_size, (255, 255, 255), self.font_thickness)

        return img

