from django.shortcuts import render, HttpResponse, get_object_or_404
from django.http.response import JsonResponse
from .. import models
from django.contrib.auth.decorators import login_required
from ..decorators import role_required
from django.contrib.auth.hashers import make_password
from django.utils.timezone import now, timedelta
from django.core.paginator import Paginator

@login_required(login_url='login')
@role_required('superadmin')
def superadmin_home(request):
    today = now()
    last_7_days = today - timedelta(days=7)
    last_30_days = today - timedelta(days=30)

    total_companies = models.Company.objects.count()
    companies_last_7_days = models.Company.objects.filter(createdAt__gte=last_7_days).count()
    companies_last_30_days = models.Company.objects.filter(createdAt__gte=last_30_days).count()

    total_accounts = models.CustomUsers.objects.count()
    accounts_last_7_days = models.CustomUsers.objects.filter(date_joined__gte=last_7_days).count()
    accounts_last_30_days = models.CustomUsers.objects.filter(date_joined__gte=last_30_days).count()

    total_employees = models.Personnels.objects.count()
    employees_last_7_days = models.Personnels.objects.filter(createdAt__gte=last_7_days).count()
    employees_last_30_days = models.Personnels.objects.filter(createdAt__gte=last_30_days).count()

    context = {
        'total_companies': total_companies,
        'companies_last_7_days': companies_last_7_days,
        'companies_last_30_days': companies_last_30_days,
        'total_accounts': total_accounts,
        'accounts_last_7_days': accounts_last_7_days,
        'accounts_last_30_days': accounts_last_30_days,
        'total_employees': total_employees,
        'employees_last_7_days': employees_last_7_days,
        'employees_last_30_days': employees_last_30_days,
        'companies': models.Company.objects.all(),
    }
    return render(request, 'superadmin/dashboard.html', context)

@login_required(login_url='login')
@role_required('superadmin')
def company(request):
    search_term = request.GET.get('search', '').lower()
    entries_per_page = int(request.GET.get('entries', 10))
    page = int(request.GET.get('page', 1))

    companies = models.Company.objects.all()
    if search_term:
        companies = companies.filter(name__icontains=search_term)

    paginator = Paginator(companies, entries_per_page)
    paginated_companies = paginator.get_page(page)

    context = {
        'companies': paginated_companies,
        'company_count': paginator.count,
        'entries_per_page': entries_per_page,
        'search_term': search_term,
        'page': page,
        'total_pages': paginator.num_pages,
    }
    return render(request, 'superadmin/company_list.html', context)

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
