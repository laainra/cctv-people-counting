from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from ..decorators import role_required
from .. import models
from django.utils import timezone
from datetime import datetime

@login_required(login_url='login')
@role_required('employee')
def employee_home(request):
    user = models.Personnels.objects.filter(user=request.user).first()
    
    # Get today's date
    today = timezone.now().date()
    
    # Get personnel entries for today
    entries_today = models.Personnel_Entries.objects.filter(personnel=user, timestamp__date=today)
    
    # Calculate summary
    summary = {
        'ontime': entries_today.filter(presence_status='ONTIME').count(),
        'late': entries_today.filter(presence_status='LATE').count(),
        'leave': entries_today.filter(presence_status='LEAVE').count(),
        'unknown': entries_today.filter(presence_status='UNKNOWN').count(),
    }
    
    context = {
        # 'user': user,
        'entries_today': entries_today,
        'summary': summary,
    }
    return render(request, 'employee/dashboard.html', context)

@login_required(login_url='login')
@role_required('employee')
def presence_history(request):
    user = models.Personnels.objects.get(user=request.user)
    return render(request, 'employee/presence_history.html')

@login_required(login_url='login')
@role_required('employee')
def take_image(request):
    user = models.Personnels.objects.get(user=request.user)
    return render(request, 'employee/take_image.html')