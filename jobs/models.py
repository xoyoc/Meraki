# apps/jobs/models.py
from django.db import models
from ckeditor_uploader.fields import RichTextUploadingField
from django.contrib.auth import get_user_model
from django.utils import timezone

from applicants.models import ApplicantProfile
from companies.models import Company

User = get_user_model()

class Skill(models.Model):
    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=50)
    
    def __str__(self):
        return self.name

class JobPost(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Borrador'),
        ('pending', 'Pendiente Aprobación'),
        ('approved', 'Aprobada'),
        ('rejected', 'Rechazada'),
        ('closed', 'Cerrada'),
    )
    
    EXPERIENCE_LEVELS = (
        ('entry', 'Junior (0-2 años)'),
        ('mid', 'Semi-senior (2-5 años)'),
        ('senior', 'Senior (5+ años)'),
    )
    
    company = models.ForeignKey(
        Company, 
        on_delete=models.CASCADE,
        related_name='job_posts',
        blank=True, null=True
    )

    title = models.CharField(max_length=200)
    description = RichTextUploadingField(
        config_name='jobs_editor',
        help_text="Descripción detallada de la vacante"
    )
    requirements = RichTextUploadingField(
        config_name='jobs_editor',
        help_text="Requisitos y cualificaciones"
    )
    
    # Campos para matching
    experience_level = models.CharField(max_length=20, choices=EXPERIENCE_LEVELS)
    skills_required = models.ManyToManyField(Skill, through='JobPostSkill')
    location = models.CharField(max_length=100)
    salary_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Control de estado
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_jobs')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deadline = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.company.name}"

class JobPostSkill(models.Model):
    job_post = models.ForeignKey(JobPost, on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    is_required = models.BooleanField(default=True)
    weight = models.IntegerField(default=1)  # Para el algoritmo de matching

class Application(models.Model):
    STATUS_CHOICES = (
        ('applied', 'Postulado'),
        ('reviewing', 'En revisión'),
        ('shortlisted', 'Preseleccionado'),
        ('interviewed', 'Entrevistado'),
        ('accepted', 'Aceptado'),
        ('rejected', 'Rechazado'),
    )
    
    job_post = models.ForeignKey(JobPost, on_delete=models.CASCADE, related_name='applications')
    applicant = models.ForeignKey(ApplicantProfile, on_delete=models.CASCADE)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='applied')
    cover_letter = models.TextField(blank=True)
    match_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['job_post', 'applicant']

class SavedJob(models.Model):
    """Modelo para vacantes guardadas por los postulantes"""
    
    job_post = models.ForeignKey(
        JobPost, 
        on_delete=models.CASCADE, 
        related_name='saved_by'
    )
    applicant = models.ForeignKey(
        ApplicantProfile, 
        on_delete=models.CASCADE,
        related_name='saved_jobs'
    )
    saved_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(
        blank=True, 
        help_text="Notas personales sobre esta vacante"
    )
    
    class Meta:
        unique_together = ['job_post', 'applicant']
        ordering = ['-saved_at']
        verbose_name = "Vacante Guardada"
        verbose_name_plural = "Vacantes Guardadas"
    
    def __str__(self):
        return f"{self.applicant.user.get_full_name()} - {self.job_post.title}"
    
    @property
    def is_still_active(self):
        """Verifica si la vacante aún está activa"""
        return (
            self.job_post.is_active and 
            self.job_post.status == 'approved' and
            self.job_post.deadline > timezone.now()
        )
    
    @property
    def days_since_saved(self):
        """Días desde que se guardó la vacante"""
        return (timezone.now() - self.saved_at).days