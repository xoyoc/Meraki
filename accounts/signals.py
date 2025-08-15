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

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Crear perfil automáticamente cuando se crea un usuario"""
    if created:
        try:
            # Crear perfil base
            Profile.objects.get_or_create(
                user=instance,
                defaults={
                    'phone': '',
                    'location': ''
                }
            )
            
            # Crear perfiles específicos según tipo de usuario
            create_specific_profile(instance)
            
        except Exception as e:
            print(f"Error creando perfil para {instance.email}: {e}")

def create_specific_profile(user):
    """Crear perfil específico según tipo de usuario"""
    if user.user_type == 'applicant':
        try:
            from applicants.models import ApplicantProfile
            ApplicantProfile.objects.get_or_create(
                user=user,
                defaults={
                    'first_name': user.first_name,
                    'last_name': user.last_name
                }
            )
        except ImportError:
            # El modelo no existe aún
            pass
        except Exception as e:
            print(f"Error creando perfil de aplicante: {e}")
            
    elif user.user_type == 'company':
        try:
            from companies.models import Company
            Company.objects.get_or_create(
                user=user,
                defaults={
                    'name': f"{user.first_name} {user.last_name}"
                }
            )
        except ImportError:
            # El modelo no existe aún
            pass
        except Exception as e:
            print(f"Error creando perfil de empresa: {e}")

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Guardar perfil cuando se actualiza el usuario"""
    try:
        if hasattr(instance, 'profile'):
            instance.profile.save()
    except:
        # Si no existe el perfil, no hacer nada
        pass