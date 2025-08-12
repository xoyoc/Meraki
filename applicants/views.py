from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import (
    TemplateView, DetailView, UpdateView, CreateView, DeleteView, 
    ListView, FormView
)
from django.views import View
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponse, Http404
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import datetime, timedelta
import csv
import json
import logging
import os

from .models import ApplicantProfile, ApplicantSkill, JobAlert
from jobs.models import Application, JobPost, Skill
from courses.models import Enrollment, Certificate
#from matching.services import MatchingService
from matching.services import MatchingService


logger = logging.getLogger(__name__)

class ApplicantRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'applicant':
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

class ApplicantDashboardView(ApplicantRequiredMixin, TemplateView):
    template_name = 'applicants/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        applicant = self.request.user.applicantprofile
        
        # Estadísticas básicas
        applications = Application.objects.filter(applicant=applicant)
        
        context.update({
            'applicant': applicant,
            'stats': {
                'total_applications': applications.count(),
                'pending_applications': applications.filter(
                    status__in=['applied', 'reviewing', 'shortlisted']
                ).count(),
                'accepted_applications': applications.filter(status='accepted').count(),
                'completed_courses': Enrollment.objects.filter(
                    applicant=applicant, status='completed'
                ).count(),
                'profile_views': getattr(applicant, 'profile_views', 0),
            },
            'recent_applications': applications.select_related(
                'job_post__company'
            ).order_by('-applied_at')[:5],
            'recommended_jobs': self.get_recommended_jobs(applicant),
            'profile_completion': self.calculate_profile_completion(applicant),
            'recent_activity': self.get_recent_activity(applicant),
        })
        
        return context
    
    def get_recommended_jobs(self, applicant):
        try:
            return MatchingService.get_recommended_jobs_for_applicant(applicant, limit=5)
        except:
            return []
    
    def calculate_profile_completion(self, applicant):
        completion = 0
        total_fields = 8
        
        if applicant.first_name: completion += 1
        if applicant.last_name: completion += 1
        if applicant.cv_file: completion += 1
        if applicant.current_position: completion += 1
        if applicant.years_experience > 0: completion += 1
        if applicant.skills.exists(): completion += 1
        if applicant.user.profile.avatar: completion += 1
        if applicant.user.profile.location: completion += 1
        
        return (completion / total_fields) * 100
    
    def get_recent_activity(self, applicant):
        activities = []
        
        # Postulaciones recientes
        recent_apps = Application.objects.filter(
            applicant=applicant
        ).order_by('-applied_at')[:3]
        
        for app in recent_apps:
            activities.append({
                'type': 'application',
                'description': f'Te postulaste a {app.job_post.title}',
                'date': app.applied_at,
                'url': reverse('applicants:application_detail', kwargs={'pk': app.pk})
            })
        
        # Cursos completados recientes
        recent_courses = Enrollment.objects.filter(
            applicant=applicant,
            status='completed'
        ).order_by('-completed_at')[:2]
        
        for course in recent_courses:
            activities.append({
                'type': 'course',
                'description': f'Completaste el curso {course.course.title}',
                'date': course.completed_at,
                'url': reverse('courses:course_detail', kwargs={'pk': course.course.pk})
            })
        
        return sorted(activities, key=lambda x: x['date'], reverse=True)[:5]

class ApplicantProfileView(ApplicantRequiredMixin, DetailView):
    model = ApplicantProfile
    template_name = 'applicants/profile.html'
    context_object_name = 'applicant'
    
    def get_object(self):
        return self.request.user.applicantprofile
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        applicant = self.object
        
        context.update({
            'certificates': Certificate.objects.filter(
                enrollment__applicant=applicant
            ).order_by('-issued_at'),
            'recent_applications': Application.objects.filter(
                applicant=applicant
            ).select_related('job_post__company').order_by('-applied_at')[:5],
            'skills_by_category': self.get_skills_by_category(applicant),
        })
        
        return context
    
    def get_skills_by_category(self, applicant):
        skills = ApplicantSkill.objects.filter(applicant=applicant).select_related('skill')
        skills_by_category = {}
        
        for skill in skills:
            category = skill.skill.category
            if category not in skills_by_category:
                skills_by_category[category] = []
            skills_by_category[category].append(skill)
        
        return skills_by_category

