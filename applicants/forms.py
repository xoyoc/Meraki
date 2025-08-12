# apps/applicants/forms.py
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from .models import ApplicantProfile, ApplicantSkill
from jobs.models import Skill, JobAlert
import os

class ApplicantProfileForm(forms.ModelForm):
    """Formulario para editar el perfil del postulante"""
    
    class Meta:
        model = ApplicantProfile
        fields = [
            'first_name', 'last_name', 'birth_date', 'current_position',
            'years_experience', 'education_level'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500',
                'placeholder': 'Tu nombre'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500',
                'placeholder': 'Tu apellido'
            }),
            'birth_date': forms.DateInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500',
                'type': 'date'
            }),
            'current_position': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500',
                'placeholder': 'Ej: Desarrollador Frontend, Gerente de Marketing'
            }),
            'years_experience': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500',
                'min': '0',
                'max': '50'
            }),
            'education_level': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500'
            })
        }
        labels = {
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'birth_date': 'Fecha de Nacimiento',
            'current_position': 'Posición Actual',
            'years_experience': 'Años de Experiencia',
            'education_level': 'Nivel Educativo'
        }
    
    def clean_years_experience(self):
        years = self.cleaned_data.get('years_experience')
        if years and years < 0:
            raise ValidationError('Los años de experiencia no pueden ser negativos.')
        if years and years > 50:
            raise ValidationError('Los años de experiencia no pueden ser más de 50.')
        return years

class AddSkillForm(forms.Form):
    """Formulario simple para agregar habilidades rápidamente"""
    
    skill = forms.ModelChoiceField(
        queryset=Skill.objects.all(),
        label='Habilidad',
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500'
        })
    )
    
    proficiency_level = forms.ChoiceField(
        choices=ApplicantSkill._meta.get_field('proficiency_level').choices,
        label='Nivel de Competencia',
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500'
        })
    )
    
    years_experience = forms.IntegerField(
        label='Años de Experiencia',
        min_value=0,
        max_value=50,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500',
            'min': '0',
            'max': '50'
        })
    )
    
    def __init__(self, *args, **kwargs):
        applicant = kwargs.pop('applicant', None)
        super().__init__(*args, **kwargs)
        
        if applicant:
            # Excluir habilidades que ya tiene el postulante
            existing_skills = applicant.skills.values_list('id', flat=True)
            self.fields['skill'].queryset = Skill.objects.exclude(id__in=existing_skills).order_by('category', 'name')

class JobAlertForm(forms.ModelForm):
    """Formulario para crear/editar alertas de empleo"""
    
    class Meta:
        model = JobAlert
        fields = [
            'name', 'keywords', 'location', 'min_salary', 'max_salary',
            'employment_type', 'experience_level', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500',
                'placeholder': 'Ej: Trabajos de Desarrollo Frontend'
            }),
            'keywords': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500',
                'placeholder': 'Ej: javascript, react, frontend (separados por comas)'
            }),
            'location': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500',
                'placeholder': 'Ciudad, Estado o País'
            }),
            'min_salary': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500',
                'placeholder': '0'
            }),
            'max_salary': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500',
                'placeholder': '999999'
            }),
            'employment_type': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500'
            }),
            'experience_level': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-meraki-600 focus:ring-meraki-500 border-gray-300 rounded'
            })
        }
        labels = {
            'name': 'Nombre de la Alerta',
            'keywords': 'Palabras Clave',
            'location': 'Ubicación',
            'min_salary': 'Salario Mínimo',
            'max_salary': 'Salario Máximo',
            'employment_type': 'Tipo de Empleo',
            'experience_level': 'Nivel de Experiencia',
            'is_active': 'Alerta Activa'
        }
        help_texts = {
            'keywords': 'Separa las palabras clave con comas',
            'min_salary': 'Deja en blanco si no tienes preferencia',
            'max_salary': 'Deja en blanco si no tienes preferencia',
        }
    
    def clean(self):
        cleaned_data = super().clean()
        min_salary = cleaned_data.get('min_salary')
        max_salary = cleaned_data.get('max_salary')
        
        if min_salary and max_salary and min_salary > max_salary:
            raise ValidationError('El salario mínimo no puede ser mayor al salario máximo.')
        
        return cleaned_data
    
    def clean_keywords(self):
        keywords = self.cleaned_data.get('keywords')
        if keywords:
            # Limpiar y validar keywords
            keywords_list = [kw.strip() for kw in keywords.split(',')]
            keywords_list = [kw for kw in keywords_list if kw]  # Remover vacíos
            
            if len(keywords_list) == 0:
                raise ValidationError('Debes especificar al menos una palabra clave.')
            
            if len(keywords_list) > 10:
                raise ValidationError('No puedes especificar más de 10 palabras clave.')
            
            return ', '.join(keywords_list)
        
        return keywords

