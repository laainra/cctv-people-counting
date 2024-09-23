import os
import shutil
import cv2
import numpy as np
import shutil
from datetime import date as set_date
from datetime import datetime, timedelta
from xlsxwriter.workbook import Workbook
from datetime import datetime

# Backend Library
from celery import shared_task
from django.shortcuts import render, redirect, HttpResponse
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.http.response import StreamingHttpResponse, JsonResponse, Http404
from django.contrib import messages
from . import forms, models

# Artificial Intelligence Library
from .Artificial_Intelligence.variables import RecognitionVariable as RV
from .Artificial_Intelligence.multi_camera import MultiCamera as MC

# Variables
class var:
    personnel_path = os.path.join(os.path.dirname(__file__), 'static/img/personnel_pics')

# ================================================== AUTHENTICATION ================================================== #

def login_user(request):
    form = forms.LoginForm(request)
    if request.method == "POST":
        try:
            if request.POST['command'] == 'reset_status':
                request.session['status'] = 'none'
        except:
            form = forms.LoginForm(request, data=request.POST)
            if form.is_valid():
                user = form.get_user()
                login(request, user)
                return redirect('home')
            else:
                request.session['status'] = 'login_error'
    return render(request, 'login.html', {'form':form})

@login_required(login_url='login')
def logout_user(request):
    logout(request)
    request.session['status'] = 'logout'
    return redirect('login')



# ================================================== STATISTICS DASHBOARD ================================================== #