class ApplicantProfileEditView(ApplicantRequiredMixin, UpdateView):
    model = ApplicantProfile
    template_name = 'applicants/profile_edit.html'
    fields = [
        'first_name', 'last_name', 'birth_date', 'current_position',
        'years_experience', 'education_level'
    ]
    success_url = reverse_lazy('applicants:profile')
    
    def get_object(self):
        return self.request.user.applicantprofile
    
    def form_valid(self, form):
        messages.success(self.request, 'Perfil actualizado correctamente.')
        
        # Recalcular profile score
        self.calculate_and_update_profile_score(form.instance)
        
        return super().form_valid(form)
    
    def calculate_and_update_profile_score(self, applicant):
        # Lógica para calcular el score del perfil
        score = 0
        
        if applicant.first_name and applicant.last_name:
            score += 15
        if applicant.cv_file:
            score += 25
        if applicant.current_position:
            score += 10
        if applicant.years_experience > 0:
            score += 10
        if applicant.skills.exists():
            score += 20
        if applicant.user.profile.avatar:
            score += 10
        if applicant.user.profile.location:
            score += 5
        if applicant.birth_date:
            score += 5
        
        applicant.profile_score = score
        applicant.save(update_fields=['profile_score'])

class MyApplicationsView(ApplicantRequiredMixin, ListView):
    model = Application
    template_name = 'applicants/my_applications.html'
    context_object_name = 'applications'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = Application.objects.filter(
            applicant=self.request.user.applicantprofile
        ).select_related('job_post__company').order_by('-applied_at')
        
        # Filtros
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        company = self.request.GET.get('company')
        if company:
            queryset = queryset.filter(job_post__company__name__icontains=company)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        applications = Application.objects.filter(
            applicant=self.request.user.applicantprofile
        )
        
        context.update({
            'status_counts': {
                status[0]: applications.filter(status=status[0]).count()
                for status in Application.STATUS_CHOICES
            },
            'total_applications': applications.count(),
            'filters': self.request.GET,
        })
        
        return context

class SkillsManagementView(ApplicantRequiredMixin, TemplateView):
    template_name = 'applicants/skills_management.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        applicant = self.request.user.applicantprofile
        
        context.update({
            'applicant_skills': ApplicantSkill.objects.filter(
                applicant=applicant
            ).select_related('skill').order_by('skill__category', 'skill__name'),
            'available_skills': Skill.objects.exclude(
                id__in=applicant.skills.values_list('skill_id', flat=True)
            ).order_by('category', 'name'),
            'skill_categories': Skill.objects.values_list('category', flat=True).distinct(),
        })
        
        return context

class AddSkillView(ApplicantRequiredMixin, View):
    def post(self, request):
        skill_id = request.POST.get('skill_id')
        proficiency_level = request.POST.get('proficiency_level')
        years_experience = request.POST.get('years_experience', 0)
        
        try:
            skill = Skill.objects.get(id=skill_id)
            applicant_skill, created = ApplicantSkill.objects.get_or_create(
                applicant=request.user.applicantprofile,
                skill=skill,
                defaults={
                    'proficiency_level': proficiency_level,
                    'years_experience': years_experience
                }
            )
            
            if created:
                messages.success(request, f'Skill "{skill.name}" agregado correctamente.')
            else:
                messages.info(request, f'Ya tienes el skill "{skill.name}" en tu perfil.')
                
        except Skill.DoesNotExist:
            messages.error(request, 'Skill no encontrado.')
        except Exception as e:
            messages.error(request, 'Error al agregar el skill.')
        
        return redirect('applicants:skills_management')

class RecommendationsView(ApplicantRequiredMixin, ListView):
    template_name = 'applicants/recommendations.html'
    context_object_name = 'matches'
    paginate_by = 10
    
    def get_queryset(self):
        try:
            return MatchingService.get_recommended_jobs_for_applicant(
                self.request.user.applicantprofile, limit=50
            )
        except:
            return []
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_recommendations'] = len(self.get_queryset())
        return context

