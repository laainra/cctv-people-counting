import cv2
import threading
from datetime import datetime, timedelta
from datetime import date as set_date
from .. import models
from ..Artificial_Intelligence.camera_stream import CameraStream

class MultiCamera:
    # List of the class object for each camera
    obj_list = {}

    # Function to add camera based on list
    def add_camera(cam_id, camera):
        if MultiCamera.obj_list.get(str(cam_id)) != None:
            del MultiCamera.obj_list[str(cam_id)]

            MultiCamera.add_camera(cam_id, camera)
        else:
            MultiCamera.obj_list[str(cam_id)] = {}
            
            if str(camera).isnumeric():
                MultiCamera.obj_list[str(cam_id)]['class'] = CameraStream(int(camera), int(cam_id))
            else:
                MultiCamera.obj_list[str(cam_id)]['class'] = CameraStream(camera,  int(cam_id))
                
            obj = MultiCamera.obj_list[str(cam_id)]['class']
            MultiCamera.obj_list[str(cam_id)]['thread'] = threading.Thread(target=obj.start_stream, daemon=True)

    # Function to start all camera on the list at once
    def start_all():
        for t in MultiCamera.obj_list.values():
            if not t['thread'].is_alive():
                t['thread'].start()
    
    # Function to stop all camera on the list at once 
    def stop_all():
        for cam_id in MultiCamera.obj_list.keys():
            MultiCamera.stop_cam(cam_id)

    # Function to delete all camera
    def delete_all():
        for cam_id in MultiCamera.obj_list.keys():
            MultiCamera.delete_cam(cam_id)

    # Function to start specific camera
    def start_cam(cam_id):
        if MultiCamera.obj_list.get(str(cam_id)) is not None:
            obj = MultiCamera.obj_list[str(cam_id)]['class']

            if MultiCamera.obj_list[str(cam_id)]['thread'] is None or not MultiCamera.obj_list[str(cam_id)]['thread'].is_alive():
                MultiCamera.obj_list[str(cam_id)]['thread'] = threading.Thread(target=obj.start_stream, daemon=True)
                MultiCamera.obj_list[str(cam_id)]['thread'].start()

    # # Function to stop specific camera
    # def stop_cam(cam_id):
    #     if MultiCamera.obj_list.get(str(cam_id)) != None:
    #         obj = MultiCamera.obj_list[str(cam_id)]['class']
    #         obj.stop_stream()

    #         MultiCamera.obj_list[str(cam_id)]['thread'] = threading.Thread(target=obj.start_stream, daemon=True)
    def stop_cam(cam_id):
        if MultiCamera.obj_list.get(str(cam_id)) is not None:
            obj = MultiCamera.obj_list[str(cam_id)]['class']
            obj.stop_stream()

            # Remove the thread from the obj_list to ensure it does not restart
            MultiCamera.obj_list[str(cam_id)]['thread'] = None
            
    # Function to delete specific camera
    def delete_cam(cam_id):
        if MultiCamera.obj_list.get(str(cam_id)) != None:
            del MultiCamera.obj_list[str(cam_id)]

    # Function to get all camera status
    def get_camera_status(cam_id):
        if MultiCamera.obj_list.get(str(cam_id)) is not None:
            # Check if the 'thread' key exists before accessing it
            thread = MultiCamera.obj_list[str(cam_id)].get('thread')
            isRunning = thread.is_alive() if thread else False
        else:
            isRunning = False

        return isRunning

    # Function to get predicted frame from camera
    def get_frame(cam_id, resize=None):
        obj = MultiCamera.obj_list[str(cam_id)]['class']
        
        frame = obj.frame
        pred_frame = obj.pred_frame

        if resize != None:
            frame = cv2.resize(frame, None, fx=resize, fy=resize)
            pred_frame = cv2.resize(pred_frame, None, fx=resize, fy=resize)

        return frame, pred_frame

    def get_variables(cam_id):
        obj = MultiCamera.obj_list[str(cam_id)]['class']

        unknown_enter = obj.GV.unknown_enter
        female_enter = obj.GV.female_enter
        male_enter = obj.GV.male_enter
        out = obj.GV.exit
        inside = obj.GV.occupancy

        return unknown_enter, female_enter, male_enter, out, inside
    
    def get_person_bbox(cam_id):
        obj = MultiCamera.obj_list[str(cam_id)]['class']

        detected_person = obj.GV.person_bboxes

        return len(detected_person)
    
    def set_polygon(cam_id, poly_coordinates):
        obj = MultiCamera.obj_list[str(cam_id)]['class']

        obj.poly = poly_coordinates

    def set_model(cam_id, recognition_active, gender_active, capture_active):
        obj = MultiCamera.obj_list[str(cam_id)]['class']

        obj.fr_active = recognition_active
        obj.gd_active = gender_active
        obj.fc_active = capture_active

    def set_time_range(cam_id, cam_start, cam_stop):
        obj = MultiCamera.obj_list[str(cam_id)]['class']

        obj.time_range = [str(cam_start), str(cam_stop)]

    def get_daily_report(cam_id, date):
        model_list = models.Counted_Instances.objects.filter(camera=cam_id)

        male_entries = [None] * 24
        female_entries = [None] * 24
        total_entries = [None] * 24
        occupancies = [None] * 24
        exits = [None] * 24

        for model in model_list:
            if model.timestamp.split('-')[0] == date:
                hour = int(model.timestamp.split('-')[1].split(':')[0])
                male_entries[hour] = model.male_entries
                female_entries[hour] = model.female_entries
                total_entries[hour] = int(model.female_entries) + int(model.male_entries) + int(model.unknown_gender_entries)
                occupancies[hour] = int(model.people_inside)
                exits[hour] = int(model.people_exits)

        return male_entries, female_entries, total_entries, occupancies, exits

    def get_monthly_report(cam_id, date):
        model_list = models.Counted_Instances.objects.filter(camera=cam_id)

        male_entries = [None] * 32
        female_entries = [None] * 32
        total_entries = [None] * 32

        for i in range(1, 32):
            male_count = None
            female_count = None
            unknown_count = None

            for model in model_list:
                model_date = model.timestamp.split('-')[0].split('/')
                if int(model_date[1]) == i and str(model_date[0] + '/' + model_date[2]) ==  date:
                    if male_count == None:
                        male_count = 0
                    if female_count == None:
                        female_count = 0
                    if unknown_count == None:
                        unknown_count = 0
                        
                    male_count += int(model.male_entries)
                    female_count += int(model.female_entries)
                    unknown_count += int(model.unknown_gender_entries)
            
            if male_entries != None and female_entries != None and unknown_count != None:
                male_entries[i] = male_count
                female_entries[i] = female_count
                total_entries[i] = male_count+female_count+unknown_count

        return male_entries, female_entries, total_entries
    
    def get_date_range_report(cam_id, start_date, end_date):
        model_list = models.Counted_Instances.objects.filter(camera=cam_id)

        start_date = datetime.strptime(start_date, '%m/%d/%y')
        end_date = datetime.strptime(end_date, '%m/%d/%y')

        start_date = set_date(int(start_date.strftime('%Y')), int(start_date.strftime('%m')), int(start_date.strftime('%d')))
        end_date = set_date(int(end_date.strftime('%Y')), int(end_date.strftime('%m')), int(end_date.strftime('%d')))

        date_range = int((end_date - start_date).days) + 1

        date_list = []

        male_entries = [None] * date_range
        female_entries = [None] * date_range
        total_entries = [None] * date_range

        for i in range(date_range):
            male_count = None
            female_count = None
            unknown_count = None

            date = start_date + timedelta(i)

            date_list.append(date.strftime("%m/%d/%Y"))

            for model in model_list:
                model_date = model.timestamp.split('-')[0]
                if model_date == date.strftime("%m/%d/%y"):
                    if male_count == None:
                        male_count = 0
                    if female_count == None:
                        female_count = 0
                    if unknown_count == None:
                        unknown_count = 0
                        
                    male_count += int(model.male_entries)
                    female_count += int(model.female_entries)
                    unknown_count += int(model.unknown_gender_entries)
            
            if male_entries != None and female_entries != None and unknown_count != None:
                male_entries[i] = male_count
                female_entries[i] = female_count
                total_entries[i] = male_count+female_count+unknown_count

        return male_entries, female_entries, total_entries, date_list

    def get_personnel_report(cam_id, date):
        personnel_list = models.Personnel_Entries.objects.filter(camera_id=cam_id)

        personnel_list = [[personnel.name, personnel.timestamp.split('-')[1]] for personnel in personnel_list if str(personnel.timestamp).split('-')[0] == date]
        personnel_list.reverse()

        return personnel_list




        