@login_required(login_url='login')
def home(request):
    data = models.Camera_Settings.objects.all()

    if len(data) == 0:
        active_cam = None
        ai_status = None
    else:
        for cam in data:
            status = MC.get_camera_status(cam.id)

            cam.cam_is_active = status
            cam.save()

        try:
            active_cam = models.Camera_Settings.objects.get(id=request.session['home_cam_num'])
        except:
            active_cam = models.Camera_Settings.objects.first()
            request.session['home_cam_num'] = int(active_cam.id)

        ai_status = (int(datetime.now().strftime('%X').replace(':', '')) > int(active_cam.cam_start.replace(':', ''))
                     and int(datetime.now().strftime('%X').replace(':', '')) < int(active_cam.cam_stop.replace(':', '')))

    if request.method == "POST":
        if request.POST['command'] == 'change_cam':
            request.session['home_cam_num'] = int(request.POST['id'])
            
            return HttpResponse("Success")
        
        elif request.POST['command'] == 'update_var':
            unknown_enter, female_enter, male_enter, out, inside = MC.get_variables(request.session['home_cam_num'])
            
            today_data = models.Counted_Instances.objects.filter(camera_id=request.session['home_cam_num'])
            
            total_male_enter = [int(model.male_entries) for model in today_data if str(model.timestamp).split('-')[0] == datetime.now().strftime('%D')]
            total_male_enter = sum(total_male_enter[:-1]) + male_enter

            total_female_enter = [int(model.female_entries) for model in today_data if str(model.timestamp).split('-')[0] == datetime.now().strftime('%D')]
            total_female_enter = sum(total_female_enter[:-1]) + female_enter

            total_unknown_enter = [int(model.unknown_gender_entries) for model in today_data if str(model.timestamp).split('-')[0] == datetime.now().strftime('%D')]
            total_unknown_enter = sum(total_unknown_enter[:-1]) + unknown_enter

            total_exit = [int(model.people_exits) for model in today_data if str(model.timestamp).split('-')[0] == datetime.now().strftime('%D')]
            total_exit = sum(total_exit[:-1]) + out

            inside = (total_male_enter + total_female_enter + total_unknown_enter) - total_exit
            inside = inside if inside >= 0 else 0
            
            male_percentage = 0
            female_percentage = 0

            if (total_female_enter + total_male_enter) != 0:
                female_percentage = (total_female_enter / (total_female_enter + total_male_enter)) * 100

                male_percentage = (total_male_enter / (total_female_enter + total_male_enter)) * 100

            total_enter = total_unknown_enter + total_female_enter + total_male_enter

            ai_status = (int(datetime.now().strftime('%X').replace(':', '')) > int(active_cam.cam_start.replace(':', ''))
                         and int(datetime.now().strftime('%X').replace(':', '')) < int(active_cam.cam_stop.replace(':', '')))

            return JsonResponse({'total_unknown_enter':str(total_unknown_enter), 
                                 'total_male_enter':str(total_male_enter), 
                                 'total_female_enter':str(total_female_enter),
                                 'total_enter':str(total_enter),
                                 'current_unknown_enter':str(unknown_enter),
                                 'current_male_enter':str(male_enter),
                                 'current_female_enter':str(female_enter),
                                 'male_percent':str(round(male_percentage)),
                                 'female_percent':str(round(female_percentage)),
                                 'total_exit': str(total_exit),
                                 'current_exit': str(out),
                                 'inside': str(inside),
                                 'ai_status': str(ai_status)})
        
        elif request.POST['command'] == 'get_daily_report':
            date = datetime.strptime(request.POST['date'], "%Y-%m-%d").strftime("%m/%d/%y")
            male_entries, female_entries, total_entries, occupancies, exits = MC.get_daily_report(active_cam.id, date)

            return JsonResponse({'male_entries': male_entries,
                                 'female_entries': female_entries,
                                 'total_entries': total_entries,
                                 'occupancies': occupancies,
                                 'exits': exits})
        
        elif request.POST['command'] == 'get_monthly_report':
            month = datetime.strptime(request.POST['date'], "%Y-%m").strftime("%m/%y")

            male_entries, female_entries, total_entries = MC.get_monthly_report(active_cam.id, month)

            return JsonResponse({'male_entries': male_entries,
                                 'female_entries': female_entries,
                                 'total_entries': total_entries})
        
        elif request.POST['command'] == 'get_date_range_report':
            start_date = datetime.strptime(request.POST['start_date'], "%Y-%m-%d").strftime("%m/%d/%y")
            end_date = datetime.strptime(request.POST['end_date'], "%Y-%m-%d").strftime("%m/%d/%y")

            male_entries, female_entries, total_entries, date_list = MC.get_date_range_report(active_cam.id, start_date, end_date)

            return JsonResponse({'male_entries': male_entries,
                                 'female_entries': female_entries,
                                 'total_entries': total_entries,
                                 'date_list': date_list})
        
        elif request.POST['command'] == 'get_personnel_report':
            if request.POST['entry_type'] == 'all_entries':

                date = datetime.strptime(request.POST['date'], "%Y-%m-%d").strftime("%m/%d/%y")

                personnel_entries_report = MC.get_personnel_report(active_cam.id, date)
            
            elif request.POST['entry_type'] == 'first_entry':
                
                date = datetime.strptime(request.POST['date'], "%Y-%m-%d").strftime("%m/%d/%y")

                personnel_entries_report = MC.get_personnel_report(active_cam.id, date)

                if len(personnel_entries_report) != 0:
                    personnel_entries_report.reverse()

                    personnel_entries_report = [personnel_entries_report[idx] for idx, val in enumerate(np.array(personnel_entries_report)[:, 0]) if val not in np.array(personnel_entries_report)[:, 0][:idx]]

            return JsonResponse({'Personnel_Entries': personnel_entries_report})
        
        elif request.POST['command'] == 'download_personnel_report':
            for file in os.listdir(os.path.join(os.path.dirname(__file__), 'static')):
                if file.endswith('.xlsx'):
                    os.remove(os.path.join(os.path.dirname(__file__), 'static', file))

            date = datetime.strptime(request.POST['date'], "%Y-%m-%d").strftime("%m/%d/%y")

            create_personnel_excel(request, date)

            return HttpResponse('success')
        
        elif request.POST['command'] == 'download_counting_report':
            for file in os.listdir(os.path.join(os.path.dirname(__file__), 'static')):
                if file.endswith('.xlsx'):
                    os.remove(os.path.join(os.path.dirname(__file__), 'static', file))

            if request.POST['chart_type'] == 'date':
                date = datetime.strptime(request.POST['date'], "%Y-%m-%d").strftime("%m/%d/%y")
                create_counting_excel(request, date, request.POST['chart_type'])
            elif request.POST['chart_type'] == 'month':
                month = datetime.strptime(request.POST['date'], "%Y-%m").strftime("%m/%y")
                create_counting_excel(request, month, request.POST['chart_type'])
            elif request.POST['chart_type'] == 'date_range':
                start_date = datetime.strptime(request.POST['start_date'], "%Y-%m-%d").strftime("%m/%d/%y")
                end_date = datetime.strptime(request.POST['end_date'], "%Y-%m-%d").strftime("%m/%d/%y")
                date = [start_date, end_date]
                create_counting_excel(request, date, request.POST['chart_type'])

            return HttpResponse('success')
    else:

        return render(request, 'index.html', {'Cams':data, 'Active_Cam':active_cam, 'AI_Status': ai_status, 'Page':"Statistic"})
    
