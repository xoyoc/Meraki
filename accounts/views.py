from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.views import (
    LoginView, LogoutView, PasswordChangeView, PasswordChangeDoneView,
    PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, 
    PasswordResetCompleteView
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, CreateView, UpdateView, DeleteView
from django.views import View
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponseRedirect
from django.core.exceptions import ValidationError
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.cache import never_cache
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

from .forms import CustomSignUpForm

class SignUpView(CreateView):
    form_class = CustomSignUpForm
    template_name = 'accounts/signup.html'
    success_url = reverse_lazy('accounts:email_verification_sent')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Crear Cuenta | Meraki'
        return context
    
    def form_valid(self, form):
        try:
            # Guardar el usuario
            response = super().form_valid(form)
            
            # El usuario ya está guardado en self.object
            user = self.object
            
            # Enviar email de verificación
            self.send_verification_email(user)
            
            messages.success(
                self.request, 
                f'¡Bienvenido a Meraki, {user.first_name}! Revisa tu email para verificar tu cuenta.'
            )
            
            return response
            
        except Exception as e:
            # Si hay algún error, agregarlo a los errores del formulario
            form.add_error(None, f'Error al crear la cuenta: {str(e)}')
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        # Si es una petición AJAX, devolver JSON
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = error_list[0]  # Primer error de cada campo
            
            return JsonResponse({
                'success': False,
                'errors': errors
            }, status=400)
        
        return super().form_invalid(form)
    
    def send_verification_email(self, user):
        """Enviar email de verificación"""
        try:
            from django.contrib.auth.tokens import default_token_generator
            from django.utils.http import urlsafe_base64_encode
            from django.utils.encoding import force_bytes
            
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            verification_url = self.request.build_absolute_uri(
                reverse('accounts:email_verify', kwargs={'uidb64': uid, 'token': token})
            )
            
            context = {
                'user': user,
                'verification_url': verification_url,
                'site_name': 'Meraki',
                'user_type_display': user.get_user_type_display()
            }
            
            html_message = render_to_string('emails/email_verification.html', context)
            
            send_mail(
                subject='Verifica tu cuenta en Meraki',
                message=f'Hola {user.first_name}, verifica tu cuenta: {verification_url}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=True  # No fallar si no se puede enviar el email
            )
        except Exception as e:
            logger.error(f"Error sending verification email: {e}")
            # No fallar la creación del usuario por problemas de email

# Autenticación Views
class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True
    
    def get_success_url(self):
        """Redirigir según el tipo de usuario"""
        user = self.request.user
        if hasattr(user, 'user_type'):
            if user.user_type == 'admin':
                return reverse('admin:index')
            elif user.user_type == 'company':
                return reverse('companies:dashboard')
            elif user.user_type == 'applicant':
                return reverse('applicants:dashboard')
        return reverse('core:home')
    
    def form_valid(self, form):
        messages.success(self.request, f'¡Bienvenido de vuelta, {form.get_user().first_name or form.get_user().username}!')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Credenciales incorrectas. Por favor, verifica tu email y contraseña.')
        return super().form_invalid(form)

class CustomLogoutView(LogoutView):
    next_page = 'core:home'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            messages.info(request, '¡Hasta pronto! Has cerrado sesión correctamente.')
        return super().dispatch(request, *args, **kwargs)

# Perfil Views
class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        context['user'] = user
        
        # Agregar perfil específico según tipo de usuario
        if hasattr(user, 'user_type'):
            if user.user_type == 'applicant' and hasattr(user, 'applicantprofile'):
                context['applicant'] = user.applicantprofile
            elif user.user_type == 'company' and hasattr(user, 'company'):
                context['company'] = user.company
        
        return context

class ProfileEditView(LoginRequiredMixin, UpdateView):
    model = User
    template_name = 'accounts/profile_edit.html'
    fields = ['first_name', 'last_name', 'email']
    success_url = reverse_lazy('accounts:profile')
    
    def get_object(self):
        return self.request.user
    
    def form_valid(self, form):
        messages.success(self.request, 'Perfil actualizado correctamente.')
        return super().form_valid(form)

class AvatarUpdateView(LoginRequiredMixin, View):
    def post(self, request):
        if 'avatar' in request.FILES:
            try:
                profile, created = request.user.profile.get_or_create(user=request.user)
                profile.avatar = request.FILES['avatar']
                profile.save()
                
                return JsonResponse({
                    'success': True,
                    'avatar_url': profile.avatar.url,
                    'message': 'Avatar actualizado correctamente'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Error al actualizar avatar: {str(e)}'
                })
        
        return JsonResponse({
            'success': False,
            'message': 'No se proporcionó ningún archivo'
        })

# Cambio de contraseña Views
class CustomPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('accounts:password_change_done')
    
    def form_valid(self, form):
        messages.success(self.request, 'Contraseña cambiada exitosamente.')
        return super().form_valid(form)

class CustomPasswordChangeDoneView(LoginRequiredMixin, PasswordChangeDoneView):
    template_name = 'accounts/password_change_done.html'

# Recuperación de contraseña Views
class CustomPasswordResetView(PasswordResetView):
    template_name = 'accounts/password_reset.html'
    email_template_name = 'emails/password_reset_email.html'
    subject_template_name = 'emails/password_reset_subject.txt'
    success_url = reverse_lazy('accounts:password_reset_done')
    
    def form_valid(self, form):
        messages.success(self.request, 'Te hemos enviado instrucciones para restablecer tu contraseña.')
        return super().form_valid(form)

class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'

class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('accounts:password_reset_complete')
    
    def form_valid(self, form):
        messages.success(self.request, 'Contraseña restablecida exitosamente. Ya puedes iniciar sesión.')
        return super().form_valid(form)

class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'

# Verificación de email Views
class EmailVerificationSentView(TemplateView):
    template_name = 'accounts/email_verification_sent.html'

class EmailVerifyView(View):
    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
        
        if user and default_token_generator.check_token(user, token):
            user.is_active = True
            user.is_verified = True
            user.save()
            
            # Auto-login después de verificación
            login(request, user)
            
            messages.success(request, f'¡Bienvenido a Meraki, {user.first_name}! Tu cuenta ha sido verificada exitosamente.')
            
            # Redirigir según tipo de usuario
            if user.user_type == 'applicant':
                return redirect('applicants:dashboard')
            elif user.user_type == 'company':
                return redirect('companies:dashboard')
            else:
                return redirect('accounts:profile')
        else:
            messages.error(request, 'El enlace de verificación es inválido o ha expirado.')
            return redirect('accounts:signup')

# Configuraciones Views
class AccountSettingsView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/settings.html'

class PrivacySettingsView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/privacy_settings.html'

class NotificationSettingsView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/notification_settings.html'

# Eliminación de cuenta Views
class AccountDeleteView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/account_delete.html'

class AccountDeleteConfirmView(LoginRequiredMixin, DeleteView):
    model = User
    template_name = 'accounts/account_delete_confirm.html'
    success_url = reverse_lazy('core:home')
    
    def get_object(self):
        return self.request.user
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Tu cuenta ha sido eliminada correctamente.')
        return super().delete(request, *args, **kwargs)
    
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def validate_email_ajax(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email', '').strip().lower()
            
            exists = User.objects.filter(email=email).exists()
            
            return JsonResponse({
                'available': not exists,
                'message': 'Email disponible' if not exists else 'Este email ya está registrado'
            })
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido'}, status=400)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)

@csrf_exempt
def check_password_strength(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            password = data.get('password', '')
            
            strength = 0
            feedback = []
            
            if len(password) >= 8:
                strength += 1
            else:
                feedback.append('Debe tener al menos 8 caracteres')
            
            if any(c.islower() for c in password):
                strength += 1
            
            if any(c.isupper() for c in password):
                strength += 1
            
            if any(c.isdigit() for c in password):
                strength += 1
            
            if any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password):
                strength += 1
            
            strength_levels = ['Muy débil', 'Débil', 'Regular', 'Fuerte', 'Muy fuerte']
            
            return JsonResponse({
                'strength': strength,
                'level': strength_levels[min(strength, 4)],
                'feedback': feedback,
                'valid': strength >= 3
            })
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON inválido'}, status=400)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)