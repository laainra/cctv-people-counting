from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..forms import ProfileForm, CompanyNameForm, PersonnelNameForm
from ..models import CustomUsers, Company, Personnels

@login_required(login_url='login')
def profile(request):
    user = request.user
    company = Company.objects.filter(user=user).first()
    employee = Personnels.objects.filter(user=user).first()

    if request.method == 'POST':
        profile_form = ProfileForm(request.POST, instance=user)
        if user.role == 'superadmin':
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Your profile has been updated successfully.')
                return redirect('profile')
        elif user.role == 'admin':
            company_form = CompanyNameForm(request.POST, instance=company)
            if profile_form.is_valid() and company_form.is_valid():
                profile_form.save()
                company_form.save()
                messages.success(request, 'Your profile has been updated successfully.')
                return redirect('profile')
        elif user.role == 'employee':
            personnel_form = PersonnelNameForm(request.POST, instance=employee)
            if profile_form.is_valid() and personnel_form.is_valid():
                profile_form.save()
                personnel_form.save()
                messages.success(request, 'Your profile has been updated successfully.')
                return redirect('profile')
    else:
        profile_form = ProfileForm(instance=user)
        if user.role == 'superadmin':
            form = profile_form
        elif user.role == 'admin':
            company_form = CompanyNameForm(instance=company)
            form = (profile_form, company_form)
        elif user.role == 'employee':
            personnel_form = PersonnelNameForm(instance=employee)
            form = (profile_form, personnel_form)

    if user.role == 'superadmin':
        name = "Super Admin"
    elif user.role == 'admin':
        name = company.name if company else "Admin"
    elif user.role == 'employee':
        name = employee.name if employee else "Employee"
    else:
        name = user.username

    context = {
        'user': user,
        'name': name,
        'form': form,
    }
    return render(request, 'profile.html', context)