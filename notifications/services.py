from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
import logging

from .models import Notification, NotificationPreference

logger = logging.getLogger(__name__)
User = get_user_model()

class NotificationService:
    """Servicio para gestionar todas las notificaciones del sistema"""
    
    @staticmethod
    def create_notification(
        recipient, 
        notification_type, 
        title, 
        message, 
        method='in_app',
        sender=None,
        action_url=None,
        extra_data=None,
        is_important=False
    ):
        """Crear una nueva notificación"""
        try:
            notification = Notification.objects.create(
                recipient=recipient,
                sender=sender,
                notification_type=notification_type,
                title=title,
                message=message,
                method=method,
                action_url=action_url,
                extra_data=extra_data or {},
                is_important=is_important
            )
            
            logger.info(f"Notification created: {notification.id} for {recipient.email}")
            return notification
            
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            return None
    
    @staticmethod
    def send_application_notification(application):
        """Enviar notificación cuando se recibe una postulación"""
        try:
            company_user = application.job_post.company.user
            applicant = application.applicant
            
            # Verificar preferencias
            preferences, created = NotificationPreference.objects.get_or_create(
                user=company_user
            )
            
            # Notificación en la app
            if preferences.should_send_notification('application_received', 'in_app'):
                NotificationService.create_notification(
                    recipient=company_user,
                    notification_type='application_received',
                    title=f'Nueva postulación para {application.job_post.title}',
                    message=f'{applicant.get_full_name()} se ha postulado a tu vacante.',
                    method='in_app',
                    action_url=reverse('jobs:job_applicants', kwargs={'pk': application.job_post.pk}),
                    extra_data={
                        'application_id': application.id,
                        'job_id': application.job_post.id,
                        'applicant_id': applicant.id
                    }
                )
            
            # Email
            if preferences.should_send_notification('application_received', 'email'):
                NotificationService._send_application_email(application)
                
        except Exception as e:
            logger.error(f"Error sending application notification: {e}")
    
    @staticmethod
    def send_application_status_update(application):
        """Enviar notificación cuando se actualiza el estado de una postulación"""
        try:
            applicant_user = application.applicant.user
            
            # Verificar preferencias
            preferences, created = NotificationPreference.objects.get_or_create(
                user=applicant_user
            )
            
            # Determinar mensaje según el estado
            status_messages = {
                'reviewing': 'Tu postulación está siendo revisada',
                'shortlisted': '¡Felicidades! Has sido preseleccionado',
                'interviewed': 'Has sido convocado a entrevista',
                'accepted': '¡Excelente! Tu postulación ha sido aceptada',
                'rejected': 'Tu postulación no fue seleccionada en esta ocasión'
            }
            
            message = status_messages.get(
                application.status, 
                f'El estado de tu postulación ha cambiado a {application.get_status_display()}'
            )
            
            # Notificación en la app
            if preferences.should_send_notification('application_status_update', 'in_app'):
                NotificationService.create_notification(
                    recipient=applicant_user,
                    notification_type='application_status_update',
                    title=f'Actualización: {application.job_post.title}',
                    message=message,
                    method='in_app',
                    action_url=reverse('jobs:application_detail', kwargs={'pk': application.pk}),
                    extra_data={
                        'application_id': application.id,
                        'job_id': application.job_post.id,
                        'old_status': getattr(application, '_old_status', None),
                        'new_status': application.status
                    },
                    is_important=application.status in ['accepted', 'rejected']
                )
            
            # Email
            if preferences.should_send_notification('application_status_update', 'email'):
                NotificationService._send_status_update_email(application)
                
        except Exception as e:
            logger.error(f"Error sending status update notification: {e}")
    
    @staticmethod
    def send_job_approval_notification(job_post, approved=True):
        """Enviar notificación cuando se aprueba o rechaza una vacante"""
        try:
            company_user = job_post.company.user
            
            # Verificar preferencias
            preferences, created = NotificationPreference.objects.get_or_create(
                user=company_user
            )
            
            if approved:
                notification_type = 'job_approved'
                title = f'Vacante aprobada: {job_post.title}'
                message = 'Tu vacante ha sido aprobada y ya está visible para los postulantes.'
            else:
                notification_type = 'job_rejected'
                title = f'Vacante rechazada: {job_post.title}'
                message = 'Tu vacante no fue aprobada. Revisa los comentarios y vuelve a enviarla.'
            
            # Notificación en la app
            if preferences.should_send_notification(notification_type, 'in_app'):
                NotificationService.create_notification(
                    recipient=company_user,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    method='in_app',
                    action_url=reverse('jobs:job_detail', kwargs={'pk': job_post.pk}),
                    extra_data={
                        'job_id': job_post.id,
                        'approved': approved
                    },
                    is_important=True
                )
            
            # Email
            if preferences.should_send_notification(notification_type, 'email'):
                NotificationService._send_job_approval_email(job_post, approved)
                
        except Exception as e:
            logger.error(f"Error sending job approval notification: {e}")
    
    @staticmethod
    def send_new_job_match_notification(applicant, job_post, match_score):
        """Enviar notificación de nueva vacante que coincide con el perfil"""
        try:
            applicant_user = applicant.user
            
            # Verificar preferencias
            preferences, created = NotificationPreference.objects.get_or_create(
                user=applicant_user
            )
            
            # Solo enviar si el match score es alto
            if match_score < 70:
                return
            
            # Notificación en la app
            if preferences.should_send_notification('new_job_match', 'in_app'):
                NotificationService.create_notification(
                    recipient=applicant_user,
                    notification_type='new_job_match',
                    title=f'Nueva oportunidad: {job_post.title}',
                    message=f'Hemos encontrado una vacante que coincide {match_score}% con tu perfil.',
                    method='in_app',
                    action_url=reverse('jobs:job_detail', kwargs={'pk': job_post.pk}),
                    extra_data={
                        'job_id': job_post.id,
                        'match_score': match_score
                    }
                )
                
        except Exception as e:
            logger.error(f"Error sending job match notification: {e}")
    
    @staticmethod
    def _send_application_email(application):
        """Enviar email de nueva postulación"""
        try:
            context = {
                'application': application,
                'job': application.job_post,
                'applicant': application.applicant,
                'company': application.job_post.company
            }
            
            html_message = render_to_string(
                'notifications/emails/application_received.html', 
                context
            )
            
            send_mail(
                subject=f'Nueva postulación para {application.job_post.title}',
                message=f'{application.applicant.get_full_name()} se ha postulado a tu vacante.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[application.job_post.company.user.email],
                html_message=html_message,
                fail_silently=True
            )
            
        except Exception as e:
            logger.error(f"Error sending application email: {e}")
    
    @staticmethod
    def _send_status_update_email(application):
        """Enviar email de actualización de estado"""
        try:
            context = {
                'application': application,
                'job': application.job_post,
                'applicant': application.applicant
            }
            
            html_message = render_to_string(
                'notifications/emails/status_update.html', 
                context
            )
            
            send_mail(
                subject=f'Actualización de tu postulación: {application.job_post.title}',
                message=f'El estado de tu postulación ha sido actualizado.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[application.applicant.user.email],
                html_message=html_message,
                fail_silently=True
            )
            
        except Exception as e:
            logger.error(f"Error sending status update email: {e}")
    
    @staticmethod
    def _send_job_approval_email(job_post, approved):
        """Enviar email de aprobación/rechazo de vacante"""
        try:
            context = {
                'job': job_post,
                'company': job_post.company,
                'approved': approved
            }
            
            html_message = render_to_string(
                'notifications/emails/job_approved.html', 
                context
            )
            
            subject = f'Tu vacante "{job_post.title}" ha sido {"aprobada" if approved else "rechazada"}'
            
            send_mail(
                subject=subject,
                message=f'Tu vacante ha sido {"aprobada" if approved else "rechazada"}.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[job_post.company.user.email],
                html_message=html_message,
                fail_silently=True
            )
            
        except Exception as e:
            logger.error(f"Error sending job approval email: {e}")
    
    @staticmethod
    def mark_all_as_read(user):
        """Marcar todas las notificaciones de un usuario como leídas"""
        Notification.objects.filter(
            recipient=user, 
            is_read=False
        ).update(
            is_read=True, 
            read_at=timezone.now(),
            status='read'
        )
    
    @staticmethod
    def get_unread_count(user):
        """Obtener el número de notificaciones no leídas"""
        return Notification.objects.filter(
            recipient=user, 
            is_read=False
        ).count()
    
    @staticmethod
    def cleanup_old_notifications(days=30):
        """Limpiar notificaciones antiguas"""
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        deleted_count = Notification.objects.filter(
            created_at__lt=cutoff_date,
            is_read=True
        ).delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} old notifications")
        return deleted_count