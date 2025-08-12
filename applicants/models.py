# apps/applicants/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class ApplicantProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    # Información personal
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    birth_date = models.DateField(null=True, blank=True)
    
    # Información profesional
    current_position = models.CharField(max_length=200, blank=True)
    years_experience = models.IntegerField(default=0)
    education_level = models.CharField(max_length=50, choices=[
        ('high_school', 'Bachillerato'),
        ('technical', 'Técnico'),
        ('bachelor', 'Universitario'),
        ('master', 'Maestría'),
        ('phd', 'Doctorado'),
    ])
    
    # Archivos
    cv_file = models.FileField(
        upload_to='cvs/', 
        blank=True,
        help_text="Formatos permitidos: PDF, DOCX"
    )
    portfolio_file = models.FileField(upload_to='portfolios/', blank=True)
    
    # Scoring
    profile_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Skills
    skills = models.ManyToManyField('jobs.Skill', through='ApplicantSkill')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class ApplicantSkill(models.Model):
    applicant = models.ForeignKey(ApplicantProfile, on_delete=models.CASCADE)
    skill = models.ForeignKey('jobs.Skill', on_delete=models.CASCADE)
    proficiency_level = models.IntegerField(choices=[
        (1, 'Básico'),
        (2, 'Intermedio'),
        (3, 'Avanzado'),
        (4, 'Experto'),
    ])
    years_experience = models.IntegerField(default=0)

class JobAlert(models.Model):
    """Alertas de empleo configuradas por los postulantes"""
    
    EMPLOYMENT_TYPE_CHOICES = [
        ('', 'Cualquier tipo'),
        ('full_time', 'Tiempo Completo'),
        ('part_time', 'Medio Tiempo'),
        ('contract', 'Contrato'),
        ('freelance', 'Freelance'),
        ('internship', 'Práctica'),
        ('remote', 'Remoto'),
    ]
    
    EXPERIENCE_LEVEL_CHOICES = [
        ('', 'Cualquier nivel'),
        ('entry', 'Nivel de Entrada'),
        ('junior', 'Junior'),
        ('mid', 'Intermedio'),
        ('senior', 'Senior'),
        ('lead', 'Líder'),
        ('executive', 'Ejecutivo'),
    ]
    
    applicant = models.ForeignKey(
        ApplicantProfile,
        on_delete=models.CASCADE,
        related_name='job_alerts',
        verbose_name="Postulante"
    )
    
    # Configuración de la alerta
    name = models.CharField(
        max_length=100,
        verbose_name="Nombre de la Alerta",
        help_text="Un nombre descriptivo para identificar esta alerta"
    )
    
    # Criterios de búsqueda
    keywords = models.CharField(
        max_length=200,
        verbose_name="Palabras Clave",
        help_text="Palabras clave separadas por comas"
    )
    location = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Ubicación",
        help_text="Ciudad, estado o país"
    )
    
    # Filtros de empleo
    employment_type = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_TYPE_CHOICES,
        blank=True,
        verbose_name="Tipo de Empleo"
    )
    experience_level = models.CharField(
        max_length=20,
        choices=EXPERIENCE_LEVEL_CHOICES,
        blank=True,
        verbose_name="Nivel de Experiencia"
    )
    
    # Rango salarial
    min_salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Salario Mínimo"
    )
    max_salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Salario Máximo"
    )
    
    # Configuración de notificaciones
    is_active = models.BooleanField(
        default=True,
        verbose_name="Alerta Activa"
    )
    email_notifications = models.BooleanField(
        default=True,
        verbose_name="Notificaciones por Email"
    )
    frequency = models.CharField(
        max_length=20,
        choices=[
            ('immediate', 'Inmediato'),
            ('daily', 'Diario'),
            ('weekly', 'Semanal'),
        ],
        default='daily',
        verbose_name="Frecuencia de Notificaciones"
    )
    
    # Métricas
    jobs_found = models.PositiveIntegerField(
        default=0,
        verbose_name="Empleos Encontrados"
    )
    last_checked = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Última Verificación"
    )
    last_notification_sent = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Última Notificación Enviada"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")
    
    class Meta:
        verbose_name = "Alerta de Empleo"
        verbose_name_plural = "Alertas de Empleo"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.applicant.full_name} - {self.name}"
    
    @property
    def keywords_list(self):
        """Retorna las palabras clave como lista"""
        return [kw.strip() for kw in self.keywords.split(',') if kw.strip()]
    
    def update_last_checked(self):
        """Actualiza la fecha de última verificación"""
        self.last_checked = timezone.now()
        self.save(update_fields=['last_checked'])
    
    def increment_jobs_found(self, count=1):
        """Incrementa el contador de empleos encontrados"""
        self.jobs_found += count
        self.save(update_fields=['jobs_found'])
    
    def should_send_notification(self):
        """Determina si se debe enviar una notificación basada en la frecuencia"""
        if not self.is_active or not self.email_notifications:
            return False
        
        if not self.last_notification_sent:
            return True
        
        now = timezone.now()
        time_diff = now - self.last_notification_sent
        
        if self.frequency == 'immediate':
            return True
        elif self.frequency == 'daily':
            return time_diff >= timedelta(days=1)
        elif self.frequency == 'weekly':
            return time_diff >= timedelta(weeks=1)
        
        return False
    
    def mark_notification_sent(self):
        """Marca que se envió una notificación"""
        self.last_notification_sent = timezone.now()
        self.save(update_fields=['last_notification_sent'])
