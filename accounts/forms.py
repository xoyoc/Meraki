from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
import re

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
      
    def create_user_profile(self, user):
        """Crear perfil según tipo de usuario"""
        from .models import Profile
        
        # Crear perfil base
        Profile.objects.create(user=user)
        
        # Crear perfil específico según tipo
        if user.user_type == 'applicant':
            from applicants.models import ApplicantProfile
            ApplicantProfile.objects.create(
                user=user,
                first_name=user.first_name,
                last_name=user.last_name
            )
        elif user.user_type == 'company':
            from companies.models import Company  # Ajusta según tu modelo
            Company.objects.create(
                user=user,
                name=f"{user.first_name} {user.last_name}"
            )