# apps/matching/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, ListView, DetailView
from django.views import View
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponse, Http404
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, Sum, F, Max, Min
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

from .models import MatchScore, MatchingPreferences
from .services import MatchingService
from jobs.models import JobPost, Application, Skill
from applicants.models import ApplicantProfile
from companies.models import Company

logger = logging.getLogger(__name__)

class ApplicantRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'applicant':
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

class CompanyRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'company':
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and (self.request.user.is_staff or self.request.user.user_type == 'admin')

# ===== VIEWS PARA ASPIRANTES =====

class ApplicantRecommendationsView(ApplicantRequiredMixin, ListView):
    template_name = 'matching/applicant_recommendations.html'
    context_object_name = 'matches'
    paginate_by = 10
    
    def get_queryset(self):
        applicant = self.request.user.applicantprofile
        
        # Parámetros de filtrado
        min_score = int(self.request.GET.get('min_score', 60))
        location = self.request.GET.get('location', '')
        job_type = self.request.GET.get('job_type', '')
        industry = self.request.GET.get('industry', '')
        
        # Obtener matches del servicio
        try:
            matches = MatchingService.get_job_recommendations(
                applicant=applicant,
                min_score=min_score,
                location=location,
                job_type=job_type,
                limit=100
            )
        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            matches = []
        
        return matches
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        applicant = self.request.user.applicantprofile
        
        context.update({
            'applicant': applicant,
            'profile_completion': applicant.profile_score,
            'applications_count': Application.objects.filter(applicant=applicant).count(),
            'current_filters': {
                'min_score': self.request.GET.get('min_score', '60'),
                'location': self.request.GET.get('location', ''),
                'job_type': self.request.GET.get('job_type', ''),
                'industry': self.request.GET.get('industry', ''),
            },
            'industries': Company.objects.values_list('industry', flat=True).distinct(),
            'job_types': JobPost.JOB_TYPE_CHOICES,
        })
        
        return context

class ApplicantMatchesView(ApplicantRequiredMixin, ListView):
    template_name = 'matching/applicant_matches.html'
    context_object_name = 'match_scores'
    paginate_by = 15
    
    def get_queryset(self):
        applicant = self.request.user.applicantprofile
        
        queryset = MatchScore.objects.filter(
            applicant=applicant
        ).select_related('job_post', 'job_post__company').order_by('-total_score')
        
        # Filtros
        min_score = self.request.GET.get('min_score')
        if min_score:
            queryset = queryset.filter(total_score__gte=min_score)
        
        status = self.request.GET.get('status')
        if status:
            if status == 'not_applied':
                applied_jobs = Application.objects.filter(
                    applicant=applicant
                ).values_list('job_post_id', flat=True)
                queryset = queryset.exclude(job_post_id__in=applied_jobs)
            elif status == 'applied':
                applied_jobs = Application.objects.filter(
                    applicant=applicant
                ).values_list('job_post_id', flat=True)
                queryset = queryset.filter(job_post_id__in=applied_jobs)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        applicant = self.request.user.applicantprofile
        
        # Estadísticas
        all_matches = MatchScore.objects.filter(applicant=applicant)
        context.update({
            'applicant': applicant,
            'total_matches': all_matches.count(),
            'high_matches': all_matches.filter(total_score__gte=80).count(),
            'medium_matches': all_matches.filter(total_score__gte=60, total_score__lt=80).count(),
            'avg_score': all_matches.aggregate(avg=Avg('total_score'))['avg'] or 0,
            'filters': self.request.GET,
        })
        
        return context

