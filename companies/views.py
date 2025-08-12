# apps/companies/views.py
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
from django.db.models import Q, Count, Avg, Sum
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import datetime, timedelta
import csv
import json
import logging

from .models import Company, SavedCandidate, Interview
from jobs.models import JobPost, Application
from applicants.models import ApplicantProfile
from matching.services import MatchingService

logger = logging.getLogger(__name__)

class CompanyRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'company':
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

class CompanyDashboardView(CompanyRequiredMixin, TemplateView):
    template_name = 'companies/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company = self.request.user.company
        
        # Estadísticas principales
        jobs = JobPost.objects.filter(company=company)
        applications = Application.objects.filter(job_post__company=company)
        
        context.update({
            'company': company,
            'stats': {
                'total_jobs': jobs.count(),
                'active_jobs': jobs.filter(status='approved', is_active=True).count(),
                'total_applications': applications.count(),
                'pending_applications': applications.filter(
                    status__in=['applied', 'reviewing']
                ).count(),
                'shortlisted_candidates': applications.filter(status='shortlisted').count(),
                'hired_candidates': applications.filter(status='accepted').count(),
            },
            'recent_applications': applications.select_related(
                'applicant__user', 'job_post'
            ).order_by('-applied_at')[:5],
            'top_performing_jobs': self.get_top_performing_jobs(company),
            'upcoming_interviews': self.get_upcoming_interviews(company),
            'hiring_funnel': self.get_hiring_funnel_data(applications),
        })
        
        return context
    
    def get_top_performing_jobs(self, company):
        return JobPost.objects.filter(
            company=company,
            status='approved'
        ).annotate(
            application_count=Count('applications')
        ).order_by('-application_count')[:5]
    
    def get_upcoming_interviews(self, company):
        try:
            return Interview.objects.filter(
                application__job_post__company=company,
                scheduled_date__gte=timezone.now(),
                status='scheduled'
            ).select_related(
                'application__applicant__user',
                'application__job_post'
            ).order_by('scheduled_date')[:5]
        except:
            return []
    
    def get_hiring_funnel_data(self, applications):
        total = applications.count()
        if total == 0:
            return {}
        
        return {
            'applied': applications.filter(status='applied').count(),
            'reviewing': applications.filter(status='reviewing').count(),
            'shortlisted': applications.filter(status='shortlisted').count(),
            'interviewed': applications.filter(status='interviewed').count(),
            'accepted': applications.filter(status='accepted').count(),
        }

class CompanyProfileView(CompanyRequiredMixin, DetailView):
    model = Company
    template_name = 'companies/profile.html'
    context_object_name = 'company'
    
    def get_object(self):
        return self.request.user.company
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company = self.object
        
        context.update({
            'active_jobs': JobPost.objects.filter(
                company=company,
                status='approved',
                is_active=True
            ).count(),
            'total_hires': Application.objects.filter(
                job_post__company=company,
                status='accepted'
            ).count(),
            'completion_percentage': self.calculate_profile_completion(company),
        })
        
        return context
    
    def calculate_profile_completion(self, company):
        completion = 0
        total_fields = 8
        
        if company.name: completion += 1
        if company.description: completion += 1
        if company.website: completion += 1
        if company.industry: completion += 1
        if company.size: completion += 1
        if company.location: completion += 1
        if company.logo: completion += 1
        if company.founded_year: completion += 1
        
        return (completion / total_fields) * 100

class CompanyProfileEditView(CompanyRequiredMixin, UpdateView):
    model = Company
    template_name = 'companies/profile_edit.html'
    fields = [
        'name', 'description', 'website', 'industry', 'size', 
        'location', 'founded_year', 'employee_count'
    ]
    success_url = reverse_lazy('companies:profile')
    
    def get_object(self):
        return self.request.user.company
    
    def form_valid(self, form):
        messages.success(self.request, 'Perfil de empresa actualizado correctamente.')
        return super().form_valid(form)

class CompleteCompanyProfileView(CompanyRequiredMixin, UpdateView):
    model = Company
    template_name = 'companies/complete_profile.html'
    fields = [
        'name', 'description', 'website', 'industry', 'size', 
        'location', 'founded_year', 'employee_count', 'logo'
    ]
    success_url = reverse_lazy('companies:dashboard')
    
    def get_object(self):
        return self.request.user.company

