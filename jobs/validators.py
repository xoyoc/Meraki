# apps/jobs/validators.py
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import timedelta
import re

def validate_job_title(value):
    """Validador para títulos de trabajo"""
    if not value or len(value.strip()) < 5:
        raise ValidationError(_('El título debe tener al menos 5 caracteres.'))
    
    if len(value) > 200:
        raise ValidationError(_('El título no puede exceder 200 caracteres.'))
    
    # Check for suspicious patterns
    suspicious_patterns = [
        r'\$\$\$+',  # Multiple dollar signs
        r'!!!+',     # Multiple exclamation marks
        r'URGENT',   # All caps urgent
        r'HIRING NOW',
        r'MAKE MONEY FAST',
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, value.upper()):
            raise ValidationError(_('El título contiene texto no permitido.'))

def validate_salary_range(salary_min, salary_max):
    """Validador para rangos de salario"""
    if salary_min is not None and salary_min < 0:
        raise ValidationError({'salary_min': _('El salario mínimo no puede ser negativo.')})
    
    if salary_max is not None and salary_max < 0:
        raise ValidationError({'salary_max': _('El salario máximo no puede ser negativo.')})
    
    if salary_min and salary_max:
        if salary_min >= salary_max:
            raise ValidationError({'salary_max': _('El salario máximo debe ser mayor al salario mínimo.')})
        
        # Check for unrealistic ranges
        if salary_max > salary_min * 5:
            raise ValidationError({
                'salary_max': _('El rango salarial parece muy amplio. Considera ajustar los valores.')
            })
        
        # Check for unrealistic low salaries (assuming minimum wage context)
        min_wage_monthly = 5000  # Adjust based on your country's minimum wage
        if salary_min and salary_min < min_wage_monthly:
            raise ValidationError({
                'salary_min': _(f'El salario mínimo parece muy bajo (menor a ${min_wage_monthly:,}).')
            })

def validate_job_deadline(value):
    """Validador para fechas límite de trabajos"""
    if not value:
        raise ValidationError(_('La fecha límite es requerida.'))
    
    now = timezone.now()
    tomorrow = now + timedelta(days=1)
    max_deadline = now + timedelta(days=365)  # Maximum 1 year
    
    if value < tomorrow:
        raise ValidationError(_('La fecha límite debe ser al menos mañana.'))
    
    if value > max_deadline:
        raise ValidationError(_('La fecha límite no puede ser mayor a 1 año.'))

def validate_description_length(value):
    """Validador para longitud de descripción"""
    if not value or len(value.strip()) < 50:
        raise ValidationError(_('La descripción debe tener al menos 50 caracteres.'))
    
    if len(value) > 5000:
        raise ValidationError(_('La descripción no puede exceder 5000 caracteres.'))
    
    # Check for minimum word count
    words = len(value.split())
    if words < 10:
        raise ValidationError(_('La descripción debe tener al menos 10 palabras.'))

def validate_requirements_length(value):
    """Validador para longitud de requisitos"""
    if not value or len(value.strip()) < 20:
        raise ValidationError(_('Los requisitos deben tener al menos 20 caracteres.'))
    
    if len(value) > 3000:
        raise ValidationError(_('Los requisitos no pueden exceder 3000 caracteres.'))

def validate_cover_letter(value):
    """Validador para carta de presentación"""
    if value and len(value) > 1000:
        raise ValidationError(_('La carta de presentación no puede exceder 1000 caracteres.'))
    
    # Check for spam patterns
    spam_patterns = [
        r'http[s]?://',  # URLs
        r'www\.',        # Web addresses
        r'@\w+\.',       # Email addresses
        r'\d{10,}',      # Long numbers (phone numbers)
    ]
    
    for pattern in spam_patterns:
        if re.search(pattern, value.lower()):
            raise ValidationError(_('La carta de presentación contiene contenido no permitido.'))

def validate_skill_name(value):
    """Validador para nombres de skills"""
    if not value or len(value.strip()) < 2:
        raise ValidationError(_('El nombre del skill debe tener al menos 2 caracteres.'))
    
    if len(value) > 100:
        raise ValidationError(_('El nombre del skill no puede exceder 100 caracteres.'))
    
    # Check for valid characters (letters, numbers, spaces, hyphens, dots)
    if not re.match(r'^[a-zA-Z0-9\s\-\.#\+]+$', value):
        raise ValidationError(_('El nombre del skill contiene caracteres no válidos.'))