def create_personnel_excel(request, date):
    d = datetime.strptime(date, '%m/%d/%y')
    filename = 'Personnel Entries Report - ' + d.strftime('%d %b %Y') + '.xlsx'

    filepath = os.path.join(os.path.dirname(__file__), 'static', filename)

    active_cam = models.Camera_Settings.objects.get(id=request.session['home_cam_num'])
    
    entries_data = models.Personnel_Entries.objects.filter(camera_id=active_cam.id)
    entries_data = [entries for entries in entries_data if str(entries.timestamp).split('-')[0] == date] 

    field = ["No", "Name", "Entry Time"]

    workbook = Workbook(filepath)
    worksheet = workbook.add_worksheet()

    worksheet.write(0, 0, active_cam.cam_name + ' - Personnel Report - ' + d.strftime('%d %b %Y'))

    for col, f in enumerate(field):
        worksheet.write(1, col, f)

    for row, entries in enumerate(entries_data, 2):
        worksheet.write(row, 0, row-1)
        worksheet.write(row, 1, entries.name)
        worksheet.write(row, 2, str(entries.timestamp).split('-')[1])
    workbook.close()

    request.session['download_file_path'] = filepath

def create_counting_excel(request, date, chart_type):

    active_cam = models.Camera_Settings.objects.get(id=request.session['home_cam_num'])
    
    if chart_type == 'date':
        d = datetime.strptime(date, '%m/%d/%y')
        filename = 'Counting Data Report - ' + d.strftime('%d %b %Y') + '.xlsx'
        filepath = os.path.join(os.path.dirname(__file__), 'static', filename)

        counting_data = models.Counted_Instances.objects.filter(camera_id=active_cam.id)
        counting_data = [data for data in counting_data if str(data.timestamp).split('-')[0] == date] 

        field = ["No", "Time Range", "Male", "Female", "Undetected", "Total Enter", "Total Exit", "Inside"]

        workbook = Workbook(filepath)
        worksheet = workbook.add_worksheet()

        worksheet.write(0, 0, active_cam.cam_name + ' - Daily Report - ' + d.strftime('%d %b %Y'))

        for col, f in enumerate(field):
            worksheet.write(1, col, f)

        for row, data in enumerate(counting_data, 2):
            current_hour = str(data.timestamp).split('-')[1].split(':')[0] 
            time_range = current_hour + ':00 - ' + str(int(current_hour) + 1) + ':00'
            total_entries = int(data.male_entries) + int(data.female_entries) + int(data.unknown_gender_entries)
            
            worksheet.write(row, 0, row-1)
            worksheet.write(row, 1, time_range)
            worksheet.write(row, 2, data.male_entries)
            worksheet.write(row, 3, data.female_entries)
            worksheet.write(row, 4, data.unknown_gender_entries)
            worksheet.write(row, 5, total_entries)
            worksheet.write(row, 6, data.people_exits)
            worksheet.write(row, 7, data.people_inside)
        workbook.close()

    elif chart_type == 'month':
        d = datetime.strptime(date, '%m/%y')
        filename = 'Counting Data Report - ' + d.strftime('%b %Y') + '.xlsx'
        filepath = os.path.join(os.path.dirname(__file__), 'static', filename)

        counting_data = models.Counted_Instances.objects.filter(camera_id=active_cam.id)
        counting_data = [data for data in counting_data if str(data.timestamp).split('-')[0].split('/')[0] == str(date).split('/')[0] and str(data.timestamp).split('-')[0].split('/')[2] == str(date).split('/')[1]] 
        
        field = ["No", "Date", "Male", "Female", "Undetected", "Total Enter"]

        workbook = Workbook(filepath)
        worksheet = workbook.add_worksheet()

        worksheet.write(0, 0, active_cam.cam_name + ' - Monthly Report - ' + d.strftime('%b %Y'))

        for col, f in enumerate(field):
            worksheet.write(1, col, f)

        row = 2

        for day in range(1, 32):
            total_male_entries = sum([int(data.male_entries) for data in counting_data if int(str(data.timestamp).split('-')[0].split('/')[1]) == day])
            total_female_entries = sum([int(data.female_entries) for data in counting_data if int(str(data.timestamp).split('-')[0].split('/')[1]) == day])
            total_unknown_entries = sum([int(data.unknown_gender_entries) for data in counting_data if int(str(data.timestamp).split('-')[0].split('/')[1]) == day])

            current_date = datetime.strptime(str(day) + '/' +date, '%d/%m/%y').strftime('%d %b %Y')

            total_entries = total_male_entries + total_female_entries + total_unknown_entries
            if total_entries != 0:
                worksheet.write(row, 0, row-1)
                worksheet.write(row, 1, current_date)
                worksheet.write(row, 2, total_male_entries)
                worksheet.write(row, 3, total_female_entries)
                worksheet.write(row, 4, total_unknown_entries)
                worksheet.write(row, 5, total_entries)
                row+=1
        workbook.close()

    elif chart_type == 'date_range':
        start_date = date[0]
        end_date = date[1]

        start_date = datetime.strptime(start_date, '%m/%d/%y')
        end_date = datetime.strptime(end_date, '%m/%d/%y')

        start_date = set_date(int(start_date.strftime('%Y')), int(start_date.strftime('%m')), int(start_date.strftime('%d')))
        end_date = set_date(int(end_date.strftime('%Y')), int(end_date.strftime('%m')), int(end_date.strftime('%d')))

        date_range = int((end_date - start_date).days) + 1

        filename = 'Counting Data Report - (' + start_date.strftime('%d %b %Y') + ' - ' + end_date.strftime('%d %b %Y') + ')' + '.xlsx'
        filepath = os.path.join(os.path.dirname(__file__), 'static', filename)

        counting_data = models.Counted_Instances.objects.filter(camera_id=active_cam.id)

        field = ["No", "Date", "Male", "Female", "Undetected", "Total Enter"]

        workbook = Workbook(filepath)
        worksheet = workbook.add_worksheet()

        worksheet.write(0, 0, active_cam.cam_name + ' - Date Range Report - (' + start_date.strftime('%d %b %Y') + ' - ' + end_date.strftime('%d %b %Y') + ')')

        for col, f in enumerate(field):
            worksheet.write(1, col, f)

        row = 2

        for i in range(date_range):
            current_date = start_date + timedelta(i)

            total_male_entries = sum([int(data.male_entries) for data in counting_data if data.timestamp.split('-')[0] == current_date.strftime("%m/%d/%y")])
            total_female_entries = sum([int(data.female_entries) for data in counting_data if data.timestamp.split('-')[0] == current_date.strftime("%m/%d/%y")])
            total_unknown_entries = sum([int(data.unknown_gender_entries) for data in counting_data if data.timestamp.split('-')[0] == current_date.strftime("%m/%d/%y")])
            total_entries = total_male_entries + total_female_entries + total_unknown_entries

            if total_entries != 0:
                worksheet.write(row, 0, row-1)
                worksheet.write(row, 1, current_date.strftime('%d %b %Y'))
                worksheet.write(row, 2, total_male_entries)
                worksheet.write(row, 3, total_female_entries)
                worksheet.write(row, 4, total_unknown_entries)
                worksheet.write(row, 5, total_entries)
            else:
                worksheet.write(row, 0, row-1)
                worksheet.write(row, 1, current_date.strftime('%d %b %Y'))
                worksheet.write(row, 2, '-')
                worksheet.write(row, 3, '-')
                worksheet.write(row, 4, '-')
                worksheet.write(row, 5, '-')

            row+=1
        workbook.close()

    request.session['download_file_path'] = filepath

