from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from posts import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('service-worker.js', views.service_worker, name='service_worker'),
    path('manifest.webmanifest', views.webmanifest, name='webmanifest'),
    path('', views.landing, name='landing'),
    path('home/', views.home, name='home'),
    path('feed/', views.feed, name='feed'),
    path('u/<str:username>/', views.profile_feed, name='profile_feed'),
    path('profile/<str:username>/', views.profile, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('orbit/<str:username>/', views.orbit_toggle, name='orbit_toggle'),
    path('notifications/', views.notifications, name='notifications'),
    path('explore/', views.explore, name='explore'),
    path('api/users/<str:username>/follow/', views.follow_account, name='follow_account'),
    path('api/users/<str:username>/unfollow/', views.unfollow_account, name='unfollow_account'),
    path('api/users/<str:username>/follow-state/', views.follow_state, name='follow_state'),
    path('post/<int:post_id>/', views.post_detail, name='post_detail_singular'),
    path('post/<int:post_id>/like/', views.post_like, name='post_like'),
    path('post/<int:post_id>/comment/', views.post_comment, name='post_comment'),
    path('posts/<int:post_id>/', views.post_detail, name='post_detail'),
    path('create/', views.create, name='create'),
    path('signup/', views.signup, name='signup'),
    path(
        'login/',
        auth_views.LoginView.as_view(template_name='login.html', redirect_authenticated_user=True),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('accounts/profile/', RedirectView.as_view(pattern_name='home', permanent=False)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
