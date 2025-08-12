from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('application_received', 'Postulación Recibida'),
        ('application_status_update', 'Actualización de Estado'),
        ('job_approved', 'Vacante Aprobada'),
        ('job_rejected', 'Vacante Rechazada'),
        ('new_job_match', 'Nueva Vacante que Coincide'),
        ('profile_viewed', 'Perfil Visto'),
        ('message_received', 'Mensaje Recibido'),
        ('system_update', 'Actualización del Sistema'),
    ]
    
    NOTIFICATION_METHODS = [
        ('email', 'Email'),
        ('in_app', 'En la Aplicación'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('sent', 'Enviado'),
        ('delivered', 'Entregado'),
        ('failed', 'Fallido'),
        ('read', 'Leído'),
    ]
    
    # Información básica
    recipient = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='notifications'
    )
    sender = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='sent_notifications'
    )
    
    # Contenido
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Método y estado
    method = models.CharField(max_length=20, choices=NOTIFICATION_METHODS, default='in_app')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Datos adicionales (JSON para flexibilidad)
    extra_data = models.JSONField(default=dict, blank=True)
    
    # URL de acción (opcional)
    action_url = models.URLField(blank=True, help_text="URL a la que redirigir al hacer clic")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Control
    is_read = models.BooleanField(default=False)
    is_important = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.recipient.email}"
    
    def mark_as_read(self):
        """Marcar notificación como leída"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.status = 'read'
            self.save(update_fields=['is_read', 'read_at', 'status'])
    
    def mark_as_sent(self):
        """Marcar notificación como enviada"""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save(update_fields=['status', 'sent_at'])
    
    def mark_as_failed(self):
        """Marcar notificación como fallida"""
        self.status = 'failed'
        self.save(update_fields=['status'])
    
    @property
    def is_expired(self):
        """Verificar si la notificación ha expirado"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

class NotificationPreference(models.Model):
    """Preferencias de notificación por usuario"""
    
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='notification_preferences'
    )
    
    # Preferencias por tipo de notificación
    application_received_email = models.BooleanField(default=True)
    application_received_in_app = models.BooleanField(default=True)
    
    application_status_update_email = models.BooleanField(default=True)
    application_status_update_in_app = models.BooleanField(default=True)
    
    job_approved_email = models.BooleanField(default=True)
    job_approved_in_app = models.BooleanField(default=True)
    
    new_job_match_email = models.BooleanField(default=False)
    new_job_match_in_app = models.BooleanField(default=True)
    
    profile_viewed_email = models.BooleanField(default=False)
    profile_viewed_in_app = models.BooleanField(default=True)
    
    # Configuración general
    email_notifications_enabled = models.BooleanField(default=True)
    in_app_notifications_enabled = models.BooleanField(default=True)
    
    # Horarios
    quiet_hours_start = models.TimeField(null=True, blank=True, help_text="Inicio de horas silenciosas (no enviar notificaciones)")
    quiet_hours_end = models.TimeField(null=True, blank=True, help_text="Fin de horas silenciosas")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Preferencias de {self.user.email}"
    
    def should_send_notification(self, notification_type, method):
        """Verificar si se debe enviar una notificación según las preferencias"""
        if not getattr(self, f"{method}_notifications_enabled", True):
            return False
        
        preference_field = f"{notification_type}_{method}"
        return getattr(self, preference_field, True)