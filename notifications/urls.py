from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='list'),
    path('<int:pk>/read/', views.MarkNotificationAsReadView.as_view(), name='mark_as_read'),
    path('mark-all-read/', views.MarkAllAsReadView.as_view(), name='mark_all_as_read'),
    path('preferences/', views.NotificationPreferencesView.as_view(), name='preferences'),
    
    # API endpoints
    path('api/unread/', views.UnreadNotificationsAPIView.as_view(), name='unread_api'),
]