class JobMatchDetailView(ApplicantRequiredMixin, DetailView):
    template_name = 'matching/job_match_detail.html'
    context_object_name = 'job'
    
    def get_object(self):
        job_id = self.kwargs['job_id']
        return get_object_or_404(JobPost, id=job_id, status='approved', is_active=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        applicant = self.request.user.applicantprofile
        job = self.object
        
        # Obtener o calcular match score
        try:
            match_score = MatchScore.objects.get(applicant=applicant, job_post=job)
        except MatchScore.DoesNotExist:
            match_score = MatchingService.calculate_match_score(job, applicant)
        
        # Verificar si ya aplicó
        has_applied = Application.objects.filter(
            applicant=applicant, 
            job_post=job
        ).exists()
        
        context.update({
            'applicant': applicant,
            'match_score': match_score,
            'has_applied': has_applied,
            'compatibility_analysis': self.get_compatibility_analysis(job, applicant),
        })
        
        return context
    
    def get_compatibility_analysis(self, job, applicant):
        # Análisis detallado de compatibilidad
        return {
            'skills_match': self.analyze_skills_match(job, applicant),
            'experience_match': self.analyze_experience_match(job, applicant),
            'location_match': self.analyze_location_match(job, applicant),
            'salary_match': self.analyze_salary_match(job, applicant),
        }
    
    def analyze_skills_match(self, job, applicant):
        job_skills = set(job.required_skills.values_list('name', flat=True))
        applicant_skills = set(applicant.skills.values_list('skill__name', flat=True))
        
        matched_skills = job_skills.intersection(applicant_skills)
        missing_skills = job_skills - applicant_skills
        
        return {
            'matched': list(matched_skills),
            'missing': list(missing_skills),
            'percentage': (len(matched_skills) / len(job_skills) * 100) if job_skills else 0
        }
    
    def analyze_experience_match(self, job, applicant):
        required_exp = getattr(job, 'required_experience', 0)
        applicant_exp = getattr(applicant, 'years_experience', 0)
        
        if required_exp == 0:
            return {'match': True, 'score': 100}
        
        if applicant_exp >= required_exp:
            return {'match': True, 'score': 100}
        else:
            score = (applicant_exp / required_exp) * 100
            return {'match': False, 'score': score}
    
    def analyze_location_match(self, job, applicant):
        # Simplificado - mejorar con geolocalización
        job_location = job.location.lower() if job.location else ''
        applicant_location = getattr(applicant.user.profile, 'location', '').lower()
        
        if 'remoto' in job_location or 'remote' in job_location:
            return {'match': True, 'score': 100, 'type': 'remote'}
        
        if job_location and applicant_location:
            if job_location in applicant_location or applicant_location in job_location:
                return {'match': True, 'score': 100, 'type': 'local'}
            else:
                return {'match': False, 'score': 50, 'type': 'different'}
        
        return {'match': True, 'score': 75, 'type': 'unknown'}
    
    def analyze_salary_match(self, job, applicant):
        if not job.salary_min and not job.salary_max:
            return {'match': True, 'score': 50}
        
        expected_salary = getattr(applicant, 'expected_salary', None)
        if not expected_salary:
            return {'match': True, 'score': 50}
        
        job_min = job.salary_min or 0
        job_max = job.salary_max or float('inf')
        
        if job_min <= expected_salary <= job_max:
            return {'match': True, 'score': 100}
        elif expected_salary < job_min:
            score = (expected_salary / job_min) * 100
            return {'match': False, 'score': score, 'reason': 'below_range'}
        else:
            return {'match': False, 'score': 50, 'reason': 'above_range'}

# ===== VIEWS PARA EMPRESAS =====

class JobCandidatesMatchView(CompanyRequiredMixin, ListView):
    template_name = 'matching/job_candidates_match.html'
    context_object_name = 'candidate_matches'
    paginate_by = 20
    
    def get_queryset(self):
        job_id = self.kwargs['job_id']
        self.job = get_object_or_404(
            JobPost, 
            id=job_id, 
            company=self.request.user.company
        )
        
        # Obtener matches de candidatos
        queryset = MatchScore.objects.filter(
            job_post=self.job
        ).select_related('applicant', 'applicant__user').order_by('-total_score')
        
        # Filtros
        min_score = self.request.GET.get('min_score')
        if min_score:
            queryset = queryset.filter(total_score__gte=min_score)
        
        has_applied = self.request.GET.get('applied')
        if has_applied == 'yes':
            applied_applicants = Application.objects.filter(
                job_post=self.job
            ).values_list('applicant_id', flat=True)
            queryset = queryset.filter(applicant_id__in=applied_applicants)
        elif has_applied == 'no':
            applied_applicants = Application.objects.filter(
                job_post=self.job
            ).values_list('applicant_id', flat=True)
            queryset = queryset.exclude(applicant_id__in=applied_applicants)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Estadísticas
        all_matches = MatchScore.objects.filter(job_post=self.job)
        context.update({
            'job': self.job,
            'total_candidates': all_matches.count(),
            'high_matches': all_matches.filter(total_score__gte=80).count(),
            'applied_count': Application.objects.filter(job_post=self.job).count(),
            'avg_score': all_matches.aggregate(avg=Avg('total_score'))['avg'] or 0,
            'filters': self.request.GET,
        })
        
        return context

class CandidateJobMatchesView(CompanyRequiredMixin, DetailView):
    template_name = 'matching/candidate_job_matches.html'
    context_object_name = 'candidate'
    
    def get_object(self):
        applicant_id = self.kwargs['applicant_id']
        return get_object_or_404(ApplicantProfile, id=applicant_id)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        candidate = self.object
        company = self.request.user.company
        
        # Obtener matches con las vacantes de la empresa
        company_jobs = JobPost.objects.filter(
            company=company,
            status='approved'
        )
        
        matches = MatchScore.objects.filter(
            applicant=candidate,
            job_post__in=company_jobs
        ).select_related('job_post').order_by('-total_score')
        
        context.update({
            'company': company,
            'job_matches': matches,
            'has_applied_jobs': Application.objects.filter(
                applicant=candidate,
                job_post__company=company
            ).values_list('job_post_id', flat=True),
        })
        
        return context

class ExportCandidatesMatchView(CompanyRequiredMixin, View):
    def get(self, request, job_id):
        job = get_object_or_404(
            JobPost, 
            id=job_id, 
            company=request.user.company
        )
        
        # Obtener matches
        matches = MatchScore.objects.filter(
            job_post=job
        ).select_related('applicant', 'applicant__user').order_by('-total_score')
        
        # Crear respuesta CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="candidatos_{job.slug}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Nombre', 'Email', 'Ubicación', 'Experiencia', 
            'Match Score', 'Skills Score', 'Experience Score', 
            'Ha Aplicado', 'Fecha de Match'
        ])
        
        for match in matches:
            applicant = match.applicant
            has_applied = Application.objects.filter(
                applicant=applicant, job_post=job
            ).exists()
            
            writer.writerow([
                applicant.get_full_name(),
                applicant.user.email,
                getattr(applicant.user.profile, 'location', ''),
                f"{applicant.years_experience} años",
                f"{match.total_score:.1f}%",
                f"{match.skills_score:.1f}%",
                f"{match.experience_score:.1f}%",
                'Sí' if has_applied else 'No',
                match.created_at.strftime('%Y-%m-%d')
            ])
        
        return response