def download(request):
    file_path = request.session['download_file_path']
    if os.path.exists(file_path):
        with open(file_path, 'rb') as fh:
            response = HttpResponse(fh.read(), content_type="application/ms-excel")
            response['Content-Disposition'] = 'inline; filename=' + os.path.basename(file_path)
            return response
    raise Http404



# ================================================== PERSONNEL DASHBOARD ================================================== #

# Function for personnel page
@login_required(login_url='login')
def personnels(request):
    try:
        request.session['selected_personnel']
    except:
        request.session['selected_personnel'] = 'Unknown'

    try:
        request.session['selected_image']
    except:
        request.session['selected_image'] = []

    for personnel_name in os.listdir(os.path.join(var.personnel_path)):
        try:
            models.Personnels.objects.get(name=personnel_name)
        except:
            models.Personnels.objects.create(name=personnel_name, gender="M")

    data = models.Personnels.objects.all()
    data = [personnel.name for personnel in data if personnel.name != 'Unknown']
    data.sort()
    data.insert(0, 'Unknown')

    profile_list = []

    for personnel_name in data:
        profile_pic = None
        for file in os.listdir(os.path.join(var.personnel_path, personnel_name)):
            if file.endswith('.jpeg'):
                profile_pic = file
        profile_list.append(profile_pic)

    data = list(map(list, zip(data, profile_list)))

    selected = models.Personnels.objects.get(name=request.session['selected_personnel'])

    img_list = [file for file in os.listdir(os.path.join(var.personnel_path, request.session['selected_personnel'])) if not file.endswith('.txt')]
    img_list.reverse()

    if request.method == "POST":
        command = request.POST.get('command', None)

        if command != None:
            if request.POST['command'] == "personnel":
                request.session['selected_personnel'] = request.POST['name']
           
            elif request.POST['command'] == "select_image":
                selected_img = list(request.session['selected_image'])
                selected_img.append(request.POST['name'])
                request.session['selected_image'] = selected_img
           
            elif request.POST['command'] == "unselect_image":
                selected_img = list(request.session['selected_image'])
                selected_img.remove(request.POST['name'])
                request.session['selected_image'] = selected_img
            
            elif request.POST['command'] == "delete_image":
                for img_name in request.session['selected_image']:
                    os.remove(os.path.join(var.personnel_path, request.session['selected_personnel'], img_name))
                RV.set_personnel_known_faces(request.session['selected_personnel'])

                request.session['status'] = 'image_deleted'
           
            elif request.POST['command'] == "move_image":
                destination_folder = request.POST['name']

                for img_name in request.session['selected_image']:
                    shutil.move(os.path.join(var.personnel_path, request.session['selected_personnel'], img_name), os.path.join(var.personnel_path, destination_folder, str(img_name).replace('.jpeg', '.jpg')))
                
                if len(os.listdir(os.path.join(var.personnel_path, destination_folder))) == len(request.session['selected_image']):
                    os.rename(os.path.join(var.personnel_path, destination_folder, request.session['selected_image'][0]), os.path.join(var.personnel_path, destination_folder, str(request.session['selected_image'][0]).replace('.jpg', '.jpeg')))
                
                RV.set_personnel_known_faces(destination_folder)
                RV.set_personnel_known_faces(request.session['selected_personnel'])

                request.session['status'] = 'image_moved'
            
            elif request.POST['command'] == 'clear_unknown':
                for filename in os.listdir(os.path.join(var.personnel_path, 'Unknown')):
                    file_path = os.path.join(var.personnel_path, 'Unknown', filename)
                    if not filename.endswith('.txt'):
                        try:
                            if os.path.isfile(file_path) or os.path.islink(file_path):
                                os.unlink(file_path)
                            elif os.path.isdir(file_path):
                                shutil.rmtree(file_path)
                        except Exception as e:
                            print('Failed to delete %s. Reason: %s' % (file_path, e))
                RV.set_personnel_known_faces('Unknown')

                request.session['status'] = 'unknown_cleared'

            elif request.POST['command'] == 'delete_personnel':

                models.Personnels.objects.get(name=request.session['selected_personnel']).delete()

                shutil.rmtree(os.path.join(var.personnel_path, request.session['selected_personnel']))

                request.session['selected_personnel'] = 'Unknown'

                request.session['status'] = 'personnel_deleted'

            elif request.POST['command'] == 'set_profile_pic':
                for file in os.listdir(os.path.join(var.personnel_path, request.session['selected_personnel'])):
                    if file.endswith('.jpeg'):
                        os.rename(os.path.join(var.personnel_path, request.session['selected_personnel'], file), os.path.join(var.personnel_path, request.session['selected_personnel'], str(file).replace('.jpeg', '.jpg')))
                
                os.rename(os.path.join(var.personnel_path, request.session['selected_personnel'], request.session['selected_image'][0]), os.path.join(var.personnel_path, request.session['selected_personnel'], str(request.session['selected_image'][0]).replace('.jpg', '.jpeg')))

                request.session['status'] = 'profile_updated'

            elif request.POST['command'] == 'reset_status':
                update_required = False

                if len(models.Camera_Settings.objects.filter(cam_is_active=True)) != 0:
                    for personnel_name in os.listdir(var.personnel_path):
                        if RV.known_features.get(personnel_name) == None:
                            RV.set_personnel_known_faces(personnel_name)
                        else:
                            if personnel_name == 'Unknown':
                                if len(RV.known_features[personnel_name]) != (len(os.listdir(os.path.join(var.personnel_path, personnel_name))) - 1):
                                    update_required = True
                                    break
                            else:
                                if len(RV.known_features[personnel_name]) != len(os.listdir(os.path.join(var.personnel_path, personnel_name))):
                                    update_required = True
                                    break

                request.session['status'] = 'none'

                return JsonResponse({'required_update': update_required})

            elif request.POST['command'] == 'update_personnel_data':
                for personnel_name in os.listdir(var.personnel_path):
                    if RV.known_features.get(personnel_name) == None:
                        RV.set_personnel_known_faces(personnel_name)
                    else:
                        if personnel_name == 'Unknown':
                            if len(RV.known_features[personnel_name]) != (len(os.listdir(os.path.join(var.personnel_path, personnel_name))) - 1):
                                RV.set_personnel_known_faces(personnel_name)
                        else:
                            if len(RV.known_features[personnel_name]) != len(os.listdir(os.path.join(var.personnel_path, personnel_name))):
                                RV.set_personnel_known_faces(personnel_name)

            return HttpResponse("Success")
        else:
            form = forms.UploadFileForm(request.POST, request.FILES)
            if form.is_valid():
                x = 0
                files = form.cleaned_data["image_file"]

                request.session['status'] = 'img_adding_success'

                no_face_count = 0

                for f in files:
                    if len(os.listdir(os.path.join(var.personnel_path, request.session['selected_personnel']))) == 0:
                        filename = datetime.now().strftime('%Y-%m-%d_%H-%M-') +  "{:02d}".format(int(datetime.now().strftime('%S')) + x) + '.jpeg'
                    else:    
                        filename = datetime.now().strftime('%Y-%m-%d_%H-%M-') +  "{:02d}".format(int(datetime.now().strftime('%S')) + x) + '.jpg'
                    
                    handle_uploaded_file(request, f, filename)

                    img = cv2.imread(os.path.join(var.personnel_path, request.session['selected_personnel'], filename))

                    feats, _ = RV.get_feature(img)

                    if len(RV.known_features) == 0:
                        RV.set_all_known_faces()

                    if len(feats) == 1:
                        RV.known_features[request.session['selected_personnel']].append(feats[0])
                    else:
                        os.remove(os.path.join(var.personnel_path, request.session['selected_personnel'], filename))
                        request.session['status'] = 'img_adding_error1'
                        no_face_count += 1

                    x+=1

                if no_face_count == len(files):
                    request.session['status'] = 'img_adding_error2'

            return redirect('personnels')
    else:
        request.session['selected_image'] = []

        return render(request, 'personnels.html', {'Personnels':data, 'Page':"Personnels", 'Selected':selected, 'Img_List':img_list})

