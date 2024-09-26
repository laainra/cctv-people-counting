import os
from django.shortcuts import render, HttpResponse
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.http.response import JsonResponse

# ================================================== SETTINGS DASHBOARD ================================================== #


@login_required(login_url='login')
def settings(request):
    user = User.objects.first()

    username = user.username

    f = open(os.path.join(os.path.dirname(__file__), '../',
             'static', 'unknown_deletion.txt'), "r")
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
        elif request.POST['command'] == 'save_del_time':
            f = open(os.path.join(os.path.dirname(__file__),
                     'static', 'unknown_deletion.txt'), "w")
            f.write(request.POST['time'])
            f.close()
            return HttpResponse("Success")

    else:
        return render(request, 'settings.html', {'Page': "Settings", 'Password': user, 'Username': username, 'Deletion_Time': deletion_time})