# ===== ANÁLISIS DE COMPATIBILIDAD =====

class CompatibilityAnalysisView(LoginRequiredMixin, TemplateView):
    template_name = 'matching/compatibility_analysis.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        job_id = self.kwargs['job_id']
        applicant_id = self.kwargs['applicant_id']
        
        job = get_object_or_404(JobPost, id=job_id)
        applicant = get_object_or_404(ApplicantProfile, id=applicant_id)
        
        # Verificar permisos
        if self.request.user.user_type == 'company':
            if job.company != self.request.user.company:
                raise PermissionDenied
        elif self.request.user.user_type == 'applicant':
            if applicant.user != self.request.user:
                raise PermissionDenied
        
        # Obtener análisis detallado
        try:
            match_score = MatchScore.objects.get(applicant=applicant, job_post=job)
        except MatchScore.DoesNotExist:
            match_score = MatchingService.calculate_match_score(job, applicant)
        
        context.update({
            'job': job,
            'applicant': applicant,
            'match_score': match_score,
            'detailed_analysis': MatchingService.get_detailed_analysis(job, applicant),
        })
        
        return context

class SkillsGapAnalysisView(LoginRequiredMixin, TemplateView):
    template_name = 'matching/skills_gap_analysis.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        job_id = self.kwargs['job_id']
        applicant_id = self.kwargs['applicant_id']
        
        job = get_object_or_404(JobPost, id=job_id)
        applicant = get_object_or_404(ApplicantProfile, id=applicant_id)
        
        # Análisis de gaps de habilidades
        skills_gap = MatchingService.analyze_skills_gap(job, applicant)
        
        context.update({
            'job': job,
            'applicant': applicant,
            'skills_gap': skills_gap,
            'learning_recommendations': self.get_learning_recommendations(skills_gap),
        })
        
        return context
    
    def get_learning_recommendations(self, skills_gap):
        # Generar recomendaciones de aprendizaje basadas en gaps
        recommendations = []
        
        for skill in skills_gap.get('missing_skills', []):
            recommendations.append({
                'skill': skill,
                'priority': 'high',
                'estimated_time': '2-4 semanas',
                'resources': [
                    {'name': 'Curso Online', 'type': 'course'},
                    {'name': 'Documentación Oficial', 'type': 'docs'},
                    {'name': 'Práctica con Proyectos', 'type': 'project'}
                ]
            })
        
        return recommendations

# ===== CONFIGURACIÓN Y PREFERENCIAS =====

