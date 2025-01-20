from django import forms
from . import models
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User


class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.widgets.TextInput(
        attrs={'placeholder': 'Username'}))
    password = forms.CharField(widget=forms.widgets.PasswordInput(
        attrs={'placeholder': 'Password'}))


class RegisterForm(UserCreationForm):
    username = forms.CharField(widget=forms.widgets.TextInput())
    password1 = forms.CharField(widget=forms.widgets.PasswordInput())
    password2 = forms.CharField(widget=forms.widgets.PasswordInput())

    class Meta:
        model = User
        fields = [
            'username', 'password1', 'password2'
        ]

class PersonnelForm(forms.ModelForm):
    name = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter name'}))
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter username'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter password'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter email'}))

    division = forms.ModelChoiceField(
        queryset=models.Divisions.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True,
    )

    class Meta:
        model = models.Personnels
        fields = ['name', 'division']

    def save(self, commit=True):
        personnel = super().save(commit=False)

        # Update or create a related user
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        email = self.cleaned_data.get('email')

        if personnel.user:
            user = personnel.user
            user.username = username
            user.email = email
            if password:
                user.set_password(password)
            user.save()
        else:
            user = models.CustomUsers.objects.create_user(
                username=username,
                password=password,
                email=email,
            )
            personnel.user = user

        if commit:
            personnel.save()
        return personnel

class AddCameraForm(forms.ModelForm):
    cam_name = forms.CharField(widget=forms.widgets.TextInput())
    feed_src = forms.CharField(widget=forms.widgets.TextInput(), )
    gender_detection = forms.BooleanField(
        widget=forms.widgets.CheckboxInput(), required=False)
    face_detection = forms.BooleanField(
        widget=forms.widgets.CheckboxInput(), required=False)
    face_capture = forms.BooleanField(
        widget=forms.widgets.CheckboxInput(), required=False)
    cam_start = forms.TimeField(
        widget=forms.widgets.TimeInput(), required=True)
    cam_stop = forms.TimeField(widget=forms.widgets.TimeInput(), required=True)
    attendance_time_start = forms.TimeField(
        widget=forms.widgets.TimeInput(), required=True)
    attendance_time_end = forms.TimeField(
        widget=forms.widgets.TimeInput(), required=True)
    leaving_time_start = forms.TimeField(
        widget=forms.widgets.TimeInput(), required=True)
    leaving_time_end = forms.TimeField(
        widget=forms.widgets.TimeInput(), required=True)

    class Meta:
        model = models.Camera_Settings
        fields = [
            'cam_name',
            'feed_src',
            'gender_detection',
            'face_detection',
            'face_capture',
            'cam_start',
            'cam_stop',
            'attendance_time_start',
            'attendance_time_end',
            'leaving_time_start',
            'leaving_time_end'
        ]

    def __init__(self, *args, **kwargs):
        super(forms.ModelForm, self).__init__(*args, **kwargs)
        self.fields['cam_name'].widget = forms.TextInput(attrs={
            'class': 'effected'})
        self.fields['feed_src'].widget = forms.TextInput(attrs={
            'class': 'effected'})


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        return result


class UploadFileForm(forms.Form):
    image_file = MultipleFileField()

    class Meta:
        model = models.Personnels
        fields = [
            'image_file'
        ]

# class PersonnelImageForm(forms.ModelForm):
#     image = forms.ImageField(
#         required=True,
#         widget=forms.FileInput(attrs={'multiple': True})  # Use FileInput for multiple files
#     )

#     class Meta:
#         model = models.PersonnelImage
#         fields = ['image']


class CompanyAdminForm(forms.ModelForm):
    username = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    company_name = forms.CharField(max_length=255, required=True, label="Company Name")

    class Meta:
        model = models.CustomUsers 
        fields = ['username', 'email', 'password']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])  
        if commit:
            user.save()
            # Create a related Company instance
            company_name = self.cleaned_data['company_name']
            models.Company.objects.create(user=user, name=company_name)
        return user
    
class AddDivisionForm(forms.ModelForm):
    name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter division name'}),
        label="Division Name"
    )

    class Meta:
        model = models.Divisions
        fields = ['name']
class AddPresenceCameraForm(forms.ModelForm):
    class Meta:
        model = models.Camera_Settings
        fields = [
            'cam_name', 
            'role_camera', 
            'feed_src', 
            'attendance_time_start', 
            'attendance_time_end', 
            'leaving_time_start', 
            'leaving_time_end'
        ]
        widgets = {
            'role_camera': forms.RadioSelect(),
            'cam_name': forms.TextInput(attrs={'class': 'form-control'}),
            'feed_src': forms.TextInput(attrs={'class': 'form-control'}),
            'attendance_time_start': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'attendance_time_end': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'leaving_time_start': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'leaving_time_end': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        }
class AddTrackingCameraForm(forms.ModelForm):
    cam_name = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'form-control'}))
    feed_src = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'form-control'}))
    uniform_detection = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    id_card_detection = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    shoes_detection = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    ciggerate_detection = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    sit_detection = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    class Meta:
        model = models.Camera_Settings
        fields = [
            'cam_name', 
            'feed_src', 
            'uniform_detection', 
            'id_card_detection', 
            'shoes_detection', 
            'ciggerate_detection',
            'sit_detection'
        ]
