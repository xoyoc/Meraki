# apps/jobs/admin_forms.py
from django import forms
from django.db import models
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse
from datetime import datetime, timedelta
import json

from .models import JobPost, Application, Skill, JobPostSkill, SavedJob
from .validators import (
    validate_job_title, validate_description_length, 
    validate_requirements_length, validate_job_deadline,
    validate_salary_range
)

class JobPostAdminForm(forms.ModelForm):
    """Formulario personalizado para JobPost en el admin"""
    
    # Campo para mostrar estadísticas del trabajo
    stats_display = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'readonly': True,
            'rows': 4,
            'style': 'background-color: #f8f9fa; border: 1px solid #dee2e6;'
        }),
        help_text="Estadísticas del trabajo (solo lectura)"
    )
    
    # Campo para notas administrativas
    admin_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Notas internas para el equipo administrativo...'
        }),
        help_text="Notas internas que no son visibles para la empresa"
    )
    
    # Campo para motivo de rechazo
    rejection_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Explica por qué se rechaza esta vacante...'
        }),
        help_text="Motivo del rechazo (se enviará a la empresa si se rechaza)"
    )
    
    # Skills con widget mejorado
    skills_required = forms.ModelMultipleChoiceField(
        queryset=Skill.objects.all(),
        widget=admin.widgets.FilteredSelectMultiple("Skills", is_stacked=False),
        required=False,
        help_text="Selecciona los skills requeridos para este puesto"
    )
    
    class Meta:
        model = JobPost
        fields = '__all__'
        widgets = {
            'title': forms.TextInput(attrs={
                'size': 80,
                'placeholder': 'Título específico y descriptivo del puesto'
            }),
            'description': forms.Textarea(attrs={
                'rows': 10,
                'cols': 80,
                'placeholder': 'Descripción detallada del puesto, responsabilidades y beneficios...'
            }),
            'requirements': forms.Textarea(attrs={
                'rows': 8,
                'cols': 80,
                'placeholder': 'Requisitos técnicos, experiencia y cualificaciones necesarias...'
            }),
            'location': forms.TextInput(attrs={
                'size': 50,
                'placeholder': 'ej. Ciudad de México, Remoto, Híbrido'
            }),
            'salary_min': forms.NumberInput(attrs={
                'min': 0,
                'step': 1000,
                'placeholder': '30000'
            }),
            'salary_max': forms.NumberInput(attrs={
                'min': 0,
                'step': 1000,
                'placeholder': '50000'
            }),
            'deadline': forms.DateTimeInput(attrs={
                'type': 'datetime-local'
            }),
            'status': forms.Select(attrs={
                'style': 'width: 200px;'
            }),
            'experience_level': forms.Select(attrs={
                'style': 'width: 200px;'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Personalizar campos según el estado del objeto
        if self.instance and self.instance.pk:
            self.setup_existing_job_fields()
        else:
            self.setup_new_job_fields()
        
        # Configurar queryset de skills ordenado
        self.fields['skills_required'].queryset = Skill.objects.all().order_by('category', 'name')
        
        # Configurar campos de solo lectura para ciertos usuarios
        self.setup_readonly_fields()
    
    def setup_existing_job_fields(self):
        """Configurar campos para trabajos existentes"""
        job = self.instance
        
        # Mostrar estadísticas
        stats_text = self.get_job_stats(job)
        self.fields['stats_display'].initial = stats_text
        
        # Configurar campo de rechazo según el estado
        if job.status == 'rejected' and job.rejection_reason:
            self.fields['rejection_reason'].initial = job.rejection_reason
        
        # Deshabilitar ciertos campos si el trabajo está cerrado
        if job.status == 'closed':
            readonly_fields = ['title', 'description', 'requirements', 'deadline']
            for field in readonly_fields:
                if field in self.fields:
                    self.fields[field].widget.attrs['readonly'] = True
                    self.fields[field].help_text += " (Solo lectura: trabajo cerrado)"
        
        # Agregar links útiles
        self.add_admin_links(job)
    
    def setup_new_job_fields(self):
        """Configurar campos para nuevos trabajos"""
        # Ocultar campo de estadísticas para nuevos trabajos
        self.fields['stats_display'].widget = forms.HiddenInput()
        
        # Establecer valores por defecto
        tomorrow = timezone.now() + timedelta(days=30)
        self.fields['deadline'].initial = tomorrow
        self.fields['status'].initial = 'pending'
    
    def setup_readonly_fields(self):
        """Configurar campos de solo lectura según permisos"""
        # Los campos de auditoría siempre son de solo lectura
        readonly_fields = ['created_at', 'updated_at', 'approved_at', 'views_count']
        
        for field in readonly_fields:
            if field in self.fields:
                self.fields[field].widget.attrs['readonly'] = True
    
    def get_job_stats(self, job):
        """Generar estadísticas del trabajo"""
        if not job.pk:
            return "Estadísticas disponibles después de guardar"
        
        stats = []
        stats.append(f"📊 ESTADÍSTICAS DEL TRABAJO")
        stats.append(f"{'='*50}")
        stats.append(f"• Postulaciones totales: {job.applications.count()}")
        stats.append(f"• Postulaciones pendientes: {job.applications.filter(status='applied').count()}")
        stats.append(f"• Preseleccionados: {job.applications.filter(status='shortlisted').count()}")
        stats.append(f"• Rechazados: {job.applications.filter(status='rejected').count()}")
        stats.append(f"• Visualizaciones: {job.views_count}")
        stats.append(f"• Guardado por: {job.saved_by.count()} usuarios")
        stats.append(f"• Días restantes: {job.days_until_deadline}")
        stats.append(f"• Skills requeridos: {job.skills_required.count()}")
        
        if job.applications.exists():
            avg_score = job.applications.aggregate(avg_score=models.Avg('match_score'))['avg_score']
            stats.append(f"• Match score promedio: {avg_score:.1f}%" if avg_score else "• Match score promedio: N/A")
        
        stats.append(f"")
        stats.append(f"📅 FECHAS IMPORTANTES")
        stats.append(f"{'='*50}")
        stats.append(f"• Creado: {job.created_at.strftime('%d/%m/%Y %H:%M')}")
        stats.append(f"• Última actualización: {job.updated_at.strftime('%d/%m/%Y %H:%M')}")
        if job.approved_at:
            stats.append(f"• Aprobado: {job.approved_at.strftime('%d/%m/%Y %H:%M')}")
        stats.append(f"• Fecha límite: {job.deadline.strftime('%d/%m/%Y %H:%M')}")
        
        return "\n".join(stats)
    
    def add_admin_links(self, job):
        """Agregar links útiles en los help_text"""
        if job.pk:
            # Link para ver postulaciones
            if job.applications.exists():
                app_url = reverse('admin:jobs_application_changelist') + f'?job_post__id__exact={job.pk}'
                self.fields['stats_display'].help_text += f' | <a href="{app_url}" target="_blank">Ver postulaciones</a>'
            
            # Link para ver en el sitio público
            if job.status == 'approved':
                try:
                    public_url = reverse('jobs:job_detail', kwargs={'pk': job.pk})
                    self.fields['stats_display'].help_text += f' | <a href="{public_url}" target="_blank">Ver en sitio</a>'
                except:
                    pass
    
    def clean_title(self):
        title = self.cleaned_data.get('title')
        if title:
            title = title.strip()
            validate_job_title(title)
            
            # Verificar duplicados para la misma empresa
            if self.instance and self.instance.company:
                existing = JobPost.objects.filter(
                    company=self.instance.company,
                    title__iexact=title,
                    status__in=['pending', 'approved']
                )
                if self.instance.pk:
                    existing = existing.exclude(pk=self.instance.pk)
                
                if existing.exists():
                    raise ValidationError(
                        f"La empresa ya tiene una vacante activa con el título '{title}'. "
                        "Considera usar un título más específico."
                    )
        
        return title
    
    def clean_description(self):
        description = self.cleaned_data.get('description')
        if description:
            description = description.strip()
            validate_description_length(description)
        return description
    
    def clean_requirements(self):
        requirements = self.cleaned_data.get('requirements')
        if requirements:
            requirements = requirements.strip()
            validate_requirements_length(requirements)
        return requirements
    
    def clean_deadline(self):
        deadline = self.cleaned_data.get('deadline')
        if deadline:
            validate_job_deadline(deadline)
            
            # Para trabajos existentes aprobados, permitir fechas actuales si ya pasaron
            if self.instance and self.instance.pk and self.instance.status == 'approved':
                if deadline < timezone.now():
                    raise ValidationError(
                        "No puedes establecer una fecha límite en el pasado para un trabajo aprobado."
                    )
        
        return deadline
    
    def clean_rejection_reason(self):
        rejection_reason = self.cleaned_data.get('rejection_reason', '').strip()
        status = self.cleaned_data.get('status')
        
        # Requerir motivo si se está rechazando
        if status == 'rejected' and not rejection_reason:
            raise ValidationError("Debes proporcionar un motivo para rechazar esta vacante.")
        
        return rejection_reason
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validar rango salarial
        salary_min = cleaned_data.get('salary_min')
        salary_max = cleaned_data.get('salary_max')
        
        try:
            validate_salary_range(salary_min, salary_max)
        except ValidationError as e:
            if hasattr(e, 'message_dict'):
                for field, messages in e.message_dict.items():
                    self.add_error(field, messages)
            else:
                self.add_error(None, e.message)
        
        # Validar cambios de estado
        status = cleaned_data.get('status')
        if self.instance and self.instance.pk:
            old_status = self.instance.status
            self.validate_status_change(old_status, status)
        
        # Validar skills
        skills = cleaned_data.get('skills_required')
        if skills and skills.count() > 20:
            self.add_error('skills_required', 'No puedes seleccionar más de 20 skills.')
        
        return cleaned_data
    
    def validate_status_change(self, old_status, new_status):
        """Validar cambios de estado permitidos"""
        if old_status == new_status:
            return
        
        # Definir transiciones válidas
        valid_transitions = {
            'draft': ['pending', 'rejected'],
            'pending': ['approved', 'rejected'],
            'approved': ['closed', 'rejected'],
            'rejected': ['pending'],
            'closed': ['approved'],  # Solo admin puede reabrir
        }
        
        if new_status not in valid_transitions.get(old_status, []):
            raise ValidationError({
                'status': f'No se puede cambiar de "{old_status}" a "{new_status}". '
                         f'Cambios válidos: {", ".join(valid_transitions.get(old_status, []))}'
            })
        
        # Validaciones específicas por estado
        if new_status == 'approved':
            if not self.cleaned_data.get('skills_required'):
                raise ValidationError({
                    'skills_required': 'Debes seleccionar al menos un skill antes de aprobar.'
                })
    
    def save(self, commit=True):
        job = super().save(commit=False)
        
        # Manejar cambios de estado
        status = self.cleaned_data.get('status')
        if status == 'approved' and job.status != 'approved':
            job.approved_at = timezone.now()
            # approved_by se manejará en la vista del admin
        elif status == 'rejected':
            job.rejection_reason = self.cleaned_data.get('rejection_reason', '')
        
        if commit:
            job.save()
            self.save_m2m()
            
            # Guardar notas administrativas si existen
            admin_notes = self.cleaned_data.get('admin_notes')
            if admin_notes:
                # Aquí podrías guardar las notas en un modelo separado
                # o agregar el campo al modelo JobPost
                pass
        
        return job

class ApplicationAdminForm(forms.ModelForm):
    """Formulario para administrar postulaciones"""
    
    # Campo calculado para mostrar información del candidato
    candidate_info = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'readonly': True,
            'rows': 6,
            'style': 'background-color: #f8f9fa;'
        }),
        help_text="Información del candidato (solo lectura)"
    )
    
    # Campo para respuesta al candidato
    response_message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Mensaje personalizado para el candidato...'
        }),
        help_text="Mensaje que se enviará al candidato (opcional)"
    )
    
    class Meta:
        model = Application
        fields = '__all__'
        widgets = {
            'cover_letter': forms.Textarea(attrs={
                'rows': 6,
                'readonly': True,
                'style': 'background-color: #f8f9fa;'
            }),
            'notes': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Notas internas sobre esta postulación...'
            }),
            'rejection_reason': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Motivo del rechazo (se enviará al candidato)'
            }),
            'status': forms.Select(attrs={
                'style': 'width: 200px;'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.pk:
            self.setup_candidate_info()
    
    def setup_candidate_info(self):
        """Configurar información del candidato"""
        if not self.instance.pk:
            return
        
        applicant = self.instance.applicant
        user = applicant.user
        
        info = []
        info.append(f"👤 INFORMACIÓN DEL CANDIDATO")
        info.append(f"{'='*50}")
        info.append(f"• Nombre: {user.get_full_name() or 'No especificado'}")
        info.append(f"• Email: {user.email}")
        info.append(f"• Teléfono: {getattr(applicant, 'phone', 'No especificado')}")
        info.append(f"• Experiencia: {getattr(applicant, 'years_experience', 'No especificado')} años")
        info.append(f"• Ubicación: {getattr(applicant, 'location', 'No especificado')}")
        info.append(f"• Fecha de registro: {user.date_joined.strftime('%d/%m/%Y')}")
        
        # Skills del candidato
        if hasattr(applicant, 'skills') and applicant.skills.exists():
            skills = [skill.skill.name for skill in applicant.skills.all()[:10]]
            info.append(f"• Skills principales: {', '.join(skills)}")
            if applicant.skills.count() > 10:
                info.append(f"  (+{applicant.skills.count() - 10} skills más)")
        
        info.append(f"")
        info.append(f"📊 ESTADÍSTICAS DE POSTULACIÓN")
        info.append(f"{'='*50}")
        info.append(f"• Match Score: {self.instance.match_score}%")
        info.append(f"• Fecha de postulación: {self.instance.applied_at.strftime('%d/%m/%Y %H:%M')}")
        info.append(f"• Última actualización: {self.instance.updated_at.strftime('%d/%m/%Y %H:%M')}")
        
        # Otras postulaciones del candidato
        other_applications = Application.objects.filter(
            applicant=applicant
        ).exclude(pk=self.instance.pk)[:5]
        
        if other_applications.exists():
            info.append(f"")
            info.append(f"📋 OTRAS POSTULACIONES RECIENTES")
            info.append(f"{'='*50}")
            for app in other_applications:
                info.append(f"• {app.job_post.title} - {app.get_status_display()} ({app.applied_at.strftime('%d/%m/%Y')})")
        
        self.fields['candidate_info'].initial = "\n".join(info)
    
    def clean_status(self):
        status = self.cleaned_data.get('status')
        old_status = self.instance.status if self.instance.pk else None
        
        # Validar transiciones de estado
        if old_status and old_status == 'withdrawn':
            raise ValidationError("No se puede cambiar el estado de una postulación retirada.")
        
        return status
    
    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        rejection_reason = cleaned_data.get('rejection_reason')
        
        # Requerir motivo de rechazo
        if status == 'rejected' and not rejection_reason:
            self.add_error('rejection_reason', 'Debes proporcionar un motivo de rechazo.')
        
        return cleaned_data

class SkillAdminForm(forms.ModelForm):
    """Formulario para administrar skills"""
    
    # Campo para mostrar estadísticas de uso
    usage_stats = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'readonly': True,
            'rows': 4,
            'style': 'background-color: #f8f9fa;'
        }),
        help_text="Estadísticas de uso del skill"
    )
    
    class Meta:
        model = Skill
        fields = '__all__'
        widgets = {
            'name': forms.TextInput(attrs={
                'size': 50,
                'placeholder': 'ej. Python, React, Marketing Digital'
            }),
            'category': forms.TextInput(attrs={
                'size': 30,
                'placeholder': 'ej. Lenguajes de Programación, Marketing'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.pk:
            self.setup_usage_stats()
    
    def setup_usage_stats(self):
        """Configurar estadísticas de uso"""
        if not self.instance.pk:
            return
        
        skill = self.instance
        
        # Contar usos
        job_count = JobPost.objects.filter(skills_required=skill).count()
        active_job_count = JobPost.objects.filter(
            skills_required=skill, 
            status='approved', 
            is_active=True
        ).count()
        
        stats = []
        stats.append(f"📊 ESTADÍSTICAS DE USO")
        stats.append(f"{'='*30}")
        stats.append(f"• Total de trabajos: {job_count}")
        stats.append(f"• Trabajos activos: {active_job_count}")
        stats.append(f"• Categoría: {skill.category}")
        
        if job_count > 0:
            # Top empresas que usan este skill
            from django.db.models import Count
            top_companies = JobPost.objects.filter(
                skills_required=skill
            ).values('company__name').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
            
            if top_companies:
                stats.append(f"")
                stats.append(f"🏢 EMPRESAS QUE MÁS LO USAN")
                stats.append(f"{'='*30}")
                for company in top_companies:
                    stats.append(f"• {company['company__name']}: {company['count']} vacantes")
        
        self.fields['usage_stats'].initial = "\n".join(stats)
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip().title()
            
            # Verificar duplicados
            existing = Skill.objects.filter(name__iexact=name)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError(f"Ya existe un skill con el nombre '{name}'.")
        
        return name
    
    def clean_category(self):
        category = self.cleaned_data.get('category')
        if category:
            category = category.strip().title()
        return category