class LogoUploadView(CompanyRequiredMixin, UpdateView):
    model = Company
    template_name = 'companies/logo_upload.html'
    fields = ['logo']
    success_url = reverse_lazy('companies:profile')
    
    def get_object(self):
        return self.request.user.company

class LogoDeleteView(CompanyRequiredMixin, View):
    def post(self, request):
        company = request.user.company
        if company.logo:
            company.logo.delete()
            messages.success(request, 'Logo eliminado correctamente.')
        return redirect('companies:profile')

class DocumentsManagementView(CompanyRequiredMixin, TemplateView):
    template_name = 'companies/documents_management.html'

class CompanyJobsView(CompanyRequiredMixin, ListView):
    model = JobPost
    template_name = 'companies/jobs.html'
    context_object_name = 'jobs'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = JobPost.objects.filter(
            company=self.request.user.company
        ).prefetch_related('applications').order_by('-created_at')
        
        # Filtros
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        jobs = JobPost.objects.filter(company=self.request.user.company)
        context.update({
            'status_counts': {
                'all': jobs.count(),
                'draft': jobs.filter(status='draft').count(),
                'pending': jobs.filter(status='pending').count(),
                'approved': jobs.filter(status='approved').count(),
                'rejected': jobs.filter(status='rejected').count(),
            },
            'filters': self.request.GET,
        })
        
        return context

class CreateJobView(CompanyRequiredMixin, CreateView):
    model = JobPost
    template_name = 'companies/create_job.html'
    fields = [
        'title', 'description', 'requirements', 'location', 
        'job_type', 'salary_min', 'salary_max', 'currency'
    ]
    
    def form_valid(self, form):
        form.instance.company = self.request.user.company
        messages.success(self.request, 'Vacante creada correctamente.')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('companies:jobs')

class EditJobView(CompanyRequiredMixin, UpdateView):
    model = JobPost
    template_name = 'companies/edit_job.html'
    fields = [
        'title', 'description', 'requirements', 'location', 
        'job_type', 'salary_min', 'salary_max', 'currency'
    ]
    
    def get_queryset(self):
        return JobPost.objects.filter(company=self.request.user.company)
    
    def get_success_url(self):
        return reverse('companies:jobs')

class DeleteJobView(CompanyRequiredMixin, DeleteView):
    model = JobPost
    template_name = 'companies/delete_job.html'
    success_url = reverse_lazy('companies:jobs')
    
    def get_queryset(self):
        return JobPost.objects.filter(company=self.request.user.company)

class CloneJobView(CompanyRequiredMixin, View):
    def post(self, request, pk):
        original_job = get_object_or_404(
            JobPost, 
            pk=pk, 
            company=request.user.company
        )
        
        # Crear copia
        new_job = JobPost.objects.create(
            company=original_job.company,
            title=f"{original_job.title} (Copia)",
            description=original_job.description,
            requirements=original_job.requirements,
            location=original_job.location,
            job_type=original_job.job_type,
            salary_min=original_job.salary_min,
            salary_max=original_job.salary_max,
            currency=original_job.currency,
            status='draft'
        )
        
        messages.success(request, 'Vacante clonada correctamente.')
        return redirect('companies:edit_job', pk=new_job.pk)

class CloseJobView(CompanyRequiredMixin, View):
    def post(self, request, pk):
        job = get_object_or_404(
            JobPost, 
            pk=pk, 
            company=request.user.company
        )
        job.is_active = False
        job.save()
        messages.success(request, 'Vacante cerrada correctamente.')
        return redirect('companies:jobs')

class ReopenJobView(CompanyRequiredMixin, View):
    def post(self, request, pk):
        job = get_object_or_404(
            JobPost, 
            pk=pk, 
            company=request.user.company
        )
        job.is_active = True
        job.save()
        messages.success(request, 'Vacante reabierta correctamente.')
        return redirect('companies:jobs')

