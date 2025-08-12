from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, 
    TemplateView, FormView
)
from django.views import View
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponse, Http404
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, Sum
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.template.loader import render_to_string
from django.contrib.syndication.views import Feed
from django.utils import timezone
from datetime import datetime, timedelta
import csv
import json
import logging

from jobs.models import Application, JobPost, SavedJob, Skill  
from matching.services import MatchingService
from notifications.services import NotificationService

logger = logging.getLogger(__name__)

# Mixins personalizados
class CompanyRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'company'

class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'admin'

class ApplicantRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.user_type == 'applicant'

# Views públicas de vacantes
class JobListView(ListView):
    model = JobPost
    template_name = 'jobs/job_list.html'
    context_object_name = 'jobs'
    paginate_by = 12
    
    @method_decorator(cache_page(60 * 5))  # Cache por 5 minutos
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_queryset(self):
        queryset = JobPost.objects.filter(
            status='approved', 
            is_active=True,
            deadline__gte=timezone.now()
        ).select_related('company').prefetch_related('skills_required')
        
        # Filtros
        location = self.request.GET.get('location')
        experience = self.request.GET.get('experience')
        skills = self.request.GET.getlist('skills')
        company_type = self.request.GET.get('company_type')
        salary_min = self.request.GET.get('salary_min')
        remote = self.request.GET.get('remote')
        
        if location:
            queryset = queryset.filter(location__icontains=location)
        
        if experience:
            queryset = queryset.filter(experience_level=experience)
        
        if skills:
            queryset = queryset.filter(skills_required__id__in=skills).distinct()
        
        if company_type:
            queryset = queryset.filter(company__company_type=company_type)
        
        if salary_min:
            queryset = queryset.filter(salary_min__gte=salary_min)
        
        if remote == 'true':
            queryset = queryset.filter(
                Q(location__icontains='remoto') | Q(location__icontains='remote')
            )
        
        # Ordenamiento
        order_by = self.request.GET.get('order_by', '-created_at')
        queryset = queryset.order_by(order_by)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Agregar datos para filtros
        context.update({
            'skills': Skill.objects.all().order_by('name'),
            'experience_levels': JobPost.EXPERIENCE_LEVELS,
            'locations': JobPost.objects.values_list('location', flat=True).distinct(),
            'filters': self.request.GET,
            'total_jobs': self.get_queryset().count(),
        })
        
        # Agregar recomendaciones si el usuario está autenticado
        if self.request.user.is_authenticated and self.request.user.user_type == 'applicant':
            try:
                recommended_jobs = MatchingService.get_recommended_jobs_for_applicant(
                    self.request.user.applicantprofile, limit=5
                )
                context['recommended_jobs'] = recommended_jobs
            except:
                pass
        
        return context

class JobDetailView(DetailView):
    model = JobPost
    template_name = 'jobs/job_detail.html'
    context_object_name = 'job'
    
    def get_queryset(self):
        return JobPost.objects.filter(
            status='approved', 
            is_active=True
        ).select_related('company').prefetch_related('skills_required')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        job = self.object
        
        # Verificar si el usuario ya se postuló
        if self.request.user.is_authenticated and self.request.user.user_type == 'applicant':
            try:
                applicant = self.request.user.applicantprofile
                has_applied = Application.objects.filter(
                    job_post=job, applicant=applicant
                ).exists()
                context['has_applied'] = has_applied
                
                # Calcular match score
                match_score = MatchingService.calculate_match_score(job, applicant)
                context['match_score'] = match_score
                
                # Verificar si está guardada
                is_saved = SavedJob.objects.filter(
                    job_post=job, applicant=applicant
                ).exists()
                context['is_saved'] = is_saved
                
            except:
                context['has_applied'] = False
                context['is_saved'] = False
        
        # Jobs similares
        similar_jobs = JobPost.objects.filter(
            status='approved',
            is_active=True,
            skills_required__in=job.skills_required.all()
        ).exclude(id=job.id).distinct()[:4]
        context['similar_jobs'] = similar_jobs
        
        # Estadísticas del job
        context['applications_count'] = job.applications.count()
        context['views_count'] = getattr(job, 'views_count', 0)
        
        return context