class ProfileScoreView(ApplicantRequiredMixin, TemplateView):
    template_name = 'applicants/profile_score.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        applicant = self.request.user.applicantprofile
        
        score_breakdown = {
            'basic_info': 0,
            'cv_uploaded': 0,
            'skills_added': 0,
            'experience_filled': 0,
            'avatar_uploaded': 0,
            'location_set': 0,
        }
        
        if applicant.first_name and applicant.last_name:
            score_breakdown['basic_info'] = 20
        if applicant.cv_file:
            score_breakdown['cv_uploaded'] = 25
        if applicant.skills.exists():
            score_breakdown['skills_added'] = 20
        if applicant.years_experience > 0 and applicant.current_position:
            score_breakdown['experience_filled'] = 15
        if applicant.user.profile.avatar:
            score_breakdown['avatar_uploaded'] = 10
        if applicant.user.profile.location:
            score_breakdown['location_set'] = 10
        
        total_score = sum(score_breakdown.values())
        
        context.update({
            'applicant': applicant,
            'score_breakdown': score_breakdown,
            'total_score': total_score,
            'suggestions': self.get_improvement_suggestions(score_breakdown),
        })
        
        return context
    
    def get_improvement_suggestions(self, score_breakdown):
        suggestions = []
        
        if score_breakdown['basic_info'] == 0:
            suggestions.append({
                'title': 'Completa tu información básica',
                'description': 'Agrega tu nombre y apellido',
                'points': 20,
                'url': reverse('applicants:profile_edit')
            })
        
        if score_breakdown['cv_uploaded'] == 0:
            suggestions.append({
                'title': 'Sube tu CV',
                'description': 'Un CV actualizado mejora significativamente tu perfil',
                'points': 25,
                'url': reverse('applicants:cv_upload')
            })
        
        if score_breakdown['skills_added'] == 0:
            suggestions.append({
                'title': 'Agrega tus habilidades',
                'description': 'Las skills son clave para el matching',
                'points': 20,
                'url': reverse('applicants:skills_management')
            })
        
        return suggestions

# API Views
class ProfileScoreAPIView(ApplicantRequiredMixin, View):
    def get(self, request):
        applicant = request.user.applicantprofile
        
        return JsonResponse({
            'current_score': float(applicant.profile_score),
            'max_score': 100, # URLs y Views de todas las aplicaciones Meraki
            'completion_percentage': float(applicant.profile_score),
            'skills_count': applicant.skills.count(),
            'applications_count': Application.objects.filter(applicant=applicant).count(),
        })

class SkillSearchAPIView(ApplicantRequiredMixin, View):
    
    def get(self, request):
        query = request.GET.get('q', '')
        if len(query) < 2:
            return JsonResponse({'skills': []})
        
        skills = Skill.objects.filter(
            name__icontains=query
        ).exclude(
            id__in=request.user.applicantprofile.skills.values_list('skill_id', flat=True)
        )[:10]
        
        skills_data = []
        for skill in skills:
            skills_data.append({
                'id': skill.id,
                'name': skill.name,
                'category': skill.category
            })
        
        return JsonResponse({'skills': skills_data})

class CompleteProfileView(ApplicantRequiredMixin, UpdateView):
    """Vista para completar el perfil del postulante"""
    model = ApplicantProfile
    template_name = 'applicants/complete_profile.html'
    fields = [
        'first_name', 'last_name', 'birth_date', 'current_position',
        'years_experience', 'education_level', 'cv_file'
    ]
    success_url = reverse_lazy('applicants:dashboard')
    
    def get_object(self):
        return self.request.user.applicantprofile
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['completion_steps'] = [
            {'name': 'Información Personal', 'completed': bool(self.object.first_name and self.object.last_name)},
            {'name': 'Información Profesional', 'completed': bool(self.object.current_position)},
            {'name': 'CV', 'completed': bool(self.object.cv_file)},
            {'name': 'Habilidades', 'completed': self.object.skills.exists()},
        ]
        return context
    
    def form_valid(self, form):
        messages.success(self.request, 'Perfil completado exitosamente.')
        self.calculate_and_update_profile_score(form.instance)
        return super().form_valid(form)
    
    def calculate_and_update_profile_score(self, applicant):
        # Misma lógica que en ApplicantProfileEditView
        score = 0
        if applicant.first_name and applicant.last_name: score += 15
        if applicant.cv_file: score += 25
        if applicant.current_position: score += 10
        if applicant.years_experience > 0: score += 10
        if applicant.skills.exists(): score += 20
        if applicant.user.profile.avatar: score += 10
        if applicant.user.profile.location: score += 5
        if applicant.birth_date: score += 5
        
        applicant.profile_score = score
        applicant.save(update_fields=['profile_score'])

