from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name="home"),
    path('login', views.login_user, name="login"),
    path('logout', views.logout_user, name="logout"),

    path('personnels', views.personnels, name="personnels"),
    path('add_personnel', views.add_personnel, name="add_personnel"),
    path('add_pic', views.add_pic, name="add_pic"),
    path('delete_personnel/<str:id>', views.delete_personnel, name="delete_personnel"),
    
    path('camera', views.camera, name="camera"),
    path('video_feed', views.video_feed, name='video_feed'),
    path('start_stream', views.start_stream, name='start_stream'),
    path('add_camera', views.add_camera, name="add_camera"),
    path('delete_camera/<str:id>', views.delete_camera, name="delete_camera"),
    path('save_coordinates', views.save_coordinates, name="save_coordinates"),
    path('stop_stream', views.stop_stream, name="stop_stream"),
    path('change_camera', views.change_camera, name="change_camera"),
    path('edit_camera/<str:id>', views.edit_camera, name="edit_camera"),
    path('edit_personnel', views.edit_personnel, name="edit_personnel"),
    path('settings', views.settings, name="settings"),
    

    path('download', views.download, name="download"),
]
