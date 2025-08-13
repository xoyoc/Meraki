# apps/jobs/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count
from django.utils import timezone
from django import forms
from .models import JobPost, Application, SavedJob, Skill, JobPostSkill
from .admin_forms import JobPostAdminForm

@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'job_count')
    list_filter = ('category',)
    search_fields = ('name', 'category')
    ordering = ('category', 'name')
    
    def job_count(self, obj):
        count = JobPost.objects.filter(skills_required=obj).count()
        return count
    job_count.short_description = 'Jobs que lo requieren'

class JobPostSkillInline(admin.TabularInline):
    model = JobPostSkill
    extra = 1
    autocomplete_fields = ['skill']

@admin.register(JobPost)
class JobPostAdmin(admin.ModelAdmin):
    form = JobPostAdminForm  # Usar el formulario personalizado
    list_display = (
        'title', 'company', 'status_badge', 'experience_level', 
        'location', 'applications_count', 'created_at', 'deadline'
    )
    list_filter = (
        'status', 'experience_level', 'is_active', 
        'created_at', 'deadline'
    )
    search_fields = ('title', 'company__name', 'location', 'description')
    readonly_fields = ('created_at', 'updated_at', 'approved_by', 'approved_at')
    inlines = [JobPostSkillInline]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('company', 'title', 'status')
        }),
        ('Descripción', {
            'fields': ('description', 'requirements'),
            'classes': ('wide',)
        }),
        ('Detalles del Empleo', {
            'fields': (
                'experience_level', 'location', 
                ('salary_min', 'salary_max'), 
                'deadline', 'is_active'
            )
        }),
        ('Aprobación', {
            'fields': ('approved_by', 'approved_at'),
            'classes': ('collapse',)
        }),
        ('Metadatos', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['approve_jobs', 'reject_jobs', 'activate_jobs', 'deactivate_jobs']
    
    def status_badge(self, obj):
        colors = {
            'draft': 'gray',
            'pending': 'orange', 
            'approved': 'green',
            'rejected': 'red',
            'closed': 'blue'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Estado'
    
    def applications_count(self, obj):
        count = obj.applications.count()
        if count > 0:
            url = reverse('admin:jobs_application_changelist') + f'?job_post__id__exact={obj.id}'
            return format_html('<a href="{}">{} postulaciones</a>', url, count)
        return '0 postulaciones'
    applications_count.short_description = 'Postulaciones'
    
    def approve_jobs(self, request, queryset):
        updated = queryset.filter(status='pending').update(
            status='approved',
            approved_by=request.user,
            approved_at=timezone.now()
        )
        self.message_user(request, f'{updated} trabajos aprobados exitosamente.')
    approve_jobs.short_description = 'Aprobar trabajos seleccionados'
    
    def reject_jobs(self, request, queryset):
        updated = queryset.filter(status='pending').update(status='rejected')
        self.message_user(request, f'{updated} trabajos rechazados.')
    reject_jobs.short_description = 'Rechazar trabajos seleccionados'
    
    def activate_jobs(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} trabajos activados.')
    activate_jobs.short_description = 'Activar trabajos seleccionados'
    
    def deactivate_jobs(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} trabajos desactivados.')
    deactivate_jobs.short_description = 'Desactivar trabajos seleccionados'

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = (
        'applicant_name', 'job_title', 'company_name', 
        'status_badge', 'match_score', 'applied_at'
    )
    list_filter = (
        'status', 'applied_at', 'job_post__company',
        'job_post__experience_level'
    )
    search_fields = (
        'applicant__user__first_name', 'applicant__user__last_name',
        'applicant__user__email', 'job_post__title', 
        'job_post__company__name'
    )
    readonly_fields = ('applied_at', 'updated_at', 'match_score')
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('job_post', 'applicant', 'status')
        }),
        ('Aplicación', {
            'fields': ('cover_letter', 'match_score'),
            'classes': ('wide',)
        }),
        ('Metadatos', {
            'fields': ('applied_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['mark_as_reviewing', 'mark_as_shortlisted', 'mark_as_rejected']
    
    def applicant_name(self, obj):
        name = obj.applicant.user.get_full_name()
        url = reverse('admin:applicants_applicantprofile_change', args=[obj.applicant.pk])
        return format_html('<a href="{}">{}</a>', url, name or obj.applicant.user.email)
    applicant_name.short_description = 'Postulante'
    
    def job_title(self, obj):
        url = reverse('admin:jobs_jobpost_change', args=[obj.job_post.pk])
        return format_html('<a href="{}">{}</a>', url, obj.job_post.title)
    job_title.short_description = 'Trabajo'
    
    def company_name(self, obj):
        return obj.job_post.company.name
    company_name.short_description = 'Empresa'
    
    def status_badge(self, obj):
        colors = {
            'applied': 'blue',
            'reviewing': 'orange',
            'shortlisted': 'purple',
            'interviewed': 'teal',
            'accepted': 'green',
            'rejected': 'red',
            'withdrawn': 'gray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Estado'
    
    def mark_as_reviewing(self, request, queryset):
        updated = queryset.update(status='reviewing')
        self.message_user(request, f'{updated} aplicaciones marcadas como en revisión.')
    mark_as_reviewing.short_description = 'Marcar como en revisión'
    
    def mark_as_shortlisted(self, request, queryset):
        updated = queryset.update(status='shortlisted')
        self.message_user(request, f'{updated} aplicaciones preseleccionadas.')
    mark_as_shortlisted.short_description = 'Preseleccionar'
    
    def mark_as_rejected(self, request, queryset):
        updated = queryset.update(status='rejected')
        self.message_user(request, f'{updated} aplicaciones rechazadas.')
    mark_as_rejected.short_description = 'Rechazar'

@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin):
    list_display = (
        'applicant_name', 'job_title', 'company_name', 
        'saved_at', 'is_still_active_display'
    )
    list_filter = ('saved_at', 'job_post__company', 'job_post__status')
    search_fields = (
        'applicant__user__first_name', 'applicant__user__last_name',
        'job_post__title', 'job_post__company__name'
    )
    readonly_fields = ('saved_at',)
    
    def applicant_name(self, obj):
        name = obj.applicant.user.get_full_name()
        return name or obj.applicant.user.email
    applicant_name.short_description = 'Postulante'
    
    def job_title(self, obj):
        url = reverse('admin:jobs_jobpost_change', args=[obj.job_post.pk])
        return format_html('<a href="{}">{}</a>', url, obj.job_post.title)
    job_title.short_description = 'Trabajo'
    
    def company_name(self, obj):
        return obj.job_post.company.name
    company_name.short_description = 'Empresa'
    
    def is_still_active_display(self, obj):
        if obj.is_still_active:
            return format_html('<span style="color: green;">✓ Activa</span>')
        else:
            return format_html('<span style="color: red;">✗ Inactiva</span>')
    is_still_active_display.short_description = 'Estado de la Vacante'

# Configuración adicional del admin
admin.site.site_header = "Meraki Admin"
admin.site.site_title = "Meraki Admin Portal"
admin.site.index_title = "Bienvenido al Portal de Administración de Meraki"
