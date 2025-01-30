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
    }
    return render(request, 'profile.html', context)

@login_required(login_url='login')
def edit_profile(request):
    user = request.user
    company = Company.objects.filter(user=user).first()
    employee = Personnels.objects.filter(user=user).first()

    if request.method == 'POST':
        if user.role == 'superadmin':
            form = ProfileForm(request.POST, instance=user)
        elif user.role == 'admin':
            form = CompanyNameForm(request.POST, instance=company)
        elif user.role == 'employee':
            form = PersonnelNameForm(request.POST, instance=employee)

        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('profile')
    else:
        if user.role == 'superadmin':
            form = ProfileForm(instance=user)
        elif user.role == 'admin':
            form = CompanyNameForm(instance=company)
        elif user.role == 'employee':
            form = PersonnelNameForm(instance=employee)

    context = {
        'form': form,
        'user': user,
    }
    return render(request, 'edit_profile.html', context)