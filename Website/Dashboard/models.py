from django.db import models


class Personnels(models.Model):
    genders = {
        "M": "Male",
        "F": "Female",
    }
    roles = {
        "S": "Staff",
        "I": "Intern",
        "U": "Unknown",
    }
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    employment_status = models.CharField(max_length=100, choices=roles)
    gender = models.CharField(max_length=100, choices=genders)
    createdAt = models.DateTimeField(auto_now_add=True, null=True)
    updatedAt = models.DateTimeField(auto_now=True, null=True)


class Camera_Settings(models.Model):
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
    face_detection = models.BooleanField(default=False)
    cam_start = models.CharField(max_length=200)
    cam_stop = models.CharField(max_length=200)
    attendance_time_start = models.CharField(max_length=200)
    attendance_time_end = models.CharField(max_length=200)
    leaving_time_start = models.CharField(max_length=200)
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)


class Counted_Instances(models.Model):
    id = models.AutoField(primary_key=True)
    timestamp = models.CharField(max_length=200)
    camera = models.ForeignKey(Camera_Settings, on_delete=models.CASCADE)
    male_entries = models.IntegerField(default=0)
    female_entries = models.IntegerField(default=0)
    unknown_gender_entries = models.IntegerField(default=0)
    people_exits = models.IntegerField(default=0)
    people_inside = models.IntegerField(default=0)


class Personnel_Entries(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200)
    timestamp = models.CharField(max_length=200)
    time_in = models.CharField(max_length=200)
    time_out = models.CharField(max_length=200)
    camera = models.ForeignKey(Camera_Settings, on_delete=models.CASCADE)
