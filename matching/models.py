# apps/matching/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import json

from applicants.models import ApplicantProfile
from companies.models import Company
from jobs.models import JobPost

User = get_user_model()

class MatchScore(models.Model):
    """Modelo para almacenar los scores de compatibilidad entre vacantes y candidatos"""
    
    job_post = models.ForeignKey(
        JobPost,
        on_delete=models.CASCADE,
        verbose_name="Vacante"
    )
    applicant = models.ForeignKey(
        ApplicantProfile,
        on_delete=models.CASCADE,
        verbose_name="Candidato"
    )
    
    # Componentes del score (0-100)
    skills_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Score de habilidades",
        help_text="Compatibilidad basada en skills requeridos vs skills del candidato"
    )
    
    experience_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Score de experiencia",
        help_text="Compatibilidad basada en años de experiencia"
    )
    
    location_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Score de ubicación",
        help_text="Compatibilidad basada en ubicación geográfica"
    )
    
    education_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Score de educación",
        help_text="Compatibilidad basada en nivel educativo"
    )
    
    salary_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Score salarial",
        help_text="Compatibilidad basada en expectativas salariales"
    )
    
    # Score total ponderado
    total_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Score total",
        help_text="Puntuación total de compatibilidad"
    )
    
    # Pesos utilizados en el cálculo (para auditoria)
    weights_used = models.JSONField(
        default=dict,
        verbose_name="Pesos utilizados",
        help_text="Pesos utilizados para calcular el score total"
    )
    
    # Metadatos adicionales del matching
    matching_details = models.JSONField(
        default=dict,
        verbose_name="Detalles del matching",
        help_text="Información detallada del análisis de compatibilidad"
    )
    
    # Información de confianza del match
    confidence_level = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Nivel de confianza",
        help_text="Qué tan confiable es este score basado en la cantidad de datos disponibles"
    )
    
    # Versión del algoritmo utilizada
    algorithm_version = models.CharField(
        max_length=20,
        default='1.0',
        verbose_name="Versión del algoritmo",
        help_text="Versión del algoritmo de matching utilizada"
    )
    
    # Timestamps
    calculated_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de cálculo"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización"
    )
    
    # Campos para optimización de consultas
    is_high_match = models.BooleanField(
        default=False,
        verbose_name="Match alto",
        help_text="True si el score total es >= 80"
    )
    is_recommended = models.BooleanField(
        default=False,
        verbose_name="Recomendado",
        help_text="True si el score total es >= 70"
    )
    
    class Meta:
        verbose_name = "Score de Matching"
        verbose_name_plural = "Scores de Matching"
        unique_together = ['job_post', 'applicant']
        ordering = ['-total_score', '-updated_at']
        indexes = [
            models.Index(fields=['job_post', '-total_score']),
            models.Index(fields=['applicant', '-total_score']),
            models.Index(fields=['total_score']),
            models.Index(fields=['is_high_match']),
            models.Index(fields=['is_recommended']),
            models.Index(fields=['calculated_at']),
        ]
    
    def __str__(self):
        return f"Match: {self.job_post.title} - {self.applicant.get_full_name()} ({self.total_score}%)"
    
    def save(self, *args, **kwargs):
        """Override save para calcular campos derivados"""
        # Actualizar campos de optimización
        self.is_high_match = self.total_score >= 80
        self.is_recommended = self.total_score >= 70
        
        super().save(*args, **kwargs)
    
    @property
    def match_quality(self):
        """Calidad del match basada en el score total"""
        score = float(self.total_score)
        
        if score >= 90:
            return 'excellent'
        elif score >= 80:
            return 'very_good'
        elif score >= 70:
            return 'good'
        elif score >= 60:
            return 'fair'
        elif score >= 50:
            return 'poor'
        else:
            return 'very_poor'
    
    @property
    def match_quality_display(self):
        """Versión en español de la calidad del match"""
        quality_map = {
            'excellent': 'Excelente',
            'very_good': 'Muy bueno',
            'good': 'Bueno',
            'fair': 'Regular',
            'poor': 'Bajo',
            'very_poor': 'Muy bajo'
        }
        return quality_map.get(self.match_quality, 'Desconocido')
    
    @property
    def score_breakdown(self):
        """Desglose detallado del score"""
        return {
            'skills': {
                'score': float(self.skills_score),
                'weight': self.weights_used.get('skills', 40),
                'contribution': float(self.skills_score) * (self.weights_used.get('skills', 40) / 100)
            },
            'experience': {
                'score': float(self.experience_score),
                'weight': self.weights_used.get('experience', 30),
                'contribution': float(self.experience_score) * (self.weights_used.get('experience', 30) / 100)
            },
            'location': {
                'score': float(self.location_score),
                'weight': self.weights_used.get('location', 20),
                'contribution': float(self.location_score) * (self.weights_used.get('location', 20) / 100)
            },
            'education': {
                'score': float(self.education_score),
                'weight': self.weights_used.get('education', 10),
                'contribution': float(self.education_score) * (self.weights_used.get('education', 10) / 100)
            },
            'salary': {
                'score': float(self.salary_score),
                'weight': self.weights_used.get('salary', 0),
                'contribution': float(self.salary_score) * (self.weights_used.get('salary', 0) / 100)
            }
        }
    
    def get_improvement_suggestions(self):
        """Generar sugerencias de mejora para el candidato"""
        suggestions = []
        
        # Sugerencias basadas en skills
        if self.skills_score < 70:
            suggestions.append({
                'category': 'skills',
                'priority': 'high',
                'message': 'Desarrollar habilidades técnicas faltantes',
                'impact': 'Alto impacto en el matching',
                'details': self.matching_details.get('missing_skills', [])
            })
        
        # Sugerencias basadas en experiencia
        if self.experience_score < 70:
            suggestions.append({
                'category': 'experience',
                'priority': 'medium',
                'message': 'Ganar más experiencia en el área',
                'impact': 'Impacto medio en el matching',
                'details': self.matching_details.get('experience_gap', {})
            })
        
        # Sugerencias basadas en ubicación
        if self.location_score < 50:
            suggestions.append({
                'category': 'location',
                'priority': 'low',
                'message': 'Considerar reubicación o trabajo remoto',
                'impact': 'Bajo impacto en el matching',
                'details': self.matching_details.get('location_mismatch', {})
            })
        
        return suggestions
    
    def get_strengths(self):
        """Obtener fortalezas del match"""
        strengths = []
        
        if self.skills_score >= 80:
            strengths.append({
                'category': 'skills',
                'message': 'Excelente alineación de habilidades técnicas',
                'score': float(self.skills_score)
            })
        
        if self.experience_score >= 80:
            strengths.append({
                'category': 'experience',
                'message': 'Experiencia muy alineada con los requisitos',
                'score': float(self.experience_score)
            })
        
        if self.location_score >= 80:
            strengths.append({
                'category': 'location',
                'message': 'Ubicación ideal para la posición',
                'score': float(self.location_score)
            })
        
        if self.education_score >= 80:
            strengths.append({
                'category': 'education',
                'message': 'Nivel educativo excepcional',
                'score': float(self.education_score)
            })
        
        return strengths
    
    @classmethod
    def get_top_matches_for_job(cls, job_post, limit=50):
        """Obtener los mejores matches para una vacante"""
        return cls.objects.filter(
            job_post=job_post
        ).select_related(
            'applicant__user'
        ).order_by('-total_score')[:limit]
    
    @classmethod
    def get_recommended_jobs_for_applicant(cls, applicant, limit=20):
        """Obtener vacantes recomendadas para un candidato"""
        return cls.objects.filter(
            applicant=applicant,
            is_recommended=True,
            job_post__status='approved',
            job_post__is_active=True
        ).select_related(
            'job_post__company'
        ).order_by('-total_score')[:limit]

