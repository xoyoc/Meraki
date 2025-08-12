from django.shortcuts import render
from django.views.generic import TemplateView
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

User = get_user_model()

class HomeView(TemplateView):
    template_name = 'core/home.html'
    
    @method_decorator(cache_page(60 * 15))  # Cache por 15 minutos
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Estadísticas para el home
        try:
            # Importar modelos solo si están disponibles
            from jobs.models import JobPost, Application
            from applicants.models import ApplicantProfile
            from companies.models import Company
            
            context.update({
                'stats': {
                    'total_professionals': ApplicantProfile.objects.filter(user__is_active=True).count(),
                    'total_companies': Company.objects.filter(user__is_active=True).count(),
                    'active_jobs': JobPost.objects.filter(status='approved', is_active=True).count(),
                    'total_applications': Application.objects.count(),
                }
            })
        except ImportError:
            # Si los modelos no existen aún, usar datos estáticos
            context.update({
                'stats': {
                    'total_professionals': 1500,
                    'total_companies': 250,
                    'active_jobs': 125,
                    'total_applications': 3200,
                }
            })
        
        return context

class AboutView(TemplateView):
    template_name = 'core/about.html'

class ContactView(TemplateView):
    template_name = 'core/contact.html'

class PrivacyView(TemplateView):
    template_name = 'core/privacy.html'

class TermsView(TemplateView):
    template_name = 'core/terms.html'