class CVUploadView(ApplicantRequiredMixin, View):
    """Vista para subir CV"""
    
    def get(self, request):
        return render(request, 'applicants/cv_upload.html', {
            'applicant': request.user.applicantprofile
        })
    
    def post(self, request):
        if 'cv_file' not in request.FILES:
            messages.error(request, 'No se seleccionó ningún archivo.')
            return redirect('applicants:cv_upload')
        
        cv_file = request.FILES['cv_file']
        
        # Validar tipo de archivo
        allowed_extensions = ['.pdf', '.doc', '.docx']
        file_extension = os.path.splitext(cv_file.name)[1].lower()
        
        if file_extension not in allowed_extensions:
            messages.error(request, 'Solo se permiten archivos PDF, DOC o DOCX.')
            return redirect('applicants:cv_upload')
        
        # Validar tamaño (máximo 5MB)
        if cv_file.size > 5 * 1024 * 1024:
            messages.error(request, 'El archivo es demasiado grande. Máximo 5MB.')
            return redirect('applicants:cv_upload')
        
        applicant = request.user.applicantprofile
        
        # Eliminar CV anterior si existe
        if applicant.cv_file:
            applicant.cv_file.delete()
        
        # Guardar nuevo CV
        applicant.cv_file = cv_file
        applicant.save()
        
        messages.success(request, 'CV subido exitosamente.')
        return redirect('applicants:profile')

class CVDeleteView(ApplicantRequiredMixin, View):
    """Vista para eliminar CV"""
    
    def post(self, request):
        applicant = request.user.applicantprofile
        
        if applicant.cv_file:
            applicant.cv_file.delete()
            applicant.cv_file = None
            applicant.save()
            messages.success(request, 'CV eliminado exitosamente.')
        else:
            messages.warning(request, 'No tienes un CV para eliminar.')
        
        return redirect('applicants:profile')

class PortfolioUploadView(ApplicantRequiredMixin, View):
    """Vista para subir portafolio"""
    
    def get(self, request):
        return render(request, 'applicants/portfolio_upload.html', {
            'applicant': request.user.applicantprofile
        })
    
    def post(self, request):
        if 'portfolio_file' not in request.FILES:
            messages.error(request, 'No se seleccionó ningún archivo.')
            return redirect('applicants:portfolio_upload')
        
        portfolio_file = request.FILES['portfolio_file']
        
        # Validar tipo de archivo
        allowed_extensions = ['.pdf', '.zip', '.rar']
        file_extension = os.path.splitext(portfolio_file.name)[1].lower()
        
        if file_extension not in allowed_extensions:
            messages.error(request, 'Solo se permiten archivos PDF, ZIP o RAR.')
            return redirect('applicants:portfolio_upload')
        
        # Validar tamaño (máximo 10MB)
        if portfolio_file.size > 10 * 1024 * 1024:
            messages.error(request, 'El archivo es demasiado grande. Máximo 10MB.')
            return redirect('applicants:portfolio_upload')
        
        applicant = request.user.applicantprofile
        
        # Eliminar portafolio anterior si existe
        if applicant.portfolio_file:
            applicant.portfolio_file.delete()
        
        # Guardar nuevo portafolio
        applicant.portfolio_file = portfolio_file
        applicant.save()
        
        messages.success(request, 'Portafolio subido exitosamente.')
        return redirect('applicants:profile')

class PortfolioDeleteView(ApplicantRequiredMixin, View):
    """Vista para eliminar portafolio"""
    
    def post(self, request):
        applicant = request.user.applicantprofile
        
        if applicant.portfolio_file:
            applicant.portfolio_file.delete()
            applicant.portfolio_file = None
            applicant.save()
            messages.success(request, 'Portafolio eliminado exitosamente.')
        else:
            messages.warning(request, 'No tienes un portafolio para eliminar.')
        
        return redirect('applicants:profile')