# Function to add personnel
@login_required(login_url='login')
def add_personnel(request):
    form = forms.PersonnelForm()
    if request.method == "POST":
        form = forms.PersonnelForm(request.POST)
        if form.is_valid():
            try:
                models.Personnels.objects.get(name=form.cleaned_data['name'])

                request.session['status'] = 'name_error'
            except: 
                form.save()
                
                if not os.path.exists(os.path.join(os.path.dirname(__file__) + '/static/img/personnel_pics/', form.data['name'] )):
                    os.mkdir(os.path.join(os.path.dirname(__file__) + '/static/img/personnel_pics/', form.data['name'] ))
                
                request.session['status'] = 'adding_success'

            return redirect('personnels')
        else :
            request.session['status'] = 'adding_error'
    return render(request, 'add_personnel.html', {'Selected_Personnel': None})

# Function to add pic
@login_required(login_url='login')
def add_pic(request):
    data = models.Personnels.objects.all().values()
    if request.method == 'POST':
        img = request.FILES.getlist('personnel_pic') 
    return render(request, 'add_personnel_pic.html', {'Personnels':data})

# Function to edit personnel
@login_required(login_url='login')
def edit_personnel(request):
    form = forms.PersonnelForm()
    selected = models.Personnels.objects.get(name=request.session['selected_personnel'])

    if request.method == 'POST':
        form = forms.PersonnelForm(request.POST)
        if form.is_valid():
            try:
                if form.cleaned_data['name'] == request.session['selected_personnel']:
                    raise
                models.Personnels.objects.get(name=form.cleaned_data['name'])

                request.session['status'] = 'name_error'
            except: 
                selected.gender = form.cleaned_data['gender']
                selected.name = form.cleaned_data['name']
                selected.save()

                os.rename(os.path.join(var.personnel_path, request.session['selected_personnel']), os.path.join(var.personnel_path, selected.name))
                
                RV.set_personnel_known_faces(selected.name)

                request.session['selected_personnel'] = selected.name

                request.session['status'] = 'edit_success'
        else:
            print(form.errors)
            request.session['status'] = 'edit_error'

    return redirect('personnels')

