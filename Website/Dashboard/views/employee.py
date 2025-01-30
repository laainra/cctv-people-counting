from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from ..decorators import role_required
from .. import models, forms

@login_required(login_url='login')
@role_required('employee')
def employee_home(request):
    user = models.Personnels.objects.get(user=request.user)
    return render(request, 'employee/dashboard.html')

@login_required(login_url='login')
@role_required('employee')
def presence_history(request):
    user = models.Personnels.objects.get(user=request.user)
    return render(request, 'employee/presence_history.html')

@login_required(login_url='login')
@role_required('employee')
def take_image(request):
    user = models.Personnels.objects.get(user=request.user)
    return render(request, 'employee/take_image.html', {"user": user})