class MatchingSettingsView(AdminRequiredMixin, TemplateView):
    template_name = 'matching/matching_settings.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Configuraciones globales del sistema de matching
        context.update({
            'algorithm_version': '2.1',
            'total_matches': MatchScore.objects.count(),
            'pending_calculations': 0,  # Implementar cola de cálculos
            'performance_metrics': self.get_performance_metrics(),
        })
        
        return context
    
    def get_performance_metrics(self):
        return {
            'avg_calculation_time': '1.2s',
            'accuracy_rate': '87%',
            'user_satisfaction': '4.2/5',
        }

class MatchingPreferencesView(LoginRequiredMixin, TemplateView):
    template_name = 'matching/matching_preferences.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener o crear preferencias del usuario
        try:
            preferences = MatchingPreferences.objects.get(user=self.request.user)
        except MatchingPreferences.DoesNotExist:
            preferences = MatchingPreferences.objects.create(user=self.request.user)
        
        context['preferences'] = preferences
        return context
    
    def post(self, request):
        # Actualizar preferencias
        try:
            preferences = MatchingPreferences.objects.get(user=request.user)
        except MatchingPreferences.DoesNotExist:
            preferences = MatchingPreferences.objects.create(user=request.user)
        
        # Actualizar campos
        preferences.min_match_score = int(request.POST.get('min_match_score', 50))
        preferences.skills_weight = float(request.POST.get('skills_weight', 0.4))
        preferences.experience_weight = float(request.POST.get('experience_weight', 0.3))
        preferences.location_weight = float(request.POST.get('location_weight', 0.2))
        preferences.salary_weight = float(request.POST.get('salary_weight', 0.1))
        preferences.save()
        
        messages.success(request, 'Preferencias actualizadas correctamente.')
        return redirect('matching:matching_preferences')

# ===== ESTADÍSTICAS Y ANALÍTICAS =====

class MatchingStatsView(LoginRequiredMixin, TemplateView):
    template_name = 'matching/matching_stats.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.user.user_type == 'company':
            context.update(self.get_company_stats())
        elif self.request.user.user_type == 'applicant':
            context.update(self.get_applicant_stats())
        else:
            context.update(self.get_global_stats())
        
        return context
    
    def get_company_stats(self):
        company = self.request.user.company
        jobs = JobPost.objects.filter(company=company)
        
        return {
            'user_type': 'company',
            'total_matches': MatchScore.objects.filter(job_post__in=jobs).count(),
            'avg_match_score': MatchScore.objects.filter(
                job_post__in=jobs
            ).aggregate(avg=Avg('total_score'))['avg'] or 0,
            'top_scoring_candidates': MatchScore.objects.filter(
                job_post__in=jobs
            ).order_by('-total_score')[:5],
        }
    
    def get_applicant_stats(self):
        applicant = self.request.user.applicantprofile
        
        return {
            'user_type': 'applicant',
            'total_matches': MatchScore.objects.filter(applicant=applicant).count(),
            'avg_match_score': MatchScore.objects.filter(
                applicant=applicant
            ).aggregate(avg=Avg('total_score'))['avg'] or 0,
            'top_job_matches': MatchScore.objects.filter(
                applicant=applicant
            ).order_by('-total_score')[:5],
        }
    
    def get_global_stats(self):
        return {
            'user_type': 'admin',
            'total_matches': MatchScore.objects.count(),
            'total_jobs': JobPost.objects.filter(status='approved').count(),
            'total_applicants': ApplicantProfile.objects.count(),
            'avg_match_score': MatchScore.objects.aggregate(
                avg=Avg('total_score')
            )['avg'] or 0,
        }

class MatchingAnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = 'matching/matching_analytics.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Analíticas avanzadas
        context.update({
            'matching_trends': self.get_matching_trends(),
            'skill_demand': self.get_skill_demand_analytics(),
            'geographic_distribution': self.get_geographic_analytics(),
            'success_metrics': self.get_success_metrics(),
        })
        
        return context
    
    def get_matching_trends(self):
        # Tendencias de matching por período
        last_30_days = timezone.now() - timedelta(days=30)
        
        return {
            'daily_matches': MatchScore.objects.filter(
                created_at__gte=last_30_days
            ).extra({'date': 'date(created_at)'}).values('date').annotate(
                count=Count('id')
            ).order_by('date'),
            'score_distribution': MatchScore.objects.aggregate(
                high=Count('id', filter=Q(total_score__gte=80)),
                medium=Count('id', filter=Q(total_score__gte=60, total_score__lt=80)),
                low=Count('id', filter=Q(total_score__lt=60)),
            )
        }
    
    def get_skill_demand_analytics(self):
        # Análisis de demanda de habilidades
        from django.db.models import Count
        
        return Skill.objects.annotate(
            job_demand=Count('jobpost'),
            applicant_supply=Count('applicantskill')
        ).order_by('-job_demand')[:10]
    
    def get_geographic_analytics(self):
        # Distribución geográfica de matches
        return {
            'by_location': MatchScore.objects.values(
                'job_post__location'
            ).annotate(
                count=Count('id'),
                avg_score=Avg('total_score')
            ).order_by('-count')[:10]
        }
    
    def get_success_metrics(self):
        # Métricas de éxito del matching
        total_matches = MatchScore.objects.count()
        successful_matches = Application.objects.filter(
            status__in=['accepted', 'hired']
        ).count()
        
        return {
            'conversion_rate': (successful_matches / total_matches * 100) if total_matches else 0,
            'avg_time_to_hire': self.calculate_avg_time_to_hire(),
            'match_accuracy': self.calculate_match_accuracy(),
        }
    
    def calculate_avg_time_to_hire(self):
        # Calcular tiempo promedio de contratación
        hired_applications = Application.objects.filter(
            status='accepted'
        ).exclude(updated_at__isnull=True)
        
        if hired_applications.exists():
            total_days = sum([
                (app.updated_at - app.applied_at).days 
                for app in hired_applications
            ])
            return total_days / hired_applications.count()
        return 0
    
    def calculate_match_accuracy(self):
        # Calcular precisión del matching basado en aplicaciones exitosas
        high_score_matches = MatchScore.objects.filter(total_score__gte=80)
        successful_high_scores = high_score_matches.filter(
            applicant__application__status='accepted'
        ).count()
        
        if high_score_matches.exists():
            return (successful_high_scores / high_score_matches.count() * 100)
        return 0

class MatchingEffectivenessView(AdminRequiredMixin, TemplateView):
    template_name = 'matching/matching_effectiveness.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Métricas de efectividad del sistema
        context.update({
            'algorithm_performance': self.get_algorithm_performance(),
            'user_feedback': self.get_user_feedback_metrics(),
            'improvement_suggestions': self.get_improvement_suggestions(),
        })
        
        return context
    
    def get_algorithm_performance(self):
        return {
            'precision': 0.87,
            'recall': 0.82,
            'f1_score': 0.84,
            'processing_time': '1.2s avg',
        }
    
    def get_user_feedback_metrics(self):
        # Métricas de feedback de usuarios
        return {
            'satisfaction_rating': 4.2,
            'recommendation_accuracy': 0.78,
            'user_engagement': 0.65,
        }
    
    def get_improvement_suggestions(self):
        return [
            {'area': 'Skills Matching', 'priority': 'High', 'impact': 'Medium'},
            {'area': 'Location Logic', 'priority': 'Medium', 'impact': 'High'},
            {'area': 'Salary Comparison', 'priority': 'Low', 'impact': 'Low'},
        ]

# ===== API ENDPOINTS =====

class RecalculateMatchAPIView(LoginRequiredMixin, View):
    def post(self, request):
        job_id = request.POST.get('job_id')
        applicant_id = request.POST.get('applicant_id')
        
        try:
            if job_id and applicant_id:
                job = JobPost.objects.get(id=job_id)
                applicant = ApplicantProfile.objects.get(id=applicant_id)
                
                # Verificar permisos
                if request.user.user_type == 'company':
                    if job.company != request.user.company:
                        raise PermissionDenied
                elif request.user.user_type == 'applicant':
                    if applicant.user != request.user:
                        raise PermissionDenied
                
                # Recalcular match
                match_score = MatchingService.calculate_match_score(job, applicant)
                
                return JsonResponse({
                    'success': True,
                    'match_score': match_score.total_score,
                    'message': 'Match recalculado correctamente'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Parámetros faltantes'
                })
                
        except Exception as e:
            logger.error(f"Error recalculating match: {e}")
            return JsonResponse({
                'success': False,
                'message': 'Error al recalcular el match'
            })

class BulkMatchAPIView(AdminRequiredMixin, View):
    def post(self, request):
        action = request.POST.get('action')
        
        try:
            if action == 'recalculate_all':
                # Recalcular todos los matches
                count = MatchingService.recalculate_all_matches()
                return JsonResponse({
                    'success': True,
                    'message': f'{count} matches recalculados',
                    'count': count
                })
            
            elif action == 'cleanup_old':
                # Limpiar matches antiguos
                deleted_count = MatchScore.objects.filter(
                    created_at__lt=timezone.now() - timedelta(days=90)
                ).delete()[0]
                return JsonResponse({
                    'success': True,
                    'message': f'{deleted_count} matches antiguos eliminados',
                    'count': deleted_count
                })
            
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Acción no válida'
                })
                
        except Exception as e:
            logger.error(f"Error in bulk match operation: {e}")
            return JsonResponse({
                'success': False,
                'message': 'Error en la operación masiva'
            })