class MatchingPreferences(models.Model):
    """Modelo para almacenar preferencias de matching por usuario/empresa"""
    
    # El propietario de las preferencias puede ser una empresa o un candidato
    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='matching_preferences',
        verbose_name="Empresa"
    )
    applicant = models.OneToOneField(
        ApplicantProfile,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='matching_preferences',
        verbose_name="Candidato"
    )
    
    # Pesos personalizados para el algoritmo de matching
    skills_weight = models.PositiveIntegerField(
        default=40,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Peso de habilidades (%)",
        help_text="Importancia de las habilidades en el matching"
    )
    
    experience_weight = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Peso de experiencia (%)",
        help_text="Importancia de la experiencia en el matching"
    )
    
    location_weight = models.PositiveIntegerField(
        default=20,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Peso de ubicación (%)",
        help_text="Importancia de la ubicación en el matching"
    )
    
    education_weight = models.PositiveIntegerField(
        default=10,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Peso de educación (%)",
        help_text="Importancia de la educación en el matching"
    )
    
    salary_weight = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Peso salarial (%)",
        help_text="Importancia del salario en el matching"
    )
    
    # Configuraciones específicas para empresas
    minimum_match_score = models.PositiveIntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Score mínimo de matching",
        help_text="Score mínimo para considerar un candidato como match"
    )
    
    prefer_overqualified = models.BooleanField(
        default=False,
        verbose_name="Preferir sobrecalificados",
        help_text="¿Preferir candidatos con más experiencia de la requerida?"
    )
    
    strict_location_matching = models.BooleanField(
        default=False,
        verbose_name="Matching estricto de ubicación",
        help_text="¿Requiere coincidencia exacta de ubicación?"
    )
    
    # Configuraciones específicas para candidatos
    willing_to_relocate = models.BooleanField(
        default=False,
        verbose_name="Dispuesto a reubicarse",
        help_text="¿El candidato está dispuesto a mudarse por trabajo?"
    )
    
    remote_work_only = models.BooleanField(
        default=False,
        verbose_name="Solo trabajo remoto",
        help_text="¿El candidato solo busca trabajo remoto?"
    )
    
    minimum_salary_expectation = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Expectativa salarial mínima",
        help_text="Salario mínimo esperado (en moneda local)"
    )
    
    # Configuraciones avanzadas
    auto_apply_threshold = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Umbral de postulación automática",
        help_text="Score mínimo para postulación automática (0 = deshabilitado)"
    )
    
    notification_threshold = models.PositiveIntegerField(
        default=70,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Umbral de notificación",
        help_text="Score mínimo para recibir notificaciones de nuevos matches"
    )
    
    # Metadatos
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización"
    )
    
    class Meta:
        verbose_name = "Preferencias de Matching"
        verbose_name_plural = "Preferencias de Matching"
        constraints = [
            models.CheckConstraint(
                check=models.Q(company__isnull=False) | models.Q(applicant__isnull=False),
                name='matching_preferences_owner_required'
            ),
            models.CheckConstraint(
                check=~(models.Q(company__isnull=False) & models.Q(applicant__isnull=False)),
                name='matching_preferences_single_owner'
            ),
        ]
    
    def __str__(self):
        if self.company:
            return f"Preferencias de {self.company.name}"
        elif self.applicant:
            return f"Preferencias de {self.applicant.get_full_name()}"
        return "Preferencias de Matching"
    
    def clean(self):
        """Validar que los pesos sumen 100%"""
        from django.core.exceptions import ValidationError
        
        total_weight = (
            self.skills_weight + 
            self.experience_weight + 
            self.location_weight + 
            self.education_weight + 
            self.salary_weight
        )
        
        if total_weight != 100:
            raise ValidationError(
                f"Los pesos deben sumar 100%. Suma actual: {total_weight}%"
            )
    
    def save(self, *args, **kwargs):
        """Override save para validar datos"""
        self.clean()
        super().save(*args, **kwargs)
    
    @property
    def weights_dict(self):
        """Diccionario con los pesos para usar en el algoritmo"""
        return {
            'skills': self.skills_weight,
            'experience': self.experience_weight,
            'location': self.location_weight,
            'education': self.education_weight,
            'salary': self.salary_weight,
        }
    
    @property
    def owner(self):
        """Propietario de las preferencias"""
        return self.company or self.applicant
    
    def reset_to_defaults(self):
        """Resetear a valores por defecto"""
        self.skills_weight = 40
        self.experience_weight = 30
        self.location_weight = 20
        self.education_weight = 10
        self.salary_weight = 0
        self.minimum_match_score = 50
        self.notification_threshold = 70
        self.save()

