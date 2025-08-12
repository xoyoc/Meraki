# apps/accounts/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Profile
from .utils import create_user_profile, send_welcome_email
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)
        
        if instance.user_type == 'applicant':
            from applicants.models import ApplicantProfile
            ApplicantProfile.objects.get_or_create(
                user=instance,
                defaults={
                    'first_name': instance.first_name,
                    'last_name': instance.last_name
                }
            )

@receiver(post_save, sender=User)
def create_user_related_profiles(sender, instance, created, **kwargs):
    """Crear perfiles relacionados cuando se crea un usuario"""
    if created:
        try:
            # Crear perfil básico
            Profile.objects.get_or_create(
                user=instance,
                defaults={
                    'phone': '',
                    'location': ''
                }
            )
            
            # Crear perfil específico según tipo de usuario
            create_user_profile(instance)
            
            logger.info(f"Profiles created for user {instance.email}")
            
        except Exception as e:
            logger.error(f"Error creating profiles for user {instance.email}: {e}")

@receiver(post_save, sender=User)
def send_welcome_email_on_activation(sender, instance, **kwargs):
    """Enviar email de bienvenida cuando se activa la cuenta"""
    if instance.is_active and not kwargs.get('created', False):
        # Solo enviar si se acaba de activar (evitar spam en updates)
        if hasattr(instance, '_just_activated'):
            try:
                send_welcome_email(instance)
                logger.info(f"Welcome email sent to {instance.email}")
            except Exception as e:
                logger.error(f"Error sending welcome email to {instance.email}: {e}")

@receiver(post_delete, sender=User)
def cleanup_user_files(sender, instance, **kwargs):
    """Limpiar archivos cuando se elimina un usuario"""
    try:
        if hasattr(instance, 'profile') and instance.profile.avatar:
            # Eliminar archivo de avatar
            instance.profile.avatar.delete(save=False)
            logger.info(f"Avatar file deleted for user {instance.email}")
    except Exception as e:
        logger.error(f"Error deleting avatar for user {instance.email}: {e}")

@receiver(post_save, sender=Profile)
def update_profile_completion(sender, instance, **kwargs):
    """Actualizar score de completitud del perfil"""
    try:
        user = instance.user
        
        # Calcular score de completitud
        completion_score = 0
        if user.first_name:
            completion_score += 20
        if user.last_name:
            completion_score += 20
        if user.email:
            completion_score += 20
        if instance.avatar:
            completion_score += 20
        if instance.phone:
            completion_score += 10
        if instance.location:
            completion_score += 10
        
        # Guardar score si es diferente al actual
        if not hasattr(instance, 'completion_score') or instance.completion_score != completion_score:
            Profile.objects.filter(id=instance.id).update(completion_score=completion_score)
            
    except Exception as e:
        logger.error(f"Error updating profile completion for user {instance.user.email}: {e}")