class EditSkillView(ApplicantRequiredMixin, UpdateView):
    """Vista para editar una habilidad"""
    model = ApplicantSkill
    template_name = 'applicants/edit_skill.html'
    fields = ['proficiency_level', 'years_experience']
    
    def get_queryset(self):
        return ApplicantSkill.objects.filter(applicant=self.request.user.applicantprofile)
    
    def form_valid(self, form):
        messages.success(self.request, f'Habilidad "{form.instance.skill.name}" actualizada correctamente.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('applicants:skills_management')

class DeleteSkillView(ApplicantRequiredMixin, DeleteView):
    """Vista para eliminar una habilidad"""
    model = ApplicantSkill
    template_name = 'applicants/delete_skill.html'
    success_url = reverse_lazy('applicants:skills_management')
    
    def get_queryset(self):
        return ApplicantSkill.objects.filter(applicant=self.request.user.applicantprofile)
    
    def delete(self, request, *args, **kwargs):
        skill_name = self.get_object().skill.name
        messages.success(request, f'Habilidad "{skill_name}" eliminada correctamente.')
        return super().delete(request, *args, **kwargs)

class ApplicationDetailView(ApplicantRequiredMixin, DetailView):
    """Vista de detalle de una postulación"""
    model = Application
    template_name = 'applicants/application_detail.html'
    context_object_name = 'application'
    
    def get_queryset(self):
        return Application.objects.filter(applicant=self.request.user.applicantprofile)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        application = self.object
        
        # Calcular match score si no existe
        if application.match_score == 0:
            try:
                match_score = MatchingService.calculate_match_score(
                    application.job_post, application.applicant
                )
                application.match_score = match_score.total_score
                application.save()
            except:
                pass
        
        context['timeline'] = self.get_application_timeline(application)
        return context
    
    def get_application_timeline(self, application):
        """Crear timeline de la postulación"""
        timeline = [
            {
                'date': application.applied_at,
                'status': 'applied',
                'title': 'Postulación Enviada',
                'description': 'Tu postulación fue enviada exitosamente.'
            }
        ]
        
        if application.status != 'applied':
            timeline.append({
                'date': application.updated_at,
                'status': application.status,
                'title': application.get_status_display(),
                'description': self.get_status_description(application.status)
            })
        
        return timeline
    
    def get_status_description(self, status):
        descriptions = {
            'reviewing': 'La empresa está revisando tu postulación.',
            'shortlisted': '¡Felicidades! Has sido preseleccionado.',
            'interviewed': 'Has sido convocado a entrevista.',
            'accepted': '¡Excelente! Tu postulación ha sido aceptada.',
            'rejected': 'Tu postulación no fue seleccionada en esta ocasión.'
        }
        return descriptions.get(status, 'Estado actualizado.')

class WithdrawApplicationView(ApplicantRequiredMixin, View):
    """Vista para retirar una postulación"""
    
    def post(self, request, pk):
        application = get_object_or_404(
            Application,
            pk=pk,
            applicant=request.user.applicantprofile,
            status__in=['applied', 'reviewing']
        )
        
        application.status = 'withdrawn'
        application.save()
        
        messages.success(request, f'Postulación a "{application.job_post.title}" retirada exitosamente.')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        
        return redirect('applicants:my_applications')

class ExportApplicationsView(ApplicantRequiredMixin, View):
    """Vista para exportar postulaciones a CSV"""
    
    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="mis_postulaciones.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Título', 'Empresa', 'Estado', 'Fecha de Postulación', 
            'Match Score', 'Ubicación', 'Salario'
        ])
        
        applications = Application.objects.filter(
            applicant=request.user.applicantprofile
        ).select_related('job_post__company')
        
        for app in applications:
            writer.writerow([
                app.job_post.title,
                app.job_post.company.name,
                app.get_status_display(),
                app.applied_at.strftime('%d/%m/%Y'),
                f"{app.match_score}%",
                app.job_post.location,
                f"${app.job_post.salary_min}-${app.job_post.salary_max}" if app.job_post.salary_min else 'No especificado'
            ])
        
        return response

class MatchesView(ApplicantRequiredMixin, ListView):
    """Vista de matches/coincidencias de empleo"""
    template_name = 'applicants/matches.html'
    context_object_name = 'matches'
    paginate_by = 15
    
    def get_queryset(self):
        try:
            return MatchingService.get_recommended_jobs_for_applicant(
                self.request.user.applicantprofile, limit=100
            )
        except:
            return []
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        matches = self.get_queryset()
        if matches:
            context.update({
                'high_matches': [m for m in matches if m.total_score >= 80],
                'medium_matches': [m for m in matches if 60 <= m.total_score < 80],
                'low_matches': [m for m in matches if m.total_score < 60],
                'avg_match_score': sum(m.total_score for m in matches) / len(matches)
            })
        
        return context

# ===============================
# ALERTAS DE EMPLEO
# ===============================

class JobAlertsView(ApplicantRequiredMixin, ListView):
    """Vista para listar alertas de empleo"""
    model = JobAlert
    template_name = 'applicants/job_alerts.html'
    context_object_name = 'alerts'
    paginate_by = 10
    
    def get_queryset(self):
        return JobAlert.objects.filter(applicant=self.request.user.applicantprofile)