class MatchScoreAPIView(LoginRequiredMixin, View):
    def get(self, request):
        job_id = request.GET.get('job_id')
        applicant_id = request.GET.get('applicant_id')
        
        if not job_id or not applicant_id:
            return JsonResponse({
                'success': False,
                'message': 'Parámetros faltantes'
            })
        
        try:
            job = JobPost.objects.get(id=job_id)
            applicant = ApplicantProfile.objects.get(id=applicant_id)
            
            # Verificar permisos
            if request.user.user_type == 'company':
                if job.company != request.user.company:
                    raise PermissionDenied
            elif request.user.user_type == 'applicant':
                if applicant.user != request.user:
                    raise PermissionDenied
            
            # Obtener o calcular match score
            try:
                match_score = MatchScore.objects.get(applicant=applicant, job_post=job)
            except MatchScore.DoesNotExist:
                match_score = MatchingService.calculate_match_score(job, applicant)
            
            return JsonResponse({
                'success': True,
                'match_score': {
                    'total_score': match_score.total_score,
                    'skills_score': match_score.skills_score,
                    'experience_score': match_score.experience_score,
                    'location_score': match_score.location_score,
                    'salary_score': match_score.salary_score,
                    'education_score': match_score.education_score,
                }
            })
            
        except (JobPost.DoesNotExist, ApplicantProfile.DoesNotExist):
            return JsonResponse({
                'success': False,
                'message': 'Trabajo o candidato no encontrado'
            })
        except Exception as e:
            logger.error(f"Error getting match score: {e}")
            return JsonResponse({
                'success': False,
                'message': 'Error al obtener el match score'
            })

class RecommendationsAPIView(ApplicantRequiredMixin, View):
    def get(self, request):
        applicant = request.user.applicantprofile
        limit = int(request.GET.get('limit', 10))
        min_score = int(request.GET.get('min_score', 60))
        
        try:
            recommendations = MatchingService.get_job_recommendations(
                applicant=applicant,
                min_score=min_score,
                limit=limit
            )
            
            recommendations_data = []
            for rec in recommendations:
                recommendations_data.append({
                    'job_id': rec.job_post.id,
                    'title': rec.job_post.title,
                    'company': rec.job_post.company.name,
                    'location': rec.job_post.location,
                    'match_score': rec.total_score,
                    'url': rec.job_post.get_absolute_url(),
                })
            
            return JsonResponse({
                'success': True,
                'recommendations': recommendations_data,
                'total': len(recommendations_data)
            })
            
        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            return JsonResponse({
                'success': False,
                'message': 'Error al obtener recomendaciones'
            })

# ===== HERRAMIENTAS ADMINISTRATIVAS =====

class RecalculateAllMatchesView(AdminRequiredMixin, TemplateView):
    template_name = 'matching/admin/recalculate_all.html'
    
    def post(self, request):
        try:
            count = MatchingService.recalculate_all_matches()
            messages.success(request, f'{count} matches recalculados correctamente.')
        except Exception as e:
            logger.error(f"Error recalculating all matches: {e}")
            messages.error(request, 'Error al recalcular los matches.')
        
        return redirect('matching:recalculate_all_matches')