class JobSearchView(ListView):
    model = JobPost
    template_name = 'jobs/job_search.html'
    context_object_name = 'jobs'
    paginate_by = 10
    
    def get_queryset(self):
        query = self.request.GET.get('q', '')
        
        if not query:
            return JobPost.objects.none()
        
        queryset = JobPost.objects.filter(
            status='approved',
            is_active=True
        ).filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(requirements__icontains=query) |
            Q(company__name__icontains=query) |
            Q(skills_required__name__icontains=query)
        ).distinct().select_related('company').prefetch_related('skills_required')
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        context['total_results'] = self.get_queryset().count()
        return context

# Views de postulaciones para aspirantes
class ApplyJobView(ApplicantRequiredMixin, FormView):
    template_name = 'jobs/apply.html'
    
    def get_object(self):
        return get_object_or_404(
            JobPost, 
            id=self.kwargs['job_id'], 
            status='approved', 
            is_active=True
        )
    
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Verificar si ya se postuló
        if Application.objects.filter(
            job_post=self.object, 
            applicant=request.user.applicantprofile
        ).exists():
            messages.warning(request, 'Ya te has postulado a esta vacante.')
            return redirect('jobs:job_detail', pk=self.object.pk)
        
        return super().get(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        try:
            # Crear la aplicación
            application = Application.objects.create(
                job_post=self.object,
                applicant=request.user.applicantprofile,
                cover_letter=request.POST.get('cover_letter', '')
            )
            
            # Calcular match score
            match_score = MatchingService.calculate_match_score(
                self.object, request.user.applicantprofile
            )
            application.match_score = match_score.total_score
            application.save()
            
            # Enviar notificación
            NotificationService.send_application_notification(application)
            
            messages.success(request, '¡Postulación enviada exitosamente!')
            return redirect('jobs:job_detail', pk=self.object.pk)
            
        except Exception as e:
            logger.error(f"Error creating application: {e}")
            messages.error(request, 'Error al enviar la postulación. Inténtalo de nuevo.')
            return redirect('jobs:apply', job_id=self.object.pk)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['job'] = self.object
        
        try:
            # Calcular match score para mostrar
            match_score = MatchingService.calculate_match_score(
                self.object, self.request.user.applicantprofile
            )
            context['match_score'] = match_score
            
            # Skills del aspirante vs requeridos
            applicant_skills = set(
                self.request.user.applicantprofile.skills.values_list('skill_id', flat=True)
            )
            context['applicant_skills'] = applicant_skills
            
        except:
            pass
        
        return context

class ApplicationDetailView(LoginRequiredMixin, DetailView):
    model = Application
    template_name = 'jobs/application_detail.html'
    context_object_name = 'application'
    
    def get_queryset(self):
        if self.request.user.user_type == 'applicant':
            return Application.objects.filter(applicant__user=self.request.user)
        elif self.request.user.user_type == 'company':
            return Application.objects.filter(job_post__company__user=self.request.user)
        elif self.request.user.user_type == 'admin':
            return Application.objects.all()
        return Application.objects.none()

class WithdrawApplicationView(ApplicantRequiredMixin, View):
    def post(self, request, pk):
        application = get_object_or_404(
            Application, 
            pk=pk, 
            applicant__user=request.user,
            status__in=['applied', 'reviewing']
        )
        
        application.status = 'withdrawn'
        application.save()
        
        messages.success(request, 'Postulación retirada exitosamente.')
        return redirect('applicants:my_applications')

# Views para empresas - Gestión de vacantes
class CreateJobView(CompanyRequiredMixin, CreateView):
    model = JobPost
    template_name = 'jobs/create_job.html'
    fields = [
        'title', 'description', 'requirements', 'experience_level',
        'location', 'salary','location', 'salary_min', 'salary_max', 'deadline', 'skills_required'
    ]

    def form_valid(self, form):
        form.instance.company = self.request.user.company
        form.instance.status = 'pending'  # Requiere aprobación
    
        messages.success(self.request, 'Vacante creada y enviada para revisión.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('jobs:my_jobs')

class EditJobView(CompanyRequiredMixin, UpdateView):
    model = JobPost
    template_name = 'jobs/edit_job.html'
    fields = [
    'title', 'description', 'requirements', 'experience_level',
    'location', 'salary_min', 'salary_max', 'deadline', 'skills_required'
    ]

    def get_queryset(self):
        return JobPost.objects.filter(company__user=self.request.user)

    def form_valid(self, form):
        # Si se edita una vacante aprobada, volver a pending
        if form.instance.status == 'approved':
            form.instance.status = 'pending'
            messages.info(self.request, 'La vacante ha sido enviada nuevamente para revisión.')
        else:
            messages.success(self.request, 'Vacante actualizada exitosamente.')
        
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('jobs:my_jobs')

class DeleteJobView(CompanyRequiredMixin, DeleteView):
    model = JobPost
    template_name = 'jobs/delete_job.html'
    success_url = reverse_lazy('jobs:my_jobs')
    
    def get_queryset(self):
        return JobPost.objects.filter(company__user=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Vacante eliminada exitosamente.')
        return super().delete(request, *args, **kwargs)
    
class MyJobsView(CompanyRequiredMixin, ListView):
    model = JobPost
    template_name = 'jobs/my_jobs.html'
    context_object_name = 'jobs'
    paginate_by = 10

    def get_queryset(self):
        return JobPost.objects.filter(
            company__user=self.request.user
        ).prefetch_related('applications').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        jobs = self.get_queryset()
        context.update({
            'total_jobs': jobs.count(),
            'draft_jobs': jobs.filter(status='draft').count(),
            'pending_jobs': jobs.filter(status='pending').count(),
            'approved_jobs': jobs.filter(status='approved').count(),
            'total_applications': sum(job.applications.count() for job in jobs),
        })
        
        return context

class JobApplicantsView(CompanyRequiredMixin, DetailView):
    model = JobPost
    template_name = 'jobs/job_applicants.html'
    context_object_name = 'job'

    def get_queryset(self):
        return JobPost.objects.filter(company__user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        applications = self.object.applications.select_related(
            'applicant__user'
        ).order_by('-applied_at')
        
        # Filtros
        status_filter = self.request.GET.get('status')
        if status_filter:
            applications = applications.filter(status=status_filter)
        
        # Paginación
        paginator = Paginator(applications, 20)
        page_number = self.request.GET.get('page')
        applications_page = paginator.get_page(page_number)
        
        context.update({
            'applications': applications_page,
            'total_applications': applications.count(),
            'status_counts': {
                status[0]: applications.filter(status=status[0]).count()
                for status in Application.STATUS_CHOICES
            },
            'current_status_filter': status_filter,
        })
        
        return context

class UpdateApplicationStatusView(CompanyRequiredMixin, View):
    
    def post(self, request, pk):
        application = get_object_or_404(
            Application,
            pk=pk,
            job_post__company__user=request.user
        )
        new_status = request.POST.get('status')
        notes = request.POST.get('notes', '')
    
        if new_status in dict(Application.STATUS_CHOICES):
            old_status = application.status
            application.status = new_status
            
            if notes:
                application.notes = notes
            
            application.save()
            
            # Enviar notificación al aspirante
            NotificationService.send_application_status_update(application)
            
            messages.success(request, f'Estado actualizado a {application.get_status_display()}')
        else:
            messages.error(request, 'Estado inválido')
        
        return redirect('jobs:job_applicants', pk=application.job_post.pk)

# Views para administradores

class PendingJobsView(AdminRequiredMixin, ListView):
    model = JobPost
    template_name = 'jobs/admin_pending_jobs.html'
    context_object_name = 'jobs'
    paginate_by = 20

    def get_queryset(self):
        return JobPost.objects.filter(
            status='pending'
        ).select_related('company__user').order_by('-created_at')

class ApproveJobView(AdminRequiredMixin, View):
    
    def post(self, request, pk):
        job = get_object_or_404(JobPost, pk=pk, status='pending')
        job.status = 'approved'
        job.approved_by = request.user
        job.approved_at = timezone.now()
        job.save()
        
        # Enviar notificación a la empresa
        NotificationService.send_job_approval_notification(job, approved=True)
        
        messages.success(request, f'Vacante "{job.title}" aprobada exitosamente.')
        return redirect('jobs:pending_approval')

class RejectJobAdminView(AdminRequiredMixin, View):
    
    def post(self, request, pk):
        job = get_object_or_404(JobPost, pk=pk, status='pending')
        reason = request.POST.get('reason', '')
        job.status = 'rejected'
        job.rejection_reason = reason
        job.save()
        
        # Enviar notificación a la empresa
        NotificationService.send_job_approval_notification(job, approved=False)
        
        messages.success(request, f'Vacante "{job.title}" rechazada.')
        return redirect('jobs:pending_approval')

# API Views

class JobSearchAPIView(View):

    def get(self, request):
        query = request.GET.get('q', '')
        location = request.GET.get('location', '')
        experience = request.GET.get('experience', '')
        jobs = JobPost.objects.filter(
        status='approved',
        is_active=True
        )
        
        if query:
            jobs = jobs.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(company__name__icontains=query)
            )
        
        if location:
            jobs = jobs.filter(location__icontains=location)
        
        if experience:
            jobs = jobs.filter(experience_level=experience)
        
        jobs_data = []
        for job in jobs[:20]:
            jobs_data.append({
                'id': job.id,
                'title': job.title,
                'company': job.company.name,
                'location': job.location,
                'experience_level': job.get_experience_level_display(),
                'created_at': job.created_at.isoformat(),
                'url': reverse('jobs:job_detail', kwargs={'pk': job.pk})
            })
        
        return JsonResponse({
            'jobs': jobs_data,
            'total': len(jobs_data)
        })
    
class ApplyJobAPIView(ApplicantRequiredMixin, View):
    
    def post(self, request, pk):
        job = get_object_or_404(JobPost, pk=pk, status='approved', is_active=True)
        # Verificar si ya se postuló
        if Application.objects.filter(
            job_post=job,
            applicant=request.user.applicantprofile
        ).exists():
            return JsonResponse({
                'success': False,
                'message': 'Ya te has postulado a esta vacante'
            })
        
        try:
            application = Application.objects.create(
                job_post=job,
                applicant=request.user.applicantprofile,
                cover_letter=request.POST.get('cover_letter', '')
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Postulación enviada exitosamente',
                'application_id': application.id
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': 'Error al procesar la postulación'
            })

class SavedJobsView(ApplicantRequiredMixin, ListView):
    model = SavedJob
    template_name = 'jobs/saved_jobs.html'
    context_object_name = 'saved_jobs'
    paginate_by = 10

    def get_queryset(self):
        return SavedJob.objects.filter(
            applicant=self.request.user.applicantprofile
        ).select_related('job_post__company').order_by('-saved_at')
    
class SaveJobView(ApplicantRequiredMixin, View):

    def post(self, request, pk):
        job = get_object_or_404(JobPost, pk=pk, status='approved', is_active=True)
        saved_job, created = SavedJob.objects.get_or_create(
            job_post=job,
            applicant=request.user.applicantprofile
        )
        
        if created:
            message = 'Vacante guardada exitosamente'
        else:
            message = 'Esta vacante ya estaba guardada'
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': message,
                'is_saved': True
            })
        
        messages.success(request, message)
        return redirect('jobs:job_detail', pk=pk)