class CreateJobAlertView(ApplicantRequiredMixin, CreateView):
    """Vista para crear alerta de empleo"""
    model = JobAlert
    template_name = 'applicants/create_job_alert.html'
    fields = [
        'name', 'keywords', 'location', 'employment_type',
        'experience_level', 'min_salary', 'max_salary',
        'email_notifications', 'frequency'
    ]
    success_url = reverse_lazy('applicants:job_alerts')
    
    def form_valid(self, form):
        form.instance.applicant = self.request.user.applicantprofile
        messages.success(self.request, f'Alerta "{form.instance.name}" creada exitosamente.')
        return super().form_valid(form)

class EditJobAlertView(ApplicantRequiredMixin, UpdateView):
    """Vista para editar alerta de empleo"""
    model = JobAlert
    template_name = 'applicants/edit_job_alert.html'
    fields = [
        'name', 'keywords', 'location', 'employment_type',
        'experience_level', 'min_salary', 'max_salary',
        'email_notifications', 'frequency'
    ]
    success_url = reverse_lazy('applicants:job_alerts')
    
    def get_queryset(self):
        return JobAlert.objects.filter(applicant=self.request.user.applicantprofile)
    
    def form_valid(self, form):
        messages.success(self.request, f'Alerta "{form.instance.name}" actualizada correctamente.')
        return super().form_valid(form)

class DeleteJobAlertView(ApplicantRequiredMixin, DeleteView):
    """Vista para eliminar alerta de empleo"""
    model = JobAlert
    template_name = 'applicants/delete_job_alert.html'
    success_url = reverse_lazy('applicants:job_alerts')
    
    def get_queryset(self):
        return JobAlert.objects.filter(applicant=self.request.user.applicantprofile)
    
    def delete(self, request, *args, **kwargs):
        alert_name = self.get_object().name
        messages.success(request, f'Alerta "{alert_name}" eliminada correctamente.')
        return super().delete(request, *args, **kwargs)

class ToggleJobAlertView(ApplicantRequiredMixin, View):
    """Vista para activar/desactivar alerta de empleo"""
    
    def post(self, request, pk):
        alert = get_object_or_404(
            JobAlert,
            pk=pk,
            applicant=request.user.applicantprofile
        )
        
        alert.is_active = not alert.is_active
        alert.save()
        
        status = 'activada' if alert.is_active else 'desactivada'
        messages.success(request, f'Alerta "{alert.name}" {status}.')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'is_active': alert.is_active
            })
        
        return redirect('applicants:job_alerts')

# ===============================
# CURSOS Y CERTIFICACIONES
# ===============================

