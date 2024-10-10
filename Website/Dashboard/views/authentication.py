from django.shortcuts import render, redirect
# Rename to avoid conflict
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required

from .. import forms

# ================================================== AUTHENTICATION ================================================== #


def user_login(request):  # Rename the view function
    form = forms.LoginForm(request)
    if request.method == "POST":
        try:
            if request.POST['command'] == 'reset_status':
                request.session['status'] = 'none'
        except:
            form = forms.LoginForm(request, data=request.POST)
            if form.is_valid():
                user = form.get_user()
                # Use the renamed auth_login function
                auth_login(request, user)
                return redirect('home')
            else:
                request.session['status'] = 'login_error'
    return render(request, 'login.html', {'form': form})


@login_required(login_url='login')
def user_logout(request):  # Rename the logout view function
    auth_logout(request)  # Use the renamed auth_logout function
    request.session['status'] = 'logout'
    return redirect('login')