class JobCandidatesView(CompanyRequiredMixin, DetailView):
    model = JobPost
    template_name = 'companies/job_candidates.html'
    context_object_name = 'job'
    
    def get_queryset(self):
        return JobPost.objects.filter(company=self.request.user.company)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        job = self.object
        
        applications = Application.objects.filter(
            job_post=job
        ).select_related('applicant__user').order_by('-applied_at')
        
        # Filtros
        status_filter = self.request.GET.get('status')
        if status_filter:
            applications = applications.filter(status=status_filter)
        
        score_filter = self.request.GET.get('min_score')
        if score_filter:
            applications = applications.filter(match_score__gte=score_filter)
        
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
            'avg_match_score': applications.aggregate(
                avg_score=Avg('match_score')
            )['avg_score'] or 0,
            'filters': self.request.GET,
        })
        
        return context

class AllCandidatesView(CompanyRequiredMixin, ListView):
    model = ApplicantProfile
    template_name = 'companies/all_candidates.html'
    context_object_name = 'candidates'
    paginate_by = 20

class CandidateDetailView(CompanyRequiredMixin, DetailView):
    model = ApplicantProfile
    template_name = 'companies/candidate_detail.html'
    context_object_name = 'candidate'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        candidate = self.object
        company = self.request.user.company
        
        # Aplicaciones del candidato a esta empresa
        applications = Application.objects.filter(
            applicant=candidate,
            job_post__company=company
        ).select_related('job_post').order_by('-applied_at')
        
        context.update({
            'applications': applications,
            'is_saved': SavedCandidate.objects.filter(
                company=company,
                applicant=candidate
            ).exists(),
        })
        
        return context

class CandidateSearchView(CompanyRequiredMixin, TemplateView):
    template_name = 'companies/candidate_search.html'

class SavedCandidatesView(CompanyRequiredMixin, ListView):
    model = SavedCandidate
    template_name = 'companies/saved_candidates.html'
    context_object_name = 'saved_candidates'
    paginate_by = 20
    
    def get_queryset(self):
        return SavedCandidate.objects.filter(
            company=self.request.user.company
        ).select_related('applicant__user')

class SaveCandidateView(CompanyRequiredMixin, View):
    def post(self, request, pk):
        candidate = get_object_or_404(ApplicantProfile, pk=pk)
        company = request.user.company
        
        saved_candidate, created = SavedCandidate.objects.get_or_create(
            company=company,
            applicant=candidate
        )
        
        if created:
            messages.success(request, 'Candidato guardado correctamente.')
        else:
            messages.info(request, 'El candidato ya estaba guardado.')
        
        return redirect('companies:candidate_detail', pk=pk)

class UnsaveCandidateView(CompanyRequiredMixin, View):
    def post(self, request, pk):
        candidate = get_object_or_404(ApplicantProfile, pk=pk)
        company = request.user.company
        
        SavedCandidate.objects.filter(
            company=company,
            applicant=candidate
        ).delete()
        
        messages.success(request, 'Candidato removido de guardados.')
        return redirect('companies:candidate_detail', pk=pk)

class AllApplicationsView(CompanyRequiredMixin, ListView):
    model = Application
    template_name = 'companies/all_applications.html'
    context_object_name = 'applications'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Application.objects.filter(
            job_post__company=self.request.user.company
        ).select_related(
            'applicant__user', 'job_post'
        ).order_by('-applied_at')
        
        # Filtros
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        job_id = self.request.GET.get('job')
        if job_id:
            queryset = queryset.filter(job_post_id=job_id)
        
        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(applied_at__gte=date_from)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        company_jobs = JobPost.objects.filter(
            company=self.request.user.company
        )
        
        all_applications = Application.objects.filter(
            job_post__company=self.request.user.company
        )
        
        context.update({
            'company_jobs': company_jobs,
            'status_counts': {
                status[0]: all_applications.filter(status=status[0]).count()
                for status in Application.STATUS_CHOICES
            },
            'total_applications': all_applications.count(),
            'filters': self.request.GET,
        })
        
        return context

class ApplicationDetailView(CompanyRequiredMixin, DetailView):
    model = Application
    template_name = 'companies/application_detail.html'
    context_object_name = 'application'
    
    def get_queryset(self):
        return Application.objects.filter(
            job_post__company=self.request.user.company
        ).select_related('applicant__user', 'job_post')

