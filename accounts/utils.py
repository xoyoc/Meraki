# apps/accounts/utils.py
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)

def send_verification_email(request, user):
    """Enviar email de verificación de cuenta"""
    try:
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        verification_url = request.build_absolute_uri(
            reverse('accounts:email_verify', kwargs={'uidb64': uid, 'token': token})
        )
        
        context = {
            'user': user,
            'verification_url': verification_url,
            'site_name': 'Meraki - Capital Humano en Acción',
            'site_url': request.build_absolute_uri('/'),
        }
        
        html_message = render_to_string('emails/verification_email.html', context)
        plain_message = render_to_string('emails/verification_email.txt', context)
        
        send_mail(
            subject='🎉 Verifica tu cuenta en Meraki',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False
        )
        return True
    except Exception as e:
        logger.error(f"Error sending verification email to {user.email}: {e}")
        return False

def send_welcome_email(user):
    """Enviar email de bienvenida después de verificar cuenta"""
    try:
        context = {
            'user': user,
            'site_name': 'Meraki',
            'dashboard_url': get_dashboard_url(user),
        }
        
        html_message = render_to_string('emails/welcome_email.html', context)
        plain_message = render_to_string('emails/welcome_email.txt', context)
        
        send_mail(
            subject='¡Bienvenido a Meraki! 🚀',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False
        )
        return True
    except Exception as e:
        logger.error(f"Error sending welcome email to {user.email}: {e}")
        return False

def get_dashboard_url(user):
    """Obtener URL del dashboard según tipo de usuario"""
    if hasattr(user, 'user_type'):
        if user.user_type == 'company':
            return reverse('companies:dashboard')
        elif user.user_type == 'applicant':
            return reverse('applicants:dashboard')
        elif user.user_type == 'admin':
            return reverse('admin:index')
    return reverse('core:home')

def get_user_avatar_url(user):
    """Obtener URL del avatar del usuario"""
    try:
        if hasattr(user, 'profile') and user.profile.avatar:
            return user.profile.avatar.url
        return None
    except:
        return None

def get_user_display_name(user):
    """Obtener nombre completo o email del usuario"""
    if user.first_name and user.last_name:
        return f"{user.first_name} {user.last_name}"
    elif user.first_name:
        return user.first_name
    else:
        return user.email

def create_user_profile(user):
    """Crear perfil específico según tipo de usuario"""
    try:
        from .models import Profile
        
        # Crear perfil básico si no existe
        profile, created = Profile.objects.get_or_create(
            user=user,
            defaults={
                'phone': '',
                'location': ''
            }
        )
        
        # Crear perfil específico según tipo de usuario
        if user.user_type == 'applicant':
            from applicants.models import ApplicantProfile
            applicant_profile, created = ApplicantProfile.objects.get_or_create(
                user=user,
                defaults={
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email
                }
            )
        elif user.user_type == 'company':
            from companies.models import Company
            company, created = Company.objects.get_or_create(
                user=user,
                defaults={
                    'name': f"Empresa de {user.first_name}",
                    'email': user.email
                }
            )
        
        return True
    except Exception as e:
        logger.error(f"Error creating user profile for {user.email}: {e}")
        return False

def get_user_stats(user):
    """Obtener estadísticas del usuario según su tipo"""
    stats = {
        'profile_completion': 0,
        'account_age_days': 0,
        'last_activity': user.last_login,
    }
    
    try:
        # Calcular días desde registro
        if user.date_joined:
            from django.utils import timezone
            stats['account_age_days'] = (timezone.now() - user.date_joined).days
        
        # Calcular completitud del perfil
        completion_score = 0
        if user.first_name:
            completion_score += 20
        if user.last_name:
            completion_score += 20
        if user.email:
            completion_score += 20
        if hasattr(user, 'profile'):
            if user.profile.avatar:
                completion_score += 20
            if user.profile.phone:
                completion_score += 10
            if user.profile.location:
                completion_score += 10
        
        stats['profile_completion'] = completion_score
        
        # Estadísticas específicas por tipo de usuario
        if user.user_type == 'applicant' and hasattr(user, 'applicantprofile'):
            stats.update(get_applicant_stats(user.applicantprofile))
        elif user.user_type == 'company' and hasattr(user, 'company'):
            stats.update(get_company_stats(user.company))
        
    except Exception as e:
        logger.error(f"Error getting user stats for {user.email}: {e}")
    
    return stats

def get_applicant_stats(applicant_profile):
    """Obtener estadísticas específicas del aspirante"""
    return {
        'applications_count': 0,  # Implementar cuando exista el modelo
        'interviews_count': 0,
        'offers_count': 0,
    }

def get_company_stats(company):
    """Obtener estadísticas específicas de la empresa"""
    return {
        'jobs_posted': 0,  # Implementar cuando exista el modelo
        'applications_received': 0,
        'hires_made': 0,
    }

def validate_avatar_file(file):
    """Validar archivo de avatar"""
    # Tamaño máximo 5MB
    max_size = 5 * 1024 * 1024
    if file.size > max_size:
        return False, "El archivo es demasiado grande. Máximo 5MB."
    
    # Tipos permitidos
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if file.content_type not in allowed_types:
        return False, "Tipo de archivo no permitido. Use JPG, PNG, GIF o WebP."
    
    return True, "Archivo válido"