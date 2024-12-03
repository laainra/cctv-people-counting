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
    name = forms.CharField(widget=forms.widgets.TextInput())
    gender = forms.ChoiceField(
        choices=models.Personnels.genders, widget=forms.Select())
    employment_status = forms.ChoiceField(
        choices=models.Personnels.roles, widget=forms.Select())

    class Meta:
        model = models.Personnels
        fields = [
            'name', 'gender', 'employment_status'
        ]


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