def validate_location(value):
    """Validador para ubicación"""
    if not value or len(value.strip()) < 2:
        raise ValidationError(_('La ubicación debe tener al menos 2 caracteres.'))
    
    if len(value) > 100:
        raise ValidationError(_('La ubicación no puede exceder 100 caracteres.'))
    
    # Common location patterns
    valid_patterns = [
        r'remoto',
        r'remote',
        r'híbrido',
        r'hybrid',
        r'presencial',
        r'on-site',
        r'[a-zA-ZÀ-ÿ\s\-,\.]+',  # City names with accents
    ]
    
    is_valid = any(re.search(pattern, value.lower()) for pattern in valid_patterns)
    if not is_valid:
        raise ValidationError(_('Por favor ingresa una ubicación válida.'))

def validate_company_can_post_job(company):
    """Validador para verificar si una empresa puede publicar trabajos"""
    if not company:
        raise ValidationError(_('Empresa no encontrada.'))
    
    if not company.is_active:
        raise ValidationError(_('La empresa no está activa.'))
    
    # Check if company has reached job posting limit
    from .models import JobPost
    active_jobs = JobPost.objects.filter(
        company=company,
        status__in=['pending', 'approved'],
        is_active=True
    ).count()
    
    max_active_jobs = getattr(company, 'max_active_jobs', 50)  # Default limit
    if active_jobs >= max_active_jobs:
        raise ValidationError(_(f'Has alcanzado el límite de {max_active_jobs} vacantes activas.'))

def validate_application_eligibility(job_post, applicant):
    """Validador para verificar si un candidato puede postularse"""
    if not job_post.is_active:
        raise ValidationError(_('Esta vacante ya no está activa.'))
    
    if job_post.status != 'approved':
        raise ValidationError(_('Esta vacante no está disponible para postulaciones.'))
    
    if job_post.deadline < timezone.now():
        raise ValidationError(_('La fecha límite para esta vacante ha expirado.'))
    
    # Check if already applied
    from .models import Application
    if Application.objects.filter(job_post=job_post, applicant=applicant).exists():
        raise ValidationError(_('Ya te has postulado a esta vacante.'))
    
    # Check if applicant's profile is complete enough
    if not applicant.user.first_name or not applicant.user.last_name:
        raise ValidationError(_('Debes completar tu nombre en el perfil antes de postularte.'))

def validate_skills_selection(skills):
    """Validador para selección de skills"""
    if not skills:
        raise ValidationError(_('Debes seleccionar al menos un skill.'))
    
    if len(skills) > 20:
        raise ValidationError(_('No puedes seleccionar más de 20 skills.'))
    
    # Check for duplicate skills
    skill_names = [skill.name.lower() for skill in skills]
    if len(skill_names) != len(set(skill_names)):
        raise ValidationError(_('Has seleccionado skills duplicados.'))

def validate_job_update_permissions(job_post, user):
    """Validador para permisos de actualización de trabajos"""
    if not job_post.company or job_post.company.user != user:
        raise ValidationError(_('No tienes permisos para editar esta vacante.'))
    
    if job_post.status == 'closed':
        raise ValidationError(_('No puedes editar una vacante cerrada.'))
    
    # Allow editing if it's in draft, pending, or rejected status
    # Approved jobs can be edited but will go back to pending
    if job_post.status not in ['draft', 'pending', 'approved', 'rejected']:
        raise ValidationError(_('Esta vacante no puede ser editada en su estado actual.'))

def validate_search_query(query):
    """Validador para consultas de búsqueda"""
    if query and len(query) > 200:
        raise ValidationError(_('La consulta de búsqueda es demasiado larga.'))
    
    # Check for potentially malicious patterns
    malicious_patterns = [
        r'<script',
        r'javascript:',
        r'onload=',
        r'onerror=',
        r'eval\(',
    ]
    
    for pattern in malicious_patterns:
        if re.search(pattern, query.lower()):
            raise ValidationError(_('La consulta contiene caracteres no permitidos.'))

