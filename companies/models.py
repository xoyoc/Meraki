# apps/companies/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator, URLValidator
from django.utils import timezone
from django.urls import reverse
from PIL import Image
import os

#from applicants.models import Application

User = get_user_model()

class Company(models.Model):
    """Modelo para representar una empresa en el sistema"""
    
    # Opciones para el tamaño de la empresa
    SIZE_CHOICES = [
        ('startup', 'Startup (1-10 empleados)'),
        ('small', 'Pequeña (11-50 empleados)'),
        ('medium', 'Mediana (51-200 empleados)'),
        ('large', 'Grande (201-1000 empleados)'),
        ('enterprise', 'Corporativa (1000+ empleados)'),
    ]
    
    # Industrias disponibles
    INDUSTRY_CHOICES = [
        ('technology', 'Tecnología'),
        ('finance', 'Finanzas'),
        ('healthcare', 'Salud'),
        ('education', 'Educación'),
        ('retail', 'Retail'),
        ('manufacturing', 'Manufactura'),
        ('consulting', 'Consultoría'),
        ('marketing', 'Marketing'),
        ('real_estate', 'Bienes Raíces'),
        ('hospitality', 'Hospitalidad'),
        ('transportation', 'Transporte'),
        ('energy', 'Energía'),
        ('agriculture', 'Agricultura'),
        ('entertainment', 'Entretenimiento'),
        ('government', 'Gobierno'),
        ('nonprofit', 'Sin Ánimo de Lucro'),
        ('other', 'Otro'),
    ]
    
    # Información básica
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE,
        related_name='company',
        help_text="Usuario asociado a la empresa"
    )
    name = models.CharField(
        max_length=200,
        verbose_name="Nombre de la empresa",
        help_text="Nombre oficial de la empresa"
    )
    slug = models.SlugField(
        max_length=200,
        unique=True,
        blank=True,
        help_text="URL amigable para la empresa (se genera automáticamente)"
    )
    
    # Información detallada
    description = models.TextField(
        blank=True,
        verbose_name="Descripción",
        help_text="Descripción de la empresa, su misión y valores"
    )
    industry = models.CharField(
        max_length=50,
        choices=INDUSTRY_CHOICES,
        blank=True,
        verbose_name="Industria",
        help_text="Sector industrial principal"
    )
    size = models.CharField(
        max_length=20,
        choices=SIZE_CHOICES,
        blank=True,
        verbose_name="Tamaño de la empresa"
    )
    
    # Información de contacto y ubicación
    website = models.URLField(
        blank=True,
        validators=[URLValidator()],
        verbose_name="Sitio web",
        help_text="URL del sitio web oficial"
    )
    location = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Ubicación",
        help_text="Ciudad, país donde se encuentra la empresa"
    )
    address = models.TextField(
        blank=True,
        verbose_name="Dirección completa"
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Teléfono"
    )
    
    # Información adicional
    founded_year = models.PositiveIntegerField(
        blank=True,
        null=True,
        validators=[
            MinValueValidator(1800),
            MaxValueValidator(timezone.now().year)
        ],
        verbose_name="Año de fundación"
    )
    employee_count = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name="Número de empleados",
        help_text="Número aproximado de empleados"
    )
    
    # Logo y branding
    logo = models.ImageField(
        upload_to='companies/logos/',
        blank=True,
        null=True,
        verbose_name="Logo de la empresa",
        help_text="Logo oficial de la empresa (recomendado: 300x300px)"
    )
    cover_image = models.ImageField(
        upload_to='companies/covers/',
        blank=True,
        null=True,
        verbose_name="Imagen de portada",
        help_text="Imagen de portada para el perfil público"
    )
    
    # Configuraciones de privacidad y visibilidad
    is_public = models.BooleanField(
        default=True,
        verbose_name="Perfil público",
        help_text="¿El perfil de la empresa es visible públicamente?"
    )
    is_verified = models.BooleanField(
        default=False,
        verbose_name="Empresa verificada",
        help_text="¿La empresa ha sido verificada por el equipo de Meraki?"
    )
    is_premium = models.BooleanField(
        default=False,
        verbose_name="Cuenta premium",
        help_text="¿La empresa tiene una suscripción premium?"
    )
    
    # Configuraciones de notificaciones
    email_notifications = models.BooleanField(
        default=True,
        verbose_name="Notificaciones por email"
    )
    sms_notifications = models.BooleanField(
        default=False,
        verbose_name="Notificaciones por SMS"
    )
    weekly_digest = models.BooleanField(
        default=True,
        verbose_name="Resumen semanal"
    )
    
    # Métricas de rendimiento
    total_jobs_posted = models.PositiveIntegerField(
        default=0,
        verbose_name="Total de vacantes publicadas"
    )
    total_hires = models.PositiveIntegerField(
        default=0,
        verbose_name="Total de contrataciones"
    )
    avg_time_to_hire = models.PositiveIntegerField(
        default=0,
        verbose_name="Tiempo promedio de contratación (días)"
    )
    profile_views = models.PositiveIntegerField(
        default=0,
        verbose_name="Vistas del perfil"
    )
    
    # Información de facturación (para suscripciones premium)
    billing_contact_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Contacto de facturación"
    )
    billing_email = models.EmailField(
        blank=True,
        verbose_name="Email de facturación"
    )
    tax_id = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="NIT/RUT",
        help_text="Número de identificación tributaria"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de registro"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización"
    )
    last_active = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actividad"
    )
    
    class Meta:
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['industry', 'size']),
            models.Index(fields=['location']),
            models.Index(fields=['is_public', 'is_verified']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """Override save para generar slug automáticamente y procesar imágenes"""
        if not self.slug:
            from django.utils.text import slugify
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            
            while Company.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            self.slug = slug
        
        super().save(*args, **kwargs)
        
        # Procesar logo si se subió uno nuevo
        if self.logo:
            self.process_logo()
    
    def process_logo(self):
        """Redimensionar y optimizar el logo"""
        try:
            img = Image.open(self.logo.path)
            
            # Redimensionar manteniendo proporción
            if img.height > 300 or img.width > 300:
                img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                img.save(self.logo.path, optimize=True, quality=85)
        except Exception as e:
            # Log error pero no fallar
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error processing company logo: {e}")
    
    def get_absolute_url(self):
        """URL del perfil público de la empresa"""
        return reverse('companies:public_profile', kwargs={'pk': self.pk})
    
    def get_dashboard_url(self):
        """URL del dashboard de la empresa"""
        return reverse('companies:dashboard')
    
    @property
    def active_jobs_count(self):
        """Número de vacantes activas"""
        return self.jobpost_set.filter(status='approved', is_active=True).count()
    
    @property
    def pending_jobs_count(self):
        """Número de vacantes pendientes de aprobación"""
        return self.jobpost_set.filter(status='pending').count()
    
    @property
    def total_applications_count(self):
        """Total de postulaciones recibidas"""
        from jobs.models import Application
        return Application.objects.filter(job_post__company=self).count()
    
    @property
    def pending_applications_count(self):
        """Postulaciones pendientes de revisión"""
        from jobs.models import Application
        return Application.objects.filter(
            job_post__company=self,
            status__in=['applied', 'reviewing']
        ).count()
    
    @property
    def company_age_years(self):
        """Años de antigüedad de la empresa"""
        if self.founded_year:
            return timezone.now().year - self.founded_year
        return None
    
    @property
    def hiring_success_rate(self):
        """Tasa de éxito en contrataciones"""
        from jobs.models import Application
        
        total_apps = Application.objects.filter(job_post__company=self).count()
        if total_apps == 0:
            return 0
        
        hired_apps = Application.objects.filter(
            job_post__company=self,
            status='accepted'
        ).count()
        
        return round((hired_apps / total_apps) * 100, 2)
    
    @property
    def avg_match_score(self):
        """Score promedio de matching con candidatos"""
        from matching.models import MatchScore
        
        scores = MatchScore.objects.filter(job_post__company=self)
        if scores.exists():
            return round(scores.aggregate(models.Avg('total_score'))['total_score__avg'], 2)
        return 0
    
    def get_size_display_short(self):
        """Versión corta del tamaño de empresa"""
        size_mapping = {
            'startup': '1-10',
            'small': '11-50',
            'medium': '51-200',
            'large': '201-1K',
            'enterprise': '1K+',
        }
        return size_mapping.get(self.size, 'N/A')
    
    def update_metrics(self):
        """Actualizar métricas de la empresa"""
        from jobs.models import Application
        from django.db.models import Avg
        
        # Actualizar total de contrataciones
        self.total_hires = Application.objects.filter(
            job_post__company=self,
            status='accepted'
        ).count()
        
        # Actualizar total de vacantes publicadas
        self.total_jobs_posted = self.jobpost_set.filter(
            status='approved'
        ).count()
        
        # Calcular tiempo promedio de contratación
        hired_apps = Application.objects.filter(
            job_post__company=self,
            status='accepted'
        ).exclude(updated_at__isnull=True)
        
        if hired_apps.exists():
            # Calcular días promedio entre postulación y contratación
            total_days = 0
            count = 0
            
            for app in hired_apps:
                days = (app.updated_at - app.applied_at).days
                if days >= 0:  # Validar que sea positivo
                    total_days += days
                    count += 1
            
            if count > 0:
                self.avg_time_to_hire = total_days // count
        
        self.save(update_fields=['total_hires', 'total_jobs_posted', 'avg_time_to_hire'])

class SavedCandidate(models.Model):
    """Modelo para candidatos guardados por las empresas"""
    
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        verbose_name="Empresa"
    )
    applicant = models.ForeignKey(
        'applicants.ApplicantProfile',
        on_delete=models.CASCADE,
        verbose_name="Candidato"
    )
    
    # Información adicional
    notes = models.TextField(
        blank=True,
        verbose_name="Notas",
        help_text="Notas privadas sobre el candidato"
    )
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True,
        verbose_name="Calificación",
        help_text="Calificación del candidato (1-5 estrellas)"
    )
    
    # Tags para categorizar candidatos
    tags = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Etiquetas",
        help_text="Etiquetas separadas por comas (ej: senior, python, remote)"
    )
    
    # Estado del seguimiento
    STATUS_CHOICES = [
        ('saved', 'Guardado'),
        ('contacted', 'Contactado'),
        ('interviewing', 'En entrevista'),
        ('hired', 'Contratado'),
        ('rejected', 'Rechazado'),
        ('not_interested', 'No interesado'),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='saved',
        verbose_name="Estado"
    )
    
    # Timestamps
    saved_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de guardado"
    )
    last_contacted = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Último contacto"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización"
    )
    
    class Meta:
        verbose_name = "Candidato Guardado"
        verbose_name_plural = "Candidatos Guardados"
        unique_together = ['company', 'applicant']
        ordering = ['-saved_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['saved_at']),
        ]
    
    def __str__(self):
        return f"{self.company.name} - {self.applicant.get_full_name()}"
    
    @property
    def tags_list(self):
        """Devolver lista de tags"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        return []
    
    def add_tag(self, tag):
        """Agregar un tag"""
        tags = self.tags_list
        if tag not in tags:
            tags.append(tag)
            self.tags = ', '.join(tags)
            self.save(update_fields=['tags'])
    
    def remove_tag(self, tag):
        """Remover un tag"""
        tags = self.tags_list
        if tag in tags:
            tags.remove(tag)
            self.tags = ', '.join(tags)
            self.save(update_fields=['tags'])

class Interview(models.Model):
    """Modelo para gestionar entrevistas"""
    
    # Tipos de entrevista
    TYPE_CHOICES = [
        ('phone', 'Telefónica'),
        ('video', 'Video llamada'),
        ('in_person', 'Presencial'),
        ('technical', 'Técnica'),
        ('hr', 'Recursos Humanos'),
        ('final', 'Final'),
    ]
    
    # Estados de la entrevista
    STATUS_CHOICES = [
        ('scheduled', 'Programada'),
        ('confirmed', 'Confirmada'),
        ('in_progress', 'En progreso'),
        ('completed', 'Completada'),
        ('cancelled', 'Cancelada'),
        ('rescheduled', 'Reprogramada'),
        ('no_show', 'No se presentó'),
    ]
    
    application = models.ForeignKey('jobs.Application', on_delete=models.CASCADE, verbose_name="Postulación", related_name='interviews')
    
    # Información de la entrevista
    interview_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        verbose_name="Tipo de entrevista"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='scheduled',
        verbose_name="Estado"
    )
    
    # Programación
    scheduled_date = models.DateTimeField(
        verbose_name="Fecha y hora programada"
    )
    duration_minutes = models.PositiveIntegerField(
        default=60,
        verbose_name="Duración (minutos)"
    )
    timezone = models.CharField(
        max_length=50,
        default='America/Bogota',
        verbose_name="Zona horaria"
    )
    
    # Información del entrevistador
    interviewer_name = models.CharField(
        max_length=200,
        verbose_name="Nombre del entrevistador"
    )
    interviewer_email = models.EmailField(
        verbose_name="Email del entrevistador"
    )
    interviewer_title = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Cargo del entrevistador"
    )
    
    # Detalles de la entrevista
    location = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Ubicación",
        help_text="Dirección física o enlace de video llamada"
    )
    instructions = models.TextField(
        blank=True,
        verbose_name="Instrucciones",
        help_text="Instrucciones especiales para el candidato"
    )
    
    # Resultados y feedback
    notes = models.TextField(
        blank=True,
        verbose_name="Notas de la entrevista"
    )
    score = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        null=True,
        blank=True,
        verbose_name="Puntuación (1-10)"
    )
    recommendation = models.CharField(
        max_length=20,
        choices=[
            ('hire', 'Contratar'),
            ('maybe', 'Tal vez'),
            ('no_hire', 'No contratar'),
            ('next_round', 'Siguiente ronda'),
        ],
        blank=True,
        verbose_name="Recomendación"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de finalización"
    )
    
    class Meta:
        verbose_name = "Entrevista"
        verbose_name_plural = "Entrevistas"
        ordering = ['scheduled_date']
        indexes = [
            models.Index(fields=['application', 'status']),
            models.Index(fields=['scheduled_date']),
            models.Index(fields=['interviewer_email']),
        ]
    
    def __str__(self):
        return f"Entrevista {self.get_interview_type_display()} - {self.application.applicant.get_full_name()}"
    
    @property
    def is_upcoming(self):
        """¿La entrevista es próxima?"""
        return self.scheduled_date > timezone.now() and self.status in ['scheduled', 'confirmed']
    
    @property
    def is_past_due(self):
        """¿La entrevista ya pasó?"""
        return self.scheduled_date < timezone.now() and self.status in ['scheduled', 'confirmed']
    
    @property
    def company(self):
        """Empresa asociada a la entrevista"""
        return self.application.job_post.company
    
    @property
    def applicant(self):
        """Candidato asociado a la entrevista"""
        return self.application.applicant
    
    def mark_completed(self, notes='', score=None, recommendation=''):
        """Marcar entrevista como completada"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        
        if notes:
            self.notes = notes
        if score:
            self.score = score
        if recommendation:
            self.recommendation = recommendation
        
        self.save()
    
    def reschedule(self, new_date):
        """Reprogramar entrevista"""
        self.scheduled_date = new_date
        self.status = 'rescheduled'
        self.save()
    
    def cancel(self, reason=''):
        """Cancelar entrevista"""
        self.status = 'cancelled'
        if reason:
            self.notes = f"Cancelada: {reason}"
        self.save()
    
    def set_application_model():
        global Application
        from applicants.models import Application
        return Application