class MatchingStatistics(models.Model):
    """Modelo para almacenar estadísticas del sistema de matching"""
    
    # Período de las estadísticas
    date = models.DateField(
        verbose_name="Fecha",
        help_text="Fecha para la cual se calculan las estadísticas"
    )
    
    # Estadísticas generales
    total_matches_calculated = models.PositiveIntegerField(
        default=0,
        verbose_name="Total de matches calculados"
    )
    average_match_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Score promedio de matching"
    )
    
    # Distribución de scores
    excellent_matches = models.PositiveIntegerField(
        default=0,
        verbose_name="Matches excelentes (90-100%)"
    )
    good_matches = models.PositiveIntegerField(
        default=0,
        verbose_name="Matches buenos (70-89%)"
    )
    fair_matches = models.PositiveIntegerField(
        default=0,
        verbose_name="Matches regulares (50-69%)"
    )
    poor_matches = models.PositiveIntegerField(
        default=0,
        verbose_name="Matches pobres (<50%)"
    )
    
    # Efectividad del matching
    successful_applications = models.PositiveIntegerField(
        default=0,
        verbose_name="Postulaciones exitosas",
        help_text="Número de postulaciones que resultaron en contratación"
    )
    total_applications = models.PositiveIntegerField(
        default=0,
        verbose_name="Total de postulaciones"
    )
    average_application_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Score promedio de postulaciones"
    )
    
    # Métricas de performance del algoritmo
    algorithm_version = models.CharField(
        max_length=20,
        default='1.0',
        verbose_name="Versión del algoritmo"
    )
    calculation_time_avg = models.FloatField(
        default=0.0,
        verbose_name="Tiempo promedio de cálculo (segundos)"
    )
    
    # Metadatos
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )
    
    class Meta:
        verbose_name = "Estadísticas de Matching"
        verbose_name_plural = "Estadísticas de Matching"
        unique_together = ['date', 'algorithm_version']
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['algorithm_version']),
        ]
    
    def __str__(self):
        return f"Estadísticas {self.date} - Algoritmo {self.algorithm_version}"
    
    @property
    def success_rate(self):
        """Tasa de éxito del matching"""
        if self.total_applications == 0:
            return 0
        return round((self.successful_applications / self.total_applications) * 100, 2)
    
    @property
    def high_quality_matches_percentage(self):
        """Porcentaje de matches de alta calidad (>= 70%)"""
        total = self.excellent_matches + self.good_matches + self.fair_matches + self.poor_matches
        if total == 0:
            return 0
        high_quality = self.excellent_matches + self.good_matches
        return round((high_quality / total) * 100, 2)
    
    @classmethod
    def calculate_daily_stats(cls, date=None):
        """Calcular estadísticas para una fecha específica"""
        if date is None:
            date = timezone.now().date()
        
        # Obtener todos los matches del día
        matches = MatchScore.objects.filter(calculated_at__date=date)
        
        if not matches.exists():
            return None
        
        # Calcular estadísticas
        total_matches = matches.count()
        avg_score = matches.aggregate(models.Avg('total_score'))['total_score__avg'] or 0
        
        # Distribución de scores
        excellent = matches.filter(total_score__gte=90).count()
        good = matches.filter(total_score__gte=70, total_score__lt=90).count()
        fair = matches.filter(total_score__gte=50, total_score__lt=70).count()
        poor = matches.filter(total_score__lt=50).count()
        
        # Aplicaciones del día
        from jobs.models import Application
        applications = Application.objects.filter(applied_at__date=date)
        successful_apps = applications.filter(status='accepted').count()
        total_apps = applications.count()
        avg_app_score = applications.aggregate(
            models.Avg('match_score')
        )['match_score__avg'] or 0
        
        # Crear o actualizar estadísticas
        stats, created = cls.objects.update_or_create(
            date=date,
            algorithm_version='1.0',  # Versión actual
            defaults={
                'total_matches_calculated': total_matches,
                'average_match_score': avg_score,
                'excellent_matches': excellent,
                'good_matches': good,
                'fair_matches': fair,
                'poor_matches': poor,
                'successful_applications': successful_apps,
                'total_applications': total_apps,
                'average_application_score': avg_app_score,
            }
        )
        
        return stats

