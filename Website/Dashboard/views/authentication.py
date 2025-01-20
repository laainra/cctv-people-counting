from django.shortcuts import render, redirect
# Rename to avoid conflict
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required

from .. import forms

# ================================================== AUTHENTICATION ================================================== #
from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from .. import forms
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def user_login(request):  # View untuk login
    form = forms.LoginForm(request)
    if request.method == "POST":
        try:
            if request.POST['command'] == 'reset_status':
                request.session['status'] = 'none'
        except KeyError:
            form = forms.LoginForm(request, data=request.POST)
            if form.is_valid():
                user = form.get_user()
                auth_login(request, user)

                # Redirect berdasarkan role
                if user.is_superadmin:
                    return redirect('superadmin_home')
                elif user.is_admin:
                    return redirect('admin_home')
                elif user.is_employee:
                    return redirect('employee_home')
                else:
                    request.session['status'] = 'unauthorized_role'
                    return redirect('login')
            else:
                request.session['status'] = 'login_error'
    return render(request, 'login.html', {'form': form})


@login_required(login_url='login')
def user_logout(request):  # View untuk logout
    auth_logout(request)
    request.session['status'] = 'logout'
    return redirect('login')