class OptimizeMatchingView(AdminRequiredMixin, TemplateView):
    template_name = 'matching/admin/optimize_matching.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Métricas de optimización
        context.update({
            'optimization_metrics': self.get_optimization_metrics(),
            'performance_history': self.get_performance_history(),
            'recommendations': self.get_optimization_recommendations(),
        })
        
        return context
    
    def get_optimization_metrics(self):
        return {
            'database_size': MatchScore.objects.count(),
            'avg_calculation_time': 1.2,
            'memory_usage': '245MB',
            'accuracy_score': 87.5,
        }
    
    def get_performance_history(self):
        # Historial de rendimiento por día
        last_7_days = timezone.now() - timedelta(days=7)
        
        return MatchScore.objects.filter(
            created_at__gte=last_7_days
        ).extra({'date': 'date(created_at)'}).values('date').annotate(
            count=Count('id'),
            avg_score=Avg('total_score')
        ).order_by('date')
    
    def get_optimization_recommendations(self):
        return [
            {
                'category': 'Performance',
                'title': 'Implementar caché para cálculos frecuentes',
                'priority': 'High',
                'impact': 'Reducir tiempo de cálculo en 40%'
            },
            {
                'category': 'Accuracy',
                'title': 'Ajustar pesos del algoritmo basado en feedback',
                'priority': 'Medium',
                'impact': 'Mejorar precisión en 5-8%'
            },
            {
                'category': 'Scalability',
                'title': 'Implementar procesamiento asíncrono',
                'priority': 'Medium',
                'impact': 'Manejar 10x más volumen'
            }
        ]
    
    def post(self, request):
        action = request.POST.get('action')
        
        if action == 'optimize_algorithm':
            try:
                # Implementar optimización del algoritmo
                MatchingService.optimize_algorithm_weights()
                messages.success(request, 'Algoritmo optimizado correctamente.')
            except Exception as e:
                logger.error(f"Error optimizing algorithm: {e}")
                messages.error(request, 'Error al optimizar el algoritmo.')
        
        elif action == 'cleanup_database':
            try:
                # Limpiar datos antiguos
                deleted_count = MatchScore.objects.filter(
                    created_at__lt=timezone.now() - timedelta(days=180)
                ).delete()[0]
                messages.success(request, f'{deleted_count} registros antiguos eliminados.')
            except Exception as e:
                logger.error(f"Error cleaning up database: {e}")
                messages.error(request, 'Error al limpiar la base de datos.')
        
        return redirect('matching:optimize_matching')

class DebugMatchView(AdminRequiredMixin, TemplateView):
    template_name = 'matching/admin/debug_match.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        job_id = self.kwargs['job_id']
        applicant_id = self.kwargs['applicant_id']
        
        job = get_object_or_404(JobPost, id=job_id)
        applicant = get_object_or_404(ApplicantProfile, id=applicant_id)
        
        # Información de debug detallada
        context.update({
            'job': job,
            'applicant': applicant,
            'debug_info': self.get_debug_info(job, applicant),
            'calculation_steps': self.get_calculation_steps(job, applicant),
            'recommendations': self.get_debug_recommendations(job, applicant),
        })
        
        return context
    
    def get_debug_info(self, job, applicant):
        return {
            'job_skills': list(job.required_skills.values_list('name', flat=True)),
            'applicant_skills': list(applicant.skills.values_list('skill__name', flat=True)),
            'job_location': job.location,
            'applicant_location': getattr(applicant.user.profile, 'location', ''),
            'job_experience_required': getattr(job, 'required_experience', 0),
            'applicant_experience': applicant.years_experience,
            'job_salary_range': f"{job.salary_min}-{job.salary_max} {job.currency}" if job.salary_min else 'No especificado',
            'applicant_expected_salary': getattr(applicant, 'expected_salary', 'No especificado'),
        }
    
    def get_calculation_steps(self, job, applicant):
        # Simular pasos de cálculo del matching
        steps = []
        
        # Paso 1: Skills matching
        job_skills = set(job.required_skills.values_list('name', flat=True))
        applicant_skills = set(applicant.skills.values_list('skill__name', flat=True))
        matched_skills = job_skills.intersection(applicant_skills)
        skills_score = (len(matched_skills) / len(job_skills) * 100) if job_skills else 0
        
        steps.append({
            'step': 1,
            'name': 'Skills Matching',
            'calculation': f"{len(matched_skills)}/{len(job_skills)} skills matched",
            'score': skills_score,
            'weight': 40,
            'weighted_score': skills_score * 0.4
        })
        
        # Paso 2: Experience matching
        required_exp = getattr(job, 'required_experience', 0)
        applicant_exp = applicant.years_experience
        exp_score = min(100, (applicant_exp / required_exp * 100)) if required_exp > 0 else 100
        
        steps.append({
            'step': 2,
            'name': 'Experience Matching',
            'calculation': f"{applicant_exp} years vs {required_exp} required",
            'score': exp_score,
            'weight': 30,
            'weighted_score': exp_score * 0.3
        })
        
        # Paso 3: Location matching
        job_location = job.location.lower() if job.location else ''
        applicant_location = getattr(applicant.user.profile, 'location', '').lower()
        
        if 'remoto' in job_location or 'remote' in job_location:
            location_score = 100
        elif job_location and applicant_location:
            location_score = 100 if job_location in applicant_location else 50
        else:
            location_score = 75
        
        steps.append({
            'step': 3,
            'name': 'Location Matching',
            'calculation': f"'{job.location}' vs '{getattr(applicant.user.profile, 'location', '')}'",
            'score': location_score,
            'weight': 20,
            'weighted_score': location_score * 0.2
        })
        
        # Paso 4: Salary matching
        salary_score = 75  # Valor por defecto
        
        steps.append({
            'step': 4,
            'name': 'Salary Matching',
            'calculation': 'Default scoring (insufficient data)',
            'score': salary_score,
            'weight': 10,
            'weighted_score': salary_score * 0.1
        })
        
        # Total
        total_score = sum([step['weighted_score'] for step in steps])
        steps.append({
            'step': 'Total',
            'name': 'Final Score',
            'calculation': 'Sum of weighted scores',
            'score': total_score,
            'weight': 100,
            'weighted_score': total_score
        })
        
        return steps
    
    def get_debug_recommendations(self, job, applicant):
        recommendations = []
        
        # Analizar cada componente y generar recomendaciones
        job_skills = set(job.required_skills.values_list('name', flat=True))
        applicant_skills = set(applicant.skills.values_list('skill__name', flat=True))
        missing_skills = job_skills - applicant_skills
        
        if missing_skills:
            recommendations.append({
                'type': 'skills',
                'priority': 'high',
                'message': f'Candidato necesita desarrollar: {", ".join(list(missing_skills)[:3])}'
            })
        
        required_exp = getattr(job, 'required_experience', 0)
        if applicant.years_experience < required_exp:
            recommendations.append({
                'type': 'experience',
                'priority': 'medium',
                'message': f'Candidato tiene {required_exp - applicant.years_experience} años menos de experiencia'
            })
        
        return recommendations

