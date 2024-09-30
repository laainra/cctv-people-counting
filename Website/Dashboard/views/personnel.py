import os
import shutil
import cv2
import shutil
from datetime import datetime
from .var import var


# Backend Library

from django.shortcuts import render, redirect, HttpResponse
from django.contrib.auth.decorators import login_required
from django.http.response import JsonResponse
from .. import forms, models

# Artificial Intelligence Library
from ..Artificial_Intelligence.variables import RecognitionVariable as RV

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
    # personnel_path = os.path.(os.path.dirname(
    #     __file__), '../static/img/personnel_pics')

    profile_list = []

    for personnel_name in data:
        profile_pic = None
        for file in os.listdir(os.path.join(var.personnel_path, personnel_name)):

            if file.endswith('.jpeg'):
                profile_pic = file
        profile_list.append(profile_pic)

    data = list(map(list, zip(data, profile_list)))

    selected = models.Personnels.objects.get(
        name=request.session['selected_personnel'])

    img_list = [file for file in os.listdir(os.path.join(
        var.personnel_path, request.session['selected_personnel'])) if not file.endswith('.txt')]
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
                    os.remove(os.path.join(var.personnel_path,
                              request.session['selected_personnel'], img_name))
                RV.set_personnel_known_faces(
                    request.session['selected_personnel'])

                request.session['status'] = 'image_deleted'

            elif request.POST['command'] == "move_image":
                destination_folder = request.POST['name']

                for img_name in request.session['selected_image']:
                    shutil.move(os.path.join(var.personnel_path, request.session['selected_personnel'], img_name), os.path.join(
                        var.personnel_path, destination_folder, str(img_name).replace('.jpeg', '.jpg')))

                if len(os.listdir(os.path.join(var.personnel_path, destination_folder))) == len(request.session['selected_image']):
                    os.rename(os.path.join(var.personnel_path, destination_folder, request.session['selected_image'][0]), os.path.join(
                        var.personnel_path, destination_folder, str(request.session['selected_image'][0]).replace('.jpg', '.jpeg')))

                RV.set_personnel_known_faces(destination_folder)
                RV.set_personnel_known_faces(
                    request.session['selected_personnel'])

                request.session['status'] = 'image_moved'

            elif request.POST['command'] == 'clear_unknown':
                for filename in os.listdir(os.path.join(var.personnel_path, 'Unknown')):
                    file_path = os.path.join(
                        var.personnel_path, 'Unknown', filename)
                    if not filename.endswith('.txt'):
                        try:
                            if os.path.isfile(file_path) or os.path.islink(file_path):
                                os.unlink(file_path)
                            elif os.path.isdir(file_path):
                                shutil.rmtree(file_path)
                        except Exception as e:
                            print('Failed to delete %s. Reason: %s' %
                                  (file_path, e))
                RV.set_personnel_known_faces('Unknown')

                request.session['status'] = 'unknown_cleared'

            elif request.POST['command'] == 'delete_personnel':

                models.Personnels.objects.get(
                    name=request.session['selected_personnel']).delete()

                shutil.rmtree(os.path.join(var.personnel_path,
                              request.session['selected_personnel']))

                request.session['selected_personnel'] = 'Unknown'

                request.session['status'] = 'personnel_deleted'

            elif request.POST['command'] == 'set_profile_pic':
                for file in os.listdir(os.path.join(var.personnel_path, request.session['selected_personnel'])):
                    if file.endswith('.jpeg'):
                        os.rename(os.path.join(var.personnel_path, request.session['selected_personnel'], file), os.path.join(
                            var.personnel_path, request.session['selected_personnel'], str(file).replace('.jpeg', '.jpg')))

                os.rename(os.path.join(var.personnel_path, request.session['selected_personnel'], request.session['selected_image'][0]), os.path.join(
                    var.personnel_path, request.session['selected_personnel'], str(request.session['selected_image'][0]).replace('.jpg', '.jpeg')))

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

                # Ensure 'selected_personnel' exists in session
                selected_personnel = request.session.get('selected_personnel')

                if not selected_personnel:
                    # Handle the case where 'selected_personnel' is not set in the session
                    request.session['status'] = 'img_adding_error_no_personnel'
                    # Redirect to an appropriate page
                    return redirect('some_error_page')

                request.session['status'] = 'img_adding_success'

                no_face_count = 0

                for f in files:
                    personnel_folder = os.path.join(
                        var.personnel_path, selected_personnel)

                    if len(os.listdir(personnel_folder)) == 0:
                        filename = datetime.now().strftime('%Y-%m-%d_%H-%M-') + \
                            "{:02d}".format(
                                int(datetime.now().strftime('%S')) + x) + '.jpeg'
                    else:
                        filename = datetime.now().strftime('%Y-%m-%d_%H-%M-') + \
                            "{:02d}".format(
                                int(datetime.now().strftime('%S')) + x) + '.jpg'

                    # Handle file upload
                    handle_uploaded_file(request, f, filename)

                    img = cv2.imread(os.path.join(personnel_folder, filename))

                    # Get face features
                    feats, _ = RV.get_feature(img)

                    # Set known faces if not already set
                    if len(RV.known_features) == 0:
                        RV.set_all_known_faces()

                    if len(feats) == 1:
                        # Append features to known_features for selected_personnel
                        if selected_personnel not in RV.known_features:
                            RV.known_features[selected_personnel] = []

                        RV.known_features[selected_personnel].append(feats[0])
                    else:
                        # Remove the file if no face is detected
                        os.remove(os.path.join(personnel_folder, filename))
                        request.session['status'] = 'img_adding_error1'
                        no_face_count += 1

                    x += 1

                if no_face_count == len(files):
                    request.session['status'] = 'img_adding_error2'

            return redirect('personnels')
    else:
        request.session['selected_image'] = []

        return render(request, 'personnels.html', {'Personnels': data, 'Page': "Personnels", 'Selected': selected, 'Img_List': img_list})

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

                if not os.path.exists(os.path.join(var.personnel_path, form.data['name'])):
                    os.mkdir(os.path.join(
                        var.personnel_path, form.data['name']))

                request.session['status'] = 'adding_success'

            return redirect('personnels')
        else:
            request.session['status'] = 'adding_error'
    return render(request, 'add_personnel.html', {'Selected_Personnel': None})

# Function to add pic


@login_required(login_url='login')
def add_pic(request):
    data = models.Personnels.objects.all().values()
    if request.method == 'POST':
        img = request.FILES.getlist('personnel_pic')
    return render(request, 'add_personnel_pic.html', {'Personnels': data})

# Function to edit personnel


@login_required(login_url='login')
def edit_personnel(request):
    form = forms.PersonnelForm()
    selected = models.Personnels.objects.get(
        name=request.session['selected_personnel'])

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
                selected.employment_status = form.cleaned_data['employment_status']
                selected.save()

                os.rename(os.path.join(var.personnel_path, request.session['selected_personnel']), os.path.join(
                    var.personnel_path, selected.name))

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
    shutil.rmtree(os.path.join(var.personnel_path, data.name))
    data.delete()
    return redirect('personnels')

# Function to upload file for personnel pics

def handle_uploaded_file(request, f, filename):
    with open(os.path.join(var.personnel_path, request.session['selected_personnel'], filename), "wb+") as destination:
        for chunk in f.chunks():
            destination.write(chunk)