class UnsaveJobView(ApplicantRequiredMixin, View):

    def post(self, request, pk):
        job = get_object_or_404(JobPost, pk=pk)
        SavedJob.objects.filter(
            job_post=job,
            applicant=request.user.applicantprofile
        ).delete()
        
        message = 'Vacante removida de guardados'
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': message,
                'is_saved': False
            })
        
        messages.success(request, message)
        return redirect('jobs:job_detail', pk=pk)

# Feed RSS

class JobsFeedView(Feed):
    title = "Meraki - Últimas Vacantes"
    link = "/jobs/"
    description = "Las últimas oportunidades laborales en Meraki"
    
    def items(self):
        return JobPost.objects.filter(
            status='approved',
            is_active=True
        ).order_by('-created_at')[:20]

    def item_title(self, item):
        return f"{item.title} - {item.company.name}"

    def item_description(self, item):
        return item.description[:200] + "..."

    def item_link(self, item):
        return reverse('jobs:job_detail', kwargs={'pk': item.pk})


class JobFilterView(ListView):
    """Vista para filtros avanzados de empleos"""
    model = JobPost
    template_name = 'jobs/job_filter.html'
    context_object_name = 'jobs'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = JobPost.objects.filter(
            status='approved',
            is_active=True,
            deadline__gte=timezone.now()
        ).select_related('company').prefetch_related('skills_required')
        
        # Filtros avanzados
        filters = {}
        
        if self.request.GET.get('location'):
            filters['location__icontains'] = self.request.GET.get('location')
        
        if self.request.GET.get('experience_level'):
            filters['experience_level'] = self.request.GET.get('experience_level')
        
        if self.request.GET.get('salary_min'):
            filters['salary_min__gte'] = self.request.GET.get('salary_min')
        
        if self.request.GET.get('salary_max'):
            filters['salary_max__lte'] = self.request.GET.get('salary_max')
        
        if self.request.GET.getlist('skills'):
            queryset = queryset.filter(skills_required__id__in=self.request.GET.getlist('skills')).distinct()
        
        return queryset.filter(**filters).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'skills': Skill.objects.all().order_by('name'),
            'experience_levels': JobPost.EXPERIENCE_LEVELS,
            'locations': JobPost.objects.values_list('location', flat=True).distinct(),
            'filters': self.request.GET,
        })
        return context