class MyCoursesView(ApplicantRequiredMixin, ListView):
    """Vista de cursos del postulante"""
    model = Enrollment
    template_name = 'applicants/my_courses.html'
    context_object_name = 'enrollments'
    paginate_by = 10
    
    def get_queryset(self):
        return Enrollment.objects.filter(
            applicant=self.request.user.applicantprofile
        ).select_related('course').order_by('-enrolled_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        enrollments = self.get_queryset()
        context.update({
            'total_courses': enrollments.count(),
            'completed_courses': enrollments.filter(status='completed').count(),
            'in_progress_courses': enrollments.filter(status='in_progress').count(),
            'completion_rate': (enrollments.filter(status='completed').count() / 
                              max(enrollments.count(), 1)) * 100,
        })
        
        return context

class MyCertificatesView(ApplicantRequiredMixin, ListView):
    """Vista de certificados del postulante"""
    model = Certificate
    template_name = 'applicants/my_certificates.html'
    context_object_name = 'certificates'
    paginate_by = 10
    
    def get_queryset(self):
        return Certificate.objects.filter(
            enrollment__applicant=self.request.user.applicantprofile
        ).select_related('enrollment__course').order_by('-issued_at')

class DownloadCertificateView(ApplicantRequiredMixin, View):
    """Vista para descargar certificado"""
    
    def get(self, request, pk):
        certificate = get_object_or_404(
            Certificate,
            pk=pk,
            enrollment__applicant=request.user.applicantprofile
        )
        
        if certificate.pdf_file:
            response = HttpResponse(certificate.pdf_file.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="certificado_{certificate.enrollment.course.title}.pdf"'
            return response
        else:
            messages.error(request, 'Certificado no disponible.')
            return redirect('applicants:my_certificates')

# ===============================
# CONFIGURACIONES
# ===============================

class PrivacySettingsView(ApplicantRequiredMixin, TemplateView):
    """Vista de configuraciones de privacidad"""
    template_name = 'applicants/privacy_settings.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['applicant'] = self.request.user.applicantprofile
        return context

class NotificationSettingsView(ApplicantRequiredMixin, TemplateView):
    """Vista de configuraciones de notificaciones"""
    template_name = 'applicants/notification_settings.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener o crear preferencias de notificación
        from notifications.models import NotificationPreference
        preferences, created = NotificationPreference.objects.get_or_create(
            user=self.request.user
        )
        
        context['preferences'] = preferences
        return context

# ===============================
# ESTADÍSTICAS
# ===============================

class PersonalStatsView(ApplicantRequiredMixin, TemplateView):
    """Vista de estadísticas personales"""
    template_name = 'applicants/personal_stats.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        applicant = self.request.user.applicantprofile
        
        applications = Application.objects.filter(applicant=applicant)
        
        # Estadísticas básicas
        context.update({
            'total_applications': applications.count(),
            'applications_by_status': {
                status[0]: applications.filter(status=status[0]).count()
                for status in Application.STATUS_CHOICES
            },
            'avg_match_score': applications.aggregate(Avg('match_score'))['match_score__avg'] or 0,
            'profile_views': getattr(applicant, 'profile_views', 0),
            'profile_completion': self.calculate_profile_completion(applicant),
            'applications_this_month': applications.filter(
                applied_at__month=timezone.now().month,
                applied_at__year=timezone.now().year
            ).count(),
        })
        
        # Tendencias por mes
        from django.db.models.functions import TruncMonth
        applications_by_month = applications.annotate(
            month=TruncMonth('applied_at')
        ).values('month').annotate(
            count=Count('id')
        ).order_by('month')
        
        context['applications_by_month'] = applications_by_month
        
        return context
    
    def calculate_profile_completion(self, applicant):
        # Misma lógica que en ApplicantDashboardView
        completion = 0
        total_fields = 8
        
        if applicant.first_name: completion += 1
        if applicant.last_name: completion += 1
        if applicant.cv_file: completion += 1
        if applicant.current_position: completion += 1
        if applicant.years_experience > 0: completion += 1
        if applicant.skills.exists(): completion += 1
        if applicant.user.profile.avatar: completion += 1
        if applicant.user.profile.location: completion += 1
        
        return (completion / total_fields) * 100

class ActivityLogView(ApplicantRequiredMixin, TemplateView):
    """Vista de log de actividades"""
    template_name = 'applicants/activity_log.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        applicant = self.request.user.applicantprofile
        
        # Crear log de actividades
        activities = []
        
        # Postulaciones
        applications = Application.objects.filter(applicant=applicant).order_by('-applied_at')[:20]
        for app in applications:
            activities.append({
                'type': 'application',
                'icon': 'fas fa-paper-plane',
                'title': f'Postulación a {app.job_post.title}',
                'description': f'Empresa: {app.job_post.company.name}',
                'date': app.applied_at,
                'status': app.status
            })
        
        # Actualizaciones de perfil
        activities.append({
            'type': 'profile_update',
            'icon': 'fas fa-user-edit',
            'title': 'Perfil actualizado',
            'description': 'Información del perfil modificada',
            'date': applicant.updated_at,
            'status': 'completed'
        })
        
        # Ordenar por fecha
        activities.sort(key=lambda x: x['date'], reverse=True)
        
        context['activities'] = activities[:50]  # Últimas 50 actividades
        return context

# ===============================
# API VIEWS
# ===============================

class ApplicationStatusAPIView(ApplicantRequiredMixin, View):
    """API para obtener estado de postulaciones"""
    
    def get(self, request):
        applications = Application.objects.filter(
            applicant=request.user.applicantprofile
        ).select_related('job_post__company')
        
        applications_data = []
        for app in applications:
            applications_data.append({
                'id': app.id,
                'job_title': app.job_post.title,
                'company': app.job_post.company.name,
                'status': app.status,
                'status_display': app.get_status_display(),
                'applied_at': app.applied_at.isoformat(),
                'match_score': float(app.match_score),
                'url': reverse('applicants:application_detail', kwargs={'pk': app.pk})
            })
        
        return JsonResponse({
            'applications': applications_data,
            'total': len(applications_data),
            'pending': len([a for a in applications_data if a['status'] in ['applied', 'reviewing', 'shortlisted']])
        })

# ===============================
# EXPORTAR DATOS
# ===============================

class ExportProfileView(ApplicantRequiredMixin, View):
    """Vista para exportar perfil completo"""
    
    def get(self, request):
        applicant = request.user.applicantprofile
        
        response = HttpResponse(content_type='application/json')
        response['Content-Disposition'] = 'attachment; filename="mi_perfil_meraki.json"'
        
        # Datos del perfil
        profile_data = {
            'personal_info': {
                'first_name': applicant.first_name,
                'last_name': applicant.last_name,
                'email': applicant.user.email,
                'birth_date': applicant.birth_date.isoformat() if applicant.birth_date else None,
                'current_position': applicant.current_position,
                'years_experience': applicant.years_experience,
                'education_level': applicant.get_education_level_display(),
            },
            'skills': [
                {
                    'name': skill.skill.name,
                    'category': skill.skill.category,
                    'proficiency_level': skill.get_proficiency_level_display(),
                    'years_experience': skill.years_experience
                }
                for skill in ApplicantSkill.objects.filter(applicant=applicant).select_related('skill')
            ],
            'applications': [
                {
                    'job_title': app.job_post.title,
                    'company': app.job_post.company.name,
                    'status': app.get_status_display(),
                    'applied_at': app.applied_at.isoformat(),
                    'match_score': float(app.match_score)
                }
                for app in Application.objects.filter(applicant=applicant).select_related('job_post__company')
            ],
            'profile_score': float(applicant.profile_score),
            'export_date': timezone.now().isoformat()
        }
        
        json.dump(profile_data, response, indent=2, ensure_ascii=False)
        return response

class ExportPersonalDataView(ApplicantRequiredMixin, View):
    """Vista para exportar todos los datos personales (GDPR compliance)"""
    
    def get(self, request):
        applicant = request.user.applicantprofile
        
        response = HttpResponse(content_type='application/json')
        response['Content-Disposition'] = 'attachment; filename="mis_datos_completos_meraki.json"'
        
        # Datos completos incluyendo metadatos
        complete_data = {
            'user_info': {
                'username': applicant.user.username,
                'email': applicant.user.email,
                'date_joined': applicant.user.date_created.isoformat() if hasattr(applicant.user, 'date_created') else None,
                'last_login': applicant.user.last_login.isoformat() if applicant.user.last_login else None,
                'user_type': applicant.user.user_type,
            },
            'profile_data': {
                'first_name': applicant.first_name,
                'last_name': applicant.last_name,
                'birth_date': applicant.birth_date.isoformat() if applicant.birth_date else None,
                'current_position': applicant.current_position,
                'years_experience': applicant.years_experience,
                'education_level': applicant.education_level,
                'profile_score': float(applicant.profile_score),
                'created_at': applicant.created_at.isoformat(),
                'updated_at': applicant.updated_at.isoformat(),
            },
            'skills': [
                {
                    'skill_name': skill.skill.name,
                    'skill_category': skill.skill.category,
                    'proficiency_level': skill.proficiency_level,
                    'years_experience': skill.years_experience
                }
                for skill in ApplicantSkill.objects.filter(applicant=applicant).select_related('skill')
            ],
            'applications': [
                {
                    'id': app.id,
                    'job_title': app.job_post.title,
                    'company_name': app.job_post.company.name,
                    'status': app.status,
                    'cover_letter': app.cover_letter,
                    'match_score': float(app.match_score),
                    'applied_at': app.applied_at.isoformat(),
                    'updated_at': app.updated_at.isoformat(),
                }
                for app in Application.objects.filter(applicant=applicant).select_related('job_post__company')
            ],
            'job_alerts': [
                {
                    'name': alert.name,
                    'keywords': alert.keywords,
                    'location': alert.location,
                    'employment_type': alert.employment_type,
                    'experience_level': alert.experience_level,
                    'min_salary': float(alert.min_salary) if alert.min_salary else None,
                    'max_salary': float(alert.max_salary) if alert.max_salary else None,
                    'is_active': alert.is_active,
                    'email_notifications': alert.email_notifications,
                    'frequency': alert.frequency,
                    'jobs_found': alert.jobs_found,
                    'created_at': alert.created_at.isoformat(),
                    'last_checked': alert.last_checked.isoformat() if alert.last_checked else None,
                }
                for alert in JobAlert.objects.filter(applicant=applicant)
            ],
            'export_metadata': {
                'export_date': timezone.now().isoformat(),
                'export_version': '1.0',
                'data_controller': 'Meraki - Capital Humano en Acción',
                'purpose': 'Exportación de datos personales según solicitud del usuario'
            }
        }
        
        json.dump(complete_data, response, indent=2, ensure_ascii=False)
        return response