from datetime import datetime
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from ..decorators import role_required
from .. import models, forms

# View for Admin Dashboard
@login_required(login_url='login')
@role_required('admin')
def tracking_report(request):
    company = models.Company.objects.get(user=request.user)
    return render(request, 'admin/tracking_report.html', {'company': company})
