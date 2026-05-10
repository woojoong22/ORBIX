from django.contrib import admin
from django.urls import path
from posts import views
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('feed/', views.feed, name='feed'),
    path('create/', views.create, name='create'),
    path('explore/', views.explore, name='explore'),
    path('notifications/', views.notifications, name='notifications'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('profile/<str:username>/', views.profile, name='profile'),
    path('orbit/<str:username>/', views.orbit_toggle, name='orbit_toggle'),
    path('post/<int:post_id>/', views.post_detail, name='post_detail'),
    path('post/<int:post_id>/like/', views.post_like, name='post_like'),
    path('post/<int:post_id>/comment/', views.post_comment, name='post_comment'),
    path('signup/', views.signup, name='signup'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