class CloneJobView(CompanyRequiredMixin, View):
    """Clonar una vacante existente"""
    
    def post(self, request, pk):
        original_job = get_object_or_404(
            JobPost, 
            pk=pk, 
            company__user=request.user
        )
        
        # Crear copia del job
        cloned_job = JobPost.objects.create(
            company=original_job.company,
            title=f"Copia de {original_job.title}",
            description=original_job.description,
            requirements=original_job.requirements,
            experience_level=original_job.experience_level,
            location=original_job.location,
            salary_min=original_job.salary_min,
            salary_max=original_job.salary_max,
            deadline=timezone.now() + timedelta(days=30),
            status='draft'
        )
        
        # Copiar skills
        for skill_relation in original_job.jobpostskill_set.all():
            JobPostSkill.objects.create(
                job_post=cloned_job,
                skill=skill_relation.skill,
                is_required=skill_relation.is_required,
                weight=skill_relation.weight
            )
        
        messages.success(request, f'Vacante clonada exitosamente como "{cloned_job.title}"')
        return redirect('jobs:edit_job', pk=cloned_job.pk)

class DraftJobsView(CompanyRequiredMixin, ListView):
    """Vista para vacantes en borrador"""
    model = JobPost
    template_name = 'jobs/draft_jobs.html'
    context_object_name = 'jobs'
    paginate_by = 10
    
    def get_queryset(self):
        return JobPost.objects.filter(
            company__user=self.request.user,
            status='draft'
        ).order_by('-updated_at')