def validate_file_upload(file_obj):
    """Validador genérico para uploads de archivos"""
    if not file_obj:
        return
    
    # Check file size (5MB limit)
    max_size = 5 * 1024 * 1024  # 5MB
    if file_obj.size > max_size:
        raise ValidationError(_('El archivo es demasiado grande. Máximo 5MB.'))
    
    # Check file extension
    allowed_extensions = ['.pdf', '.doc', '.docx', '.txt']
    file_extension = file_obj.name.lower().split('.')[-1]
    if f'.{file_extension}' not in allowed_extensions:
        raise ValidationError(_(f'Tipo de archivo no permitido. Usa: {", ".join(allowed_extensions)}'))

def validate_email_domain(email):
    """Validador para dominios de email empresariales"""
    if not email:
        return
    
    blocked_domains = [
        'tempmail.com',
        '10minutemail.com',
        'guerrillamail.com',
        'mailinator.com',
        'throwaway.email',
    ]
    
    domain = email.split('@')[-1].lower()
    if domain in blocked_domains:
        raise ValidationError(_('No se permiten emails temporales.'))

def validate_phone_number(phone):
    """Validador para números de teléfono"""
    if not phone:
        return
    
    # Remove spaces, dashes, parentheses
    cleaned_phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Check if it's a valid format (Mexican phone numbers)
    if not re.match(r'^\+?52?[0-9]{10}', cleaned_phone):
        if not re.match(r'^[0-9]{10}', cleaned_phone):
            raise ValidationError(_('Ingresa un número de teléfono válido (10 dígitos).'))

def validate_job_category_limits(company, experience_level):
    """Validador para límites por categoría de trabajo"""
    from .models import JobPost
    
    # Count current jobs by experience level
    current_count = JobPost.objects.filter(
        company=company,
        experience_level=experience_level,
        status__in=['pending', 'approved'],
        is_active=True
    ).count()
    
    # Set limits by experience level
    limits = {
        'entry': 20,    # More entry level positions allowed
        'mid': 15,      # Moderate limit for mid-level
        'senior': 10,   # Fewer senior positions
    }
    
    limit = limits.get(experience_level, 15)
    if current_count >= limit:
        level_display = dict(JobPost.EXPERIENCE_LEVELS).get(experience_level, experience_level)
        raise ValidationError(
            _(f'Has alcanzado el límite de {limit} vacantes activas para nivel {level_display}.')
        )

class JobPostValidator:
    """Validador compuesto para JobPost"""
    
    def __init__(self, user=None, instance=None):
        self.user = user
        self.instance = instance
    
    def __call__(self, cleaned_data):
        errors = {}
        
        # Validate title
        title = cleaned_data.get('title')
        try:
            validate_job_title(title)
        except ValidationError as e:
            errors['title'] = e.message
        
        # Validate salary range
        salary_min = cleaned_data.get('salary_min')
        salary_max = cleaned_data.get('salary_max')
        try:
            validate_salary_range(salary_min, salary_max)
        except ValidationError as e:
            errors.update(e.message_dict if hasattr(e, 'message_dict') else {'salary': e.message})
        
        # Validate deadline
        deadline = cleaned_data.get('deadline')
        try:
            validate_job_deadline(deadline)
        except ValidationError as e:
            errors['deadline'] = e.message
        
        # Validate description
        description = cleaned_data.get('description')
        try:
            validate_description_length(description)
        except ValidationError as e:
            errors['description'] = e.message
        
        # Validate requirements
        requirements = cleaned_data.get('requirements')
        try:
            validate_requirements_length(requirements)
        except ValidationError as e:
            errors['requirements'] = e.message
        
        # Validate location
        location = cleaned_data.get('location')
        try:
            validate_location(location)
        except ValidationError as e:
            errors['location'] = e.message
        
        # Validate company permissions (for updates)
        if self.instance and self.instance.pk and self.user:
            try:
                validate_job_update_permissions(self.instance, self.user)
            except ValidationError as e:
                errors['__all__'] = e.message
        
        # Validate company can post job (for new jobs)
        if not self.instance and self.user and hasattr(self.user, 'company'):
            try:
                validate_company_can_post_job(self.user.company)
            except ValidationError as e:
                errors['__all__'] = e.message
        
        if errors:
            raise ValidationError(errors)
        
        return cleaned_data