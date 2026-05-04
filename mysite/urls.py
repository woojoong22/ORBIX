from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from posts import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('u/<str:username>/', views.profile_feed, name='profile_feed'),
    path('api/users/<str:username>/follow/', views.follow_account, name='follow_account'),
    path('api/users/<str:username>/unfollow/', views.unfollow_account, name='unfollow_account'),
    path('api/users/<str:username>/follow-state/', views.follow_state, name='follow_state'),
    path('posts/<int:post_id>/', views.post_detail, name='post_detail'),
    path('create/', views.create, name='create'),
    path('signup/', views.signup, name='signup'),
    path(
        'login/',
        auth_views.LoginView.as_view(template_name='login.html', redirect_authenticated_user=True),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
