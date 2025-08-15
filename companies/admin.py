# apps/companies/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Company, SavedCandidate, Interview


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'user_email', 'industry', 'size', 'location', 
        'is_verified', 'is_premium', 'is_public', 'created_at'
    ]
    list_filter = [
        'industry', 'size', 'is_verified', 'is_premium', 
        'is_public', 'created_at'
    ]
    search_fields = ['name', 'user__email', 'location', 'description']
    readonly_fields = [
        'user', 'slug', 'created_at', 'updated_at', 'last_active',
        'total_jobs_posted', 'total_hires', 'avg_time_to_hire',
        'profile_views', 'logo_preview'
    ]
    fieldsets = (
        ('Información Básica', {
            'fields': ('user', 'name', 'slug', 'description')
        }),
        ('Detalles de la Empresa', {
            'fields': ('industry', 'size', 'founded_year', 'employee_count')
        }),
        ('Información de Contacto', {
            'fields': ('website', 'location', 'address', 'phone')
        }),
        ('Branding', {
            'fields': ('logo', 'logo_preview', 'cover_image')
        }),
        ('Configuraciones', {
            'fields': (
                'is_public', 'is_verified', 'is_premium',
                'email_notifications', 'sms_notifications', 'weekly_digest'
            )
        }),
        ('Métricas', {
            'fields': (
                'total_jobs_posted', 'total_hires', 'avg_time_to_hire',
                'profile_views'
            ),
            'classes': ('collapse',)
        }),
        ('Información de Facturación', {
            'fields': ('billing_contact_name', 'billing_email', 'tax_id'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_active'),
            'classes': ('collapse',)
        })
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email del Usuario'
    user_email.admin_order_field = 'user__email'
    
    def logo_preview(self, obj):
        if obj.logo:
            return format_html(
                '<img src="{}" width="100" height="100" style="object-fit: cover; border-radius: 8px;" />',
                obj.logo.url
            )
        return "Sin logo"
    logo_preview.short_description = 'Vista Previa del Logo'
    
    actions = ['make_verified', 'make_unverified', 'make_premium', 'make_regular']
    
    def make_verified(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} empresas marcadas como verificadas.')
    make_verified.short_description = 'Marcar como verificadas'
    
    def make_unverified(self, request, queryset):
        updated = queryset.update(is_verified=False)
        self.message_user(request, f'{updated} empresas marcadas como no verificadas.')
    make_unverified.short_description = 'Marcar como no verificadas'
    
    def make_premium(self, request, queryset):
        updated = queryset.update(is_premium=True)
        self.message_user(request, f'{updated} empresas marcadas como premium.')
    make_premium.short_description = 'Marcar como premium'
    
    def make_regular(self, request, queryset):
        updated = queryset.update(is_premium=False)
        self.message_user(request, f'{updated} empresas marcadas como regulares.')
    make_regular.short_description = 'Marcar como regulares'


@admin.register(SavedCandidate)
class SavedCandidateAdmin(admin.ModelAdmin):
    list_display = [
        'company', 'applicant_name', 'status', 'rating', 
        'saved_at', 'last_contacted'
    ]
    list_filter = ['status', 'rating', 'saved_at', 'last_contacted']
    search_fields = [
        'company__name', 'applicant__first_name', 
        'applicant__last_name', 'applicant__user__email'
    ]
    readonly_fields = ['saved_at', 'updated_at']
    raw_id_fields = ['company', 'applicant']
    
    fieldsets = (
        ('Información Principal', {
            'fields': ('company', 'applicant', 'status', 'rating')
        }),
        ('Detalles', {
            'fields': ('notes', 'tags')
        }),
        ('Timestamps', {
            'fields': ('saved_at', 'last_contacted', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def applicant_name(self, obj):
        return obj.applicant.get_full_name()
    applicant_name.short_description = 'Nombre del Candidato'
    applicant_name.admin_order_field = 'applicant__first_name'


@admin.register(Interview)
class InterviewAdmin(admin.ModelAdmin):
    list_display = [
        'applicant_name', 'company_name', 'interview_type', 
        'status', 'scheduled_date', 'interviewer_name'
    ]
    list_filter = [
        'interview_type', 'status', 'scheduled_date', 
        'created_at', 'application__job_post__company'
    ]
    search_fields = [
        'application__applicant__first_name',
        'application__applicant__last_name',
        'application__job_post__title',
        'application__job_post__company__name',
        'interviewer_name', 'interviewer_email'
    ]
    readonly_fields = ['created_at', 'updated_at', 'completed_at']
    raw_id_fields = ['application']
    date_hierarchy = 'scheduled_date'
    
    fieldsets = (
        ('Información de la Entrevista', {
            'fields': (
                'application', 'interview_type', 'status',
                'scheduled_date', 'duration_minutes', 'timezone'
            )
        }),
        ('Entrevistador', {
            'fields': (
                'interviewer_name', 'interviewer_email', 'interviewer_title'
            )
        }),
        ('Detalles', {
            'fields': ('location', 'instructions')
        }),
        ('Resultados', {
            'fields': ('notes', 'score', 'recommendation'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        })
    )
    
    def applicant_name(self, obj):
        return obj.applicant.get_full_name()
    applicant_name.short_description = 'Candidato'
    applicant_name.admin_order_field = 'application__applicant__first_name'
    
    def company_name(self, obj):
        return obj.company.name
    company_name.short_description = 'Empresa'
    company_name.admin_order_field = 'application__job_post__company__name'
    
    actions = ['mark_completed', 'mark_cancelled']
    
    def mark_completed(self, request, queryset):
        updated = queryset.update(status='completed')
        self.message_user(request, f'{updated} entrevistas marcadas como completadas.')
    mark_completed.short_description = 'Marcar como completadas'
    
    def mark_cancelled(self, request, queryset):
        updated = queryset.update(status='cancelled')
        self.message_user(request, f'{updated} entrevistas marcadas como canceladas.')
    mark_cancelled.short_description = 'Marcar como canceladas'


# Configuración adicional para el admin
admin.site.site_header = "Meraki - Administración"
admin.site.site_title = "Meraki Admin"
admin.site.index_title = "Panel de Administración"