class MatchingAuditLog(models.Model):
    """Modelo para auditoría del sistema de matching"""
    
    ACTION_CHOICES = [
        ('calculate', 'Cálculo de match'),
        ('recalculate', 'Recálculo de match'),
        ('bulk_calculate', 'Cálculo masivo'),
        ('algorithm_update', 'Actualización de algoritmo'),
        ('preferences_update', 'Actualización de preferencias'),
        ('manual_adjustment', 'Ajuste manual'),
    ]
    
    # Información básica del evento
    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
        verbose_name="Acción realizada"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Usuario",
        help_text="Usuario que realizó la acción (si aplica)"
    )
    
    # Objetos afectados
    job_post = models.ForeignKey(
        JobPost,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Vacante afectada"
    )
    applicant = models.ForeignKey(
        ApplicantProfile,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Candidato afectado"
    )
    match_score = models.ForeignKey(
        MatchScore,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Score de matching afectado"
    )
    
    # Detalles del evento
    old_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Score anterior"
    )
    new_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Score nuevo"
    )
    
    algorithm_version = models.CharField(
        max_length=20,
        default='1.0',
        verbose_name="Versión del algoritmo utilizada"
    )
    
    execution_time = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Tiempo de ejecución (segundos)"
    )
    
    # Metadatos adicionales
    metadata = models.JSONField(
        default=dict,
        verbose_name="Metadatos adicionales",
        help_text="Información adicional sobre la acción realizada"
    )
    
    # Información de error (si aplica)
    error_message = models.TextField(
        blank=True,
        verbose_name="Mensaje de error",
        help_text="Descripción del error si la acción falló"
    )
    
    success = models.BooleanField(
        default=True,
        verbose_name="Acción exitosa"
    )
    
    # Timestamp
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha y hora"
    )
    
    class Meta:
        verbose_name = "Log de Auditoría de Matching"
        verbose_name_plural = "Logs de Auditoría de Matching"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['job_post', 'created_at']),
            models.Index(fields=['applicant', 'created_at']),
            models.Index(fields=['success', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_action_display()} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    @classmethod
    def log_match_calculation(cls, job_post, applicant, match_score, user=None, 
                            execution_time=None, algorithm_version='1.0', metadata=None):
        """Registrar un cálculo de match en el log"""
        return cls.objects.create(
            action='calculate',
            user=user,
            job_post=job_post,
            applicant=applicant,
            match_score=match_score,
            new_score=match_score.total_score if match_score else None,
            algorithm_version=algorithm_version,
            execution_time=execution_time,
            metadata=metadata or {},
            success=match_score is not None
        )
    
    @classmethod
    def log_bulk_calculation(cls, jobs_count, applicants_count, matches_created, 
                           user=None, execution_time=None, algorithm_version='1.0'):
        """Registrar un cálculo masivo en el log"""
        return cls.objects.create(
            action='bulk_calculate',
            user=user,
            algorithm_version=algorithm_version,
            execution_time=execution_time,
            metadata={
                'jobs_processed': jobs_count,
                'applicants_processed': applicants_count,
                'matches_created': matches_created,
            },
            success=True
        )
    
    @classmethod
    def log_error(cls, action, error_message, job_post=None, applicant=None, 
                  user=None, metadata=None):
        """Registrar un error en el log"""
        return cls.objects.create(
            action=action,
            user=user,
            job_post=job_post,
            applicant=applicant,
            error_message=error_message,
            metadata=metadata or {},
            success=False
        )
    
    @property
    def score_improvement(self):
        """Mejora en el score (si aplica)"""
        if self.old_score is not None and self.new_score is not None:
            return float(self.new_score) - float(self.old_score)
        return None
    
    @property
    def formatted_execution_time(self):
        """Tiempo de ejecución formateado"""
        if self.execution_time is not None:
            if self.execution_time < 1:
                return f"{self.execution_time * 1000:.0f}ms"
            else:
                return f"{self.execution_time:.2f}s"
        return "N/A"