# Function to delete personnel
@login_required(login_url='login')
def delete_personnel(request, id):
    data = models.Personnels.objects.get(id=id)
    shutil.rmtree(os.path.join(os.path.dirname(__file__) + '/static/img/personnel_pics/' , data.name))
    data.delete()
    return redirect('personnels')

# Function to upload file for personnel pics
def handle_uploaded_file(request, f, filename):
    with open(os.path.join(os.path.dirname(__file__), 'static/img/personnel_pics', request.session['selected_personnel'], filename), "wb+") as destination:
        for chunk in f.chunks():
            destination.write(chunk)


# ================================================== CAMERA DASHBOARD ================================================== #

@login_required(login_url='login')
def camera(request):
    frame_shape = (0.1, 0.1)
    data = models.Camera_Settings.objects.all()

    if len(data) == 0:
        active_cam = None
    else:
        for cam in data:
            status = MC.get_camera_status(cam.id) 

            cam.cam_is_active = status
            cam.save()

        try:
            active_cam = models.Camera_Settings.objects.get(id=request.session['cam_id'])
        except:
            active_cam = models.Camera_Settings.objects.first()
            request.session['cam_id'] = active_cam.id

        while active_cam.cam_is_active:
            try:
                frame, _ = MC.get_frame(request.session['cam_id'])
                frame_shape = (frame.shape[0], frame.shape[1])
                break
            except:
                pass
    
        if status:
            cam = active_cam
            poly = np.array([[cam.x1, cam.y1], [cam.x2, cam.y2], [cam.x3, cam.y3], [cam.x4, cam.y4], 
                             [cam.x8, cam.y8], [cam.x7, cam.y7], [cam.x6, cam.y6], [cam.x5, cam.y5]])
            poly = poly.astype(int)

            MC.set_polygon(request.session['cam_id'], poly)

    if request.method == "POST":
        if request.POST['command'] == 'open_settings':
            request.session['toggle_polygon'] = True
        elif request.POST['command'] == 'close_settings':
            request.session['toggle_polygon'] = False
        elif request.POST['command'] == 'select_camera':
            request.session['cam_id'] = int(request.POST['id'])
            request.session['toggle_polygon'] = False
        elif request.POST['command'] == 'reset_status':
            request.session['status'] = 'none'
        elif request.POST['command'] == 'get_camera':
            cam  = models.Camera_Settings.objects.get(id=request.POST['id'])
            return JsonResponse({'cam_name':cam.cam_name,
                                 'feed_src':cam.feed_src,
                                 'cam_start':cam.cam_start,
                                 'cam_stop':cam.cam_stop,
                                 'gender_detection':cam.gender_detection,
                                 'face_detection':cam.face_detection})

        return HttpResponse("Success")
    else:

        try: 
            request.session['toggle_polygon']
        except:
            request.session['toggle_polygon'] = False

        return render(request, 'camera.html', {'Cams':data,
                                               'Active_Cam':active_cam, 
                                               'Frame_X':frame_shape[1], 
                                               'Frame_Y':frame_shape[0], 
                                               'Toggle_Settings':request.session['toggle_polygon'],
                                               'Page':"Camera"})

