from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
import re
import uuid

User = get_user_model()

class CustomSignUpForm(UserCreationForm):
    USER_TYPE_CHOICES = [
        ('applicant', 'Busco empleo'),
        ('company', 'Busco talento'),
    ]
    
    # Campos adicionales
    user_type = forms.ChoiceField(
        choices=USER_TYPE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'hidden',
            'id': 'id_user_type'
        }),
        error_messages={
            'required': 'Por favor, selecciona cómo quieres usar Meraki'
        }
    )
    
    first_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Tu nombre',
            'id': 'id_first_name'
        }),
        error_messages={
            'required': 'El nombre es requerido'
        }
    )
    
    last_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Tu apellido',
            'id': 'id_last_name'
        }),
        error_messages={
            'required': 'El apellido es requerido'
        }
    )
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'tu@email.com',
            'id': 'id_email'
        }),
        error_messages={
            'required': 'El email es requerido',
            'invalid': 'Ingresa un email válido'
        }
    )
    
    password1 = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input pr-10',
            'placeholder': 'Mínimo 8 caracteres',
            'id': 'id_password1'
        }),
        error_messages={
            'required': 'La contraseña es requerida'
        }
    )
    
    password2 = forms.CharField(
        label='Confirmar Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input pr-10',
            'placeholder': 'Repite tu contraseña',
            'id': 'id_password2'
        }),
        error_messages={
            'required': 'Debes confirmar tu contraseña'
        }
    )
    
    terms_accepted = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'mt-1 h-4 w-4 text-meraki-600 focus:ring-meraki-500 border-gray-300 rounded',
            'id': 'id_terms_accepted'
        }),
        error_messages={
            'required': 'Debes aceptar los términos y condiciones'
        }
    )
    
    class Meta:
        model = User
        fields = ('user_type', 'first_name', 'last_name', 'email', 'password1', 'password2', 'terms_accepted')
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('Ya existe una cuenta con este email.')
        return email
    
    def clean_password1(self):
        password1 = self.cleaned_data.get('password1')
        
        if len(password1) < 8:
            raise ValidationError('La contraseña debe tener al menos 8 caracteres.')
        
        # Validaciones adicionales de fortaleza
        if not re.search(r'[A-Za-z]', password1):
            raise ValidationError('La contraseña debe contener al menos una letra.')
        
        if not re.search(r'\d', password1):
            raise ValidationError('La contraseña debe contener al menos un número.')
        
        return password1
    
    def save(self, commit=True):
        user = super().save(commit=False)
        
        # Asignar campos adicionales
        user.user_type = self.cleaned_data['user_type']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        
        # Generar username único basado en email
        base_username = self.cleaned_data['email'].split('@')[0]
        username = base_username
        counter = 1
        
        # Asegurar que el username sea único
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1
        
        user.username = username
        
        if commit:
            user.save()
            # Solo crear perfiles si el usuario se guardó exitosamente
            self.create_user_profile(user)
        
        return user
      
    def create_user_profile(self, user):
        """Crear perfil según tipo de usuario"""
        from .models import Profile
        
        try:
            # Crear perfil base solo si no existe
            profile, created = Profile.objects.get_or_create(
                user=user,
                defaults={
                    'phone': '',
                    'location': ''
                }
            )
            
            # Solo crear perfiles específicos si se creó el perfil base
            if created:
                self._create_specific_profile(user)
                
        except Exception as e:
            # Log del error pero no fallar la creación del usuario
            print(f"Error creando perfil para {user.email}: {e}")
    
    def _create_specific_profile(self, user):
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