from django.shortcuts import render, HttpResponse, get_object_or_404
from django.http.response import JsonResponse
from .. import models
from django.contrib.auth.decorators import login_required
from ..decorators import role_required
from django.contrib.auth.hashers import make_password
from django.utils.timezone import now, timedelta


@login_required(login_url='login')
@role_required('superadmin')
def superadmin_home(request):
    today = now()
    last_7_days = today - timedelta(days=7)
    last_30_days = today - timedelta(days=30)

    total_companies = models.Company.objects.count()
    companies_last_7_days = models.Company.objects.filter(createdAt__gte=last_7_days).count()
    companies_last_30_days = models.Company.objects.filter(createdAt__gte=last_30_days).count()

    context = {
        'total_companies': total_companies,
        'companies_last_7_days': companies_last_7_days,
        'companies_last_30_days': companies_last_30_days,
        'companies': models.Company.objects.all(),
    }
    return render(request, 'superadmin/dashboard.html', context)

@login_required(login_url='login')
@role_required('superadmin')
def company(request):
    return render(request, 'superadmin/company_list.html', {'companies': models.Company.objects.all()})

@login_required(login_url='login')
@role_required('superadmin')
def get_company(request, company_id):
    company = models.Company.objects.get(id=company_id)
    data = {
        'id': company_id,
        'company_name': company.name,
        'username': company.user.username,
        'email': company.user.email,
        'password': company.user.password,
    }
    return JsonResponse(data)

@login_required(login_url='login')
@role_required('superadmin')
def add_company(request):
    if request.method == "POST":
        data = request.POST
        try:
            user = models.CustomUsers.objects.create(
                username=data['username'],
                email=data['email'],
                password=make_password(data['password']),
                role='admin',
                is_admin=True,
            )
            models.Company.objects.create(name=data['company_name'], user=user)
            return JsonResponse({'success': True, 'message': 'Company created successfully!'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return HttpResponse(status=405)

@login_required(login_url='login')
@role_required('superadmin')
def edit_company(request, company_id):
    if request.method == "POST":
        data = request.POST
        try:
            company = get_object_or_404(models.Company, id=company_id)
            company.name = data.get('company_name', company.name)
            company.user.username = data.get('username', company.user.username)
            company.user.email = data.get('email', company.user.email)
            if 'password' in data and data['password']:
                company.user.password = make_password(data['password'])
            company.user.save()
            company.save()
            return JsonResponse({'success': True, 'message': 'Company updated successfully!'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return HttpResponse(status=405)

@login_required(login_url='login')
@role_required('superadmin')
def delete_company(request, company_id):
    if request.method == "POST":
        try:
            company = get_object_or_404(models.Company, id=company_id)
            company.user.delete()  # Delete the associated user
            company.delete()
            return JsonResponse({'success': True, 'message': 'Company deleted successfully!'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return HttpResponse(status=405)