@login_required
def start_stream(request):
    cam = models.Camera_Settings.objects.get(id=request.session['cam_id'])
    cam.cam_is_active = True
    cam.save()

    poly = np.array([[cam.x1, cam.y1], [cam.x2, cam.y2], [cam.x3, cam.y3], [cam.x4, cam.y4], 
                     [cam.x8, cam.y8], [cam.x7, cam.y7], [cam.x6, cam.y6], [cam.x5, cam.y5]])
    poly = poly.astype(int)

    try:
        cap = cv2.VideoCapture(int(cam.feed_src))
    except:
        cap = cv2.VideoCapture(cam.feed_src)

    # Check if feed source is valid
    if cap.isOpened():
        request.session['stream_running'] = False

        # Set known faces for face recognition
        if len(RV.known_features) == 0: 
            RV.set_all_known_faces()
        else:
            for personnel_name in os.listdir(var.personnel_path):
                if RV.known_features.get(personnel_name) == None:
                    RV.set_personnel_known_faces(personnel_name)
                else:
                    if personnel_name == 'Unknown':
                        if len(RV.known_features[personnel_name]) != (len(os.listdir(os.path.join(var.personnel_path, personnel_name))) - 1):
                            RV.set_personnel_known_faces(personnel_name)
                    else:
                        if len(RV.known_features[personnel_name]) != len(os.listdir(os.path.join(var.personnel_path, personnel_name))):
                            RV.set_personnel_known_faces(personnel_name)

        # Add camera
        MC.add_camera(cam.id, cam.feed_src)
        
        # Set polygon coordinates
        MC.set_polygon(cam.id, poly)

        # Set activated model
        MC.set_model(cam.id, cam.face_detection, cam.gender_detection)

        # Set AI time range
        MC.set_time_range(cam.id, cam.cam_start, cam.cam_stop)

        # Stop stream if camera is already running
        MC.stop_cam(cam.id)

        # Start stream
        MC.start_cam(cam.id)
        
        request.session['status'] = 'stream_success'
    else:
        request.session['status'] = 'stream_error'

    return redirect('camera')

@login_required
def change_camera(request):
    request.session['cam_id'] = int(request.POST['cam_number'])

    return redirect('camera')

@login_required
def stop_stream(request):
    cam = models.Camera_Settings.objects.get(id=request.session['cam_id'])
    cam.cam_is_active = False
    cam.save()

    MC.stop_cam(cam.id)

    return redirect('camera')

@login_required
def delete_camera(request, id):
    models.Camera_Settings.objects.get(id=id).delete()
    try:
        models.Counted_Instances.objects.filter(camera=id).delete()
    except:
        pass

    MC.stop_cam(id)

    MC.delete_cam(id)

    first_cam = models.Camera_Settings.objects.first()

    if str(id) == str(request.session['cam_id']):
        if first_cam != None:
            request.session['cam_id'] = int(first_cam.id)

    if str(id) == str(request.session['home_cam_num']):
        if first_cam != None:
            request.session['home_cam_num'] = int(first_cam.id)

    request.session['status'] = 'camera_deleted'

    return redirect('camera')