class UpdateApplicationStatusView(CompanyRequiredMixin, View):
    def post(self, request, pk):
        application = get_object_or_404(
            Application,
            pk=pk,
            job_post__company=request.user.company
        )
        
        new_status = request.POST.get('status')
        notes = request.POST.get('notes', '')
        
        if new_status in dict(Application.STATUS_CHOICES):
            old_status = application.status
            application.status = new_status
            
            if notes:
                application.notes = notes
            
            application.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'Estado actualizado a {application.get_status_display()}',
                    'new_status': new_status
                })
            
            messages.success(request, f'Estado actualizado a {application.get_status_display()}')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Estado inválido'
                })
            messages.error(request, 'Estado inválido')
        
        return redirect('companies:application_detail', pk=pk)

class ApplicationNotesView(CompanyRequiredMixin, UpdateView):
    model = Application
    template_name = 'companies/application_notes.html'
    fields = ['notes']
    
    def get_queryset(self):
        return Application.objects.filter(
            job_post__company=self.request.user.company
        )

class BulkApplicationActionView(CompanyRequiredMixin, View):
    def post(self, request):
        application_ids = request.POST.getlist('applications')
        action = request.POST.get('action')
        
        applications = Application.objects.filter(
            id__in=application_ids,
            job_post__company=request.user.company
        )
        
        if action == 'shortlist':
            applications.update(status='shortlisted')
            messages.success(request, f'{applications.count()} candidatos preseleccionados.')
        elif action == 'reject':
            applications.update(status='rejected')
            messages.success(request, f'{applications.count()} candidatos rechazados.')
        
        return redirect('companies:all_applications')

class InterviewsView(CompanyRequiredMixin, ListView):
    model = Interview
    template_name = 'companies/interviews.html'
    context_object_name = 'interviews'
    paginate_by = 20
    
    def get_queryset(self):
        return Interview.objects.filter(
            application__job_post__company=self.request.user.company
        ).select_related(
            'application__applicant__user',
            'application__job_post'
        ).order_by('scheduled_date')

class ScheduleInterviewView(CompanyRequiredMixin, CreateView):
    model = Interview
    template_name = 'companies/schedule_interview.html'
    fields = [
        'interview_type', 'scheduled_date', 'duration_minutes',
        'interviewer_name', 'interviewer_email', 'location', 'instructions'
    ]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        application_id = self.request.GET.get('application')
        if application_id:
            context['application'] = get_object_or_404(
                Application,
                pk=application_id,
                job_post__company=self.request.user.company
            )
        return context
    
    def form_valid(self, form):
        application_id = self.request.POST.get('application_id')
        form.instance.application = get_object_or_404(
            Application,
            pk=application_id,
            job_post__company=self.request.user.company
        )
        messages.success(self.request, 'Entrevista programada correctamente.')
        return super().form_valid(form)

class InterviewDetailView(CompanyRequiredMixin, DetailView):
    model = Interview
    template_name = 'companies/interview_detail.html'
    context_object_name = 'interview'
    
    def get_queryset(self):
        return Interview.objects.filter(
            application__job_post__company=self.request.user.company
        )

class EditInterviewView(CompanyRequiredMixin, UpdateView):
    model = Interview
    template_name = 'companies/edit_interview.html'
    fields = [
        'interview_type', 'scheduled_date', 'duration_minutes',
        'interviewer_name', 'interviewer_email', 'location', 'instructions'
    ]
    
    def get_queryset(self):
        return Interview.objects.filter(
            application__job_post__company=self.request.user.company
        )

class CancelInterviewView(CompanyRequiredMixin, View):
    def post(self, request, pk):
        interview = get_object_or_404(
            Interview,
            pk=pk,
            application__job_post__company=request.user.company
        )
        
        reason = request.POST.get('reason', '')
        interview.cancel(reason)
        
        messages.success(request, 'Entrevista cancelada correctamente.')
        return redirect('companies:interviews')