class SkillSearchForm(forms.Form):
    """Formulario para buscar habilidades"""
    
    query = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500',
            'placeholder': 'Buscar habilidades...',
            'autocomplete': 'off'
        })
    )
    
    category = forms.ChoiceField(
        choices=[('', 'Todas las categorías')],
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Obtener categorías disponibles
        categories = Skill.objects.values_list('category', flat=True).distinct()
        category_choices = [('', 'Todas las categorías')]
        category_choices.extend([(cat, cat.title()) for cat in categories if cat])
        
        self.fields['category'].choices = category_choices

class ContactPreferencesForm(forms.Form):
    """Formulario para configurar preferencias de contacto"""
    
    allow_contact_email = forms.BooleanField(
        required=False,
        initial=True,
        label='Permitir contacto por email',
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-meraki-600 focus:ring-meraki-500 border-gray-300 rounded'
        })
    )
    
    allow_contact_phone = forms.BooleanField(
        required=False,
        initial=False,
        label='Permitir contacto por teléfono',
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-meraki-600 focus:ring-meraki-500 border-gray-300 rounded'
        })
    )
    
    profile_visibility = forms.ChoiceField(
        choices=[
            ('public', 'Público - Visible para todos'),
            ('companies', 'Solo empresas verificadas'),
            ('private', 'Privado - Solo yo')
        ],
        initial='companies',
        label='Visibilidad del perfil',
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500'
        })
    )
    
    show_salary_expectations = forms.BooleanField(
        required=False,
        initial=True,
        label='Mostrar expectativas salariales',
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-meraki-600 focus:ring-meraki-500 border-gray-300 rounded'
        })
    )

class NotificationPreferencesForm(forms.Form):
    """Formulario para configurar preferencias de notificaciones"""
    
    email_job_alerts = forms.BooleanField(
        required=False,
        initial=True,
        label='Alertas de empleo por email',
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-meraki-600 focus:ring-meraki-500 border-gray-300 rounded'
        })
    )
    
    email_application_updates = forms.BooleanField(
        required=False,
        initial=True,
        label='Actualizaciones de postulaciones por email',
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-meraki-600 focus:ring-meraki-500 border-gray-300 rounded'
        })
    )
    
    email_course_updates = forms.BooleanField(
        required=False,
        initial=True,
        label='Actualizaciones de cursos por email',
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-meraki-600 focus:ring-meraki-500 border-gray-300 rounded'
        })
    )
    
    email_newsletter = forms.BooleanField(
        required=False,
        initial=False,
        label='Newsletter semanal',
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-meraki-600 focus:ring-meraki-500 border-gray-300 rounded'
        })
    )
    
    email_marketing = forms.BooleanField(
        required=False,
        initial=False,
        label='Comunicaciones de marketing',
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-meraki-600 focus:ring-meraki-500 border-gray-300 rounded'
        })
    )
    
    sms_important_updates = forms.BooleanField(
        required=False,
        initial=False,
        label='SMS para actualizaciones importantes',
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-meraki-600 focus:ring-meraki-500 border-gray-300 rounded'
        })
    )
    
    push_notifications = forms.BooleanField(
        required=False,
        initial=True,
        label='Notificaciones push del navegador',
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-meraki-600 focus:ring-meraki-500 border-gray-300 rounded'
        })
    )

class ApplicationFilterForm(forms.Form):
    """Formulario para filtrar postulaciones"""
    
    status = forms.ChoiceField(
        choices=[('', 'Todos los estados')],
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500'
        })
    )
    
    company = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500',
            'placeholder': 'Filtrar por empresa...'
        })
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500',
            'type': 'date'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Importar aquí para evitar dependencias circulares
        from jobs.models import Application
        
        # Agregar opciones de estado
        status_choices = [('', 'Todos los estados')]
        status_choices.extend(Application.STATUS_CHOICES)
        self.fields['status'].choices = status_choices
    
    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise ValidationError('La fecha de inicio no puede ser posterior a la fecha de fin.')
        
        return cleaned_data