class ActiveJobsView(CompanyRequiredMixin, ListView):
    """Vista para vacantes activas"""
    model = JobPost
    template_name = 'jobs/active_jobs.html'
    context_object_name = 'jobs'
    paginate_by = 10
    
    def get_queryset(self):
        return JobPost.objects.filter(
            company__user=self.request.user,
            status='approved',
            is_active=True
        ).order_by('-created_at')

class ClosedJobsView(CompanyRequiredMixin, ListView):
    """Vista para vacantes cerradas"""
    model = JobPost
    template_name = 'jobs/closed_jobs.html'
    context_object_name = 'jobs'
    paginate_by = 10
    
    def get_queryset(self):
        return JobPost.objects.filter(
            company__user=self.request.user,
            status__in=['closed', 'rejected']
        ).order_by('-updated_at')

class ExportApplicantsView(CompanyRequiredMixin, View):
    """Exportar lista de postulantes a CSV"""
    
    def get(self, request, pk):
        job = get_object_or_404(
            JobPost, 
            pk=pk, 
            company__user=request.user
        )
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="postulantes_{job.title}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Nombre', 'Email', 'Teléfono', 'Estado', 'Fecha de Postulación', 
            'Match Score', 'Experiencia', 'Ubicación'
        ])
        
        for application in job.applications.select_related('applicant__user'):
            writer.writerow([
                application.applicant.get_full_name(),
                application.applicant.user.email,
                getattr(application.applicant.user.profile, 'phone', ''),
                application.get_status_display(),
                application.applied_at.strftime('%d/%m/%Y'),
                f"{application.match_score}%",
                f"{application.applicant.years_experience} años",
                getattr(application.applicant.user.profile, 'location', '')
            ])
        
        return response

