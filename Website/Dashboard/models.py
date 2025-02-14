from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser

class CustomUsers(AbstractUser):
    ROLE_CHOICES = [
        ('superadmin', 'Super Admin'),
        ('admin', 'Admin'),
        ('employee', 'Employee'),
    ]
    id = models.AutoField(primary_key=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee')
    email = models.EmailField(unique=True, null=True)
    username = models.CharField(max_length=255, unique=True)
    password = models.CharField(max_length=255)
    is_superadmin = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    is_employee = models.BooleanField(default=False)
    
    
    
    def save(self, *args, **kwargs):
        # Auto-set the role-related boolean flags based on `role`
        self.is_superadmin = self.role == 'superadmin'
        self.is_admin = self.role == 'admin'
        self.is_employee = self.role == 'employee'
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username
    
class Company(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    createdAt = models.DateTimeField(auto_now_add=True, null=True)
    updatedAt = models.DateTimeField(auto_now=True, null=True)
    user = models.OneToOneField(CustomUsers, on_delete=models.CASCADE, null=True)
    
class Divisions(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    createdAt = models.DateTimeField(auto_now_add=True, null=True)
    updatedAt = models.DateTimeField(auto_now=True, null=True) 

class Personnels(models.Model):
    genders = {
        "M": "Male",
        "F": "Female",
    }
    roles = {
        "S": "Staff",
        "I": "Intern",
    }
    id = models.AutoField(primary_key=True)
    # employeeid = models.CharField(max_length=100, unique=True, null=True)
    name = models.CharField(max_length=100)
    # employment_status = models.CharField(max_length=100, choices=roles)
    # gender = models.CharField(max_length=10, choices=genders)
    createdAt = models.DateTimeField(auto_now_add=True, null=True)
    updatedAt = models.DateTimeField(auto_now=True, null=True)
    user = models.OneToOneField(CustomUsers, on_delete=models.CASCADE, null=True)
    division = models.ForeignKey(Divisions, on_delete=models.CASCADE, null=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True)

class Personnel_Images(models.Model):

    id = models.AutoField(primary_key=True)
    personnel = models.ForeignKey(
        Personnels, on_delete=models.CASCADE, related_name='images', default=1)
    image_path = models.CharField(max_length=255, null=True)
    createdAt = models.DateTimeField(auto_now_add=True, null=True)


class Camera_Settings(models.Model):
    ROLE_CAMERA_CHOICES = [
    ("P_IN", "Presence_In"),
    ("P_OUT", "Presence_Out"),
    ("T", "Tracking")
]

    id = models.AutoField(primary_key=True)
    cam_name = models.CharField(max_length=200)
    feed_src = models.CharField(max_length=200)
    x1 = models.IntegerField(default=0)
    y1 = models.IntegerField(default=0)
    x2 = models.IntegerField(default=0)
    y2 = models.IntegerField(default=0)
    x3 = models.IntegerField(default=0)
    y3 = models.IntegerField(default=0)
    x4 = models.IntegerField(default=0)
    y4 = models.IntegerField(default=0)
    x5 = models.IntegerField(default=0)
    y5 = models.IntegerField(default=0)
    x6 = models.IntegerField(default=0)
    y6 = models.IntegerField(default=0)
    x7 = models.IntegerField(default=0)
    y7 = models.IntegerField(default=0)
    x8 = models.IntegerField(default=0)
    y8 = models.IntegerField(default=0)
    cam_is_active = models.BooleanField(default=False)
    gender_detection = models.BooleanField(default=False)
    face_detection = models.BooleanField(default=True)
    face_capture = models.BooleanField(default=True)
    id_card_detection = models.BooleanField(default=False)
    uniform_detection = models.BooleanField(default=False)
    shoes_detection = models.BooleanField(default=False)
    ciggerate_detection = models.BooleanField(default=False)
    sit_detection = models.BooleanField(default=False)
    cam_start = models.CharField(max_length=200, default="00:01:00", null=True, blank=True)
    cam_stop = models.CharField(max_length=200, default="23:59:00", null=True, blank=True)
    attendance_time_start = models.CharField(max_length=200, null=True, blank=True)
    attendance_time_end = models.CharField(max_length=200, null=True, blank=True)
    leaving_time_start = models.CharField(max_length=200, null=True, blank=True)
    leaving_time_end = models.CharField(max_length=200, null=True, blank=True)
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)
    role_camera = models.CharField(max_length=10, choices=ROLE_CAMERA_CHOICES, default="T")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, null=True)


class Counted_Instances(models.Model):
    id = models.AutoField(primary_key=True)
    timestamp = models.CharField(max_length=200)
    camera = models.ForeignKey(Camera_Settings, on_delete=models.CASCADE)
    male_entries = models.IntegerField(default=0)
    female_entries = models.IntegerField(default=0)
    unknown_gender_entries = models.IntegerField(default=0)
    staff_entries = models.IntegerField(default=0)
    intern_entries = models.IntegerField(default=0)
    unknown_role_entries = models.IntegerField(default=0)
    people_exits = models.IntegerField(default=0)
    people_inside = models.IntegerField(default=0)


class Personnel_Entries(models.Model):
    status_choices = [
        ('ONTIME', 'On Time'),
        ('LATE', 'Late'),
        ('LEAVE', 'Already Leave'),
        ('UNKNOWN', 'No Presence'),
    ]
    id = models.AutoField(primary_key=True)
    camera = models.ForeignKey(Camera_Settings, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    presence_status = models.CharField(
        max_length=10, choices=status_choices, default="UNKNOWN")
    personnel = models.ForeignKey(Personnels, on_delete=models.CASCADE)
    image=models.CharField(max_length=255, null=True)
    
class Work_Timer(models.Model):
    type_choices = [
        ('SIT', 'Sit'),
        ('FACE_DETECTED', 'Face Detected'),
    ]
    id = models.AutoField(primary_key=True)
    camera = models.ForeignKey(Camera_Settings, on_delete=models.CASCADE, null=True)
    datetime = models.DateTimeField()
    type = models.CharField(max_length=15, choices=type_choices)
    timer = models.IntegerField(default=0) 
    personnel = models.ForeignKey(Personnels, on_delete=models.CASCADE)