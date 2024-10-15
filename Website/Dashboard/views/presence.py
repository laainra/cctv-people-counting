from django.shortcuts import render
from django.http import HttpResponse

def presence(request):
    return render(request, 'presence.html', {'Page': "Presence"})