class ShortlistApplicationView(CompanyRequiredMixin, View):
    """Agregar postulante a lista corta"""
    
    def post(self, request, pk):
        application = get_object_or_404(
            Application,
            pk=pk,
            job_post__company__user=request.user
        )
        
        application.status = 'shortlisted'
        application.save()
        
        # Enviar notificación
        NotificationService.send_application_status_update(application)
        
        messages.success(request, f'{application.applicant.get_full_name()} agregado a la lista corta.')
        return redirect('jobs:job_applicants', pk=application.job_post.pk)

class RejectApplicationView(CompanyRequiredMixin, View):
    """Rechazar postulación"""
    
    def post(self, request, pk):
        application = get_object_or_404(
            Application,
            pk=pk,
            job_post__company__user=request.user
        )
        
        reason = request.POST.get('reason', '')
        application.status = 'rejected'
        application.rejection_reason = reason
        application.save()
        
        # Enviar notificación
        NotificationService.send_application_status_update(application)
        
        messages.success(request, f'Postulación de {application.applicant.get_full_name()} rechazada.')
        return redirect('jobs:job_applicants', pk=application.job_post.pk)

class ApplicationNotesView(CompanyRequiredMixin, View):
    """Agregar notas a una postulación"""
    
    def post(self, request, pk):
        application = get_object_or_404(
            Application,
            pk=pk,
            job_post__company__user=request.user
        )
        
        notes = request.POST.get('notes', '')
        application.notes = notes
        application.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Notas guardadas exitosamente'
            })
        
        messages.success(request, 'Notas guardadas exitosamente.')
        return redirect('jobs:job_applicants', pk=application.job_post.pk)

class AllJobsAdminView(AdminRequiredMixin, ListView):
    """Vista de todas las vacantes para administradores"""
    model = JobPost
    template_name = 'jobs/admin_all_jobs.html'
    context_object_name = 'jobs'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = JobPost.objects.all().select_related('company__user')
        
        # Filtros para admin
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        company = self.request.GET.get('company')
        if company:
            queryset = queryset.filter(company__name__icontains=company)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        all_jobs = JobPost.objects.all()
        context.update({
            'total_jobs': all_jobs.count(),
            'pending_jobs': all_jobs.filter(status='pending').count(),
            'approved_jobs': all_jobs.filter(status='approved').count(),
            'rejected_jobs': all_jobs.filter(status='rejected').count(),
            'status_choices': JobPost.STATUS_CHOICES,
            'filters': self.request.GET,
        })
        return context

class FeatureJobView(AdminRequiredMixin, View):
    """Destacar una vacante"""
    
    def post(self, request, pk):
        job = get_object_or_404(JobPost, pk=pk)
        
        # Toggle featured status
        job.is_featured = not getattr(job, 'is_featured', False)
        job.save()
        
        status = 'destacada' if job.is_featured else 'no destacada'
        messages.success(request, f'Vacante "{job.title}" marcada como {status}.')
        
        return redirect('jobs:all_jobs_admin')

class JobStatsView(LoginRequiredMixin, TemplateView):
    """Estadísticas de empleos"""
    template_name = 'jobs/job_stats.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.user.user_type == 'company':
            # Stats para empresa
            jobs = JobPost.objects.filter(company__user=self.request.user)
            
            context.update({
                'total_jobs': jobs.count(),
                'active_jobs': jobs.filter(status='approved', is_active=True).count(),
                'total_applications': Application.objects.filter(job_post__in=jobs).count(),
                'pending_applications': Application.objects.filter(
                    job_post__in=jobs, 
                    status__in=['applied', 'reviewing']
                ).count(),
            })
            
        elif self.request.user.user_type == 'admin':
            # Stats para admin
            context.update({
                'total_jobs': JobPost.objects.count(),
                'pending_approval': JobPost.objects.filter(status='pending').count(),
                'active_jobs': JobPost.objects.filter(status='approved', is_active=True).count(),
                'total_applications': Application.objects.count(),
                'total_companies': User.objects.filter(user_type='company').count(),
                'total_applicants': User.objects.filter(user_type='applicant').count(),
            })
            
        return context

