from django.contrib import admin
from django.urls import path
from posts import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home),
    path('create/', views.create),

    path('login/', auth_views.LoginView.as_view(template_name='login.html')),
    path('logout/', auth_views.LogoutView.as_view()),
]