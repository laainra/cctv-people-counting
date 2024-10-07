# views.py

from django.shortcuts import render
from ..models import Personnel_Entries, Personnels
from django.db.models import F
from django.utils import timezone

def reports(request):
    # Get today's date
    today = timezone.now().date()

    # Query the Personnel Entries with related personnel information
    entries = Personnel_Entries.objects.select_related('personnel').filter(
        timestamp__date=today
    ).annotate(
        personnel_name=F('personnel__name'),  # Assuming the Personnels model has a 'name' field
        employment_status=F('personnel__employment_status')  # Assuming the Personnels model has an 'employment_status' field
    ).values(
        'personnel_name', 
        'employment_status', 
        'timestamp', 
        'presence_status'
    ).order_by('timestamp')

    context = {
        'entries': entries,
    }

    return render(request, 'reports.html', context)
