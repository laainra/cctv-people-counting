from datetime import datetime
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from ..decorators import role_required
from .. import models, forms
from django.db.models import Count, Q


# View for Admin Dashboard
@login_required(login_url='login')
@role_required('admin')
def admin_home(request):
    company = models.Company.objects.get(user=request.user)
    current_month = datetime.now().month
    current_year = datetime.now().year

    # Summary statistics for the current month
    summary = {
        'ontime': models.Personnel_Entries.objects.filter(presence_status='ontime', timestamp__month=current_month, timestamp__year=current_year).count(),
        'late': models.Personnel_Entries.objects.filter(presence_status='late', timestamp__month=current_month, timestamp__year=current_year).count(),
        'unknown': models.Personnel_Entries.objects.filter(presence_status='unknown', timestamp__month=current_month, timestamp__year=current_year).count(),
    }

    # Fetch Personnel_Entries data for today
    today = datetime.now().date()
    presence_data = models.Personnel_Entries.objects.filter(
        timestamp__date=today,
        personnel__company=company  # Corrected to filter by related Personnel
    )

    # Fetch top employees based on on-time Personnel_Entries
    top_employees = models.Personnel_Entries.objects.filter(
        timestamp__month=current_month,
        timestamp__year=current_year,
        presence_status='ontime').values('personnel').annotate(total_ontime=Count('id')).order_by('-total_ontime')[:5]

    # Render the dashboard with the fetched data
    return render(request, 'admin/dashboard.html', {
        'company': company,
        'summary': summary,
        'presence_data': presence_data,
        'top_employees': top_employees,
    })

@login_required(login_url='login')
@role_required('admin')
def division(request):
    company = models.Company.objects.get(user=request.user)
    divisions = models.Divisions.objects.filter(company=company)
    division_count = divisions.count()
    return render(request, 'admin/division.html', {'divisions': divisions,'division_count': division_count})

@login_required(login_url='login')
@role_required('admin')
def get_divisions(request):
    company = models.Company.objects.get(user=request.user)
    divisions = models.Divisions.objects.filter(company=company)
    divisions_data = [{'id': division.id, 'name': division.name} for division in divisions]
    return JsonResponse({'presence_status': 'success', 'divisions': divisions_data})

@login_required(login_url='login')
@role_required('admin')
def add_division(request):
    try:
        # Get the company associated with the currently logged-in user
        company = models.Company.objects.get(user=request.user)
    except models.Company.DoesNotExist:
        return JsonResponse({'presence_status': 'error', 'message': 'User does not belong to any company'}, presence_status=403)

    if request.method == 'POST':
        form = forms.AddDivisionForm(request.POST)
        if form.is_valid():
            # Save the form, associating it with the logged-in user's company
            division = form.save(commit=False)
            division.company = company
            division.save()
            return JsonResponse({'presence_status': 'success', 'message': 'Division created successfully'})
        else:
            return JsonResponse({'presence_status': 'error', 'message': 'Invalid form data', 'errors': form.errors})

@login_required(login_url='login')
@role_required('admin')
def edit_division(request, id):
    division = get_object_or_404(models.Divisions, id=id)
    if request.method == 'POST':
        form = forms.AddDivisionForm(request.POST, instance=division)
        if form.is_valid():
            form.save()
            return JsonResponse({'presence_status': 'success', 'message': 'Division updated successfully'})
        else:
            return JsonResponse({'presence_status': 'error', 'message': 'Invalid form data', 'errors': form.errors})
    return JsonResponse({'presence_status': 'error', 'message': 'Invalid request method'})

@login_required(login_url='login')
@role_required('admin')
def delete_division(request, id):
    division = get_object_or_404(models.Divisions, id=id)
    try:
        division.delete()
        return JsonResponse({'presence_status': 'success', 'message': 'Division deleted successfully'})
    except Exception as e:
        return JsonResponse({'presence_status': 'error', 'message': f'Failed to delete division: {str(e)}'})

@login_required(login_url='login')
@role_required('admin')
def get_division(request, id):
    division = get_object_or_404(models.Divisions, id=id)
    division_data = {'id': division.id, 'name': division.name}
    return JsonResponse({'presence_status': 'success', 'division': division_data})

@login_required(login_url='login')
@role_required('admin')
def employees(request):
    company = models.Company.objects.get(user=request.user)
    employees = models.Personnels.objects.filter(company=company)
    divisions = models.Divisions.objects.filter(company=company)
    return render(request, 'admin/employees.html', {'employees': employees, 'divisions': divisions})



@login_required(login_url='login')
@role_required('admin')
def presence(request):
    company = models.Company.objects.get(user=request.user)
    date = request.GET.get('date')
    personnel_id = request.GET.get('personnel_id')
    
    if date:
        date = datetime.strptime(date, "%Y-%m-%d").date()
    else:
        date = datetime.now().date()

    if personnel_id:
        presence_data = models.Personnel_Entries.objects.filter(timestamp__date=date, personnel_id=personnel_id)
    else:
        presence_data = models.Personnel_Entries.objects.filter(timestamp__date=date)

    personnel_list = models.Personnels.objects.filter(company=company)


    context = {
        'presence_data': presence_data,
        'personnel_list': personnel_list,
        'selected_date': date,
        'selected_personnel': personnel_id,
    }


    return render(request, 'admin/presence.html', context)

@login_required(login_url='login')
@role_required('admin')
def presence_cam(request):
    company = models.Company.objects.get(user=request.user)
    cams = models.Camera_Settings.objects.filter(
        Q(role_camera='P_IN') | Q(role_camera='P_OUT'),
        company=company
    )
    return render(request, 'admin/presence_cam.html', {'cams': cams})

@login_required(login_url='login')
@role_required('admin')
def tracking_cam(request):
    company = models.Company.objects.get(user=request.user)
    cams = models.Camera_Settings.objects.filter(role_camera='T', company=company) 
    return render(request, 'admin/tracking_cam.html', {'cams': cams})