class JobReportsView(AdminRequiredMixin, TemplateView):
    """Reportes detallados de empleos"""
    template_name = 'jobs/job_reports.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Reportes por mes
        from django.db.models import Count
        from django.db.models.functions import TruncMonth
        
        jobs_by_month = JobPost.objects.annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            count=Count('id')
        ).order_by('month')
        
        applications_by_month = Application.objects.annotate(
            month=TruncMonth('applied_at')
        ).values('month').annotate(
            count=Count('id')
        ).order_by('month')
        
        context.update({
            'jobs_by_month': jobs_by_month,
            'applications_by_month': applications_by_month,
            'top_skills': Skill.objects.annotate(
                job_count=Count('jobpostskill')
            ).order_by('-job_count')[:10],
            'top_locations': JobPost.objects.values('location').annotate(
                count=Count('id')
            ).order_by('-count')[:10],
        })
        
        return context

class JobAnalyticsView(CompanyRequiredMixin, TemplateView):
    """Analytics para empresas"""
    template_name = 'jobs/job_analytics.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        jobs = JobPost.objects.filter(company__user=self.request.user)
        applications = Application.objects.filter(job_post__in=jobs)
        
        # Métricas de performance
        context.update({
            'avg_applications_per_job': applications.count() / max(jobs.count(), 1),
            'conversion_rate': (applications.filter(status='accepted').count() / 
                              max(applications.count(), 1)) * 100,
            'avg_time_to_hire': self.calculate_avg_time_to_hire(applications),
            'top_performing_jobs': jobs.annotate(
                app_count=Count('applications')
            ).order_by('-app_count')[:5],
        })
        
        return context
    
    def calculate_avg_time_to_hire(self, applications):
        """Calcular tiempo promedio de contratación"""
        hired_apps = applications.filter(status='accepted')
        if not hired_apps.exists():
            return 0
        
        total_days = 0
        for app in hired_apps:
            total_days += (app.updated_at - app.applied_at).days
        
        return total_days / hired_apps.count()

class SkillsAPIView(View):
    """API para obtener skills"""
    
    def get(self, request):
        query = request.GET.get('q', '')
        category = request.GET.get('category', '')
        
        skills = Skill.objects.all()
        
        if query:
            skills = skills.filter(name__icontains=query)
        
        if category:
            skills = skills.filter(category=category)
        
        skills_data = []
        for skill in skills[:20]:
            skills_data.append({
                'id': skill.id,
                'name': skill.name,
                'category': skill.category
            })
        
        return JsonResponse({
            'skills': skills_data,
            'categories': list(Skill.objects.values_list('category', flat=True).distinct())
        })

class SavedJobsAPIView(ApplicantRequiredMixin, View):
    """API para vacantes guardadas"""
    
    def get(self, request):
        saved_jobs = SavedJob.objects.filter(
            applicant=request.user.applicantprofile
        ).select_related('job_post__company')
        
        saved_jobs_data = []
        for saved_job in saved_jobs:
            saved_jobs_data.append({
                'id': saved_job.id,
                'job_id': saved_job.job_post.id,
                'title': saved_job.job_post.title,
                'company': saved_job.job_post.company.name,
                'location': saved_job.job_post.location,
                'saved_at': saved_job.saved_at.isoformat(),
                'is_still_active': saved_job.is_still_active,
                'url': reverse('jobs:job_detail', kwargs={'pk': saved_job.job_post.pk})
            })
        
        return JsonResponse({
            'saved_jobs': saved_jobs_data,
            'total': len(saved_jobs_data)
        })
    
    def post(self, request):
        """Guardar/quitar vacante"""
        job_id = request.POST.get('job_id')
        action = request.POST.get('action')  # 'save' or 'unsave'
        
        job = get_object_or_404(JobPost, pk=job_id, status='approved', is_active=True)
        
        if action == 'save':
            saved_job, created = SavedJob.objects.get_or_create(
                job_post=job,
                applicant=request.user.applicantprofile
            )
            message = 'Vacante guardada' if created else 'Ya estaba guardada'
            
        elif action == 'unsave':
            SavedJob.objects.filter(
                job_post=job,
                applicant=request.user.applicantprofile
            ).delete()
            message = 'Vacante removida de guardados'
        
        return JsonResponse({
            'success': True,
            'message': message
        })