class CompanyAnalyticsView(CompanyRequiredMixin, TemplateView):
    template_name = 'companies/analytics.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company = self.request.user.company
        
        # Período de análisis (últimos 6 meses)
        end_date = timezone.now()
        start_date = end_date - timedelta(days=180)
        
        jobs = JobPost.objects.filter(company=company)
        applications = Application.objects.filter(
            job_post__company=company,
            applied_at__gte=start_date
        )
        
        context.update({
            'date_range': {
                'start': start_date,
                'end': end_date
            },
            'job_performance': self.get_job_performance_data(jobs, applications),
            'application_trends': self.get_application_trends(applications),
            'hiring_funnel': self.get_hiring_funnel_conversion(applications),
        })
        
        return context
    
    def get_job_performance_data(self, jobs, applications):
        job_performance = []
        
        for job in jobs.filter(status='approved')[:10]:
            job_applications = applications.filter(job_post=job)
            
            job_performance.append({
                'job': job,
                'total_applications': job_applications.count(),
                'qualified_applications': job_applications.filter(
                    match_score__gte=70
                ).count(),
                'hired': job_applications.filter(status='accepted').count(),
                'avg_match_score': job_applications.aggregate(
                    avg=Avg('match_score')
                )['avg'] or 0
            })
        
        return sorted(job_performance, key=lambda x: x['total_applications'], reverse=True)
    
    def get_application_trends(self, applications):
        # Agrupar aplicaciones por semana
        trends = {}
        
        for app in applications:
            week_start = app.applied_at.date() - timedelta(
                days=app.applied_at.weekday()
            )
            
            if week_start not in trends:
                trends[week_start] = 0
            trends[week_start] += 1
        
        return sorted(trends.items())
    
    def get_hiring_funnel_conversion(self, applications):
        total = applications.count()
        if total == 0:
            return {}
        
        stages = {
            'applied': applications.filter(status='applied').count(),
            'reviewing': applications.filter(status='reviewing').count(),
            'shortlisted': applications.filter(status='shortlisted').count(),
            'interviewed': applications.filter(status='interviewed').count(),
            'accepted': applications.filter(status='accepted').count(),
        }
        
        # Calcular tasas de conversión
        conversions = {}
        prev_count = total
        
        for stage, count in stages.items():
            if prev_count > 0:
                conversions[stage] = {
                    'count': count,
                    'percentage': (count / total) * 100,
                    'conversion_rate': (count / prev_count) * 100 if prev_count > 0 else 0
                }
            prev_count = count
        
        return conversions

class CompanyReportsView(CompanyRequiredMixin, TemplateView):
    template_name = 'companies/reports.html'

class ExportReportsView(CompanyRequiredMixin, View):
    def get(self, request):
        # Lógica para exportar reportes
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="company_report.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Fecha', 'Vacante', 'Candidatos', 'Contratados'])
        
        return response

class JobStatsView(CompanyRequiredMixin, View):
    def get(self, request):
        company = request.user.company
        jobs = JobPost.objects.filter(company=company)
        
        return JsonResponse({
            'total_jobs': jobs.count(),
            'active_jobs': jobs.filter(is_active=True).count(),
            'draft_jobs': jobs.filter(status='draft').count(),
        })

class HiringStatsView(CompanyRequiredMixin, View):
    def get(self, request):
        company = request.user.company
        applications = Application.objects.filter(job_post__company=company)
        
        return JsonResponse({
            'total_applications': applications.count(),
            'hired': applications.filter(status='accepted').count(),
            'pending': applications.filter(status='applied').count(),
        })

class CompanySettingsView(CompanyRequiredMixin, UpdateView):
    model = Company
    template_name = 'companies/settings.html'
    fields = [
        'email_notifications', 'sms_notifications', 'weekly_digest',
        'is_public'
    ]
    success_url = reverse_lazy('companies:settings')
    
    def get_object(self):
        return self.request.user.company

class TeamManagementView(CompanyRequiredMixin, TemplateView):
    template_name = 'companies/team_management.html'

class PermissionsView(CompanyRequiredMixin, TemplateView):
    template_name = 'companies/permissions.html'

class BillingView(CompanyRequiredMixin, TemplateView):
    template_name = 'companies/billing.html'

class NotificationSettingsView(CompanyRequiredMixin, UpdateView):
    model = Company
    template_name = 'companies/notification_settings.html'
    fields = ['email_notifications', 'sms_notifications', 'weekly_digest']
    success_url = reverse_lazy('companies:notification_settings')
    
    def get_object(self):
        return self.request.user.company

class SubscriptionView(CompanyRequiredMixin, TemplateView):
    template_name = 'companies/subscription.html'

class UpgradeSubscriptionView(CompanyRequiredMixin, TemplateView):
    template_name = 'companies/upgrade_subscription.html'

class CancelSubscriptionView(CompanyRequiredMixin, TemplateView):
    template_name = 'companies/cancel_subscription.html'