@login_required
def add_camera(request):
    if request.method == 'POST':
        form = forms.AddCameraForm(request.POST)
        if form.is_valid():
            form.save()
            cam = models.Camera_Settings.objects.last()

            MC.add_camera(cam.id, cam.feed_src)

            MC.set_time_range(cam.id, cam.cam_start, cam.cam_stop)

            request.session['status'] = 'adding_success'

            return redirect('camera')
        else:
            request.session['status'] = 'adding_error'
            
    return render(request,'add_camera.html', {'Active_Cam':None})

@login_required
def edit_camera(request, id):
    form = forms.AddCameraForm()
    active_cam = models.Camera_Settings.objects.get(id=id)

    if request.method == 'POST':
        form = forms.AddCameraForm(request.POST)
        if form.is_valid():
            if active_cam.feed_src != form.cleaned_data['feed_src']:
                MC.stop_cam(active_cam.id)
                MC.add_camera(active_cam.id, form.cleaned_data['feed_src'])
                active_cam.cam_is_active = False

            active_cam.feed_src = form.cleaned_data['feed_src']
            active_cam.cam_name = form.cleaned_data['cam_name']
            active_cam.gender_detection = form.cleaned_data['gender_detection']
            active_cam.face_detection = form.cleaned_data['face_detection']
            active_cam.cam_start = form.cleaned_data['cam_start']
            active_cam.cam_stop = form.cleaned_data['cam_stop']
            active_cam.save()

            try:
                MC.set_model(active_cam.id, bool(active_cam.face_detection), bool(active_cam.gender_detection))
                MC.set_time_range(active_cam.id, active_cam.cam_start, active_cam.cam_stop)
            except:
                pass

            request.session['status'] = 'edit_success'
            return redirect('camera')
        else:
            print(form.errors)
            request.session['status'] = 'edit_error'
            
    return render(request,'add_camera.html', {'Active_Cam':active_cam})

def gen(request):
    request.session['stream_running'] = True

    while request.session['stream_running']:
        try:
            frame, pred_frame = MC.get_frame(request.session['cam_id'])
        except:
            continue

        buffer = cv2.imencode('.jpg',pred_frame)[1]
        pred_frame = buffer.tobytes()

        yield(b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + pred_frame + b'\r\n\r\n')

@login_required(login_url='login')
def video_feed(request):
    return StreamingHttpResponse(gen(request), content_type='multipart/x-mixed-replace; boundary=frame')

@login_required
def save_coordinates(request):
    cam = models.Camera_Settings.objects.get(id=request.session['cam_id'])
    cam.x1=request.POST['x1']
    cam.y1=request.POST['y1']
    cam.x2=request.POST['x2']
    cam.y2=request.POST['y2']
    cam.x3=request.POST['x3']
    cam.y3=request.POST['y3']
    cam.x4=request.POST['x4']
    cam.y4=request.POST['y4']
    cam.x5=request.POST['x5']
    cam.y5=request.POST['y5']
    cam.x6=request.POST['x6']
    cam.y6=request.POST['y6']
    cam.x7=request.POST['x7']
    cam.y7=request.POST['y7']
    cam.x8=request.POST['x8']
    cam.y8=request.POST['y8']
    cam.save()

    poly = np.array([[cam.x1, cam.y1], [cam.x2, cam.y2], [cam.x3, cam.y3], [cam.x4, cam.y4], 
                     [cam.x8, cam.y8], [cam.x7, cam.y7], [cam.x6, cam.y6], [cam.x5, cam.y5]])
        
    poly = poly.astype(int)

    MC.set_polygon(cam.id, poly)

    return HttpResponse("Success")



# ================================================== SETTINGS DASHBOARD ================================================== #

@login_required(login_url='login')
def settings(request):
    user = User.objects.first()
    
    username = user.username

    f = open(os.path.join(os.path.dirname(__file__), 'static', 'unknown_deletion.txt'), "r")
    deletion_time = int(f.read())

    if request.method == 'POST':
        if request.POST['command'] == 'save_username':
            user.username = request.POST['username']
            user.save()
            return HttpResponse("Success")
        elif request.POST['command'] == 'check_pass':
            status = user.check_password(request.POST['password'])
            return JsonResponse({'status': status})
        elif request.POST['command'] == 'save_pass':
            user.password = make_password(request.POST['password'])
            user.save()
            update_session_auth_hash(request, user)
            return HttpResponse("Success")
        elif  request.POST['command'] == 'save_del_time':
            f = open(os.path.join(os.path.dirname(__file__), 'static', 'unknown_deletion.txt'), "w")
            f.write(request.POST['time'])
            f.close()
            return HttpResponse("Success")

    else:
        return render(request, 'settings.html', {'Page':"Settings", 'Password': user, 'Username': username, 'Deletion_Time': deletion_time})