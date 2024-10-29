import os
import random
import numpy as np
from datetime import datetime, timedelta
from datetime import date as set_date
from xlsxwriter.workbook import Workbook
# from ..var import var

# Backend Library

from django.shortcuts import render,  HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.hashers import make_password
from django.http.response import JsonResponse, Http404
from django.shortcuts import redirect
from django.utils.timezone import now
from django.db.models import DateField
from django.db.models.functions import Cast
from django.db.models import Q
from .. import models
from django.conf import settings

# Artificial Intelligence Library
from ..Artificial_Intelligence.variables import RecognitionVariable as RV
from ..Artificial_Intelligence.multi_camera import MultiCamera as MC

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
            static_path = os.path.join(settings.BASE_DIR, 'dashboard', 'static')
            for file in os.listdir(static_path):
                if file.endswith('.xlsx'):
                    os.remove(settings.BASE_DIR, 'dashboard', 'static', file)

            date = datetime.strptime(request.POST['date'], "%Y-%m-%d").strftime("%m/%d/%y")

            create_personnel_excel(request, date)

            return HttpResponse('success')
        
        elif request.POST['command'] == 'download_counting_report':
            static_path = os.path.join(settings.BASE_DIR, 'dashboard', 'static')
            for file in os.listdir(static_path):
                if file.endswith('.xlsx'):
                    os.remove(settings.BASE_DIR, 'dashboard', 'static', file)

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

    filepath = os.path.join(settings.BASE_DIR, 'dashboard', 'static', filename)

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
        filepath = os.path.join(settings.BASE_DIR, 'dashboard', 'static', filename)

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