# API Views
class CompanyStatsAPIView(CompanyRequiredMixin, View):
    def get(self, request):
        company = request.user.company
        
        jobs = JobPost.objects.filter(company=company)
        applications = Application.objects.filter(job_post__company=company)
        
        return JsonResponse({
            'total_jobs': jobs.count(),
            'active_jobs': jobs.filter(status='approved', is_active=True).count(),
            'total_applications': applications.count(),
            'pending_applications': applications.filter(
                status__in=['applied', 'reviewing']
            ).count(),
            'hired_candidates': applications.filter(status='accepted').count(),
            'avg_match_score': applications.aggregate(
                avg=Avg('match_score')
            )['avg'] or 0,
        })

class CandidateSearchAPIView(CompanyRequiredMixin, View):
    def get(self, request):
        query = request.GET.get('q', '')
        skills = request.GET.getlist('skills')
        experience_min = request.GET.get('experience_min')
        location = request.GET.get('location')
        
        candidates = ApplicantProfile.objects.filter(
            user__is_active=True
        )
        
        if query:
            candidates = candidates.filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(current_position__icontains=query)
            )
        
        if skills:
            candidates = candidates.filter(
                skills__skill__id__in=skills
            ).distinct()
        
        if experience_min:
            candidates = candidates.filter(
                years_experience__gte=experience_min
            )
        
        if location:
            candidates = candidates.filter(
                user__profile__location__icontains=location
            )
        
        candidates_data = []
        for candidate in candidates[:20]:
            candidates_data.append({
                'id': candidate.id,
                'name': f"{candidate.first_name} {candidate.last_name}",
                'current_position': candidate.current_position,
                'years_experience': candidate.years_experience,
                'location': getattr(candidate.user.profile, 'location', ''),
                'profile_score': float(getattr(candidate, 'profile_score', 0)),
                'url': reverse('companies:candidate_detail', kwargs={'pk': candidate.pk})
            })
        
        return JsonResponse({
            'candidates': candidates_data,
            'total': len(candidates_data)
        })

class ApplicationStatusAPIView(CompanyRequiredMixin, View):
    def post(self, request):
        application_id = request.POST.get('application_id')
        new_status = request.POST.get('status')
        
        try:
            application = Application.objects.get(
                id=application_id,
                job_post__company=request.user.company
            )
            
            if new_status in dict(Application.STATUS_CHOICES):
                application.status = new_status
                application.save()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Estado actualizado correctamente'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Estado inválido'
                })
                
        except Application.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Aplicación no encontrada'
            })

# Views públicas
class CompanyDirectoryView(ListView):
    model = Company
    template_name = 'companies/directory.html'
    context_object_name = 'companies'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Company.objects.filter(
            user__is_active=True,
            is_public=True
        ).annotate(
            active_jobs_count=Count(
                'jobpost',
                filter=Q(jobpost__status='approved', jobpost__is_active=True)
            )
        ).filter(active_jobs_count__gt=0)
        
        # Filtros
        industry = self.request.GET.get('industry')
        if industry:
            queryset = queryset.filter(industry=industry)
        
        size = self.request.GET.get('size')
        if size:
            queryset = queryset.filter(size=size)
        
        location = self.request.GET.get('location')
        if location:
            queryset = queryset.filter(location__icontains=location)
        
        return queryset.order_by('-active_jobs_count')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context.update({
            'industries': Company.objects.values_list('industry', flat=True).distinct(),
            'company_sizes': Company.SIZE_CHOICES,
            'filters': self.request.GET,
        })
        
        return context

class PublicCompanyProfileView(DetailView):
    model = Company
    template_name = 'companies/public_profile.html'
    context_object_name = 'company'
    
    def get_queryset(self):
        return Company.objects.filter(is_public=True, user__is_active=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company = self.object
        
        context.update({
            'active_jobs': JobPost.objects.filter(
                company=company,
                status='approved',
                is_active=True
            ).order_by('-created_at'),
            'total_hires': Application.objects.filter(
                job_post__company=company,
                status='accepted'
            ).count(),
            'company_stats': {
                'total_jobs_posted': JobPost.objects.filter(
                    company=company,
                    status='approved'
                ).count(),
                'active_positions': JobPost.objects.filter(
                    company=company,
                    status='approved',
                    is_active=True
                ).count(),
            }
        })
        
        return context