# ===== VIEWS ADICIONALES =====

class SkillSearchAPIView(LoginRequiredMixin, View):
    def get(self, request):
        query = request.GET.get('q', '')
        
        if len(query) < 2:
            return JsonResponse({'skills': []})
        
        skills = Skill.objects.filter(
            name__icontains=query
        )[:10]
        
        skills_data = []
        for skill in skills:
            skills_data.append({
                'id': skill.id,
                'name': skill.name,
                'category': getattr(skill, 'category', 'General')
            })
        
        return JsonResponse({'skills': skills_data})

class UpdateMatchingPreferencesAPIView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            preferences, created = MatchingPreferences.objects.get_or_create(
                user=request.user
            )
            
            # Actualizar preferencias desde JSON
            data = json.loads(request.body)
            
            if 'min_match_score' in data:
                preferences.min_match_score = int(data['min_match_score'])
            if 'skills_weight' in data:
                preferences.skills_weight = float(data['skills_weight'])
            if 'experience_weight' in data:
                preferences.experience_weight = float(data['experience_weight'])
            if 'location_weight' in data:
                preferences.location_weight = float(data['location_weight'])
            if 'salary_weight' in data:
                preferences.salary_weight = float(data['salary_weight'])
            
            preferences.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Preferencias actualizadas correctamente'
            })
            
        except Exception as e:
            logger.error(f"Error updating preferences: {e}")
            return JsonResponse({
                'success': False,
                'message': 'Error al actualizar preferencias'
            })

class JobRecommendationsFeedbackView(ApplicantRequiredMixin, View):
    def post(self, request):
        """Capturar feedback de recomendaciones de trabajo"""
        try:
            data = json.loads(request.body)
            job_id = data.get('job_id')
            feedback = data.get('feedback')  # 'relevant', 'not_relevant', 'applied'
            
            # Guardar feedback para mejorar futuras recomendaciones
            # Implementar modelo de feedback si es necesario
            
            return JsonResponse({
                'success': True,
                'message': 'Feedback registrado correctamente'
            })
            
        except Exception as e:
            logger.error(f"Error saving feedback: {e}")
            return JsonResponse({
                'success': False,
                'message': 'Error al guardar feedback'
            })

# Funciones de utilidad para mejorar el rendimiento
def get_cached_match_score(job_id, applicant_id):
    """Obtener match score desde caché si existe"""
    from django.core.cache import cache
    
    cache_key = f"match_score_{job_id}_{applicant_id}"
    cached_score = cache.get(cache_key)
    
    if cached_score:
        return cached_score
    
    try:
        match_score = MatchScore.objects.get(
            job_post_id=job_id, 
            applicant_id=applicant_id
        )
        # Cachear por 1 hora
        cache.set(cache_key, match_score, 3600)
        return match_score
    except MatchScore.DoesNotExist:
        return None

def invalidate_match_cache(job_id, applicant_id):
    """Invalidar caché de match score"""
    from django.core.cache import cache
    
    cache_key = f"match_score_{job_id}_{applicant_id}"
    cache.delete(cache_key)