class ProfileCompletionForm(forms.Form):
    """Formulario para completar elementos faltantes del perfil"""
    
    def __init__(self, *args, **kwargs):
        applicant = kwargs.pop('applicant', None)
        super().__init__(*args, **kwargs)
        
        if applicant:
            # Agregar campos dinámicamente basado en lo que falta
            if not applicant.first_name:
                self.fields['first_name'] = forms.CharField(
                    max_length=100,
                    widget=forms.TextInput(attrs={
                        'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500',
                        'placeholder': 'Tu nombre'
                    })
                )
            
            if not applicant.last_name:
                self.fields['last_name'] = forms.CharField(
                    max_length=100,
                    widget=forms.TextInput(attrs={
                        'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500',
                        'placeholder': 'Tu apellido'
                    })
                )
            
            if not applicant.current_position:
                self.fields['current_position'] = forms.CharField(
                    max_length=200,
                    widget=forms.TextInput(attrs={
                        'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500',
                        'placeholder': 'Tu posición actual'
                    })
                )
            
            if not applicant.education_level:
                self.fields['education_level'] = forms.ChoiceField(
                    choices=ApplicantProfile._meta.get_field('education_level').choices,
                    widget=forms.Select(attrs={
                        'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500'
                    })
                )
            
            if not applicant.cv_file:
                self.fields['cv_file'] = forms.FileField(
                    validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx'])],
                    widget=forms.FileInput(attrs={
                        'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-meraki-50 file:text-meraki-700 hover:file:bg-meraki-100',
                        'accept': '.pdf,.doc,.docx'
                    })
                )

class BulkSkillsForm(forms.Form):
    """Formulario para agregar múltiples habilidades de una vez"""
    
    skills_data = forms.CharField(
        widget=forms.HiddenInput()
    )
    
    def clean_skills_data(self):
        import json
        skills_data = self.cleaned_data.get('skills_data')
        
        try:
            skills_list = json.loads(skills_data)
            
            if not isinstance(skills_list, list):
                raise ValidationError('Formato de datos inválido.')
            
            for skill_data in skills_list:
                if not all(k in skill_data for k in ['skill_id', 'proficiency_level', 'years_experience']):
                    raise ValidationError('Datos de habilidad incompletos.')
                
                # Validar que skill_id existe
                try:
                    Skill.objects.get(id=skill_data['skill_id'])
                except Skill.DoesNotExist:
                    raise ValidationError(f'Habilidad con ID {skill_data["skill_id"]} no encontrada.')
                
                # Validar proficiency_level
                valid_levels = [choice[0] for choice in ApplicantSkill._meta.get_field('proficiency_level').choices]
                if skill_data['proficiency_level'] not in valid_levels:
                    raise ValidationError('Nivel de competencia inválido.')
                
                # Validar years_experience
                years = skill_data['years_experience']
                if not isinstance(years, int) or years < 0 or years > 50:
                    raise ValidationError('Años de experiencia inválidos.')
            
            return skills_list
            
        except json.JSONDecodeError:
            raise ValidationError('Formato JSON inválido.')
        except Exception as e:
            raise ValidationError(f'Error procesando datos: {str(e)}')

