# apps/applicants/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Avg
from django.utils import timezone
from datetime import timedelta

from .models import ApplicantProfile, ApplicantSkill, JobAlert
from jobs.models import Application

class ApplicantSkillInline(admin.TabularInline):
    """Inline para mostrar habilidades del postulante"""
    model = ApplicantSkill
    extra = 0
    fields = ['skill', 'proficiency_level', 'years_experience']
    readonly_fields = []
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('skill')

@admin.register(ApplicantProfile)
class ApplicantProfileAdmin(admin.ModelAdmin):
    list_display = [
        'full_name_display', 'user_email', 'current_position', 'years_experience', 
        'education_level', 'profile_score_display', 'applications_count', 
        'skills_count', 'cv_status', 'created_at'
    ]
    
    list_filter = [
        'education_level', 'years_experience', 'created_at'
    ]
    
    search_fields = [
        'first_name', 'last_name', 'user__username', 'user__email', 
        'current_position', 'summary'
    ]
    
    readonly_fields = [
        'profile_score', 'created_at', 'updated_at',
        'completion_percentage_display', 'age_display'
    ]
    
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Información del Usuario', {
            'fields': ('user',)
        }),
        ('Información Personal', {
            'fields': (
                'first_name', 'last_name', 'birth_date', 'age_display',
                'summary'
            )
        }),
        ('Información Profesional', {
            'fields': (
                'current_position', 'years_experience', 'education_level',
                'desired_salary_min', 'desired_salary_max', 'willing_to_relocate'
            )
        }),
        ('Archivos', {
            'fields': ('cv_file', 'portfolio_file')
        }),
        ('Configuraciones', {
            'fields': ('profile_visible', 'allow_contact')
        }),
        ('Métricas', {
            'fields': (
                'profile_score', 'completion_percentage_display', 
                'profile_views', 'created_at', 'updated_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [ApplicantSkillInline]
    
    # Acciones personalizadas
    actions = ['recalculate_profile_scores', 'export_selected_profiles', 'mark_as_featured']
    
    def full_name_display(self, obj):
        """Muestra el nombre completo con enlace al perfil"""
        full_name = obj.full_name
        if obj.cv_file:
            return format_html(
                '<strong>{}</strong> <a href="{}" target="_blank" title="Ver CV">📄</a>',
                full_name,
                obj.cv_file.url
            )
        return format_html('<strong>{}</strong>', full_name)
    full_name_display.short_description = 'Nombre Completo'
    
    def user_email(self, obj):
        """Muestra el email del usuario"""
        return obj.user.email
    user_email.short_description = 'Email'
    
    def profile_score_display(self, obj):
        """Muestra la puntuación del perfil con colores"""
        score = obj.profile_score
        if score >= 80:
            color = 'green'
        elif score >= 60:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}/100</span>',
            color,
            score
        )
    profile_score_display.short_description = 'Puntuación'
    
    def applications_count(self, obj):
        """Cuenta las postulaciones del usuario"""
        count = Application.objects.filter(applicant=obj).count()
        if count > 0:
            url = reverse('admin:jobs_application_changelist') + f'?applicant__id__exact={obj.id}'
            return format_html('<a href="{}">{} postulaciones</a>', url, count)
        return '0 postulaciones'
    applications_count.short_description = 'Postulaciones'
    
    def skills_count(self, obj):
        """Cuenta las habilidades del postulante"""
        count = obj.skills.count()
        return f"{count} habilidades"
    skills_count.short_description = 'Habilidades'
    
    def cv_status(self, obj):
        """Muestra el estado del CV"""
        if obj.cv_file:
            return format_html(
                '<span style="color: green;">✓ Subido</span> '
                '<a href="{}" target="_blank">Ver</a>',
                obj.cv_file.url
            )
        return format_html('<span style="color: red;">✗ No subido</span>')
    cv_status.short_description = 'CV'
    
    def completion_percentage_display(self, obj):
        """Muestra el porcentaje de completación del perfil"""
        percentage = obj.completion_percentage
        return f"{percentage:.1f}%"
    completion_percentage_display.short_description = 'Completación del Perfil'
    
    def age_display(self, obj):
        """Muestra la edad del postulante"""
        age = obj.age
        return f"{age} años" if age else "No especificado"
    age_display.short_description = 'Edad'
    
    def get_queryset(self, request):
        """Optimiza las consultas"""
        return super().get_queryset(request).select_related('user').prefetch_related('skills')
    
    # Acciones personalizadas
    def recalculate_profile_scores(self, request, queryset):
        """Recalcula las puntuaciones de los perfiles seleccionados"""
        updated = 0
        for profile in queryset:
            profile.calculate_profile_score()
            updated += 1
        
        self.message_user(
            request,
            f'Se recalcularon las puntuaciones de {updated} perfiles.'
        )
    recalculate_profile_scores.short_description = "Recalcular puntuaciones de perfil"
    
    def export_selected_profiles(self, request, queryset):
        """Exporta los perfiles seleccionados a CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="perfiles_postulantes.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Nombre', 'Email', 'Posición Actual', 'Años Experiencia',
            'Nivel Educativo', 'Puntuación', 'Fecha Creación'
        ])
        
        for profile in queryset:
            writer.writerow([
                profile.full_name,
                profile.user.email,
                profile.current_position,
                profile.years_experience,
                profile.get_education_level_display(),
                profile.profile_score,
                profile.created_at.strftime('%Y-%m-%d')
            ])
        
        return response
    export_selected_profiles.short_description = "Exportar perfiles seleccionados"
    
    def mark_as_featured(self, request, queryset):
        """Marcar perfiles como destacados (requiere campo featured en el modelo)"""
        # Esta acción requeriría agregar un campo 'featured' al modelo
        self.message_user(request, "Funcionalidad de destacados no implementada aún.")
    mark_as_featured.short_description = "Marcar como destacados"

@admin.register(ApplicantSkill)
class ApplicantSkillAdmin(admin.ModelAdmin):
    list_display = [
        'applicant_name', 'skill_name', 'skill_category', 
        'proficiency_level_display', 'years_experience'
    ]
    
    list_filter = [
        'proficiency_level', 'skill__category', 'years_experience'
    ]
    
    search_fields = [
        'applicant__first_name', 'applicant__last_name', 
        'applicant__user__username', 'skill__name'
    ]
    
    ordering = ['applicant', 'skill__category', 'skill__name']
    
    def applicant_name(self, obj):
        """Muestra el nombre del postulante"""
        return obj.applicant.full_name
    applicant_name.short_description = 'Postulante'
    
    def skill_name(self, obj):
        """Muestra el nombre de la habilidad"""
        return obj.skill.name
    skill_name.short_description = 'Habilidad'
    
    def skill_category(self, obj):
        """Muestra la categoría de la habilidad"""
        return obj.skill.category
    skill_category.short_description = 'Categoría'
    
    def proficiency_level_display(self, obj):
        """Muestra el nivel de competencia con colores"""
        level_colors = {
            1: '#ff6b6b',  # Rojo para básico
            2: '#ffa726',  # Naranja para intermedio
            3: '#66bb6a',  # Verde para avanzado
            4: '#42a5f5',  # Azul para experto
        }
        
        color = level_colors.get(obj.proficiency_level, '#666')
        level_text = obj.get_proficiency_level_display()
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            level_text
        )
    proficiency_level_display.short_description = 'Nivel'
    
    def get_queryset(self, request):
        """Optimiza las consultas"""
        return super().get_queryset(request).select_related('applicant', 'skill')

# Registro de modelos relacionados de otras apps (si no están registrados)
try:
    from jobs.models import JobAlert
    
    @admin.register(JobAlert)
    class JobAlertAdmin(admin.ModelAdmin):
        list_display = [
            'name', 'applicant_name', 'keywords_display', 'location', 
            'is_active', 'created_at'
        ]
        
        list_filter = ['is_active', 'employment_type', 'experience_level', 'created_at']
        
        search_fields = [
            'name', 'keywords', 'location', 'applicant__first_name', 
            'applicant__last_name', 'applicant__user__username'
        ]
        
        ordering = ['-created_at']
        date_hierarchy = 'created_at'
        
        fieldsets = (
            ('Información Básica', {
                'fields': ('applicant', 'name', 'is_active')
            }),
            ('Criterios de Búsqueda', {
                'fields': (
                    'keywords', 'location', 'employment_type', 
                    'experience_level', 'min_salary', 'max_salary'
                )
            }),
            ('Fechas', {
                'fields': ('created_at', 'updated_at'),
                'classes': ('collapse',)
            }),
        )
        
        readonly_fields = ['created_at', 'updated_at']
        
        def applicant_name(self, obj):
            """Muestra el nombre del postulante"""
            return obj.applicant.full_name
        applicant_name.short_description = 'Postulante'
        
        def keywords_display(self, obj):
            """Muestra las palabras clave truncadas"""
            if len(obj.keywords) > 50:
                return obj.keywords[:50] + "..."
            return obj.keywords
        keywords_display.short_description = 'Palabras Clave'
        
        def get_queryset(self, request):
            """Optimiza las consultas"""
            return super().get_queryset(request).select_related('applicant')

except ImportError:
    # JobAlert no está disponible
    pass

# Personalización adicional del admin
admin.site.site_header = "Meraki - Administración de Postulantes"
admin.site.site_title = "Meraki Admin"
admin.site.index_title = "Panel de Administración de Postulantes"

# Filtros personalizados
class ProfileScoreFilter(admin.SimpleListFilter):
    """Filtro personalizado para puntuación del perfil"""
    title = 'Puntuación del Perfil'
    parameter_name = 'profile_score_range'
    
    def lookups(self, request, model_admin):
        return (
            ('high', 'Alta (80-100)'),
            ('medium', 'Media (60-79)'),
            ('low', 'Baja (0-59)'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'high':
            return queryset.filter(profile_score__gte=80)
        if self.value() == 'medium':
            return queryset.filter(profile_score__gte=60, profile_score__lt=80)
        if self.value() == 'low':
            return queryset.filter(profile_score__lt=60)

class ExperienceRangeFilter(admin.SimpleListFilter):
    """Filtro personalizado para rango de experiencia"""
    title = 'Rango de Experiencia'
    parameter_name = 'experience_range'
    
    def lookups(self, request, model_admin):
        return (
            ('junior', 'Junior (0-2 años)'),
            ('mid', 'Mid (3-7 años)'),
            ('senior', 'Senior (8-15 años)'),
            ('expert', 'Experto (15+ años)'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'junior':
            return queryset.filter(years_experience__lte=2)
        if self.value() == 'mid':
            return queryset.filter(years_experience__gte=3, years_experience__lte=7)
        if self.value() == 'senior':
            return queryset.filter(years_experience__gte=8, years_experience__lte=15)
        if self.value() == 'expert':
            return queryset.filter(years_experience__gte=15)

class RecentActivityFilter(admin.SimpleListFilter):
    """Filtro para actividad reciente"""
    title = 'Actividad Reciente'
    parameter_name = 'recent_activity'
    
    def lookups(self, request, model_admin):
        return (
            ('week', 'Última semana'),
            ('month', 'Último mes'),
            ('quarter', 'Último trimestre'),
        )
    
    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'week':
            return queryset.filter(updated_at__gte=now - timedelta(days=7))
        if self.value() == 'month':
            return queryset.filter(updated_at__gte=now - timedelta(days=30))
        if self.value() == 'quarter':
            return queryset.filter(updated_at__gte=now - timedelta(days=90))

# Agregar los filtros personalizados al admin de ApplicantProfile
ApplicantProfileAdmin.list_filter = [
    ProfileScoreFilter,
    ExperienceRangeFilter,
    RecentActivityFilter,
    'education_level',
    'created_at'
]

# Configuración adicional para el admin
class ApplicantProfileAdminConfig:
    """Configuraciones adicionales para el admin de perfiles"""
    
    @staticmethod
    def get_profile_stats():
        """Obtiene estadísticas de perfiles para el dashboard"""
        total_profiles = ApplicantProfile.objects.count()
        
        stats = {
            'total': total_profiles,
            'with_cv': ApplicantProfile.objects.exclude(cv_file='').count(),
            'high_score': ApplicantProfile.objects.filter(profile_score__gte=80).count(),
            'recent': ApplicantProfile.objects.filter(
                created_at__gte=timezone.now() - timedelta(days=30)
            ).count(),
        }
        
        return stats

# Funciones auxiliares para el admin
def bulk_recalculate_scores():
    """Función para recalcular todas las puntuaciones de perfiles"""
    profiles = ApplicantProfile.objects.all()
    updated = 0
    
    for profile in profiles:
        profile.calculate_profile_score()
        updated += 1
    
    return updated

def get_top_skills_report():
    """Genera un reporte de las habilidades más populares"""
    from django.db.models import Count
    
    top_skills = ApplicantSkill.objects.values(
        'skill__name', 'skill__category'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:20]
    
    return top_skills

def get_experience_distribution():
    """Obtiene la distribución de experiencia de los postulantes"""
    ranges = {
        'junior': ApplicantProfile.objects.filter(years_experience__lte=2).count(),
        'mid': ApplicantProfile.objects.filter(
            years_experience__gte=3, years_experience__lte=7
        ).count(),
        'senior': ApplicantProfile.objects.filter(
            years_experience__gte=8, years_experience__lte=15
        ).count(),
        'expert': ApplicantProfile.objects.filter(years_experience__gte=15).count(),
    }
    
    return ranges