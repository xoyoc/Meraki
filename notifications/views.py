from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, UpdateView
from django.views import View
from django.http import JsonResponse
from django.contrib import messages
from django.core.paginator import Paginator

from .models import Notification, NotificationPreference
from .services import NotificationService

class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'notifications/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20
    
    def get_queryset(self):
        return Notification.objects.filter(
            recipient=self.request.user,
            method='in_app'
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        notifications = self.get_queryset()
        context.update({
            'unread_count': notifications.filter(is_read=False).count(),
            'total_count': notifications.count(),
        })
        
        return context

class MarkNotificationAsReadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        notification = get_object_or_404(
            Notification, 
            pk=pk, 
            recipient=request.user
        )
        
        notification.mark_as_read()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        
        return redirect('notifications:list')

class MarkAllAsReadView(LoginRequiredMixin, View):
    def post(self, request):
        NotificationService.mark_all_as_read(request.user)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        
        messages.success(request, 'Todas las notificaciones marcadas como leídas.')
        return redirect('notifications:list')

class NotificationPreferencesView(LoginRequiredMixin, UpdateView):
    model = NotificationPreference
    template_name = 'notifications/preferences.html'
    fields = [
        'application_received_email', 'application_received_in_app',
        'application_status_update_email', 'application_status_update_in_app',
        'job_approved_email', 'job_approved_in_app',
        'new_job_match_email', 'new_job_match_in_app',
        'email_notifications_enabled', 'in_app_notifications_enabled'
    ]
    
    def get_object(self):
        obj, created = NotificationPreference.objects.get_or_create(
            user=self.request.user
        )
        return obj
    
    def form_valid(self, form):
        messages.success(self.request, 'Preferencias actualizadas correctamente.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return self.request.path

class UnreadNotificationsAPIView(LoginRequiredMixin, View):
    def get(self, request):
        notifications = Notification.objects.filter(
            recipient=request.user,
            is_read=False,
            method='in_app'
        ).order_by('-created_at')[:10]
        
        notifications_data = []
        for notification in notifications:
            notifications_data.append({
                'id': notification.id,
                'title': notification.title,
                'message': notification.message,
                'type': notification.notification_type,
                'created_at': notification.created_at.isoformat(),
                'action_url': notification.action_url,
                'is_important': notification.is_important
            })
        
        return JsonResponse({
            'notifications': notifications_data,
            'unread_count': NotificationService.get_unread_count(request.user)
        })