class QuickApplicationForm(forms.Form):
    """Formulario rápido para postularse a un empleo"""
    
    job_id = forms.IntegerField(widget=forms.HiddenInput())
    
    cover_letter = forms.CharField(
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500',
            'rows': 4,
            'placeholder': 'Escribe una breve carta de presentación (opcional)...'
        }),
        help_text='Máximo 1000 caracteres'
    )
    
    use_profile_cv = forms.BooleanField(
        required=False,
        initial=True,
        label='Usar CV del perfil',
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-meraki-600 focus:ring-meraki-500 border-gray-300 rounded'
        })
    )
    
    custom_cv = forms.FileField(
        required=False,
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx'])],
        widget=forms.FileInput(attrs={
            'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-meraki-50 file:text-meraki-700 hover:file:bg-meraki-100',
            'accept': '.pdf,.doc,.docx'
        }),
        help_text='Solo si quieres usar un CV diferente al de tu perfil'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        use_profile_cv = cleaned_data.get('use_profile_cv')
        custom_cv = cleaned_data.get('custom_cv')
        
        if not use_profile_cv and not custom_cv:
            raise ValidationError('Debes usar el CV de tu perfil o subir uno personalizado.')
        
        return cleaned_data
        if years and years > 50:
            raise ValidationError('Los años de experiencia no pueden ser más de 50.')
        return years
    
    def clean_birth_date(self):
        from datetime import date, timedelta
        birth_date = self.cleaned_data.get('birth_date')
        if birth_date:
            today = date.today()
            min_age = today - timedelta(days=16*365)  # 16 años mínimo
            max_age = today - timedelta(days=100*365)  # 100 años máximo
            
            if birth_date > min_age:
                raise ValidationError('Debes tener al menos 16 años.')
            if birth_date < max_age:
                raise ValidationError('Fecha de nacimiento no válida.')
        
        return birth_date

class CVUploadForm(forms.Form):
    """Formulario para subir CV"""
    
    cv_file = forms.FileField(
        label='Archivo CV',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx'])],
        widget=forms.FileInput(attrs={
            'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-meraki-50 file:text-meraki-700 hover:file:bg-meraki-100',
            'accept': '.pdf,.doc,.docx'
        }),
        help_text='Formatos permitidos: PDF, DOC, DOCX. Tamaño máximo: 5MB'
    )
    
    def clean_cv_file(self):
        cv_file = self.cleaned_data.get('cv_file')
        
        if cv_file:
            # Validar tamaño (5MB máximo)
            if cv_file.size > 5 * 1024 * 1024:
                raise ValidationError('El archivo no puede ser mayor a 5MB.')
            
            # Validar extensión
            ext = os.path.splitext(cv_file.name)[1].lower()
            if ext not in ['.pdf', '.doc', '.docx']:
                raise ValidationError('Solo se permiten archivos PDF, DOC o DOCX.')
        
        return cv_file

class PortfolioUploadForm(forms.Form):
    """Formulario para subir portfolio"""
    
    portfolio_file = forms.FileField(
        label='Archivo Portfolio',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'zip', 'rar'])],
        widget=forms.FileInput(attrs={
            'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-meraki-50 file:text-meraki-700 hover:file:bg-meraki-100',
            'accept': '.pdf,.zip,.rar'
        }),
        help_text='Formatos permitidos: PDF, ZIP, RAR. Tamaño máximo: 10MB'
    )
    
    def clean_portfolio_file(self):
        portfolio_file = self.cleaned_data.get('portfolio_file')
        
        if portfolio_file:
            # Validar tamaño (10MB máximo)
            if portfolio_file.size > 10 * 1024 * 1024:
                raise ValidationError('El archivo no puede ser mayor a 10MB.')
            
            # Validar extensión
            ext = os.path.splitext(portfolio_file.name)[1].lower()
            if ext not in ['.pdf', '.zip', '.rar']:
                raise ValidationError('Solo se permiten archivos PDF, ZIP o RAR.')
        
        return portfolio_file

class SkillForm(forms.ModelForm):
    """Formulario para agregar/editar habilidades"""
    
    class Meta:
        model = ApplicantSkill
        fields = ['skill', 'proficiency_level', 'years_experience']
        widgets = {
            'skill': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500'
            }),
            'proficiency_level': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500'
            }),
            'years_experience': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-meraki-500',
                'min': '0',
                'max': '50'
            })
        }
        labels = {
            'skill': 'Habilidad',
            'proficiency_level': 'Nivel de Competencia',
            'years_experience': 'Años de Experiencia'
        }
    
    def __init__(self, *args, **kwargs):
        applicant = kwargs.pop('applicant', None)
        super().__init__(*args, **kwargs)
        
        if applicant:
            # Excluir habilidades que ya tiene el postulante
            existing_skills = applicant.skills.values_list('id', flat=True)
            self.fields['skill'].queryset = Skill.objects.exclude(id__in=existing_skills)
    
    def clean_years_experience(self):
        years = self.cleaned_data.get('years_experience')
        if years and years < 0:
            raise ValidationError('Los años de experiencia no pueden ser negativos.')