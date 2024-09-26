# Backend Library
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required

from .. import forms

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

