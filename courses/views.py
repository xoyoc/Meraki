from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import (
    TemplateView, DetailView, UpdateView, CreateView, DeleteView, 
    ListView, FormView
)
from django.views import View
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponse, Http404
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, Sum, Min, Max, Case, When, IntegerField, F
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import datetime, timedelta
import logging

from accounts.models import User

from .models import Course, Enrollment, Certificate, Lesson, LessonProgress, Quiz, QuizAttempt
from .services import CertificateGenerator

logger = logging.getLogger(__name__)

class ApplicantRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'applicant':
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

class InstructorRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return (self.request.user.is_authenticated and 
                self.request.user.user_type in ['admin', 'instructor'])

# Views públicas de cursos
class CourseListView(ListView):
    model = Course
    template_name = 'courses/course_list.html'
    context_object_name = 'courses'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Course.objects.filter(
            is_active=True
        ).annotate(
            enrollment_count=Count('enrollment')
        ).order_by('-created_at')
        
        # Filtros
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        duration = self.request.GET.get('duration')
        if duration:
            if duration == 'short':
                queryset = queryset.filter(duration_hours__lt=10)
            elif duration == 'medium':
                queryset = queryset.filter(duration_hours__gte=10, duration_hours__lt=30)
            elif duration == 'long':
                queryset = queryset.filter(duration_hours__gte=30)
        
        difficulty = self.request.GET.get('difficulty')
        if difficulty:
            queryset = queryset.filter(difficulty_level=difficulty)
        
        # Búsqueda
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(instructor__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context.update({
            'categories': Course.objects.values_list('category', flat=True).distinct(),
            'difficulty_levels': Course.DIFFICULTY_CHOICES,
            'total_courses': self.get_queryset().count(),
            'filters': self.request.GET,
            'featured_courses': Course.objects.filter(
                is_active=True, is_featured=True
            )[:6],
        })
        
        return context

class CourseSearchView(ListView):
    """Vista para búsqueda avanzada de cursos"""
    model = Course
    template_name = 'courses/course_search.html'
    context_object_name = 'courses'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Course.objects.filter(is_active=True)
        
        # Búsqueda por texto
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(instructor__icontains=query)
            )
        
        # Filtro por categoría
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Filtro por nivel de dificultad
        difficulty = self.request.GET.get('difficulty')
        if difficulty:
            queryset = queryset.filter(difficulty_level=difficulty)
        
        # Filtro por duración
        duration = self.request.GET.get('duration')
        if duration:
            if duration == 'short':
                queryset = queryset.filter(duration_hours__lt=10)
            elif duration == 'medium':
                queryset = queryset.filter(duration_hours__gte=10, duration_hours__lt=30)
            elif duration == 'long':
                queryset = queryset.filter(duration_hours__gte=30)
        
        # Filtro por instructor
        instructor = self.request.GET.get('instructor')
        if instructor:
            queryset = queryset.filter(instructor__icontains=instructor)
        
        # Ordenamiento
        sort_by = self.request.GET.get('sort', 'newest')
        if sort_by == 'newest':
            queryset = queryset.order_by('-created_at')
        elif sort_by == 'oldest':
            queryset = queryset.order_by('created_at')
        elif sort_by == 'popular':
            queryset = queryset.annotate(
                enrollment_count=Count('enrollment')
            ).order_by('-enrollment_count')
        elif sort_by == 'alphabetical':
            queryset = queryset.order_by('title')
        elif sort_by == 'duration_asc':
            queryset = queryset.order_by('duration_hours')
        elif sort_by == 'duration_desc':
            queryset = queryset.order_by('-duration_hours')
        else:
            queryset = queryset.annotate(
                enrollment_count=Count('enrollment')
            ).order_by('-created_at')
        
        # Si no hay ordenamiento específico, agregar enrollment_count
        if 'enrollment_count' not in [field.name for field in queryset.query.annotations]:
            queryset = queryset.annotate(enrollment_count=Count('enrollment'))
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Pasar parámetros de búsqueda al contexto
        context.update({
            'search_query': self.request.GET.get('q', ''),
            'selected_category': self.request.GET.get('category', ''),
            'selected_difficulty': self.request.GET.get('difficulty', ''),
            'selected_duration': self.request.GET.get('duration', ''),
            'selected_instructor': self.request.GET.get('instructor', ''),
            'selected_sort': self.request.GET.get('sort', 'newest'),
            
            # Opciones para filtros
            'categories': Course.objects.values_list('category', flat=True).distinct().order_by('category'),
            'difficulty_levels': Course.DIFFICULTY_CHOICES,
            'instructors': Course.objects.values_list('instructor', flat=True).distinct().order_by('instructor'),
            
            # Opciones de ordenamiento
            'sort_options': [
                ('newest', 'Más recientes'),
                ('oldest', 'Más antiguos'),
                ('popular', 'Más populares'),
                ('alphabetical', 'Orden alfabético'),
                ('duration_asc', 'Duración (menor a mayor)'),
                ('duration_desc', 'Duración (mayor a menor)'),
            ],
            
            # Estadísticas de búsqueda
            'total_results': self.get_queryset().count(),
            'has_filters': any([
                self.request.GET.get('q'),
                self.request.GET.get('category'),
                self.request.GET.get('difficulty'),
                self.request.GET.get('duration'),
                self.request.GET.get('instructor'),
            ]),
        })
        
        return context

class CourseDetailView(DetailView):
    model = Course
    template_name = 'courses/course_detail.html'
    context_object_name = 'course'
    
    def get_queryset(self):
        return Course.objects.filter(is_active=True)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object
        
        # Verificar si el usuario está inscrito
        is_enrolled = False
        enrollment = None
        progress = 0
        
        if self.request.user.is_authenticated and self.request.user.user_type == 'applicant':
            try:
                enrollment = Enrollment.objects.get(
                    course=course,
                    applicant=self.request.user.applicantprofile
                )
                is_enrolled = True
                progress = enrollment.progress_percentage
            except Enrollment.DoesNotExist:
                pass
        
        context.update({
            'is_enrolled': is_enrolled,
            'enrollment': enrollment,
            'progress': progress,
            'total_enrollments': course.enrollment_set.filter(status='enrolled').count(),
            'completion_rate': self.calculate_completion_rate(course),
            'related_courses': self.get_related_courses(course),
            'lessons': course.lesson_set.all().order_by('order') if is_enrolled else [],
        })
        
        return context
    
    def calculate_completion_rate(self, course):
        total_enrollments = course.enrollment_set.count()
        if total_enrollments == 0:
            return 0
        
        completed_enrollments = course.enrollment_set.filter(status='completed').count()
        return (completed_enrollments / total_enrollments) * 100
    
    def get_related_courses(self, course):
        return Course.objects.filter(
            category=course.category,
            is_active=True
        ).exclude(id=course.id)[:4]

class CourseCategoriesView(TemplateView):
    """Vista para mostrar cursos organizados por categorías"""
    template_name = 'courses/course_categories.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        categories_data = []
        total_courses = 0
        total_students = 0
        
        # Iterar sobre todas las categorías disponibles
        for category_code, category_name in Course.CATEGORY_CHOICES:
            # Obtener cursos activos de esta categoría
            category_courses = Course.objects.filter(
                category=category_code, 
                is_active=True
            ).annotate(
                enrollment_count=Count('enrollment')
            ).order_by('-enrollment_count')
            
            course_count = category_courses.count()
            
            # Solo incluir categorías que tengan cursos
            if course_count > 0:
                # Calcular estadísticas de la categoría
                category_enrollments = Enrollment.objects.filter(
                    course__category=category_code,
                    course__is_active=True
                ).count()
                
                category_completions = Enrollment.objects.filter(
                    course__category=category_code,
                    course__is_active=True,
                    status='completed'
                ).count()
                
                completion_rate = (category_completions / category_enrollments * 100) if category_enrollments > 0 else 0
                
                # Obtener el curso más popular de la categoría
                most_popular_course = category_courses.first()
                
                # Calcular duración promedio de cursos en la categoría
                avg_duration = category_courses.aggregate(
                    avg_duration=Avg('duration_hours')
                )['avg_duration'] or 0
                
                categories_data.append({
                    'code': category_code,
                    'name': category_name,
                    'course_count': course_count,
                    'enrollment_count': category_enrollments,
                    'completion_rate': round(completion_rate, 1),
                    'avg_duration': round(avg_duration, 1),
                    'most_popular_course': most_popular_course,
                    'featured_courses': category_courses[:3],  # Primeros 3 cursos más populares
                    'all_courses': category_courses[:6],  # Primeros 6 para preview
                    'has_more_courses': course_count > 6,
                    'icon_class': self.get_category_icon(category_code),
                    'color_class': self.get_category_color(category_code),
                })
                
                total_courses += course_count
                total_students += category_enrollments
        
        # Ordenar categorías por número de cursos (descendente)
        categories_data.sort(key=lambda x: x['course_count'], reverse=True)
        
        # Obtener estadísticas generales
        context.update({
            'categories': categories_data,
            'total_categories': len(categories_data),
            'total_courses': total_courses,
            'total_students': total_students,
            'featured_categories': categories_data[:4],  # Primeras 4 categorías más populares
            'recent_courses': Course.objects.filter(
                is_active=True
            ).order_by('-created_at')[:6],
            'popular_courses': Course.objects.filter(
                is_active=True
            ).annotate(
                enrollment_count=Count('enrollment')
            ).order_by('-enrollment_count')[:6],
        })
        
        return context
    
    def get_category_icon(self, category_code):
        """Retorna la clase de icono Font Awesome para cada categoría"""
        icons = {
            'tecnologia': 'fas fa-laptop-code',
            'marketing': 'fas fa-bullhorn',
            'negocios': 'fas fa-briefcase',
            'diseno': 'fas fa-palette',
            'desarrollo_personal': 'fas fa-user-graduate',
            'idiomas': 'fas fa-language',
            'salud': 'fas fa-heartbeat',
            'finanzas': 'fas fa-chart-line',
        }
        return icons.get(category_code, 'fas fa-book')
    
    def get_category_color(self, category_code):
        """Retorna las clases de color para cada categoría"""
        colors = {
            'tecnologia': 'bg-blue-100 text-blue-800 border-blue-200',
            'marketing': 'bg-green-100 text-green-800 border-green-200',
            'negocios': 'bg-purple-100 text-purple-800 border-purple-200',
            'diseno': 'bg-pink-100 text-pink-800 border-pink-200',
            'desarrollo_personal': 'bg-yellow-100 text-yellow-800 border-yellow-200',
            'idiomas': 'bg-indigo-100 text-indigo-800 border-indigo-200',
            'salud': 'bg-red-100 text-red-800 border-red-200',
            'finanzas': 'bg-emerald-100 text-emerald-800 border-emerald-200',
        }
        return colors.get(category_code, 'bg-gray-100 text-gray-800 border-gray-200')

class CoursesByCategory(ListView):
    """Vista para mostrar cursos de una categoría específica"""
    model = Course
    template_name = 'courses/courses_by_category.html'
    context_object_name = 'courses'
    paginate_by = 12
    
    def get_queryset(self):
        category = self.kwargs.get('category')
        queryset = Course.objects.filter(
            category=category,
            is_active=True
        ).annotate(enrollment_count=Count('enrollment'))
        
        # Filtros adicionales
        difficulty = self.request.GET.get('difficulty')
        if difficulty:
            queryset = queryset.filter(difficulty_level=difficulty)
        
        duration = self.request.GET.get('duration')
        if duration:
            if duration == 'short':
                queryset = queryset.filter(duration_hours__lt=10)
            elif duration == 'medium':
                queryset = queryset.filter(duration_hours__gte=10, duration_hours__lt=30)
            elif duration == 'long':
                queryset = queryset.filter(duration_hours__gte=30)
        
        instructor = self.request.GET.get('instructor')
        if instructor:
            queryset = queryset.filter(instructor__icontains=instructor)
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(instructor__icontains=search)
            )
        
        # Ordenamiento
        sort_by = self.request.GET.get('sort', 'newest')
        if sort_by == 'newest':
            queryset = queryset.order_by('-created_at')
        elif sort_by == 'oldest':
            queryset = queryset.order_by('created_at')
        elif sort_by == 'popular':
            queryset = queryset.order_by('-enrollment_count')
        elif sort_by == 'alphabetical':
            queryset = queryset.order_by('title')
        elif sort_by == 'duration_asc':
            queryset = queryset.order_by('duration_hours')
        elif sort_by == 'duration_desc':
            queryset = queryset.order_by('-duration_hours')
        else:
            queryset = queryset.order_by('-created_at')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category_code = self.kwargs.get('category')
        
        # Validar que la categoría existe
        valid_categories = dict(Course.CATEGORY_CHOICES)
        if category_code not in valid_categories:
            raise Http404("Categoría no encontrada")
        
        category_name = valid_categories[category_code]
        
        # Obtener todos los cursos de la categoría para estadísticas
        all_category_courses = Course.objects.filter(
            category=category_code,
            is_active=True
        )
        
        # Calcular estadísticas de la categoría
        total_courses = all_category_courses.count()
        total_enrollments = Enrollment.objects.filter(
            course__category=category_code,
            course__is_active=True
        ).count()
        
        completed_enrollments = Enrollment.objects.filter(
            course__category=category_code,
            course__is_active=True,
            status='completed'
        ).count()
        
        completion_rate = (completed_enrollments / total_enrollments * 100) if total_enrollments > 0 else 0
        
        # Obtener instructores únicos en esta categoría
        instructors = all_category_courses.values_list('instructor', flat=True).distinct().order_by('instructor')
        
        # Obtener rangos de duración disponibles
        durations = all_category_courses.aggregate(
            min_duration=Min('duration_hours'),
            max_duration=Max('duration_hours'),
            avg_duration=Avg('duration_hours')
        )
        
        # Curso más popular de la categoría
        most_popular_course = all_category_courses.annotate(
            enrollment_count=Count('enrollment')
        ).order_by('-enrollment_count').first()
        
        # Cursos relacionados (de otras categorías similares)
        related_categories = self.get_related_categories(category_code)
        related_courses = Course.objects.filter(
            category__in=related_categories,
            is_active=True
        ).exclude(
            category=category_code
        ).annotate(
            enrollment_count=Count('enrollment')
        ).order_by('-enrollment_count')[:4]
        
        context.update({
            'category_code': category_code,
            'category_name': category_name,
            'category_icon': self.get_category_icon(category_code),
            'category_color': self.get_category_color(category_code),
            'category_description': self.get_category_description(category_code),
            
            # Estadísticas
            'total_courses': total_courses,
            'total_enrollments': total_enrollments,
            'completion_rate': round(completion_rate, 1),
            'avg_duration': round(durations['avg_duration'] or 0, 1),
            'min_duration': durations['min_duration'] or 0,
            'max_duration': durations['max_duration'] or 0,
            'most_popular_course': most_popular_course,
            
            # Filtros y opciones
            'instructors': instructors,
            'difficulty_levels': Course.DIFFICULTY_CHOICES,
            'sort_options': [
                ('newest', 'Más recientes'),
                ('oldest', 'Más antiguos'),
                ('popular', 'Más populares'),
                ('alphabetical', 'Orden alfabético'),
                ('duration_asc', 'Duración (menor a mayor)'),
                ('duration_desc', 'Duración (mayor a menor)'),
            ],
            
            # Parámetros actuales
            'current_filters': {
                'difficulty': self.request.GET.get('difficulty', ''),
                'duration': self.request.GET.get('duration', ''),
                'instructor': self.request.GET.get('instructor', ''),
                'search': self.request.GET.get('search', ''),
                'sort': self.request.GET.get('sort', 'newest'),
            },
            
            # Cursos relacionados
            'related_courses': related_courses,
            'related_categories': [
                {'code': cat, 'name': dict(Course.CATEGORY_CHOICES)[cat]} 
                for cat in related_categories
            ],
            
            # Indicadores
            'has_filters': any([
                self.request.GET.get('difficulty'),
                self.request.GET.get('duration'),
                self.request.GET.get('instructor'),
                self.request.GET.get('search'),
            ]),
            'filtered_count': self.get_queryset().count(),
        })
        
        return context
    
    def get_category_icon(self, category_code):
        """Retorna la clase de icono Font Awesome para cada categoría"""
        icons = {
            'tecnologia': 'fas fa-laptop-code',
            'marketing': 'fas fa-bullhorn',
            'negocios': 'fas fa-briefcase',
            'diseno': 'fas fa-palette',
            'desarrollo_personal': 'fas fa-user-graduate',
            'idiomas': 'fas fa-language',
            'salud': 'fas fa-heartbeat',
            'finanzas': 'fas fa-chart-line',
        }
        return icons.get(category_code, 'fas fa-book')
    
    def get_category_color(self, category_code):
        """Retorna las clases de color para cada categoría"""
        colors = {
            'tecnologia': 'from-blue-400 to-blue-600',
            'marketing': 'from-green-400 to-green-600',
            'negocios': 'from-purple-400 to-purple-600',
            'diseno': 'from-pink-400 to-pink-600',
            'desarrollo_personal': 'from-yellow-400 to-yellow-600',
            'idiomas': 'from-indigo-400 to-indigo-600',
            'salud': 'from-red-400 to-red-600',
            'finanzas': 'from-emerald-400 to-emerald-600',
        }
        return colors.get(category_code, 'from-gray-400 to-gray-600')
    
    def get_category_description(self, category_code):
        """Retorna una descripción para cada categoría"""
        descriptions = {
            'tecnologia': 'Domina las últimas tecnologías y herramientas de desarrollo que demanda el mercado actual.',
            'marketing': 'Aprende estrategias efectivas de marketing digital y tradicional para hacer crecer tu negocio.',
            'negocios': 'Desarrolla habilidades empresariales y de liderazgo para destacar en el mundo corporativo.',
            'diseno': 'Crea diseños impactantes y desarrolla tu creatividad con herramientas profesionales.',
            'desarrollo_personal': 'Potencia tus habilidades blandas y crece tanto personal como profesionalmente.',
            'idiomas': 'Amplía tus oportunidades laborales dominando nuevos idiomas de forma práctica.',
            'salud': 'Cuida tu bienestar físico y mental con conocimientos respaldados por expertos.',
            'finanzas': 'Toma control de tus finanzas personales y aprende sobre inversiones inteligentes.',
        }
        return descriptions.get(category_code, 'Descubre cursos especializados en esta área de conocimiento.')
    
    def get_related_categories(self, category_code):
        """Retorna categorías relacionadas basadas en afinidad temática"""
        related_map = {
            'tecnologia': ['diseno', 'negocios'],
            'marketing': ['negocios', 'tecnologia'],
            'negocios': ['marketing', 'finanzas', 'desarrollo_personal'],
            'diseno': ['tecnologia', 'marketing'],
            'desarrollo_personal': ['negocios', 'salud'],
            'idiomas': ['desarrollo_personal'],
            'salud': ['desarrollo_personal'],
            'finanzas': ['negocios', 'desarrollo_personal'],
        }
        return related_map.get(category_code, [])

class EnrollCourseView(ApplicantRequiredMixin, View):
    def post(self, request, course_id):
        course = get_object_or_404(Course, id=course_id, is_active=True)
        applicant = request.user.applicantprofile
        
        # Verificar si ya está inscrito
        if Enrollment.objects.filter(course=course, applicant=applicant).exists():
            messages.warning(request, 'Ya estás inscrito en este curso.')
            return redirect('courses:course_detail', pk=course.pk)
        
        # Crear inscripción
        enrollment = Enrollment.objects.create(
            course=course,
            applicant=applicant,
            status='enrolled'
        )
        
        messages.success(request, f'¡Te has inscrito exitosamente en "{course.title}"!')
        return redirect('courses:enrollment_detail', pk=enrollment.pk)

class MyCoursesView(ApplicantRequiredMixin, ListView):
    model = Enrollment
    template_name = 'courses/my_courses.html'
    context_object_name = 'enrollments'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Enrollment.objects.filter(
            applicant=self.request.user.applicantprofile
        ).select_related('course').order_by('-enrolled_at')
        
        # Filtros
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(course__category=category)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        enrollments = Enrollment.objects.filter(
            applicant=self.request.user.applicantprofile
        )
        
        context.update({
            'status_counts': {
                'all': enrollments.count(),
                'enrolled': enrollments.filter(status='enrolled').count(),
                'completed': enrollments.filter(status='completed').count(),
                'cancelled': enrollments.filter(status='cancelled').count(),
            },
            'total_hours': sum(
                e.course.duration_hours for e in enrollments.filter(status='completed')
            ),
            'certificates_earned': Certificate.objects.filter(
                enrollment__applicant=self.request.user.applicantprofile
            ).count(),
            'filters': self.request.GET,
        })
        
        return context

class CompleteEnrollmentView(ApplicantRequiredMixin, View):
    """Vista para completar una inscripción de curso"""
    
    def post(self, request, pk):
        enrollment = get_object_or_404(
            Enrollment,
            pk=pk,
            applicant=request.user.applicantprofile,
            status='enrolled'
        )
        
        # Verificar que se cumplan los requisitos de completación
        completion_check = self.check_completion_requirements(enrollment)
        
        if completion_check['can_complete']:
            # Marcar como completado
            enrollment.status = 'completed'
            enrollment.completed_at = timezone.now()
            enrollment.progress_percentage = 100
            enrollment.save()
            
            # Intentar generar certificado automáticamente
            certificate_created = False
            try:
                certificate = CertificateGenerator.create_certificate_record(enrollment)
                certificate_created = True
                
                messages.success(
                    request, 
                    f'¡Felicitaciones! Has completado exitosamente el curso "{enrollment.course.title}". '
                    f'Tu certificado ha sido generado y está disponible para descarga.'
                )
                
                logger.info(
                    f"Curso completado y certificado generado - Usuario: {request.user.username}, "
                    f"Curso: {enrollment.course.title}, Certificado: {certificate.certificate_id}"
                )
                
            except Exception as e:
                logger.error(f"Error generando certificado automático: {e}")
                
                # El curso se marca como completado pero sin certificado
                messages.success(
                    request,
                    f'¡Felicitaciones! Has completado el curso "{enrollment.course.title}". '
                    f'Hubo un problema generando tu certificado, pero será procesado pronto.'
                )
                
                # Notificar a administradores sobre el error
                self.notify_certificate_error(enrollment, str(e))
            
            # Registrar el logro
            self.log_course_completion(enrollment)
            
            # Enviar notificación (si está configurado)
            self.send_completion_notification(enrollment, certificate_created)
            
        else:
            # No cumple requisitos
            missing_requirements = completion_check['missing_requirements']
            error_message = 'No puedes completar este curso aún. Te falta: ' + ', '.join(missing_requirements)
            
            messages.error(request, error_message)
            
            logger.warning(
                f"Intento de completar curso sin requisitos - Usuario: {request.user.username}, "
                f"Curso: {enrollment.course.title}, Faltantes: {missing_requirements}"
            )
        
        return redirect('courses:enrollment_detail', pk=pk)
    
    def check_completion_requirements(self, enrollment):
        """
        Verificar exhaustivamente si el estudiante cumple con todos los requisitos
        para completar el curso
        """
        missing_requirements = []
        course = enrollment.course
        
        # 1. Verificar lecciones completadas
        total_lessons = course.lesson_set.filter(is_active=True).count()
        if total_lessons > 0:
            completed_lessons = LessonProgress.objects.filter(
                enrollment=enrollment,
                is_completed=True,
                lesson__is_active=True
            ).count()
            
            if completed_lessons < total_lessons:
                missing_count = total_lessons - completed_lessons
                missing_requirements.append(f"{missing_count} lección{'es' if missing_count != 1 else ''}")
        
        # 2. Verificar quizzes obligatorios aprobados
        required_quizzes = course.quiz_set.filter(is_active=True)
        failed_quizzes = []
        
        for quiz in required_quizzes:
            # Buscar el mejor intento del estudiante
            best_attempt = QuizAttempt.objects.filter(
                enrollment=enrollment,
                quiz=quiz
            ).order_by('-score').first()
            
            if not best_attempt or not best_attempt.is_passed:
                failed_quizzes.append(quiz.title)
        
        if failed_quizzes:
            quiz_text = "quiz" if len(failed_quizzes) == 1 else "quizzes"
            missing_requirements.append(f"aprobar {quiz_text}: {', '.join(failed_quizzes)}")
        
        # 3. Verificar tiempo mínimo en el curso (opcional)
        min_time_hours = getattr(course, 'minimum_time_hours', None)
        if min_time_hours:
            total_time_spent = LessonProgress.objects.filter(
                enrollment=enrollment
            ).aggregate(
                total_time=Sum('time_spent')
            )['total_time'] or 0
            
            total_time_hours = total_time_spent / 60  # convertir minutos a horas
            
            if total_time_hours < min_time_hours:
                remaining_hours = min_time_hours - total_time_hours
                missing_requirements.append(f"{remaining_hours:.1f} horas más de estudio")
        
        # 4. Verificar si ya está completado
        if enrollment.status == 'completed':
            return {
                'can_complete': False,
                'missing_requirements': ['El curso ya está completado'],
                'already_completed': True
            }
        
        # 5. Verificar que la inscripción esté activa
        if enrollment.status != 'enrolled':
            return {
                'can_complete': False,
                'missing_requirements': ['La inscripción no está activa'],
                'invalid_status': True
            }
        
        return {
            'can_complete': len(missing_requirements) == 0,
            'missing_requirements': missing_requirements,
            'total_lessons': total_lessons,
            'completed_lessons': completed_lessons if total_lessons > 0 else 0,
            'required_quizzes': required_quizzes.count(),
            'passed_quizzes': required_quizzes.count() - len(failed_quizzes)
        }
    
    def log_course_completion(self, enrollment):
        """Registrar la completación del curso para analytics"""
        try:
            # Aquí puedes agregar lógica para analytics, métricas, etc.
            completion_time = (enrollment.completed_at - enrollment.enrolled_at).days
            
            logger.info(
                f"Curso completado - Usuario: {enrollment.applicant.user.username}, "
                f"Curso: {enrollment.course.title}, Tiempo: {completion_time} días, "
                f"Progreso final: {enrollment.progress_percentage}%"
            )
            
            # Actualizar estadísticas del curso (ejemplo)
            # CourseAnalyticsService.update_completion_stats(enrollment.course)
            
        except Exception as e:
            logger.error(f"Error registrando completación del curso: {e}")
    
    def send_completion_notification(self, enrollment, certificate_created=False):
        """Enviar notificación de completación (email, etc.)"""
        try:
            # Aquí puedes agregar lógica para enviar emails de felicitación
            # o integrar con sistemas de notificaciones
            
            user = enrollment.applicant.user
            course = enrollment.course
            
            # Ejemplo de estructura para email
            notification_data = {
                'user_name': user.get_full_name() or user.username,
                'course_title': course.title,
                'course_duration': course.duration_hours,
                'completion_date': enrollment.completed_at,
                'certificate_available': certificate_created,
                'course_url': reverse('courses:course_detail', kwargs={'pk': course.pk}),
            }
            
            # Aquí integrarías con tu sistema de emails
            # EmailService.send_completion_notification(user.email, notification_data)
            
            logger.info(f"Notificación de completación enviada a {user.email}")
            
        except Exception as e:
            logger.error(f"Error enviando notificación de completación: {e}")
    
    def notify_certificate_error(self, enrollment, error_message):
        """Notificar a administradores sobre errores en generación de certificados"""
        try:
            # Aquí puedes agregar lógica para notificar a administradores
            admin_notification = {
                'type': 'certificate_generation_error',
                'enrollment_id': enrollment.id,
                'user': enrollment.applicant.user.username,
                'course': enrollment.course.title,
                'error': error_message,
                'timestamp': timezone.now()
            }
            
            # Integrar con sistema de notificaciones administrativas
            # AdminNotificationService.send_alert(admin_notification)
            
            logger.error(
                f"Error de certificado reportado - Inscripción: {enrollment.id}, "
                f"Error: {error_message}"
            )
            
        except Exception as e:
            logger.error(f"Error notificando problema de certificado: {e}")
    
    def get(self, request, pk):
        """
        Método GET para mostrar información antes de completar
        (opcional - redirige a enrollment_detail por defecto)
        """
        enrollment = get_object_or_404(
            Enrollment,
            pk=pk,
            applicant=request.user.applicantprofile,
            status='enrolled'
        )
        
        # Verificar requisitos
        completion_check = self.check_completion_requirements(enrollment)
        
        if completion_check['can_complete']:
            # Redirigir al detalle con mensaje informativo
            messages.info(
                request,
                f'Estás listo para completar el curso "{enrollment.course.title}". '
                f'Haz clic en "Completar Curso" cuando estés preparado.'
            )
        else:
            # Mostrar qué falta
            missing = ', '.join(completion_check['missing_requirements'])
            messages.warning(
                request,
                f'Para completar el curso "{enrollment.course.title}" te falta: {missing}'
            )
        
        return redirect('courses:enrollment_detail', pk=pk)

class CancelEnrollmentView(ApplicantRequiredMixin, View):
    """Vista para cancelar una inscripción de curso"""
    
    def post(self, request, pk):
        enrollment = get_object_or_404(
            Enrollment,
            pk=pk,
            applicant=request.user.applicantprofile,
            status='enrolled'
        )
        
        # Obtener razón de cancelación si se proporciona
        cancellation_reason = request.POST.get('reason', '').strip()
        
        # Verificar si la cancelación está permitida
        cancellation_check = self.check_cancellation_policy(enrollment)
        
        if cancellation_check['can_cancel']:
            # Realizar cancelación
            self.process_cancellation(enrollment, cancellation_reason)
            
            messages.success(
                request, 
                f'Has cancelado exitosamente tu inscripción en el curso "{enrollment.course.title}". '
                f'Tu progreso ha sido guardado por si decides inscribirte nuevamente.'
            )
            
            logger.info(
                f"Inscripción cancelada - Usuario: {request.user.username}, "
                f"Curso: {enrollment.course.title}, Progreso: {enrollment.progress_percentage}%, "
                f"Razón: {cancellation_reason or 'No especificada'}"
            )
            
        else:
            # No se puede cancelar
            messages.error(
                request,
                f'No puedes cancelar esta inscripción: {cancellation_check["reason"]}'
            )
            
            logger.warning(
                f"Intento de cancelación rechazado - Usuario: {request.user.username}, "
                f"Curso: {enrollment.course.title}, Razón: {cancellation_check['reason']}"
            )
        
        return redirect('courses:my_courses')
    
    def get(self, request, pk):
        """
        Método GET para mostrar página de confirmación de cancelación
        """
        enrollment = get_object_or_404(
            Enrollment,
            pk=pk,
            applicant=request.user.applicantprofile,
            status='enrolled'
        )
        
        # Verificar política de cancelación
        cancellation_check = self.check_cancellation_policy(enrollment)
        
        context = {
            'enrollment': enrollment,
            'course': enrollment.course,
            'can_cancel': cancellation_check['can_cancel'],
            'cancellation_reason': cancellation_check.get('reason', ''),
            'progress_info': self.get_progress_info(enrollment),
            'cancellation_consequences': self.get_cancellation_consequences(enrollment),
        }
        
        return render(request, 'courses/cancel_enrollment.html', context)
    
    def check_cancellation_policy(self, enrollment):
        """
        Verificar si la cancelación está permitida según las políticas del curso
        """
        # 1. Verificar si el curso ya está completado
        if enrollment.status == 'completed':
            return {
                'can_cancel': False,
                'reason': 'No puedes cancelar un curso ya completado'
            }
        
        # 2. Verificar si ya está cancelado
        if enrollment.status == 'cancelled':
            return {
                'can_cancel': False,
                'reason': 'Esta inscripción ya está cancelada'
            }
        
        # 3. Verificar política de tiempo (ejemplo: no cancelar después de cierto tiempo)
        days_enrolled = (timezone.now() - enrollment.enrolled_at).days
        max_cancellation_days = getattr(settings, 'COURSE_CANCELLATION_DAYS', 30)  # 30 días por defecto
        
        if days_enrolled > max_cancellation_days:
            return {
                'can_cancel': False,
                'reason': f'Solo puedes cancelar dentro de los primeros {max_cancellation_days} días de inscripción'
            }
        
        # 4. Verificar progreso máximo para cancelación
        max_progress_for_cancellation = getattr(settings, 'MAX_PROGRESS_FOR_CANCELLATION', 80)  # 80% por defecto
        
        if enrollment.progress_percentage > max_progress_for_cancellation:
            return {
                'can_cancel': False,
                'reason': f'No puedes cancelar un curso con más del {max_progress_for_cancellation}% de progreso'
            }
        
        # 5. Verificar si tiene certificados emitidos
        if hasattr(enrollment, 'certificate'):
            return {
                'can_cancel': False,
                'reason': 'No puedes cancelar un curso para el cual ya se emitió un certificado'
            }
        
        # 6. Políticas específicas del curso (si existen)
        course = enrollment.course
        if hasattr(course, 'cancellation_policy') and course.cancellation_policy:
            # Aquí puedes agregar lógica específica por curso
            pass
        
        return {
            'can_cancel': True,
            'reason': None
        }
    
    def process_cancellation(self, enrollment, reason=None):
        """
        Procesar la cancelación de la inscripción
        """
        # Guardar datos antes de cancelar (para posible restauración)
        cancellation_data = {
            'original_enrolled_at': enrollment.enrolled_at,
            'progress_at_cancellation': enrollment.progress_percentage,
            'last_accessed_at': enrollment.last_accessed,
            'cancellation_reason': reason,
            'cancelled_at': timezone.now(),
            'cancelled_by': enrollment.applicant.user,
        }
        
        # Actualizar el estado de la inscripción
        enrollment.status = 'cancelled'
        enrollment.save()
        
        # Crear registro de cancelación (opcional - para auditoría)
        self.create_cancellation_record(enrollment, cancellation_data)
        
        # Preservar progreso de lecciones (no eliminar)
        # Las LessonProgress se mantienen para posible re-inscripción
        
        # Marcar intentos de quiz como cancelados (opcional)
        QuizAttempt.objects.filter(enrollment=enrollment).update(
            # Agregar un campo 'is_cancelled' si lo tienes en el modelo
            # is_cancelled=True
        )
        
        # Notificar al sistema de analytics
        self.notify_cancellation_analytics(enrollment, cancellation_data)
        
        # Enviar notificación opcional
        self.send_cancellation_notification(enrollment, reason)
    
    def create_cancellation_record(self, enrollment, cancellation_data):
        """
        Crear un registro de auditoría para la cancelación
        """
        try:
            # Si tienes un modelo CancellationRecord, crearlo aquí
            # CancellationRecord.objects.create(
            #     enrollment=enrollment,
            #     **cancellation_data
            # )
            
            # Por ahora, solo logging detallado
            logger.info(
                f"Registro de cancelación - ID: {enrollment.id}, "
                f"Progreso: {cancellation_data['progress_at_cancellation']}%, "
                f"Razón: {cancellation_data['cancellation_reason']}"
            )
            
        except Exception as e:
            logger.error(f"Error creando registro de cancelación: {e}")
    
    def get_progress_info(self, enrollment):
        """
        Obtener información detallada del progreso para mostrar al usuario
        """
        try:
            # Lecciones completadas
            completed_lessons = LessonProgress.objects.filter(
                enrollment=enrollment,
                is_completed=True
            ).count()
            
            total_lessons = enrollment.course.lesson_set.filter(is_active=True).count()
            
            # Quizzes completados
            quiz_attempts = QuizAttempt.objects.filter(enrollment=enrollment)
            passed_quizzes = quiz_attempts.filter(is_passed=True).count()
            total_quizzes = enrollment.course.quiz_set.filter(is_active=True).count()
            
            # Tiempo invertido
            total_time = LessonProgress.objects.filter(
                enrollment=enrollment
            ).aggregate(
                total_time=Sum('time_spent')
            )['total_time'] or 0
            
            return {
                'progress_percentage': enrollment.progress_percentage,
                'completed_lessons': completed_lessons,
                'total_lessons': total_lessons,
                'passed_quizzes': passed_quizzes,
                'total_quizzes': total_quizzes,
                'total_time_hours': round(total_time / 60, 1),
                'days_enrolled': (timezone.now() - enrollment.enrolled_at).days,
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo información de progreso: {e}")
            return {}
    
    def get_cancellation_consequences(self, enrollment):
        """
        Obtener información sobre las consecuencias de la cancelación
        """
        consequences = []
        
        # Progreso se mantiene
        consequences.append({
            'type': 'positive',
            'message': 'Tu progreso actual será guardado por si decides reinscribirte'
        })
        
        # Acceso perdido
        consequences.append({
            'type': 'negative',
            'message': 'Perderás acceso inmediato al contenido del curso'
        })
        
        # Certificado
        if enrollment.progress_percentage >= 100:
            consequences.append({
                'type': 'negative',
                'message': 'No podrás obtener el certificado al cancelar'
            })
        
        # Re-inscripción
        consequences.append({
            'type': 'neutral',
            'message': 'Podrás inscribirte nuevamente en cualquier momento'
        })
        
        return consequences
    
    def notify_cancellation_analytics(self, enrollment, cancellation_data):
        """
        Notificar al sistema de analytics sobre la cancelación
        """
        try:
            # Actualizar métricas del curso
            # CourseAnalyticsService.update_cancellation_stats(enrollment.course)
            
            # Registrar patrón de cancelación para mejoras
            analytics_data = {
                'course_category': enrollment.course.category,
                'progress_at_cancellation': cancellation_data['progress_at_cancellation'],
                'days_enrolled': (cancellation_data['cancelled_at'] - enrollment.enrolled_at).days,
                'reason': cancellation_data['cancellation_reason'],
            }
            
            logger.info(f"Analytics de cancelación: {analytics_data}")
            
        except Exception as e:
            logger.error(f"Error en analytics de cancelación: {e}")
    
    def send_cancellation_notification(self, enrollment, reason=None):
        """
        Enviar notificación de cancelación (opcional)
        """
        try:
            user = enrollment.applicant.user
            
            # Datos para el email de cancelación
            notification_data = {
                'user_name': user.get_full_name() or user.username,
                'course_title': enrollment.course.title,
                'progress_percentage': enrollment.progress_percentage,
                'cancellation_reason': reason,
                'course_url': reverse('courses:course_detail', kwargs={'pk': enrollment.course.pk}),
                'my_courses_url': reverse('courses:my_courses'),
            }
            
            # Aquí integrarías con tu sistema de emails
            # EmailService.send_cancellation_notification(user.email, notification_data)
            
            logger.info(f"Notificación de cancelación enviada a {user.email}")
            
        except Exception as e:
            logger.error(f"Error enviando notificación de cancelación: {e}")

class EnrollmentDetailView(ApplicantRequiredMixin, DetailView):
    model = Enrollment
    template_name = 'courses/enrollment_detail.html'
    context_object_name = 'enrollment'
    
    def get_queryset(self):
        return Enrollment.objects.filter(
            applicant=self.request.user.applicantprofile
        ).select_related('course')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enrollment = self.object
        
        context.update({
            'lessons': enrollment.course.lesson_set.all().order_by('order'),
            'completed_lessons': self.get_completed_lessons(enrollment),
            'next_lesson': self.get_next_lesson(enrollment),
            'quiz_attempts': QuizAttempt.objects.filter(
                enrollment=enrollment
            ).order_by('-attempted_at'),
            'certificate': self.get_certificate(enrollment),
        })
        
        return context
    
    def get_completed_lessons(self, enrollment):
        # Implementar lógica para obtener lecciones completadas
        return []
    
    def get_next_lesson(self, enrollment):
        # Implementar lógica para obtener próxima lección
        lessons = enrollment.course.lesson_set.all().order_by('order')
        return lessons.first() if lessons else None
    
    def get_certificate(self, enrollment):
        try:
            return Certificate.objects.get(enrollment=enrollment)
        except Certificate.DoesNotExist:
            return None

class ActiveCoursesView(ApplicantRequiredMixin, ListView):
    """Vista para mostrar cursos activos (en progreso) del estudiante"""
    model = Enrollment
    template_name = 'courses/active_courses.html'
    context_object_name = 'enrollments'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Enrollment.objects.filter(
            applicant=self.request.user.applicantprofile,
            status='enrolled'
        ).select_related('course').prefetch_related(
            'lessonprogress_set',
            'quizattempt_set'
        )
        
        # Filtros adicionales
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(course__category=category)
        
        difficulty = self.request.GET.get('difficulty')
        if difficulty:
            queryset = queryset.filter(course__difficulty_level=difficulty)
        
        progress_filter = self.request.GET.get('progress')
        if progress_filter:
            if progress_filter == 'low':  # 0-25%
                queryset = queryset.filter(progress_percentage__lt=25)
            elif progress_filter == 'medium':  # 25-75%
                queryset = queryset.filter(
                    progress_percentage__gte=25,
                    progress_percentage__lt=75
                )
            elif progress_filter == 'high':  # 75-99%
                queryset = queryset.filter(
                    progress_percentage__gte=75,
                    progress_percentage__lt=100
                )
            elif progress_filter == 'ready':  # 100% (listo para completar)
                queryset = queryset.filter(progress_percentage__gte=100)
        
        # Búsqueda por título de curso
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(course__title__icontains=search) |
                Q(course__instructor__icontains=search)
            )
        
        # Ordenamiento
        sort_by = self.request.GET.get('sort', 'recent_activity')
        if sort_by == 'recent_activity':
            # Ordenar por última actividad (last_accessed) descendente
            queryset = queryset.order_by('-last_accessed', '-enrolled_at')
        elif sort_by == 'progress_desc':
            queryset = queryset.order_by('-progress_percentage', '-last_accessed')
        elif sort_by == 'progress_asc':
            queryset = queryset.order_by('progress_percentage', '-last_accessed')
        elif sort_by == 'enrolled_newest':
            queryset = queryset.order_by('-enrolled_at')
        elif sort_by == 'enrolled_oldest':
            queryset = queryset.order_by('enrolled_at')
        elif sort_by == 'alphabetical':
            queryset = queryset.order_by('course__title')
        elif sort_by == 'deadline':
            # Si tienes fechas límite, ordenar por eso
            queryset = queryset.annotate(
                estimated_deadline=Case(
                    When(progress_percentage__gt=0, 
                         then=F('enrolled_at') + timedelta(days=30)),
                    default=F('enrolled_at') + timedelta(days=60)
                )
            ).order_by('estimated_deadline')
        else:
            queryset = queryset.order_by('-last_accessed', '-enrolled_at')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener todas las inscripciones activas para estadísticas
        all_active_enrollments = Enrollment.objects.filter(
            applicant=self.request.user.applicantprofile,
            status='enrolled'
        ).select_related('course')
        
        # Calcular estadísticas generales
        total_active = all_active_enrollments.count()
        if total_active > 0:
            avg_progress = all_active_enrollments.aggregate(
                avg_progress=Avg('progress_percentage')
            )['avg_progress'] or 0
            
            # Distribución por progreso
            progress_distribution = {
                'starting': all_active_enrollments.filter(progress_percentage__lt=25).count(),
                'progressing': all_active_enrollments.filter(
                    progress_percentage__gte=25, progress_percentage__lt=75
                ).count(),
                'advanced': all_active_enrollments.filter(
                    progress_percentage__gte=75, progress_percentage__lt=100
                ).count(),
                'ready_to_complete': all_active_enrollments.filter(progress_percentage__gte=100).count(),
            }
            
            # Categorías más frecuentes
            category_stats = all_active_enrollments.values('course__category').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
            
            # Cursos con actividad reciente (últimos 7 días)
            recent_activity_count = all_active_enrollments.filter(
                last_accessed__gte=timezone.now() - timedelta(days=7)
            ).count()
            
            # Tiempo promedio invertido
            total_study_time = LessonProgress.objects.filter(
                enrollment__in=all_active_enrollments
            ).aggregate(
                total_time=Sum('time_spent')
            )['total_time'] or 0
            
            avg_study_time_per_course = (total_study_time / total_active) if total_active > 0 else 0
        else:
            avg_progress = 0
            progress_distribution = {'starting': 0, 'progressing': 0, 'advanced': 0, 'ready_to_complete': 0}
            category_stats = []
            recent_activity_count = 0
            avg_study_time_per_course = 0
        
        # Obtener próximas lecciones recomendadas
        recommended_lessons = self.get_recommended_next_lessons(all_active_enrollments[:5])
        
        # Cursos que necesitan atención (sin actividad reciente)
        courses_needing_attention = all_active_enrollments.filter(
            Q(last_accessed__lt=timezone.now() - timedelta(days=14)) |
            Q(last_accessed__isnull=True)
        ).order_by('last_accessed')[:3]
        
        # Hitos próximos a alcanzar
        upcoming_milestones = self.get_upcoming_milestones(all_active_enrollments)
        
        context.update({
            # Estadísticas principales
            'total_active_courses': total_active,
            'avg_progress': round(avg_progress, 1),
            'progress_distribution': progress_distribution,
            'recent_activity_count': recent_activity_count,
            'avg_study_time_hours': round(avg_study_time_per_course / 60, 1),
            
            # Análisis de contenido
            'category_stats': category_stats,
            'recommended_lessons': recommended_lessons,
            'courses_needing_attention': courses_needing_attention,
            'upcoming_milestones': upcoming_milestones,
            
            # Opciones de filtrado
            'categories': all_active_enrollments.values_list(
                'course__category', flat=True
            ).distinct(),
            'difficulty_levels': Course.DIFFICULTY_CHOICES,
            'progress_options': [
                ('low', 'Iniciando (0-24%)'),
                ('medium', 'En progreso (25-74%)'),
                ('high', 'Avanzado (75-99%)'),
                ('ready', 'Listo para completar (100%)'),
            ],
            'sort_options': [
                ('recent_activity', 'Actividad reciente'),
                ('progress_desc', 'Mayor progreso'),
                ('progress_asc', 'Menor progreso'),
                ('enrolled_newest', 'Inscritos recientemente'),
                ('enrolled_oldest', 'Inscritos hace más tiempo'),
                ('alphabetical', 'Orden alfabético'),
                ('deadline', 'Próximas fechas límite'),
            ],
            
            # Filtros actuales
            'current_filters': {
                'category': self.request.GET.get('category', ''),
                'difficulty': self.request.GET.get('difficulty', ''),
                'progress': self.request.GET.get('progress', ''),
                'search': self.request.GET.get('search', ''),
                'sort': self.request.GET.get('sort', 'recent_activity'),
            },
            
            # Estado de filtros
            'has_filters': any([
                self.request.GET.get('category'),
                self.request.GET.get('difficulty'),
                self.request.GET.get('progress'),
                self.request.GET.get('search'),
            ]),
            'filtered_count': self.get_queryset().count(),
            
            # Motivación y gamificación
            'study_streak': self.calculate_study_streak(),
            'weekly_goals': self.get_weekly_goals(),
        })
        
        return context
    
    def get_recommended_next_lessons(self, enrollments):
        """
        Obtener las próximas lecciones recomendadas para continuar
        """
        recommendations = []
        
        for enrollment in enrollments[:5]:  # Top 5 cursos activos
            # Buscar la próxima lección no completada
            completed_lessons = LessonProgress.objects.filter(
                enrollment=enrollment,
                is_completed=True
            ).values_list('lesson_id', flat=True)
            
            next_lesson = enrollment.course.lesson_set.filter(
                is_active=True
            ).exclude(
                id__in=completed_lessons
            ).order_by('order').first()
            
            if next_lesson:
                recommendations.append({
                    'enrollment': enrollment,
                    'lesson': next_lesson,
                    'course_progress': enrollment.progress_percentage,
                    'estimated_time': next_lesson.duration,
                })
        
        return recommendations
    
    def get_upcoming_milestones(self, enrollments):
        """
        Identificar hitos próximos a alcanzar (25%, 50%, 75%, 100%)
        """
        milestones = []
        milestone_thresholds = [25, 50, 75, 100]
        
        for enrollment in enrollments:
            current_progress = enrollment.progress_percentage
            
            # Encontrar el próximo hito
            next_milestone = None
            for threshold in milestone_thresholds:
                if current_progress < threshold:
                    next_milestone = threshold
                    break
            
            if next_milestone:
                progress_needed = next_milestone - current_progress
                
                # Estimar lecciones restantes para el hito
                total_lessons = enrollment.course.lesson_set.filter(is_active=True).count()
                completed_lessons = LessonProgress.objects.filter(
                    enrollment=enrollment,
                    is_completed=True
                ).count()
                
                if total_lessons > 0:
                    lessons_for_milestone = max(1, int(
                        (next_milestone / 100) * total_lessons - completed_lessons
                    ))
                    
                    milestones.append({
                        'enrollment': enrollment,
                        'milestone': next_milestone,
                        'progress_needed': round(progress_needed, 1),
                        'lessons_estimated': lessons_for_milestone,
                    })
        
        # Ordenar por cercanía al hito
        return sorted(milestones, key=lambda x: x['progress_needed'])[:5]
    
    def calculate_study_streak(self):
        """
        Calcular racha de días de estudio consecutivos
        """
        try:
            # Obtener actividad de lecciones de los últimos 30 días
            recent_activities = LessonProgress.objects.filter(
                enrollment__applicant=self.request.user.applicantprofile,
                enrollment__status='enrolled',
                completed_at__isnull=False,
                completed_at__gte=timezone.now() - timedelta(days=30)
            ).values_list('completed_at__date', flat=True).distinct().order_by('-completed_at__date')
            
            if not recent_activities:
                return 0
            
            # Calcular racha consecutiva desde hoy hacia atrás
            streak = 0
            current_date = timezone.now().date()
            
            for activity_date in recent_activities:
                if activity_date == current_date or activity_date == current_date - timedelta(days=streak):
                    streak += 1
                    current_date = activity_date
                else:
                    break
            
            return streak
            
        except Exception as e:
            logger.error(f"Error calculando racha de estudio: {e}")
            return 0
    
    def get_weekly_goals(self):
        """
        Obtener objetivos y progreso semanal
        """
        try:
            # Definir inicio de semana (lunes)
            today = timezone.now().date()
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            
            # Actividad de esta semana
            weekly_lessons = LessonProgress.objects.filter(
                enrollment__applicant=self.request.user.applicantprofile,
                enrollment__status='enrolled',
                completed_at__date__range=[week_start, week_end],
                is_completed=True
            ).count()
            
            weekly_time = LessonProgress.objects.filter(
                enrollment__applicant=self.request.user.applicantprofile,
                enrollment__status='enrolled',
                completed_at__date__range=[week_start, week_end]
            ).aggregate(
                total_time=Sum('time_spent')
            )['total_time'] or 0
            
            # Objetivos (configurables)
            goal_lessons_per_week = 5
            goal_hours_per_week = 3
            
            return {
                'lessons_completed': weekly_lessons,
                'lessons_goal': goal_lessons_per_week,
                'lessons_progress': min(100, (weekly_lessons / goal_lessons_per_week) * 100),
                'hours_studied': round(weekly_time / 60, 1),
                'hours_goal': goal_hours_per_week,
                'hours_progress': min(100, (weekly_time / 60 / goal_hours_per_week) * 100),
                'week_start': week_start,
                'week_end': week_end,
            }
            
        except Exception as e:
            logger.error(f"Error calculando objetivos semanales: {e}")
            return {
                'lessons_completed': 0,
                'lessons_goal': 5,
                'lessons_progress': 0,
                'hours_studied': 0,
                'hours_goal': 3,
                'hours_progress': 0,
            }

class CompletedCoursesView(ApplicantRequiredMixin, ListView):
    """Vista para mostrar cursos completados del estudiante"""
    model = Enrollment
    template_name = 'courses/completed_courses.html'
    context_object_name = 'enrollments'
    paginate_by = 12
    
    def get_queryset(self):
        queryset = Enrollment.objects.filter(
            applicant=self.request.user.applicantprofile,
            status='completed'
        ).select_related('course').prefetch_related(
            'certificate',
            'lessonprogress_set',
            'quizattempt_set'
        )
        
        # Filtros adicionales
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(course__category=category)
        
        difficulty = self.request.GET.get('difficulty')
        if difficulty:
            queryset = queryset.filter(course__difficulty_level=difficulty)
        
        # Filtro por período de completación
        period = self.request.GET.get('period')
        if period:
            now = timezone.now()
            if period == 'this_month':
                start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                queryset = queryset.filter(completed_at__gte=start_date)
            elif period == 'last_month':
                # Primer día del mes pasado
                first_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                first_last_month = (first_this_month - timedelta(days=1)).replace(day=1)
                queryset = queryset.filter(
                    completed_at__gte=first_last_month,
                    completed_at__lt=first_this_month
                )
            elif period == 'last_3_months':
                three_months_ago = now - timedelta(days=90)
                queryset = queryset.filter(completed_at__gte=three_months_ago)
            elif period == 'this_year':
                start_year = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                queryset = queryset.filter(completed_at__gte=start_year)
            elif period == 'last_year':
                start_last_year = now.replace(year=now.year-1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                start_this_year = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                queryset = queryset.filter(
                    completed_at__gte=start_last_year,
                    completed_at__lt=start_this_year
                )
        
        # Filtro por certificado
        certificate_filter = self.request.GET.get('certificate')
        if certificate_filter == 'with_certificate':
            queryset = queryset.filter(certificate__isnull=False)
        elif certificate_filter == 'without_certificate':
            queryset = queryset.filter(certificate__isnull=True)
        
        # Filtro por duración del curso
        duration = self.request.GET.get('duration')
        if duration:
            if duration == 'short':
                queryset = queryset.filter(course__duration_hours__lt=10)
            elif duration == 'medium':
                queryset = queryset.filter(course__duration_hours__gte=10, course__duration_hours__lt=30)
            elif duration == 'long':
                queryset = queryset.filter(course__duration_hours__gte=30)
        
        # Búsqueda por título de curso o instructor
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(course__title__icontains=search) |
                Q(course__instructor__icontains=search) |
                Q(course__description__icontains=search)
            )
        
        # Ordenamiento
        sort_by = self.request.GET.get('sort', 'completion_newest')
        if sort_by == 'completion_newest':
            queryset = queryset.order_by('-completed_at')
        elif sort_by == 'completion_oldest':
            queryset = queryset.order_by('completed_at')
        elif sort_by == 'enrolled_newest':
            queryset = queryset.order_by('-enrolled_at')
        elif sort_by == 'enrolled_oldest':
            queryset = queryset.order_by('enrolled_at')
        elif sort_by == 'alphabetical':
            queryset = queryset.order_by('course__title')
        elif sort_by == 'duration_desc':
            queryset = queryset.order_by('-course__duration_hours')
        elif sort_by == 'duration_asc':
            queryset = queryset.order_by('course__duration_hours')
        elif sort_by == 'completion_time':
            # Ordenar por tiempo que tomó completar (más rápido primero)
            queryset = queryset.annotate(
                completion_time=F('completed_at') - F('enrolled_at')
            ).order_by('completion_time')
        else:
            queryset = queryset.order_by('-completed_at')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener todas las inscripciones completadas para estadísticas
        all_completed_enrollments = Enrollment.objects.filter(
            applicant=self.request.user.applicantprofile,
            status='completed'
        ).select_related('course').prefetch_related('certificate')
        
        total_completed = all_completed_enrollments.count()
        
        if total_completed > 0:
            # Estadísticas de completación
            completion_stats = self.calculate_completion_statistics(all_completed_enrollments)
            
            # Distribución por categorías
            category_distribution = all_completed_enrollments.values(
                'course__category'
            ).annotate(
                count=Count('id'),
                total_hours=Sum('course__duration_hours')
            ).order_by('-count')
            
            # Distribución por dificultad
            difficulty_distribution = all_completed_enrollments.values(
                'course__difficulty_level'
            ).annotate(count=Count('id')).order_by('-count')
            
            # Certificados obtenidos
            certificates_count = Certificate.objects.filter(
                enrollment__in=all_completed_enrollments
            ).count()
            
            # Logros y hitos
            achievements = self.calculate_achievements(all_completed_enrollments)
            
            # Progreso a lo largo del tiempo
            monthly_progress = self.get_monthly_completion_progress(all_completed_enrollments)
            
            # Cursos más rápidos y más lentos de completar
            completion_extremes = self.get_completion_time_extremes(all_completed_enrollments)
            
            # Instructores favoritos
            favorite_instructors = all_completed_enrollments.values(
                'course__instructor'
            ).annotate(count=Count('id')).order_by('-count')[:5]
            
        else:
            completion_stats = {}
            category_distribution = []
            difficulty_distribution = []
            certificates_count = 0
            achievements = {}
            monthly_progress = []
            completion_extremes = {}
            favorite_instructors = []
        
        # Recomendaciones basadas en cursos completados
        recommended_courses = self.get_course_recommendations(all_completed_enrollments)
        
        context.update({
            # Estadísticas principales
            'total_completed_courses': total_completed,
            'certificates_earned': certificates_count,
            'certificate_rate': (certificates_count / total_completed * 100) if total_completed > 0 else 0,
            'completion_stats': completion_stats,
            
            # Distribuciones
            'category_distribution': category_distribution,
            'difficulty_distribution': difficulty_distribution,
            'favorite_instructors': favorite_instructors,
            
            # Análisis temporal
            'monthly_progress': monthly_progress,
            'completion_extremes': completion_extremes,
            
            # Logros y gamificación
            'achievements': achievements,
            'recommended_courses': recommended_courses,
            
            # Opciones de filtrado
            'categories': all_completed_enrollments.values_list(
                'course__category', flat=True
            ).distinct(),
            'difficulty_levels': Course.DIFFICULTY_CHOICES,
            'period_options': [
                ('this_month', 'Este mes'),
                ('last_month', 'Mes pasado'),
                ('last_3_months', 'Últimos 3 meses'),
                ('this_year', 'Este año'),
                ('last_year', 'Año pasado'),
            ],
            'certificate_options': [
                ('with_certificate', 'Con certificado'),
                ('without_certificate', 'Sin certificado'),
            ],
            'duration_options': [
                ('short', 'Cortos (< 10h)'),
                ('medium', 'Medios (10-30h)'),
                ('long', 'Largos (> 30h)'),
            ],
            'sort_options': [
                ('completion_newest', 'Completados recientemente'),
                ('completion_oldest', 'Completados hace tiempo'),
                ('enrolled_newest', 'Inscritos recientemente'),
                ('enrolled_oldest', 'Inscritos hace tiempo'),
                ('alphabetical', 'Orden alfabético'),
                ('duration_desc', 'Duración (mayor a menor)'),
                ('duration_asc', 'Duración (menor a mayor)'),
                ('completion_time', 'Tiempo de completación'),
            ],
            
            # Filtros actuales
            'current_filters': {
                'category': self.request.GET.get('category', ''),
                'difficulty': self.request.GET.get('difficulty', ''),
                'period': self.request.GET.get('period', ''),
                'certificate': self.request.GET.get('certificate', ''),
                'duration': self.request.GET.get('duration', ''),
                'search': self.request.GET.get('search', ''),
                'sort': self.request.GET.get('sort', 'completion_newest'),
            },
            
            # Estado de filtros
            'has_filters': any([
                self.request.GET.get('category'),
                self.request.GET.get('difficulty'),
                self.request.GET.get('period'),
                self.request.GET.get('certificate'),
                self.request.GET.get('duration'),
                self.request.GET.get('search'),
            ]),
            'filtered_count': self.get_queryset().count(),
        })
        
        return context
    
    def calculate_completion_statistics(self, enrollments):
        """Calcular estadísticas detalladas de completación"""
        try:
            total_hours = enrollments.aggregate(
                total_hours=Sum('course__duration_hours')
            )['total_hours'] or 0
            
            # Tiempo promedio para completar
            completion_times = []
            for enrollment in enrollments:
                if enrollment.completed_at and enrollment.enrolled_at:
                    days_to_complete = (enrollment.completed_at - enrollment.enrolled_at).days
                    completion_times.append(days_to_complete)
            
            avg_completion_days = sum(completion_times) / len(completion_times) if completion_times else 0
            
            # Año con más completaciones
            yearly_completions = enrollments.extra(
                select={'year': 'EXTRACT(year FROM completed_at)'}
            ).values('year').annotate(count=Count('id')).order_by('-count')
            
            most_productive_year = yearly_completions.first()['year'] if yearly_completions else None
            
            return {
                'total_study_hours': total_hours,
                'avg_course_duration': total_hours / enrollments.count() if enrollments.count() > 0 else 0,
                'avg_completion_days': round(avg_completion_days, 1),
                'fastest_completion': min(completion_times) if completion_times else 0,
                'slowest_completion': max(completion_times) if completion_times else 0,
                'most_productive_year': most_productive_year,
            }
            
        except Exception as e:
            logger.error(f"Error calculando estadísticas de completación: {e}")
            return {}
    
    def calculate_achievements(self, enrollments):
        """Calcular logros y badges del estudiante"""
        achievements = {
            'badges': [],
            'milestones': [],
            'streaks': []
        }
        
        try:
            total_completed = enrollments.count()
            total_certificates = Certificate.objects.filter(enrollment__in=enrollments).count()
            total_hours = enrollments.aggregate(Sum('course__duration_hours'))['course__duration_hours__sum'] or 0
            
            # Badges por número de cursos
            if total_completed >= 50:
                achievements['badges'].append({
                    'name': 'Maestro del Aprendizaje',
                    'description': '50+ cursos completados',
                    'icon': 'fas fa-crown',
                    'color': 'gold'
                })
            elif total_completed >= 25:
                achievements['badges'].append({
                    'name': 'Estudiante Experto',
                    'description': '25+ cursos completados',
                    'icon': 'fas fa-medal',
                    'color': 'silver'
                })
            elif total_completed >= 10:
                achievements['badges'].append({
                    'name': 'Estudiante Dedicado',
                    'description': '10+ cursos completados',
                    'icon': 'fas fa-award',
                    'color': 'bronze'
                })
            
            # Badges por horas de estudio
            if total_hours >= 200:
                achievements['badges'].append({
                    'name': 'Estudiante de Elite',
                    'description': '200+ horas de estudio',
                    'icon': 'fas fa-star',
                    'color': 'purple'
                })
            elif total_hours >= 100:
                achievements['badges'].append({
                    'name': 'Estudiante Comprometido',
                    'description': '100+ horas de estudio',
                    'icon': 'fas fa-clock',
                    'color': 'blue'
                })
            
            # Badge por diversidad de categorías
            unique_categories = enrollments.values('course__category').distinct().count()
            if unique_categories >= 5:
                achievements['badges'].append({
                    'name': 'Explorador del Conocimiento',
                    'description': f'Cursos en {unique_categories} categorías diferentes',
                    'icon': 'fas fa-compass',
                    'color': 'green'
                })
            
            # Badge por tasa de certificación
            cert_rate = (total_certificates / total_completed * 100) if total_completed > 0 else 0
            if cert_rate >= 90:
                achievements['badges'].append({
                    'name': 'Coleccionista de Certificados',
                    'description': f'{cert_rate:.0f}% de cursos certificados',
                    'icon': 'fas fa-certificate',
                    'color': 'yellow'
                })
            
            # Calcular racha de completaciones
            streak = self.calculate_completion_streak(enrollments)
            if streak >= 7:
                achievements['streaks'].append({
                    'type': 'Racha de Completación',
                    'value': f'{streak} días consecutivos',
                    'icon': 'fas fa-fire'
                })
            
            # Hitos próximos
            next_course_milestone = self.get_next_milestone(total_completed, [5, 10, 25, 50, 100])
            if next_course_milestone:
                achievements['milestones'].append({
                    'type': 'Próximo Hito',
                    'description': f'{next_course_milestone - total_completed} cursos para alcanzar {next_course_milestone} completados',
                    'progress': (total_completed / next_course_milestone) * 100
                })
            
        except Exception as e:
            logger.error(f"Error calculando logros: {e}")
        
        return achievements
    
    def get_monthly_completion_progress(self, enrollments):
        """Obtener progreso mensual de completaciones"""
        try:
            # Últimos 12 meses
            monthly_data = []
            current_date = timezone.now().date()
            
            for i in range(12):
                month_start = (current_date.replace(day=1) - timedelta(days=i*30)).replace(day=1)
                month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                
                completions = enrollments.filter(
                    completed_at__date__range=[month_start, month_end]
                ).count()
                
                monthly_data.append({
                    'month': month_start.strftime('%b %Y'),
                    'completions': completions,
                    'month_start': month_start,
                })
            
            return list(reversed(monthly_data))
            
        except Exception as e:
            logger.error(f"Error calculando progreso mensual: {e}")
            return []
    
    def get_completion_time_extremes(self, enrollments):
        """Obtener cursos completados más rápido y más lento"""
        try:
            completion_times = []
            
            for enrollment in enrollments:
                if enrollment.completed_at and enrollment.enrolled_at:
                    days = (enrollment.completed_at - enrollment.enrolled_at).days
                    completion_times.append({
                        'enrollment': enrollment,
                        'days': days,
                        'hours_per_day': enrollment.course.duration_hours / max(days, 1)
                    })
            
            if completion_times:
                fastest = min(completion_times, key=lambda x: x['days'])
                slowest = max(completion_times, key=lambda x: x['days'])
                
                return {
                    'fastest': fastest,
                    'slowest': slowest,
                }
            
        except Exception as e:
            logger.error(f"Error calculando extremos de completación: {e}")
        
        return {}
    
    def get_course_recommendations(self, completed_enrollments):
        """Generar recomendaciones basadas en cursos completados"""
        try:
            if not completed_enrollments.exists():
                return []
            
            # Categorías más frecuentes
            top_categories = completed_enrollments.values('course__category').annotate(
                count=Count('id')
            ).order_by('-count')[:3]
            
            # Instructores favoritos
            top_instructors = completed_enrollments.values('course__instructor').annotate(
                count=Count('id')
            ).order_by('-count')[:2]
            
            # Obtener recomendaciones
            recommendations = Course.objects.filter(
                is_active=True
            ).exclude(
                id__in=completed_enrollments.values_list('course_id', flat=True)
            ).annotate(
                enrollment_count=Count('enrollment')
            )
            
            # Filtrar por categorías favoritas
            category_recs = recommendations.filter(
                category__in=[cat['course__category'] for cat in top_categories]
            ).order_by('-enrollment_count')[:3]
            
            # Filtrar por instructores favoritos
            instructor_recs = recommendations.filter(
                instructor__in=[inst['course__instructor'] for inst in top_instructors]
            ).order_by('-enrollment_count')[:2]
            
            # Combinar recomendaciones
            all_recs = list(category_recs) + list(instructor_recs)
            
            # Eliminar duplicados manteniendo orden
            seen = set()
            unique_recs = []
            for course in all_recs:
                if course.id not in seen:
                    unique_recs.append(course)
                    seen.add(course.id)
            
            return unique_recs[:5]
            
        except Exception as e:
            logger.error(f"Error generando recomendaciones: {e}")
            return []
    
    def calculate_completion_streak(self, enrollments):
        """Calcular racha de días consecutivos con completaciones"""
        try:
            completion_dates = enrollments.values_list(
                'completed_at__date', flat=True
            ).distinct().order_by('-completed_at__date')
            
            if not completion_dates:
                return 0
            
            streak = 0
            current_date = timezone.now().date()
            
            for completion_date in completion_dates:
                expected_date = current_date - timedelta(days=streak)
                
                if completion_date == expected_date:
                    streak += 1
                else:
                    break
            
            return streak
            
        except Exception as e:
            logger.error(f"Error calculando racha de completación: {e}")
            return 0
    
    def get_next_milestone(self, current_value, milestones):
        """Obtener el próximo hito a alcanzar"""
        for milestone in sorted(milestones):
            if current_value < milestone:
                return milestone
        return None

class MyCertificatesView(ApplicantRequiredMixin, ListView):
    model = Certificate
    template_name = 'courses/my_certificates.html'
    context_object_name = 'certificates'
    paginate_by = 12
    
    def get_queryset(self):
        return Certificate.objects.filter(
            enrollment__applicant=self.request.user.applicantprofile
        ).select_related('enrollment__course').order_by('-issued_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        certificates = self.get_queryset()
        context.update({
            'total_certificates': certificates.count(),
            'total_hours': sum(
                cert.enrollment.course.duration_hours for cert in certificates
            ),
            'categories': certificates.values_list(
                'enrollment__course__category', flat=True
            ).distinct(),
        })
        
        return context

class DownloadCertificateView(ApplicantRequiredMixin, View):
    def get(self, request, pk):
        certificate = get_object_or_404(
            Certificate,
            pk=pk,
            enrollment__applicant=request.user.applicantprofile
        )
        
        if certificate.pdf_file:
            response = HttpResponse(
                certificate.pdf_file.read(),
                content_type='application/pdf'
            )
            response['Content-Disposition'] = (
                f'attachment; filename="certificado_{certificate.certificate_id}.pdf"'
            )
            return response
        
        messages.error(request, 'Certificado no disponible para descarga.')
        return redirect('courses:my_certificates')

class CourseProgressView(ApplicantRequiredMixin, TemplateView):
    """Vista para mostrar el progreso general de todos los cursos del estudiante"""
    template_name = 'courses/course_progress.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener todas las inscripciones del usuario
        all_enrollments = Enrollment.objects.filter(
            applicant=self.request.user.applicantprofile
        ).select_related('course').prefetch_related(
            'lessonprogress_set',
            'quizattempt_set',
            'certificate'
        ).order_by('-enrolled_at')
        
        # Separar por estado
        active_enrollments = all_enrollments.filter(status='enrolled')
        completed_enrollments = all_enrollments.filter(status='completed')
        cancelled_enrollments = all_enrollments.filter(status='cancelled')
        
        # Calcular datos de progreso detallado para cada inscripción activa
        progress_data = []
        for enrollment in active_enrollments:
            summary = CourseProgressService.get_student_progress_summary(enrollment)
            
            # Información adicional de progreso
            additional_info = self.get_detailed_progress_info(enrollment)
            
            progress_data.append({
                'enrollment': enrollment,
                'summary': summary,
                'details': additional_info,
                'next_actions': self.get_next_actions(enrollment, summary),
                'time_analysis': self.analyze_study_time(enrollment),
                'difficulty_analysis': self.analyze_difficulty_progress(enrollment),
            })
        
        # Ordenar por prioridad (cursos con más progreso o actividad reciente primero)
        progress_data.sort(key=lambda x: (
            -x['enrollment'].progress_percentage,
            -(x['enrollment'].last_accessed or x['enrollment'].enrolled_at).timestamp()
        ))
        
        # Calcular estadísticas globales
        global_stats = self.calculate_global_statistics(all_enrollments)
        
        # Análisis de patrones de aprendizaje
        learning_patterns = self.analyze_learning_patterns(all_enrollments)
        
        # Objetivos y metas
        goals_analysis = self.analyze_goals_and_targets(active_enrollments)
        
        # Recomendaciones personalizadas
        recommendations = self.generate_progress_recommendations(progress_data)
        
        # Análisis comparativo
        comparative_analysis = self.get_comparative_analysis(all_enrollments)
        
        context.update({
            # Datos principales
            'progress_data': progress_data,
            'active_count': active_enrollments.count(),
            'completed_count': completed_enrollments.count(),
            'cancelled_count': cancelled_enrollments.count(),
            
            # Estadísticas globales
            'global_stats': global_stats,
            'learning_patterns': learning_patterns,
            'goals_analysis': goals_analysis,
            'recommendations': recommendations,
            'comparative_analysis': comparative_analysis,
            
            # Datos para gráficos
            'chart_data': self.prepare_chart_data(progress_data, completed_enrollments),
            
            # Filtros y opciones
            'filter_options': self.get_filter_options(all_enrollments),
            'current_filters': self.get_current_filters(),
        })
        
        return context
    
    def get_detailed_progress_info(self, enrollment):
        """Obtener información detallada del progreso de un curso"""
        try:
            course = enrollment.course
            
            # Progreso de lecciones
            total_lessons = course.lesson_set.filter(is_active=True).count()
            lesson_progress = LessonProgress.objects.filter(enrollment=enrollment)
            completed_lessons = lesson_progress.filter(is_completed=True).count()
            
            # Progreso de quizzes
            total_quizzes = course.quiz_set.filter(is_active=True).count()
            quiz_attempts = QuizAttempt.objects.filter(enrollment=enrollment)
            passed_quizzes = quiz_attempts.filter(is_passed=True).values('quiz').distinct().count()
            
            # Última actividad
            last_lesson_activity = lesson_progress.filter(
                completed_at__isnull=False
            ).order_by('-completed_at').first()
            
            last_quiz_activity = quiz_attempts.order_by('-attempted_at').first()
            
            # Determinar última actividad general
            last_activities = []
            if last_lesson_activity:
                last_activities.append(('lesson', last_lesson_activity.completed_at))
            if last_quiz_activity:
                last_activities.append(('quiz', last_quiz_activity.attempted_at))
            
            last_activity = max(last_activities, key=lambda x: x[1]) if last_activities else None
            
            # Tiempo estimado para completar
            estimated_completion = self.estimate_completion_time(enrollment)
            
            # Análisis de consistencia
            consistency_score = self.calculate_study_consistency(enrollment)
            
            return {
                'lesson_progress': {
                    'completed': completed_lessons,
                    'total': total_lessons,
                    'percentage': (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0
                },
                'quiz_progress': {
                    'passed': passed_quizzes,
                    'total': total_quizzes,
                    'percentage': (passed_quizzes / total_quizzes * 100) if total_quizzes > 0 else 0
                },
                'last_activity': last_activity,
                'estimated_completion': estimated_completion,
                'consistency_score': consistency_score,
                'days_enrolled': (timezone.now() - enrollment.enrolled_at).days,
                'completion_readiness': self.assess_completion_readiness(enrollment),
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo progreso detallado: {e}")
            return {}
    
    def get_next_actions(self, enrollment, summary):
        """Determinar las próximas acciones recomendadas para el estudiante"""
        actions = []
        
        try:
            # Si puede completar el curso
            if summary.get('overall_progress', 0) >= 100 and not summary.get('is_completed'):
                actions.append({
                    'type': 'complete_course',
                    'priority': 'high',
                    'title': 'Completar Curso',
                    'description': '¡Felicitaciones! Estás listo para completar este curso',
                    'icon': 'fas fa-trophy',
                    'color': 'green'
                })
            
            # Si tiene lecciones pendientes
            elif summary.get('completed_lessons', 0) < summary.get('total_lessons', 0):
                next_lesson = enrollment.next_lesson
                if next_lesson:
                    actions.append({
                        'type': 'continue_lesson',
                        'priority': 'high',
                        'title': f'Continuar con: {next_lesson.title}',
                        'description': f'Próxima lección ({next_lesson.duration} min)',
                        'icon': 'fas fa-play-circle',
                        'color': 'blue',
                        'lesson_id': next_lesson.id
                    })
            
            # Si tiene quizzes pendientes
            pending_quizzes = enrollment.course.quiz_set.filter(is_active=True)
            for quiz in pending_quizzes:
                best_attempt = QuizAttempt.objects.filter(
                    enrollment=enrollment, quiz=quiz
                ).order_by('-score').first()
                
                if not best_attempt or not best_attempt.is_passed:
                    attempt_text = "Reintentar" if best_attempt else "Tomar"
                    actions.append({
                        'type': 'take_quiz',
                        'priority': 'medium',
                        'title': f'{attempt_text} Quiz: {quiz.title}',
                        'description': f'Puntuación mínima: {quiz.passing_score}%',
                        'icon': 'fas fa-question-circle',
                        'color': 'orange',
                        'quiz_id': quiz.id
                    })
            
            # Si no ha tenido actividad reciente
            days_inactive = (timezone.now() - (enrollment.last_accessed or enrollment.enrolled_at)).days
            if days_inactive > 7:
                actions.append({
                    'type': 'resume_study',
                    'priority': 'medium',
                    'title': 'Retomar Estudio',
                    'description': f'Sin actividad por {days_inactive} días',
                    'icon': 'fas fa-clock',
                    'color': 'yellow'
                })
            
            # Si el progreso es muy lento
            expected_progress = self.calculate_expected_progress(enrollment)
            if enrollment.progress_percentage < expected_progress * 0.5:
                actions.append({
                    'type': 'increase_pace',
                    'priority': 'low',
                    'title': 'Acelerar Ritmo',
                    'description': 'El progreso está por debajo del promedio',
                    'icon': 'fas fa-tachometer-alt',
                    'color': 'red'
                })
            
        except Exception as e:
            logger.error(f"Error generando próximas acciones: {e}")
        
        return sorted(actions, key=lambda x: {'high': 0, 'medium': 1, 'low': 2}[x['priority']])
    
    def analyze_study_time(self, enrollment):
        """Analizar patrones de tiempo de estudio"""
        try:
            lesson_progress = LessonProgress.objects.filter(enrollment=enrollment)
            
            total_time = lesson_progress.aggregate(Sum('time_spent'))['time_spent__sum'] or 0
            sessions = lesson_progress.filter(time_spent__gt=0).count()
            
            if sessions > 0:
                avg_session_time = total_time / sessions
                
                # Analizar distribución de tiempo
                short_sessions = lesson_progress.filter(time_spent__lt=15).count()
                medium_sessions = lesson_progress.filter(time_spent__gte=15, time_spent__lt=45).count()
                long_sessions = lesson_progress.filter(time_spent__gte=45).count()
                
                # Determinar patrón preferido
                if short_sessions > medium_sessions and short_sessions > long_sessions:
                    study_pattern = "Sesiones cortas frecuentes"
                elif long_sessions > medium_sessions:
                    study_pattern = "Sesiones largas intensivas"
                else:
                    study_pattern = "Sesiones moderadas equilibradas"
                
                return {
                    'total_minutes': total_time,
                    'total_hours': round(total_time / 60, 1),
                    'avg_session_minutes': round(avg_session_time, 1),
                    'total_sessions': sessions,
                    'study_pattern': study_pattern,
                    'session_distribution': {
                        'short': short_sessions,
                        'medium': medium_sessions,
                        'long': long_sessions
                    }
                }
            
        except Exception as e:
            logger.error(f"Error analizando tiempo de estudio: {e}")
        
        return {'total_minutes': 0, 'total_hours': 0, 'avg_session_minutes': 0, 'total_sessions': 0}
    
    def analyze_difficulty_progress(self, enrollment):
        """Analizar progreso según dificultad del curso"""
        try:
            course = enrollment.course
            difficulty = course.difficulty_level
            
            # Comparar con promedio de cursos de la misma dificultad
            same_difficulty_enrollments = Enrollment.objects.filter(
                course__difficulty_level=difficulty,
                status__in=['enrolled', 'completed']
            ).exclude(id=enrollment.id)
            
            if same_difficulty_enrollments.exists():
                avg_progress = same_difficulty_enrollments.aggregate(
                    avg_progress=Avg('progress_percentage')
                )['avg_progress'] or 0
                
                performance = "above_average" if enrollment.progress_percentage > avg_progress else "below_average"
                
                return {
                    'difficulty': difficulty,
                    'avg_progress_for_difficulty': round(avg_progress, 1),
                    'performance_vs_average': performance,
                    'progress_difference': round(enrollment.progress_percentage - avg_progress, 1)
                }
            
        except Exception as e:
            logger.error(f"Error analizando dificultad: {e}")
        
        return {}
    
    def calculate_global_statistics(self, all_enrollments):
        """Calcular estadísticas globales del estudiante"""
        try:
            active_enrollments = all_enrollments.filter(status='enrolled')
            completed_enrollments = all_enrollments.filter(status='completed')
            
            # Progreso promedio de cursos activos
            avg_active_progress = active_enrollments.aggregate(
                avg_progress=Avg('progress_percentage')
            )['avg_progress'] or 0
            
            # Tiempo total invertido
            total_study_time = LessonProgress.objects.filter(
                enrollment__in=all_enrollments
            ).aggregate(Sum('time_spent'))['time_spent__sum'] or 0
            
            # Tasa de completación
            total_enrollments = all_enrollments.count()
            completion_rate = (completed_enrollments.count() / total_enrollments * 100) if total_enrollments > 0 else 0
            
            # Promedio de tiempo para completar
            completion_times = []
            for enrollment in completed_enrollments:
                if enrollment.completed_at and enrollment.enrolled_at:
                    days = (enrollment.completed_at - enrollment.enrolled_at).days
                    completion_times.append(days)
            
            avg_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0
            
            # Certificados obtenidos
            certificates_count = Certificate.objects.filter(
                enrollment__in=completed_enrollments
            ).count()
            
            return {
                'avg_active_progress': round(avg_active_progress, 1),
                'total_study_hours': round(total_study_time / 60, 1),
                'completion_rate': round(completion_rate, 1),
                'avg_completion_days': round(avg_completion_time, 1),
                'certificates_earned': certificates_count,
                'certificate_rate': (certificates_count / completed_enrollments.count() * 100) if completed_enrollments.count() > 0 else 0,
                'total_course_hours': all_enrollments.aggregate(
                    Sum('course__duration_hours')
                )['course__duration_hours__sum'] or 0
            }
            
        except Exception as e:
            logger.error(f"Error calculando estadísticas globales: {e}")
            return {}
    
    def analyze_learning_patterns(self, all_enrollments):
        """Analizar patrones de aprendizaje del estudiante"""
        try:
            patterns = {}
            
            # Categorías preferidas
            category_stats = all_enrollments.values('course__category').annotate(
                count=Count('id'),
                avg_progress=Avg('progress_percentage')
            ).order_by('-count')
            
            patterns['preferred_categories'] = list(category_stats[:3])
            
            # Niveles de dificultad preferidos
            difficulty_stats = all_enrollments.values('course__difficulty_level').annotate(
                count=Count('id'),
                completion_rate=Count('id', filter=Q(status='completed')) * 100.0 / Count('id')
            ).order_by('-count')
            
            patterns['difficulty_performance'] = list(difficulty_stats)
            
            # Patrones temporales (horas del día más activas)
            # Esto requeriría más datos de actividad, por ahora estimamos
            patterns['study_time_preference'] = self.estimate_study_time_preference(all_enrollments)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error analizando patrones de aprendizaje: {e}")
            return {}
    
    def analyze_goals_and_targets(self, active_enrollments):
        """Analizar objetivos y metas del estudiante"""
        try:
            # Objetivos sugeridos basados en progreso actual
            goals = []
            
            # Objetivo de completar cursos con alto progreso
            high_progress_courses = active_enrollments.filter(progress_percentage__gte=75).count()
            if high_progress_courses > 0:
                goals.append({
                    'type': 'completion',
                    'title': f'Completar {high_progress_courses} curso{"s" if high_progress_courses != 1 else ""} este mes',
                    'description': 'Tienes cursos con más del 75% de progreso',
                    'priority': 'high',
                    'estimated_time': '2-4 semanas'
                })
            
            # Objetivo de mantener consistencia
            if active_enrollments.count() > 2:
                goals.append({
                    'type': 'consistency',
                    'title': 'Estudiar al menos 30 minutos diarios',
                    'description': 'Mantener constancia en el aprendizaje',
                    'priority': 'medium',
                    'estimated_time': 'Diario'
                })
            
            # Objetivo de diversificación
            unique_categories = active_enrollments.values('course__category').distinct().count()
            if unique_categories < 3:
                goals.append({
                    'type': 'diversification',
                    'title': 'Explorar una nueva categoría',
                    'description': 'Ampliar áreas de conocimiento',
                    'priority': 'low',
                    'estimated_time': '1-2 meses'
                })
            
            return {
                'suggested_goals': goals,
                'current_focus': self.determine_current_focus(active_enrollments)
            }
            
        except Exception as e:
            logger.error(f"Error analizando objetivos: {e}")
            return {}
    
    def generate_progress_recommendations(self, progress_data):
        """Generar recomendaciones personalizadas de progreso"""
        recommendations = []
        
        try:
            # Recomendación para cursos estancados
            stalled_courses = [p for p in progress_data if p['enrollment'].progress_percentage < 25 and 
                             (timezone.now() - (p['enrollment'].last_accessed or p['enrollment'].enrolled_at)).days > 14]
            
            if stalled_courses:
                recommendations.append({
                    'type': 'restart',
                    'title': 'Retomar cursos estancados',
                    'description': f'Tienes {len(stalled_courses)} curso{"s" if len(stalled_courses) != 1 else ""} sin progreso reciente',
                    'action': 'Revisar y reorganizar prioridades',
                    'courses': [p['enrollment'] for p in stalled_courses[:3]]
                })
            
            # Recomendación para optimizar tiempo de estudio
            avg_session_times = [p['time_analysis'].get('avg_session_minutes', 0) for p in progress_data]
            if avg_session_times and sum(avg_session_times) / len(avg_session_times) < 20:
                recommendations.append({
                    'type': 'time_optimization',
                    'title': 'Optimizar sesiones de estudio',
                    'description': 'Tus sesiones son muy cortas. Considera sesiones de 25-45 minutos',
                    'action': 'Usar técnica Pomodoro o bloquear más tiempo'
                })
            
            # Recomendación basada en patrón de completación
            completion_ready = [p for p in progress_data if p['enrollment'].progress_percentage >= 100]
            if completion_ready:
                recommendations.append({
                    'type': 'completion',
                    'title': 'Finalizar cursos completados',
                    'description': f'{len(completion_ready)} curso{"s" if len(completion_ready) != 1 else ""} listo{"s" if len(completion_ready) != 1 else ""} para completar',
                    'action': 'Completar para obtener certificados',
                    'courses': [p['enrollment'] for p in completion_ready]
                })
            
        except Exception as e:
            logger.error(f"Error generando recomendaciones: {e}")
        
        return recommendations
    
    def get_comparative_analysis(self, all_enrollments):
        """Obtener análisis comparativo con otros estudiantes"""
        try:
            # Comparar con promedio general de la plataforma
            platform_stats = Enrollment.objects.aggregate(
                avg_progress=Avg('progress_percentage'),
                avg_completion_rate=Count('id', filter=Q(status='completed')) * 100.0 / Count('id')
            )
            
            user_stats = all_enrollments.aggregate(
                avg_progress=Avg('progress_percentage'),
                completion_rate=Count('id', filter=Q(status='completed')) * 100.0 / Count('id')
            )
            
            return {
                'platform_avg_progress': round(platform_stats['avg_progress'] or 0, 1),
                'user_avg_progress': round(user_stats['avg_progress'] or 0, 1),
                'platform_completion_rate': round(platform_stats['avg_completion_rate'] or 0, 1),
                'user_completion_rate': round(user_stats['completion_rate'] or 0, 1),
                'performance_vs_platform': 'above' if (user_stats['avg_progress'] or 0) > (platform_stats['avg_progress'] or 0) else 'below'
            }
            
        except Exception as e:
            logger.error(f"Error en análisis comparativo: {e}")
            return {}
    
    def prepare_chart_data(self, progress_data, completed_enrollments):
        """Preparar datos para gráficos"""
        try:
            # Datos para gráfico de progreso por curso
            progress_chart = []
            for p in progress_data[:10]:  # Top 10 cursos
                progress_chart.append({
                    'course_name': p['enrollment'].course.title[:30] + '...' if len(p['enrollment'].course.title) > 30 else p['enrollment'].course.title,
                    'progress': p['enrollment'].progress_percentage,
                    'category': p['enrollment'].course.category
                })
            
            # Datos para gráfico temporal de completaciones
            completion_timeline = []
            if completed_enrollments.exists():
                # Agrupar por mes
                monthly_completions = completed_enrollments.extra(
                    select={'month': 'DATE_FORMAT(completed_at, "%%Y-%%m")'}
                ).values('month').annotate(count=Count('id')).order_by('month')
                
                completion_timeline = list(monthly_completions)
            
            return {
                'progress_by_course': progress_chart,
                'completion_timeline': completion_timeline,
                'category_distribution': self.get_category_distribution_data(progress_data)
            }
            
        except Exception as e:
            logger.error(f"Error preparando datos de gráficos: {e}")
            return {}
    
    # Métodos auxiliares
    def estimate_completion_time(self, enrollment):
        """Estimar tiempo para completar el curso"""
        try:
            if enrollment.progress_percentage > 0:
                days_elapsed = (timezone.now() - enrollment.enrolled_at).days
                progress_rate = enrollment.progress_percentage / max(days_elapsed, 1)
                remaining_progress = 100 - enrollment.progress_percentage
                estimated_days = remaining_progress / progress_rate if progress_rate > 0 else 30
                return min(estimated_days, 90)  # Máximo 90 días
        except:
            pass
        return 30  # Default: 30 días
    
    def calculate_study_consistency(self, enrollment):
        """Calcular puntuación de consistencia de estudio"""
        try:
            lesson_progress = LessonProgress.objects.filter(
                enrollment=enrollment,
                completed_at__isnull=False
            ).order_by('completed_at')
            
            if lesson_progress.count() < 2:
                return 0
            
            # Calcular intervalos entre sesiones
            intervals = []
            prev_date = None
            
            for progress in lesson_progress:
                if prev_date:
                    interval = (progress.completed_at.date() - prev_date).days
                    intervals.append(interval)
                prev_date = progress.completed_at.date()
            
            if intervals:
                avg_interval = sum(intervals) / len(intervals)
                # Puntuación inversa: menor intervalo = mayor consistencia
                consistency = max(0, 100 - (avg_interval * 10))
                return min(consistency, 100)
        except:
            pass
        return 0
    
    def assess_completion_readiness(self, enrollment):
        """Evaluar qué tan listo está para completar el curso"""
        if enrollment.progress_percentage >= 100:
            return "ready"
        elif enrollment.progress_percentage >= 75:
            return "almost_ready"
        elif enrollment.progress_percentage >= 25:
            return "in_progress"
        else:
            return "just_started"
    
    def calculate_expected_progress(self, enrollment):
        """Calcular progreso esperado basado en tiempo transcurrido"""
        days_enrolled = (timezone.now() - enrollment.enrolled_at).days
        expected_days = enrollment.course.duration_hours * 2  # 2 días por hora de curso
        return min((days_enrolled / expected_days) * 100, 100) if expected_days > 0 else 0
    
    def estimate_study_time_preference(self, enrollments):
        """Estimar preferencia de horario de estudio"""
        # Simplificado - en una implementación real usarías datos de actividad por hora
        return "evening"  # morning, afternoon, evening, night
    
    def determine_current_focus(self, active_enrollments):
        """Determinar el enfoque actual del estudiante"""
        if not active_enrollments.exists():
            return "no_active_courses"
        
        # Curso con más progreso
        top_course = active_enrollments.order_by('-progress_percentage').first()
        return {
            'course': top_course.course.title,
            'category': top_course.course.category,
            'progress': top_course.progress_percentage
        }
    
    def get_category_distribution_data(self, progress_data):
        """Obtener distribución por categorías para gráficos"""
        categories = {}
        for p in progress_data:
            category = p['enrollment'].course.category
            categories[category] = categories.get(category, 0) + 1
        
        return [{'category': k, 'count': v} for k, v in categories.items()]
    
    def get_filter_options(self, all_enrollments):
        """Obtener opciones de filtrado"""
        return {
            'categories': all_enrollments.values_list('course__category', flat=True).distinct(),
            'difficulties': Course.DIFFICULTY_CHOICES,
            'statuses': Enrollment.STATUS_CHOICES
        }
    
    def get_current_filters(self):
        """Obtener filtros actuales de la URL"""
        return {
            'category': self.request.GET.get('category', ''),
            'difficulty': self.request.GET.get('difficulty', ''),
            'status': self.request.GET.get('status', ''),
        }

class CertificateDetailView(ApplicantRequiredMixin, DetailView):
    """Vista para mostrar detalles completos de un certificado"""
    model = Certificate
    template_name = 'courses/certificate_detail.html'
    context_object_name = 'certificate'
    
    def get_queryset(self):
        return Certificate.objects.filter(
            enrollment__applicant=self.request.user.applicantprofile
        ).select_related(
            'enrollment__course',
            'enrollment__applicant__user'
        ).prefetch_related(
            'enrollment__lessonprogress_set',
            'enrollment__quizattempt_set'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        certificate = self.object
        enrollment = certificate.enrollment
        course = enrollment.course
        
        # Información básica del certificado
        basic_info = self.get_certificate_basic_info(certificate)
        
        # Información académica detallada
        academic_info = self.get_academic_information(enrollment)
        
        # Estadísticas de rendimiento
        performance_stats = self.get_performance_statistics(enrollment)
        
        # Información de verificación
        verification_info = self.get_verification_information(certificate)
        
        # Análisis comparativo
        comparative_analysis = self.get_comparative_analysis(enrollment)
        
        # Logros y reconocimientos
        achievements = self.get_achievement_analysis(enrollment, certificate)
        
        # Cursos relacionados y recomendaciones
        related_content = self.get_related_content(course, enrollment.applicant)
        
        # Información para compartir
        sharing_info = self.get_sharing_information(certificate)
        
        # Validaciones del certificado
        certificate_validation = self.validate_certificate_integrity(certificate)
        
        context.update({
            # Información principal
            'basic_info': basic_info,
            'academic_info': academic_info,
            'performance_stats': performance_stats,
            'verification_info': verification_info,
            
            # Análisis y logros
            'comparative_analysis': comparative_analysis,
            'achievements': achievements,
            'related_content': related_content,
            
            # Funcionalidades
            'sharing_info': sharing_info,
            'certificate_validation': certificate_validation,
            
            # URLs y enlaces
            'download_url': reverse('courses:download_certificate', kwargs={'pk': certificate.pk}),
            'verification_url': self.build_verification_url(certificate),
            'public_url': self.build_public_certificate_url(certificate),
            'course_url': reverse('courses:course_detail', kwargs={'pk': course.pk}),
            
            # Estado y acciones disponibles
            'can_regenerate': self.can_regenerate_certificate(certificate),
            'can_share_publicly': certificate.is_public,
            'is_recent': self.is_recent_certificate(certificate),
        })
        
        return context
    
    def get_certificate_basic_info(self, certificate):
        """Obtener información básica del certificado"""
        try:
            enrollment = certificate.enrollment
            course = enrollment.course
            student = enrollment.applicant.user
            
            return {
                'certificate_id': certificate.certificate_id,
                'student_name': student.get_full_name() or student.username,
                'student_email': student.email,
                'course_title': course.title,
                'course_category': course.get_category_display(),
                'course_difficulty': course.get_difficulty_level_display(),
                'instructor': course.instructor,
                'duration_hours': course.duration_hours,
                'issued_date': certificate.issued_at,
                'completion_date': enrollment.completed_at,
                'enrollment_date': enrollment.enrolled_at,
                'file_size': self.get_file_size(certificate.pdf_file),
                'file_available': bool(certificate.pdf_file),
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo información básica del certificado: {e}")
            return {}
    
    def get_academic_information(self, enrollment):
        """Obtener información académica detallada"""
        try:
            course = enrollment.course
            
            # Progreso de lecciones
            lesson_progress = LessonProgress.objects.filter(enrollment=enrollment)
            total_lessons = course.lesson_set.filter(is_active=True).count()
            completed_lessons = lesson_progress.filter(is_completed=True).count()
            
            # Tiempo total de estudio
            total_study_time = lesson_progress.aggregate(
                total_time=Sum('time_spent')
            )['total_time'] or 0
            
            # Progreso de quizzes
            quiz_attempts = QuizAttempt.objects.filter(enrollment=enrollment)
            quizzes = course.quiz_set.filter(is_active=True)
            
            quiz_performance = []
            for quiz in quizzes:
                best_attempt = quiz_attempts.filter(quiz=quiz).order_by('-score').first()
                if best_attempt:
                    quiz_performance.append({
                        'quiz_title': quiz.title,
                        'score': best_attempt.score,
                        'passed': best_attempt.is_passed,
                        'attempts': quiz_attempts.filter(quiz=quiz).count(),
                        'time_taken': best_attempt.time_taken,
                    })
            
            # Tiempo para completar el curso
            completion_time_days = None
            if enrollment.completed_at and enrollment.enrolled_at:
                completion_time_days = (enrollment.completed_at - enrollment.enrolled_at).days
            
            return {
                'lessons': {
                    'total': total_lessons,
                    'completed': completed_lessons,
                    'completion_rate': (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0
                },
                'study_time': {
                    'total_minutes': total_study_time,
                    'total_hours': round(total_study_time / 60, 1),
                    'avg_per_lesson': round(total_study_time / completed_lessons, 1) if completed_lessons > 0 else 0,
                    'efficiency_score': self.calculate_study_efficiency(total_study_time, course.duration_hours)
                },
                'quiz_performance': quiz_performance,
                'overall_quiz_average': self.calculate_quiz_average(quiz_performance),
                'completion_time': {
                    'days': completion_time_days,
                    'weeks': round(completion_time_days / 7, 1) if completion_time_days else None,
                    'pace_rating': self.evaluate_completion_pace(completion_time_days, course.duration_hours)
                },
                'final_progress': enrollment.progress_percentage,
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo información académica: {e}")
            return {}
    
    def get_performance_statistics(self, enrollment):
        """Obtener estadísticas de rendimiento del estudiante"""
        try:
            # Comparar con otros estudiantes del mismo curso
            same_course_enrollments = Enrollment.objects.filter(
                course=enrollment.course,
                status='completed'
            ).exclude(id=enrollment.id)
            
            if same_course_enrollments.exists():
                # Tiempo de completación comparativo
                completion_times = []
                for e in same_course_enrollments:
                    if e.completed_at and e.enrolled_at:
                        days = (e.completed_at - e.enrolled_at).days
                        completion_times.append(days)
                
                user_completion_days = (enrollment.completed_at - enrollment.enrolled_at).days if enrollment.completed_at and enrollment.enrolled_at else None
                
                # Percentil de rendimiento
                percentile = None
                if user_completion_days and completion_times:
                    faster_than = sum(1 for t in completion_times if t > user_completion_days)
                    percentile = (faster_than / len(completion_times)) * 100
                
                # Promedio de quizzes comparativo
                user_quiz_avg = self.get_user_quiz_average(enrollment)
                course_quiz_avg = self.get_course_quiz_average(enrollment.course)
                
                return {
                    'completion_time_percentile': round(percentile, 1) if percentile else None,
                    'avg_course_completion_days': round(sum(completion_times) / len(completion_times), 1) if completion_times else None,
                    'user_completion_days': user_completion_days,
                    'performance_vs_average': self.compare_performance(user_completion_days, completion_times),
                    'quiz_performance_vs_course': {
                        'user_average': user_quiz_avg,
                        'course_average': course_quiz_avg,
                        'performance_rating': 'above_average' if user_quiz_avg > course_quiz_avg else 'below_average'
                    },
                    'top_performer': percentile >= 90 if percentile else False,
                }
            
            return {
                'completion_time_percentile': None,
                'insufficient_data': True
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de rendimiento: {e}")
            return {}
    
    def get_verification_information(self, certificate):
        """Obtener información de verificación del certificado"""
        try:
            # Generar código QR para verificación (si está disponible)
            verification_url = self.build_verification_url(certificate)
            
            return {
                'certificate_id': certificate.certificate_id,
                'verification_url': verification_url,
                'public_verification_url': certificate.verification_url,
                'is_publicly_verifiable': certificate.is_public,
                'issued_timestamp': certificate.issued_at.timestamp(),
                'blockchain_hash': getattr(certificate, 'blockchain_hash', None),  # Si usas blockchain
                'digital_signature': self.generate_digital_signature(certificate),
                'verification_instructions': [
                    f"Visita {verification_url}",
                    f"Ingresa el ID: {certificate.certificate_id}",
                    "Verifica que los datos coincidan"
                ],
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo información de verificación: {e}")
            return {}
    
    def get_comparative_analysis(self, enrollment):
        """Obtener análisis comparativo con otros estudiantes"""
        try:
            applicant = enrollment.applicant
            
            # Comparar con otros certificados del mismo estudiante
            user_certificates = Certificate.objects.filter(
                enrollment__applicant=applicant
            ).select_related('enrollment__course')
            
            # Ranking dentro de sus propios cursos
            same_category_certs = user_certificates.filter(
                enrollment__course__category=enrollment.course.category
            )
            
            # Tiempo promedio de completación del usuario
            user_completion_times = []
            for cert in user_certificates:
                if cert.enrollment.completed_at and cert.enrollment.enrolled_at:
                    days = (cert.enrollment.completed_at - cert.enrollment.enrolled_at).days
                    user_completion_times.append(days)
            
            user_avg_completion = sum(user_completion_times) / len(user_completion_times) if user_completion_times else None
            
            return {
                'total_certificates': user_certificates.count(),
                'certificates_in_category': same_category_certs.count(),
                'user_avg_completion_time': round(user_avg_completion, 1) if user_avg_completion else None,
                'fastest_completion': min(user_completion_times) if user_completion_times else None,
                'improvement_over_time': self.analyze_improvement_trend(user_certificates),
                'specialization_areas': self.identify_specialization_areas(user_certificates),
            }
            
        except Exception as e:
            logger.error(f"Error en análisis comparativo: {e}")
            return {}
    
    def get_achievement_analysis(self, enrollment, certificate):
        """Analizar logros y reconocimientos especiales"""
        try:
            achievements = []
            
            # Logro por velocidad de completación
            completion_days = (enrollment.completed_at - enrollment.enrolled_at).days if enrollment.completed_at and enrollment.enrolled_at else None
            expected_days = enrollment.course.duration_hours * 2  # 2 días por hora esperada
            
            if completion_days and completion_days <= expected_days * 0.5:
                achievements.append({
                    'type': 'speed',
                    'title': 'Completación Rápida',
                    'description': f'Completaste el curso en {completion_days} días, muy por debajo del promedio',
                    'icon': 'fas fa-bolt',
                    'color': 'yellow'
                })
            
            # Logro por puntuación en quizzes
            quiz_attempts = QuizAttempt.objects.filter(enrollment=enrollment)
            if quiz_attempts.exists():
                avg_score = quiz_attempts.aggregate(avg_score=Avg('score'))['avg_score']
                if avg_score >= 95:
                    achievements.append({
                        'type': 'excellence',
                        'title': 'Excelencia Académica',
                        'description': f'Promedio de {avg_score:.1f}% en evaluaciones',
                        'icon': 'fas fa-star',
                        'color': 'gold'
                    })
            
            # Logro por constancia
            study_consistency = self.calculate_study_consistency_score(enrollment)
            if study_consistency >= 80:
                achievements.append({
                    'type': 'consistency',
                    'title': 'Estudiante Constante',
                    'description': f'Puntuación de consistencia: {study_consistency}%',
                    'icon': 'fas fa-calendar-check',
                    'color': 'green'
                })
            
            # Logro por ser de los primeros en completar
            earlier_completions = Enrollment.objects.filter(
                course=enrollment.course,
                status='completed',
                completed_at__lt=enrollment.completed_at
            ).count()
            
            total_completions = Enrollment.objects.filter(
                course=enrollment.course,
                status='completed'
            ).count()
            
            if total_completions >= 10 and earlier_completions <= 5:
                achievements.append({
                    'type': 'pioneer',
                    'title': 'Pionero del Curso',
                    'description': f'Entre los primeros {earlier_completions + 1} en completar este curso',
                    'icon': 'fas fa-flag',
                    'color': 'blue'
                })
            
            return {
                'achievements': achievements,
                'special_recognition': len(achievements) >= 2,
                'achievement_score': self.calculate_achievement_score(achievements),
            }
            
        except Exception as e:
            logger.error(f"Error analizando logros: {e}")
            return {'achievements': []}
    
    def get_related_content(self, course, applicant):
        """Obtener contenido relacionado y recomendaciones"""
        try:
            # Cursos del mismo instructor
            instructor_courses = Course.objects.filter(
                instructor=course.instructor,
                is_active=True
            ).exclude(id=course.id).annotate(
                enrollment_count=Count('enrollment')
            ).order_by('-enrollment_count')[:3]
            
            # Cursos de la misma categoría
            category_courses = Course.objects.filter(
                category=course.category,
                is_active=True
            ).exclude(id=course.id).annotate(
                enrollment_count=Count('enrollment')
            ).order_by('-enrollment_count')[:3]
            
            # Cursos ya completados por el usuario en la misma categoría
            completed_in_category = Certificate.objects.filter(
                enrollment__applicant=applicant,
                enrollment__course__category=course.category
            ).select_related('enrollment__course').count()
            
            # Próximo nivel sugerido
            next_level_course = None
            if course.difficulty_level == 'beginner':
                next_level_course = Course.objects.filter(
                    category=course.category,
                    difficulty_level='intermediate',
                    is_active=True
                ).annotate(enrollment_count=Count('enrollment')).order_by('-enrollment_count').first()
            elif course.difficulty_level == 'intermediate':
                next_level_course = Course.objects.filter(
                    category=course.category,
                    difficulty_level='advanced',
                    is_active=True
                ).annotate(enrollment_count=Count('enrollment')).order_by('-enrollment_count').first()
            
            return {
                'instructor_courses': instructor_courses,
                'category_courses': category_courses,
                'next_level_course': next_level_course,
                'completed_in_category': completed_in_category,
                'category_expertise_level': self.assess_category_expertise(completed_in_category),
                'learning_path_suggestions': self.generate_learning_path(course, applicant),
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo contenido relacionado: {e}")
            return {}
    
    def get_sharing_information(self, certificate):
        """Obtener información para compartir el certificado"""
        try:
            enrollment = certificate.enrollment
            course = enrollment.course
            student = enrollment.applicant.user
            
            # URLs para compartir en redes sociales
            public_url = self.build_public_certificate_url(certificate)
            course_url = self.build_course_url(course)
            
            # Textos predefinidos para compartir
            share_texts = {
                'linkedin': f"¡Orgulloso de haber completado el curso '{course.title}' en Meraki! "
                           f"#{course.category} #Certificación #AprendizajeContinuo",
                'twitter': f"¡He completado '{course.title}' en @MerakiEducation! 🎓 "
                          f"#{course.category} #{course.difficulty_level}",
                'facebook': f"¡Emocionado de compartir que he completado exitosamente el curso "
                           f"'{course.title}' en Meraki! Gracias {course.instructor} por la excelente instrucción.",
                'email': f"He completado el curso '{course.title}' y obtenido mi certificado. "
                        f"Puedes verificar mi certificado en: {public_url}"
            }
            
            return {
                'public_url': public_url if certificate.is_public else None,
                'share_texts': share_texts,
                'social_media_urls': {
                    'linkedin': f"https://www.linkedin.com/sharing/share-offsite/?url={public_url}",
                    'twitter': f"https://twitter.com/intent/tweet?text={share_texts['twitter']}&url={public_url}",
                    'facebook': f"https://www.facebook.com/sharer/sharer.php?u={public_url}",
                },
                'qr_code_data': public_url,
                'embed_code': self.generate_embed_code(certificate) if certificate.is_public else None,
                'can_share': certificate.is_public,
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo información para compartir: {e}")
            return {}
    
    def validate_certificate_integrity(self, certificate):
        """Validar la integridad y autenticidad del certificado"""
        try:
            validations = {
                'file_exists': bool(certificate.pdf_file and certificate.pdf_file.name),
                'id_format_valid': self.validate_certificate_id_format(certificate.certificate_id),
                'dates_consistent': self.validate_certificate_dates(certificate),
                'enrollment_valid': certificate.enrollment.status == 'completed',
                'course_active': certificate.enrollment.course.is_active,
                'not_expired': self.check_certificate_expiration(certificate),
            }
            
            overall_valid = all(validations.values())
            
            return {
                'validations': validations,
                'overall_valid': overall_valid,
                'integrity_score': sum(validations.values()) / len(validations) * 100,
                'validation_timestamp': timezone.now(),
                'warnings': self.get_certificate_warnings(validations),
            }
            
        except Exception as e:
            logger.error(f"Error validando integridad del certificado: {e}")
            return {'overall_valid': False, 'error': str(e)}
    
    # Métodos auxiliares
    def get_file_size(self, file_field):
        """Obtener tamaño del archivo en formato legible"""
        try:
            if file_field and file_field.size:
                size = file_field.size
                if size < 1024:
                    return f"{size} bytes"
                elif size < 1024 * 1024:
                    return f"{size / 1024:.1f} KB"
                else:
                    return f"{size / (1024 * 1024):.1f} MB"
        except:
            pass
        return "Desconocido"
    
    def calculate_study_efficiency(self, study_time_minutes, course_duration_hours):
        """Calcular eficiencia de estudio"""
        expected_minutes = course_duration_hours * 60
        if study_time_minutes > 0 and expected_minutes > 0:
            efficiency = expected_minutes / study_time_minutes
            return min(efficiency * 100, 200)  # Cap at 200%
        return 0
    
    def calculate_quiz_average(self, quiz_performance):
        """Calcular promedio de quizzes"""
        if not quiz_performance:
            return 0
        scores = [q['score'] for q in quiz_performance]
        return sum(scores) / len(scores) if scores else 0
    
    def evaluate_completion_pace(self, completion_days, course_hours):
        """Evaluar ritmo de completación"""
        if not completion_days or not course_hours:
            return "unknown"
        
        expected_days = course_hours * 2  # 2 días por hora
        ratio = completion_days / expected_days
        
        if ratio <= 0.5:
            return "very_fast"
        elif ratio <= 0.8:
            return "fast"
        elif ratio <= 1.2:
            return "normal"
        elif ratio <= 2.0:
            return "slow"
        else:
            return "very_slow"
    
    def build_verification_url(self, certificate):
        """Construir URL de verificación"""
        return f"{settings.SITE_URL}/courses/certificates/verify/?id={certificate.certificate_id}"
    
    def build_public_certificate_url(self, certificate):
        """Construir URL pública del certificado"""
        if certificate.is_public:
            return f"{settings.SITE_URL}/courses/certificates/public/{certificate.certificate_id}/"
        return None
    
    def build_course_url(self, course):
        """Construir URL del curso"""
        return f"{settings.SITE_URL}/courses/{course.id}/"
    
    def generate_digital_signature(self, certificate):
        """Generar firma digital del certificado"""
        import hashlib
        data = f"{certificate.certificate_id}{certificate.issued_at.isoformat()}{certificate.enrollment.id}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def can_regenerate_certificate(self, certificate):
        """Verificar si se puede regenerar el certificado"""
        # Permitir regeneración solo si es reciente (últimos 30 días) o si hay problemas
        days_since_issued = (timezone.now() - certificate.issued_at).days
        return days_since_issued <= 30 or not bool(certificate.pdf_file)
    
    def is_recent_certificate(self, certificate):
        """Verificar si es un certificado reciente"""
        return (timezone.now() - certificate.issued_at).days <= 7
    
    # Métodos de análisis adicionales
    def get_user_quiz_average(self, enrollment):
        """Obtener promedio de quizzes del usuario"""
        attempts = QuizAttempt.objects.filter(enrollment=enrollment)
        if attempts.exists():
            return attempts.aggregate(avg_score=Avg('score'))['avg_score']
        return 0
    
    def get_course_quiz_average(self, course):
        """Obtener promedio de quizzes del curso"""
        attempts = QuizAttempt.objects.filter(enrollment__course=course)
        if attempts.exists():
            return attempts.aggregate(avg_score=Avg('score'))['avg_score']
        return 0
    
    def compare_performance(self, user_days, all_completion_times):
        """Comparar rendimiento del usuario"""
        if not user_days or not all_completion_times:
            return "unknown"
        
        avg_days = sum(all_completion_times) / len(all_completion_times)
        if user_days <= avg_days * 0.8:
            return "excellent"
        elif user_days <= avg_days:
            return "good"
        elif user_days <= avg_days * 1.2:
            return "average"
        else:
            return "below_average"
    
    def calculate_study_consistency_score(self, enrollment):
        """Calcular puntuación de consistencia de estudio"""
        # Implementación similar a la de CourseProgressView
        return 75  # Placeholder
    
    def calculate_achievement_score(self, achievements):
        """Calcular puntuación total de logros"""
        score_map = {'speed': 25, 'excellence': 30, 'consistency': 20, 'pioneer': 25}
        return sum(score_map.get(a['type'], 10) for a in achievements)
    
    def analyze_improvement_trend(self, certificates):
        """Analizar tendencia de mejora del estudiante"""
        # Simplificado - analizar tiempos de completación a lo largo del tiempo
        return "improving"  # improving, stable, declining
    
    def identify_specialization_areas(self, certificates):
        """Identificar áreas de especialización"""
        categories = certificates.values_list('enrollment__course__category', flat=True)
        category_counts = {}
        for cat in categories:
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        return sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    
    def assess_category_expertise(self, completed_count):
        """Evaluar nivel de expertise en una categoría"""
        if completed_count >= 10:
            return "expert"
        elif completed_count >= 5:
            return "advanced"
        elif completed_count >= 2:
            return "intermediate"
        else:
            return "beginner"
    
    def generate_learning_path(self, course, applicant):
        """Generar sugerencias de ruta de aprendizaje"""
        # Simplificado - retornar cursos relacionados
        return []
    
    def generate_embed_code(self, certificate):
        """Generar código embed para el certificado"""
        if not certificate.is_public:
            return None
        
        public_url = self.build_public_certificate_url(certificate)
        return f'<iframe src="{public_url}" width="600" height="400" frameborder="0"></iframe>'
    
    def validate_certificate_id_format(self, cert_id):
        """Validar formato del ID del certificado"""
        import re
        pattern = r'^MERAKI-[A-Z0-9]{8}$'
        return bool(re.match(pattern, cert_id))
    
    def validate_certificate_dates(self, certificate):
        """Validar consistencia de fechas"""
        enrollment = certificate.enrollment
        return (certificate.issued_at >= enrollment.completed_at and 
                enrollment.completed_at >= enrollment.enrolled_at)
    
    def check_certificate_expiration(self, certificate):
        """Verificar si el certificado ha expirado"""
        # Los certificados de Meraki no expiran por defecto
        return True
    
    def get_certificate_warnings(self, validations):
        """Obtener advertencias sobre el certificado"""
        warnings = []
        if not validations.get('file_exists'):
            warnings.append("Archivo PDF no disponible")
        if not validations.get('dates_consistent'):
            warnings.append("Inconsistencia en fechas")
        if not validations.get('course_active'):
            warnings.append("Curso ya no está activo")
        return warnings

# Views para instructores/administradores
class ManageCoursesView(InstructorRequiredMixin, ListView):
    model = Course
    template_name = 'courses/manage_courses.html'
    context_object_name = 'courses'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = Course.objects.all().annotate(
            enrollment_count=Count('enrollment')
        ).order_by('-created_at')
        
        # Filtros
        status = self.request.GET.get('status')
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        courses = Course.objects.all()
        context.update({
            'total_courses': courses.count(),
            'active_courses': courses.filter(is_active=True).count(),
            'total_enrollments': Enrollment.objects.count(),
            'certificates_issued': Certificate.objects.count(),
        })
        
        return context

class CreateCourseView(InstructorRequiredMixin, CreateView):
    model = Course
    template_name = 'courses/create_course.html'
    fields = [
        'title', 'description', 'category', 'difficulty_level',
        'duration_hours', 'instructor', 'prerequisites', 'is_featured'
    ]
    success_url = reverse_lazy('courses:manage_courses')
    
    def form_valid(self, form):
        messages.success(self.request, f'Curso "{form.instance.title}" creado exitosamente.')
        return super().form_valid(form)

class CourseStudentsView(InstructorRequiredMixin, DetailView):
    model = Course
    template_name = 'courses/course_students.html'
    context_object_name = 'course'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object
        
        enrollments = Enrollment.objects.filter(
            course=course
        ).select_related('applicant__user').order_by('-enrolled_at')
        
        # Filtros
        status_filter = self.request.GET.get('status')
        if status_filter:
            enrollments = enrollments.filter(status=status_filter)
        
        # Paginación
        paginator = Paginator(enrollments, 20)
        page_number = self.request.GET.get('page')
        enrollments_page = paginator.get_page(page_number)
        
        context.update({
            'enrollments': enrollments_page,
            'total_students': enrollments.count(),
            'status_counts': {
                'enrolled': enrollments.filter(status='enrolled').count(),
                'completed': enrollments.filter(status='completed').count(),
                'cancelled': enrollments.filter(status='cancelled').count(),
            },
            'completion_rate': self.calculate_completion_rate(course),
            'avg_progress': enrollments.aggregate(
                avg_progress=Avg('progress_percentage')
            )['avg_progress'] or 0,
        })
        
        return context
    
    def calculate_completion_rate(self, course):
        total = course.enrollment_set.count()
        if total == 0:
            return 0
        completed = course.enrollment_set.filter(status='completed').count()
        return (completed / total) * 100

# 1. Vistas de Certificados
class VerifyCertificateView(TemplateView):
    """Vista para verificar la autenticidad de un certificado"""
    template_name = 'courses/verify_certificate.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        certificate_id = self.request.GET.get('id') or self.kwargs.get('pk')
        
        if certificate_id:
            try:
                certificate = Certificate.objects.get(certificate_id=certificate_id)
                context.update({
                    'certificate': certificate,
                    'is_valid': True,
                    'verification_details': {
                        'student_name': certificate.enrollment.applicant.user.get_full_name(),
                        'course_title': certificate.enrollment.course.title,
                        'completion_date': certificate.enrollment.completed_at,
                        'issue_date': certificate.issued_at,
                        'certificate_id': certificate.certificate_id,
                    }
                })
            except Certificate.DoesNotExist:
                context.update({
                    'certificate': None,
                    'is_valid': False,
                    'error': 'Certificado no encontrado'
                })
        
        return context

class PublicCertificateView(DetailView):
    """Vista pública para mostrar un certificado compartible"""
    model = Certificate
    template_name = 'courses/public_certificate.html'
    context_object_name = 'certificate'
    slug_field = 'certificate_id'
    slug_url_kwarg = 'certificate_id'
    
    def get_queryset(self):
        return Certificate.objects.filter(is_public=True).select_related(
            'enrollment__course',
            'enrollment__applicant__user'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        certificate = self.object
        
        context.update({
            'student_name': certificate.enrollment.applicant.user.get_full_name(),
            'course': certificate.enrollment.course,
            'completion_stats': self.get_completion_stats(certificate.enrollment),
            'verification_url': self.build_verification_url(certificate),
            'social_sharing': self.get_social_sharing_data(certificate),
        })
        
        return context
    
    def get_completion_stats(self, enrollment):
        """Obtener estadísticas de completación"""
        return {
            'completion_time': (enrollment.completed_at - enrollment.enrolled_at).days,
            'final_progress': enrollment.progress_percentage,
            'lessons_completed': enrollment.lessonprogress_set.filter(is_completed=True).count(),
            'total_lessons': enrollment.course.lesson_set.filter(is_active=True).count(),
        }
    
    def build_verification_url(self, certificate):
        """Construir URL de verificación"""
        return self.request.build_absolute_uri(
            reverse('courses:verify_certificate', kwargs={'pk': certificate.pk})
        )
    
    def get_social_sharing_data(self, certificate):
        """Datos para compartir en redes sociales"""
        return {
            'title': f"Certificado de {certificate.enrollment.course.title}",
            'description': f"Certificado obtenido por completar exitosamente el curso {certificate.enrollment.course.title}",
            'image_url': certificate.enrollment.course.image.url if certificate.enrollment.course.image else None,
        }

# 2. Vistas de Gestión de Cursos
class EditCourseView(InstructorRequiredMixin, UpdateView):
    """Vista para editar un curso existente"""
    model = Course
    template_name = 'courses/edit_course.html'
    fields = [
        'title', 'description', 'category', 'difficulty_level',
        'duration_hours', 'instructor', 'prerequisites', 'is_featured', 'is_active'
    ]
    
    def get_success_url(self):
        messages.success(
            self.request, 
            f'Curso "{self.object.title}" actualizado exitosamente.'
        )
        return reverse('courses:manage_courses')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object
        
        context.update({
            'course_stats': {
                'total_enrollments': course.enrollment_set.count(),
                'active_enrollments': course.enrollment_set.filter(status='enrolled').count(),
                'completed_enrollments': course.enrollment_set.filter(status='completed').count(),
                'avg_progress': course.enrollment_set.aggregate(
                    avg_progress=Avg('progress_percentage')
                )['avg_progress'] or 0,
            },
            'recent_enrollments': course.enrollment_set.select_related(
                'applicant__user'
            ).order_by('-enrolled_at')[:5],
        })
        
        return context

class DeleteCourseView(InstructorRequiredMixin, DeleteView):
    """Vista para eliminar un curso"""
    model = Course
    template_name = 'courses/delete_course.html'
    success_url = reverse_lazy('courses:manage_courses')
    
    def delete(self, request, *args, **kwargs):
        course = self.get_object()
        course_title = course.title
        
        # Verificar si tiene inscripciones activas
        active_enrollments = course.enrollment_set.filter(status='enrolled').count()
        if active_enrollments > 0:
            messages.error(
                request,
                f'No se puede eliminar el curso "{course_title}" porque tiene {active_enrollments} estudiantes activos.'
            )
            return redirect('courses:manage_courses')
        
        # En lugar de eliminar, desactivar el curso
        course.is_active = False
        course.save()
        
        messages.success(
            request,
            f'Curso "{course_title}" desactivado exitosamente.'
        )
        return redirect('courses:manage_courses')

class CourseAnalyticsView(InstructorRequiredMixin, DetailView):
    """Vista para mostrar analíticas detalladas de un curso"""
    model = Course
    template_name = 'courses/course_analytics.html'
    context_object_name = 'course'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object
        
        # Estadísticas generales
        enrollments = course.enrollment_set.all()
        general_stats = {
            'total_enrollments': enrollments.count(),
            'active_enrollments': enrollments.filter(status='enrolled').count(),
            'completed_enrollments': enrollments.filter(status='completed').count(),
            'cancelled_enrollments': enrollments.filter(status='cancelled').count(),
            'completion_rate': self.calculate_completion_rate(course),
            'avg_progress': enrollments.aggregate(avg_progress=Avg('progress_percentage'))['avg_progress'] or 0,
        }
        
        # Análisis temporal
        temporal_analysis = self.get_temporal_analysis(enrollments)
        
        # Análisis de rendimiento
        performance_analysis = self.get_performance_analysis(course)
        
        # Feedback y calificaciones (si existe sistema de rating)
        feedback_analysis = self.get_feedback_analysis(course)
        
        # Análisis demográfico
        demographic_analysis = self.get_demographic_analysis(enrollments)
        
        context.update({
            'general_stats': general_stats,
            'temporal_analysis': temporal_analysis,
            'performance_analysis': performance_analysis,
            'feedback_analysis': feedback_analysis,
            'demographic_analysis': demographic_analysis,
            'chart_data': self.prepare_analytics_chart_data(course),
        })
        
        return context
    
    def calculate_completion_rate(self, course):
        """Calcular tasa de completación"""
        total = course.enrollment_set.count()
        if total == 0:
            return 0
        completed = course.enrollment_set.filter(status='completed').count()
        return round((completed / total) * 100, 2)
    
    def get_temporal_analysis(self, enrollments):
        """Análisis temporal de inscripciones y completaciones"""
        # Inscripciones por mes
        monthly_enrollments = enrollments.extra(
            select={'month': 'DATE_FORMAT(enrolled_at, "%%Y-%%m")'}
        ).values('month').annotate(count=Count('id')).order_by('month')
        
        # Completaciones por mes
        monthly_completions = enrollments.filter(
            status='completed'
        ).extra(
            select={'month': 'DATE_FORMAT(completed_at, "%%Y-%%m")'}
        ).values('month').annotate(count=Count('id')).order_by('month')
        
        return {
            'monthly_enrollments': list(monthly_enrollments),
            'monthly_completions': list(monthly_completions),
            'peak_enrollment_month': self.get_peak_month(monthly_enrollments),
        }
    
    def get_performance_analysis(self, course):
        """Análisis de rendimiento de estudiantes"""
        enrollments = course.enrollment_set.filter(status__in=['enrolled', 'completed'])
        
        if not enrollments.exists():
            return {}
        
        # Distribución de progreso
        progress_distribution = {
            'low': enrollments.filter(progress_percentage__lt=25).count(),
            'medium': enrollments.filter(progress_percentage__gte=25, progress_percentage__lt=75).count(),
            'high': enrollments.filter(progress_percentage__gte=75, progress_percentage__lt=100).count(),
            'completed': enrollments.filter(progress_percentage=100).count(),
        }
        
        # Tiempo promedio de completación
        completed_enrollments = enrollments.filter(status='completed')
        completion_times = []
        for enrollment in completed_enrollments:
            if enrollment.completed_at and enrollment.enrolled_at:
                days = (enrollment.completed_at - enrollment.enrolled_at).days
                completion_times.append(days)
        
        avg_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0
        
        return {
            'progress_distribution': progress_distribution,
            'avg_completion_time_days': round(avg_completion_time, 1),
            'fastest_completion': min(completion_times) if completion_times else 0,
            'slowest_completion': max(completion_times) if completion_times else 0,
            'quiz_performance': self.get_quiz_performance_stats(course),
        }
    
    def get_quiz_performance_stats(self, course):
        """Estadísticas de rendimiento en quizzes"""
        quiz_attempts = QuizAttempt.objects.filter(enrollment__course=course)
        
        if not quiz_attempts.exists():
            return {}
        
        return {
            'total_attempts': quiz_attempts.count(),
            'avg_score': quiz_attempts.aggregate(avg_score=Avg('score'))['avg_score'] or 0,
            'pass_rate': quiz_attempts.filter(is_passed=True).count() / quiz_attempts.count() * 100,
            'most_difficult_quiz': self.get_most_difficult_quiz(course),
        }
    
    def get_feedback_analysis(self, course):
        """Análisis de feedback (placeholder para futuro sistema de ratings)"""
        return {
            'avg_rating': 4.5,  # Placeholder
            'total_reviews': 0,
            'rating_distribution': {5: 0, 4: 0, 3: 0, 2: 0, 1: 0},
        }
    
    def get_demographic_analysis(self, enrollments):
        """Análisis demográfico de estudiantes"""
        # Esto dependería de los campos disponibles en el perfil del usuario
        return {
            'total_students': enrollments.values('applicant').distinct().count(),
            'top_locations': [],  # Placeholder
            'age_distribution': {},  # Placeholder
        }
    
    def prepare_analytics_chart_data(self, course):
        """Preparar datos para gráficos"""
        return {
            'enrollment_trend': [],  # Datos para gráfico de tendencia
            'progress_distribution': [],  # Datos para gráfico de distribución
            'completion_timeline': [],  # Datos para línea de tiempo
        }
    
    def get_peak_month(self, monthly_data):
        """Obtener mes con más inscripciones"""
        if not monthly_data:
            return None
        return max(monthly_data, key=lambda x: x['count'])
    
    def get_most_difficult_quiz(self, course):
        """Identificar quiz más difícil basado en tasa de aprobación"""
        quizzes = course.quiz_set.filter(is_active=True)
        quiz_stats = []
        
        for quiz in quizzes:
            attempts = QuizAttempt.objects.filter(quiz=quiz)
            if attempts.exists():
                pass_rate = attempts.filter(is_passed=True).count() / attempts.count() * 100
                quiz_stats.append({
                    'quiz': quiz,
                    'pass_rate': pass_rate,
                    'avg_score': attempts.aggregate(avg_score=Avg('score'))['avg_score'] or 0,
                })
        
        return min(quiz_stats, key=lambda x: x['pass_rate']) if quiz_stats else None

# 3. Vistas de Lecciones
class CourseLessonsView(ApplicantRequiredMixin, DetailView):
    """Vista para mostrar todas las lecciones de un curso"""
    model = Course
    template_name = 'courses/course_lessons.html'
    context_object_name = 'course'
    pk_url_kwarg = 'course_id'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object
        
        # Verificar inscripción
        try:
            enrollment = Enrollment.objects.get(
                course=course,
                applicant=self.request.user.applicantprofile,
                status='enrolled'
            )
        except Enrollment.DoesNotExist:
            raise PermissionDenied("No estás inscrito en este curso")
        
        # Obtener lecciones con progreso
        lessons = course.lesson_set.filter(is_active=True).order_by('order')
        lesson_progress_data = []
        
        for lesson in lessons:
            try:
                progress = LessonProgress.objects.get(
                    enrollment=enrollment,
                    lesson=lesson
                )
            except LessonProgress.DoesNotExist:
                progress = None
            
            lesson_progress_data.append({
                'lesson': lesson,
                'progress': progress,
                'is_completed': progress.is_completed if progress else False,
                'time_spent': progress.time_spent if progress else 0,
            })
        
        context.update({
            'enrollment': enrollment,
            'lesson_progress_data': lesson_progress_data,
            'total_lessons': lessons.count(),
            'completed_lessons': sum(1 for lpd in lesson_progress_data if lpd['is_completed']),
            'next_lesson': self.get_next_lesson(lesson_progress_data),
        })
        
        return context
    
    def get_next_lesson(self, lesson_progress_data):
        """Obtener la próxima lección no completada"""
        for lpd in lesson_progress_data:
            if not lpd['is_completed']:
                return lpd['lesson']
        return None

class LessonDetailView(ApplicantRequiredMixin, DetailView):
    """Vista para mostrar el detalle de una lección"""
    model = Lesson
    template_name = 'courses/lesson_detail.html'
    context_object_name = 'lesson'
    pk_url_kwarg = 'lesson_id'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lesson = self.object
        course_id = self.kwargs['course_id']
        
        # Verificar que la lección pertenece al curso
        if lesson.course.id != course_id:
            raise Http404("Lección no encontrada en este curso")
        
        # Verificar inscripción
        try:
            enrollment = Enrollment.objects.get(
                course_id=course_id,
                applicant=self.request.user.applicantprofile,
                status='enrolled'
            )
        except Enrollment.DoesNotExist:
            raise PermissionDenied("No estás inscrito en este curso")
        
        # Obtener o crear progreso de la lección
        lesson_progress, created = LessonProgress.objects.get_or_create(
            enrollment=enrollment,
            lesson=lesson,
            defaults={'time_spent': 0, 'is_completed': False}
        )
        
        # Actualizar último acceso
        enrollment.last_accessed = timezone.now()
        enrollment.save(update_fields=['last_accessed'])
        
        # Obtener lecciones anterior y siguiente
        prev_lesson, next_lesson = self.get_adjacent_lessons(lesson)
        
        context.update({
            'course': lesson.course,
            'enrollment': enrollment,
            'lesson_progress': lesson_progress,
            'prev_lesson': prev_lesson,
            'next_lesson': next_lesson,
            'all_lessons': lesson.course.lesson_set.filter(is_active=True).order_by('order'),
        })
        
        return context
    
    def get_adjacent_lessons(self, current_lesson):
        """Obtener lecciones anterior y siguiente"""
        lessons = current_lesson.course.lesson_set.filter(
            is_active=True
        ).order_by('order')
        
        lesson_list = list(lessons)
        current_index = lesson_list.index(current_lesson)
        
        prev_lesson = lesson_list[current_index - 1] if current_index > 0 else None
        next_lesson = lesson_list[current_index + 1] if current_index < len(lesson_list) - 1 else None
        
        return prev_lesson, next_lesson

class CompleteLessonView(ApplicantRequiredMixin, View):
    """Vista para marcar una lección como completada"""
    
    def post(self, request, pk):
        lesson = get_object_or_404(Lesson, pk=pk)
        
        # Verificar inscripción
        try:
            enrollment = Enrollment.objects.get(
                course=lesson.course,
                applicant=request.user.applicantprofile,
                status='enrolled'
            )
        except Enrollment.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'No estás inscrito en este curso'
            })
        
        # Actualizar progreso de la lección
        lesson_progress, created = LessonProgress.objects.get_or_create(
            enrollment=enrollment,
            lesson=lesson,
            defaults={'time_spent': 0, 'is_completed': False}
        )
        
        if not lesson_progress.is_completed:
            lesson_progress.is_completed = True
            lesson_progress.completed_at = timezone.now()
            
            # Agregar tiempo si se proporciona
            time_spent = request.POST.get('time_spent', 0)
            if time_spent:
                lesson_progress.time_spent += int(time_spent)
            
            lesson_progress.save()
            
            # Actualizar progreso general del curso
            self.update_course_progress(enrollment)
            
            return JsonResponse({
                'success': True,
                'message': 'Lección completada exitosamente',
                'new_progress': enrollment.progress_percentage
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Esta lección ya está completada'
            })
    
    def update_course_progress(self, enrollment):
        """Actualizar el progreso general del curso"""
        total_lessons = enrollment.course.lesson_set.filter(is_active=True).count()
        completed_lessons = LessonProgress.objects.filter(
            enrollment=enrollment,
            is_completed=True,
            lesson__is_active=True
        ).count()
        
        if total_lessons > 0:
            progress_percentage = (completed_lessons / total_lessons) * 100
            enrollment.progress_percentage = min(progress_percentage, 100)
            enrollment.save(update_fields=['progress_percentage'])

# 4. Vistas de Quizzes
class CourseQuizView(ApplicantRequiredMixin, DetailView):
    """Vista para mostrar los quizzes de un curso"""
    model = Course
    template_name = 'courses/course_quiz.html'
    context_object_name = 'course'
    pk_url_kwarg = 'course_id'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object
        
        # Verificar inscripción
        try:
            enrollment = Enrollment.objects.get(
                course=course,
                applicant=self.request.user.applicantprofile,
                status='enrolled'
            )
        except Enrollment.DoesNotExist:
            raise PermissionDenied("No estás inscrito en este curso")
        
        # Obtener quizzes con intentos del estudiante
        quizzes = course.quiz_set.filter(is_active=True)
        quiz_data = []
        
        for quiz in quizzes:
            attempts = QuizAttempt.objects.filter(
                enrollment=enrollment,
                quiz=quiz
            ).order_by('-attempted_at')
            
            best_attempt = attempts.order_by('-score').first()
            
            quiz_data.append({
                'quiz': quiz,
                'attempts': attempts,
                'best_attempt': best_attempt,
                'total_attempts': attempts.count(),
                'is_passed': best_attempt.is_passed if best_attempt else False,
                'can_attempt': self.can_attempt_quiz(quiz, attempts),
            })
        
        context.update({
            'enrollment': enrollment,
            'quiz_data': quiz_data,
            'total_quizzes': quizzes.count(),
            'passed_quizzes': sum(1 for qd in quiz_data if qd['is_passed']),
        })
        
        return context
    
    def can_attempt_quiz(self, quiz, attempts):
        """Verificar si se puede intentar el quiz"""
        max_attempts = getattr(quiz, 'max_attempts', None)
        if max_attempts and attempts.count() >= max_attempts:
            return False
        
        # Verificar tiempo entre intentos si existe
        last_attempt = attempts.first()
        if last_attempt and hasattr(quiz, 'retry_delay_hours'):
            time_since_last = timezone.now() - last_attempt.attempted_at
            if time_since_last.total_seconds() < quiz.retry_delay_hours * 3600:
                return False
        
        return True

class QuizAttemptView(ApplicantRequiredMixin, DetailView):
    """Vista para realizar un intento de quiz"""
    model = Quiz
    template_name = 'courses/quiz_attempt.html'
    context_object_name = 'quiz'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        quiz = self.object
        
        # Verificar inscripción
        try:
            enrollment = Enrollment.objects.get(
                course=quiz.course,
                applicant=self.request.user.applicantprofile,
                status='enrolled'
            )
        except Enrollment.DoesNotExist:
            raise PermissionDenied("No estás inscrito en este curso")
        
        # Verificar si puede intentar el quiz
        previous_attempts = QuizAttempt.objects.filter(
            enrollment=enrollment,
            quiz=quiz
        ).order_by('-attempted_at')
        
        if not self.can_attempt_quiz(quiz, previous_attempts):
            messages.error(self.request, "No puedes intentar este quiz en este momento.")
            return redirect('courses:course_quiz', course_id=quiz.course.id)
        
        # Obtener preguntas del quiz (en orden aleatorio si está configurado)
        questions = quiz.question_set.filter(is_active=True)
        if getattr(quiz, 'randomize_questions', False):
            questions = questions.order_by('?')
        else:
            questions = questions.order_by('order')
        
        context.update({
            'enrollment': enrollment,
            'questions': questions,
            'previous_attempts': previous_attempts,
            'attempt_number': previous_attempts.count() + 1,
            'time_limit': getattr(quiz, 'time_limit_minutes', None),
        })
        
        return context
    
    def can_attempt_quiz(self, quiz, attempts):
        """Verificar si se puede intentar el quiz"""
        max_attempts = getattr(quiz, 'max_attempts', None)
        if max_attempts and attempts.count() >= max_attempts:
            return False
        return True
    
    def post(self, request, pk):
        """Procesar respuestas del quiz"""
        quiz = get_object_or_404(Quiz, pk=pk)
        
        try:
            enrollment = Enrollment.objects.get(
                course=quiz.course,
                applicant=request.user.applicantprofile,
                status='enrolled'
            )
        except Enrollment.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'No estás inscrito en este curso'
            })
        
        # Procesar respuestas y calcular puntuación
        answers = request.POST.getlist('answers')
        score = self.calculate_quiz_score(quiz, answers)
        
        # Crear intento de quiz
        quiz_attempt = QuizAttempt.objects.create(
            enrollment=enrollment,
            quiz=quiz,
            score=score,
            answers=answers,  # Guardar como JSON si el campo lo permite
            time_taken=request.POST.get('time_taken', 0),
            attempted_at=timezone.now()
        )
        
        return redirect('courses:quiz_results', pk=quiz_attempt.pk)
    
    def calculate_quiz_score(self, quiz, answers):
        """Calcular puntuación del quiz"""
        questions = quiz.question_set.filter(is_active=True).order_by('order')
        correct_answers = 0
        total_questions = questions.count()
        
        for i, question in enumerate(questions):
            if i < len(answers):
                # Lógica para verificar respuesta correcta
                # Esto dependería de cómo estructures las preguntas
                if self.is_correct_answer(question, answers[i]):
                    correct_answers += 1
        
        return (correct_answers / total_questions) * 100 if total_questions > 0 else 0
    
    def is_correct_answer(self, question, answer):
        """Verificar si la respuesta es correcta"""
        # Implementar lógica según el tipo de pregunta
        # Esto es un placeholder
        return True

class QuizResultsView(ApplicantRequiredMixin, DetailView):
    """Vista para mostrar resultados de un quiz"""
    model = QuizAttempt
    template_name = 'courses/quiz_results.html'
    context_object_name = 'quiz_attempt'
    
    def get_queryset(self):
        return QuizAttempt.objects.filter(
            enrollment__applicant=self.request.user.applicantprofile
        ).select_related('quiz', 'enrollment__course')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        quiz_attempt = self.object
        quiz = quiz_attempt.quiz
        
        # Análisis detallado de respuestas
        answer_analysis = self.analyze_answers(quiz_attempt)
        
        # Comparación con otros intentos
        all_attempts = QuizAttempt.objects.filter(
            enrollment=quiz_attempt.enrollment,
            quiz=quiz
        ).order_by('-attempted_at')
        
        # Estadísticas del quiz
        quiz_stats = self.get_quiz_statistics(quiz)
        
        context.update({
            'quiz': quiz,
            'course': quiz.course,
            'is_passed': quiz_attempt.is_passed,
            'passing_score': quiz.passing_score,
            'answer_analysis': answer_analysis,
            'all_attempts': all_attempts,
            'attempt_number': all_attempts.count(),
            'best_score': all_attempts.aggregate(best_score=Max('score'))['best_score'],
            'quiz_stats': quiz_stats,
            'can_retake': self.can_retake_quiz(quiz, all_attempts),
        })
        
        return context
    
    def analyze_answers(self, quiz_attempt):
        """Analizar respuestas del intento"""
        # Placeholder para análisis detallado
        return {
            'correct_count': 0,
            'incorrect_count': 0,
            'question_breakdown': []
        }
    
    def get_quiz_statistics(self, quiz):
        """Obtener estadísticas del quiz"""
        all_attempts = QuizAttempt.objects.filter(quiz=quiz)
        
        if not all_attempts.exists():
            return {}
        
        return {
            'avg_score': all_attempts.aggregate(avg_score=Avg('score'))['avg_score'],
            'pass_rate': all_attempts.filter(is_passed=True).count() / all_attempts.count() * 100,
            'total_attempts': all_attempts.count(),
            'highest_score': all_attempts.aggregate(max_score=Max('score'))['max_score'],
        }
    
    def can_retake_quiz(self, quiz, attempts):
        """Verificar si se puede volver a intentar el quiz"""
        if hasattr(quiz, 'max_attempts'):
            return attempts.count() < quiz.max_attempts
        return True

# 5. Vistas de Foro (básicas)
class CourseForumView(ApplicantRequiredMixin, DetailView):
    """Vista del foro de un curso"""
    model = Course
    template_name = 'courses/course_forum.html'
    context_object_name = 'course'
    pk_url_kwarg = 'course_id'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object
        
        # Verificar inscripción
        try:
            enrollment = Enrollment.objects.get(
                course=course,
                applicant=self.request.user.applicantprofile,
                status='enrolled'
            )
        except Enrollment.DoesNotExist:
            raise PermissionDenied("No estás inscrito en este curso")
        
        # Obtener temas del foro (necesitarías crear modelo ForumTopic)
        # Por ahora retornamos estructura básica
        context.update({
            'enrollment': enrollment,
            'forum_topics': [],  # Placeholder para ForumTopic.objects.filter(course=course)
            'can_create_topic': True,
            'total_topics': 0,
            'total_posts': 0,
        })
        
        return context

class ForumTopicView(ApplicantRequiredMixin, DetailView):
    """Vista de un tema específico del foro"""
    # model = ForumTopic  # Necesitarías crear este modelo
    template_name = 'courses/forum_topic.html'
    context_object_name = 'topic'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Implementación básica para cuando tengas el modelo ForumTopic
        context.update({
            'posts': [],  # ForumPost.objects.filter(topic=self.object)
            'can_reply': True,
        })
        return context

class CreateForumTopicView(ApplicantRequiredMixin, TemplateView):
    """Vista para crear un nuevo tema en el foro"""
    template_name = 'courses/create_forum_topic.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Obtener curso del parámetro GET
        course_id = self.request.GET.get('course_id')
        if course_id:
            try:
                course = Course.objects.get(id=course_id)
                context['course'] = course
            except Course.DoesNotExist:
                pass
        
        return context
    
    def post(self, request):
        # Lógica para crear nuevo tema del foro
        # Placeholder hasta tener el modelo ForumTopic
        messages.success(request, "Tema creado exitosamente")
        course_id = request.POST.get('course_id')
        return redirect('courses:course_forum', course_id=course_id)

# 6. Vistas de Estadísticas y Reportes
class CourseStatsView(ApplicantRequiredMixin, TemplateView):
    """Vista de estadísticas personales del estudiante"""
    template_name = 'courses/course_stats.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        applicant = self.request.user.applicantprofile
        
        # Estadísticas generales
        all_enrollments = Enrollment.objects.filter(applicant=applicant)
        
        general_stats = {
            'total_enrollments': all_enrollments.count(),
            'active_courses': all_enrollments.filter(status='enrolled').count(),
            'completed_courses': all_enrollments.filter(status='completed').count(),
            'cancelled_courses': all_enrollments.filter(status='cancelled').count(),
            'certificates_earned': Certificate.objects.filter(enrollment__applicant=applicant).count(),
            'total_study_hours': self.calculate_total_study_hours(applicant),
            'avg_completion_time': self.calculate_avg_completion_time(all_enrollments),
        }
        
        # Estadísticas por categoría
        category_stats = self.get_category_statistics(all_enrollments)
        
        # Progreso mensual
        monthly_progress = self.get_monthly_progress(all_enrollments)
        
        # Comparación con otros estudiantes
        comparative_stats = self.get_comparative_statistics(applicant)
        
        # Logros y badges
        achievements = self.calculate_achievements(applicant)
        
        # Tendencias de aprendizaje
        learning_trends = self.analyze_learning_trends(all_enrollments)
        
        context.update({
            'general_stats': general_stats,
            'category_stats': category_stats,
            'monthly_progress': monthly_progress,
            'comparative_stats': comparative_stats,
            'achievements': achievements,
            'learning_trends': learning_trends,
            'chart_data': self.prepare_stats_chart_data(all_enrollments),
        })
        
        return context
    
    def calculate_total_study_hours(self, applicant):
        """Calcular total de horas de estudio"""
        total_minutes = LessonProgress.objects.filter(
            enrollment__applicant=applicant
        ).aggregate(total_time=Sum('time_spent'))['total_time'] or 0
        
        return round(total_minutes / 60, 1)
    
    def calculate_avg_completion_time(self, enrollments):
        """Calcular tiempo promedio de completación"""
        completed = enrollments.filter(status='completed')
        completion_times = []
        
        for enrollment in completed:
            if enrollment.completed_at and enrollment.enrolled_at:
                days = (enrollment.completed_at - enrollment.enrolled_at).days
                completion_times.append(days)
        
        return round(sum(completion_times) / len(completion_times), 1) if completion_times else 0
    
    def get_category_statistics(self, enrollments):
        """Obtener estadísticas por categoría"""
        category_data = enrollments.values('course__category').annotate(
            total=Count('id'),
            completed=Count('id', filter=Q(status='completed')),
            avg_progress=Avg('progress_percentage')
        ).order_by('-total')
        
        return list(category_data)
    
    def get_monthly_progress(self, enrollments):
        """Obtener progreso por mes"""
        # Últimos 12 meses de actividad
        monthly_data = []
        current_date = timezone.now().date()
        
        for i in range(12):
            month_start = (current_date.replace(day=1) - timedelta(days=i*30)).replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            enrollments_month = enrollments.filter(
                enrolled_at__date__range=[month_start, month_end]
            ).count()
            
            completions_month = enrollments.filter(
                completed_at__date__range=[month_start, month_end]
            ).count()
            
            monthly_data.append({
                'month': month_start.strftime('%b %Y'),
                'enrollments': enrollments_month,
                'completions': completions_month,
            })
        
        return list(reversed(monthly_data))
    
    def get_comparative_statistics(self, applicant):
        """Obtener estadísticas comparativas"""
        # Comparar con promedio de la plataforma
        platform_avg_completion_rate = Enrollment.objects.aggregate(
            completion_rate=Count('id', filter=Q(status='completed')) * 100.0 / Count('id')
        )['completion_rate'] or 0
        
        user_enrollments = Enrollment.objects.filter(applicant=applicant)
        user_completion_rate = user_enrollments.filter(status='completed').count() / user_enrollments.count() * 100 if user_enrollments.count() > 0 else 0
        
        return {
            'platform_avg_completion_rate': round(platform_avg_completion_rate, 1),
            'user_completion_rate': round(user_completion_rate, 1),
            'performance_vs_average': 'above' if user_completion_rate > platform_avg_completion_rate else 'below',
            'percentile_rank': self.calculate_percentile_rank(applicant),
        }
    
    def calculate_achievements(self, applicant):
        """Calcular logros del estudiante"""
        enrollments = Enrollment.objects.filter(applicant=applicant)
        certificates = Certificate.objects.filter(enrollment__applicant=applicant)
        
        achievements = []
        
        # Logros por número de cursos completados
        completed_count = enrollments.filter(status='completed').count()
        if completed_count >= 50:
            achievements.append({'name': 'Maestro del Aprendizaje', 'icon': 'fas fa-crown', 'color': 'gold'})
        elif completed_count >= 25:
            achievements.append({'name': 'Estudiante Experto', 'icon': 'fas fa-medal', 'color': 'silver'})
        elif completed_count >= 10:
            achievements.append({'name': 'Estudiante Dedicado', 'icon': 'fas fa-award', 'color': 'bronze'})
        
        # Logros por diversidad de categorías
        unique_categories = enrollments.values('course__category').distinct().count()
        if unique_categories >= 5:
            achievements.append({'name': 'Explorador del Conocimiento', 'icon': 'fas fa-compass', 'color': 'green'})
        
        return achievements
    
    def analyze_learning_trends(self, enrollments):
        """Analizar tendencias de aprendizaje"""
        # Análisis de mejora a lo largo del tiempo
        completed_by_month = enrollments.filter(status='completed').extra(
            select={'month': 'DATE_FORMAT(completed_at, "%%Y-%%m")'}
        ).values('month').annotate(count=Count('id')).order_by('month')
        
        trend = 'stable'
        if len(completed_by_month) >= 3:
            recent_months = list(completed_by_month)[-3:]
            if recent_months[-1]['count'] > recent_months[0]['count']:
                trend = 'improving'
            elif recent_months[-1]['count'] < recent_months[0]['count']:
                trend = 'declining'
        
        return {
            'completion_trend': trend,
            'most_productive_month': max(completed_by_month, key=lambda x: x['count']) if completed_by_month else None,
            'consistency_score': self.calculate_consistency_score(enrollments),
        }
    
    def calculate_percentile_rank(self, applicant):
        """Calcular percentil del estudiante"""
        user_completed = Enrollment.objects.filter(applicant=applicant, status='completed').count()
        
        # Contar cuántos estudiantes tienen menos cursos completados
        students_with_less = User.objects.filter(
            applicantprofile__enrollment__status='completed'
        ).annotate(
            completed_count=Count('applicantprofile__enrollment')
        ).filter(completed_count__lt=user_completed).count()
        
        total_students = User.objects.filter(user_type='applicant').count()
        
        if total_students > 0:
            percentile = (students_with_less / total_students) * 100
            return round(percentile, 1)
        
        return 0
    
    def calculate_consistency_score(self, enrollments):
        """Calcular puntuación de consistencia"""
        # Simplificado - basado en frecuencia de completaciones
        completed = enrollments.filter(status='completed')
        if completed.count() < 2:
            return 0
        
        # Calcular intervalos entre completaciones
        completion_dates = completed.values_list('completed_at__date', flat=True).order_by('completed_at')
        intervals = []
        
        for i in range(1, len(completion_dates)):
            interval = (completion_dates[i] - completion_dates[i-1]).days
            intervals.append(interval)
        
        if intervals:
            avg_interval = sum(intervals) / len(intervals)
            # Puntuación inversa: menor intervalo = mayor consistencia
            consistency = max(0, 100 - (avg_interval / 30 * 100))  # Normalizado a 30 días
            return round(min(consistency, 100), 1)
        
        return 0
    
    def prepare_stats_chart_data(self, enrollments):
        """Preparar datos para gráficos"""
        return {
            'progress_over_time': [],
            'category_distribution': [],
            'completion_timeline': [],
        }

class CourseReportsView(InstructorRequiredMixin, TemplateView):
    """Vista de reportes para instructores/administradores"""
    template_name = 'courses/course_reports.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Reportes generales de la plataforma
        platform_stats = self.get_platform_statistics()
        
        # Reportes por curso
        course_performance = self.get_course_performance_report()
        
        # Reportes de estudiantes
        student_analytics = self.get_student_analytics()
        
        # Reportes de certificaciones
        certification_reports = self.get_certification_reports()
        
        # Tendencias temporales
        temporal_trends = self.get_temporal_trends()
        
        context.update({
            'platform_stats': platform_stats,
            'course_performance': course_performance,
            'student_analytics': student_analytics,
            'certification_reports': certification_reports,
            'temporal_trends': temporal_trends,
            'report_data': self.prepare_report_data(),
        })
        
        return context
    
    def get_platform_statistics(self):
        """Estadísticas generales de la plataforma"""
        return {
            'total_courses': Course.objects.count(),
            'active_courses': Course.objects.filter(is_active=True).count(),
            'total_students': User.objects.filter(user_type='applicant').count(),
            'total_enrollments': Enrollment.objects.count(),
            'total_completions': Enrollment.objects.filter(status='completed').count(),
            'total_certificates': Certificate.objects.count(),
            'overall_completion_rate': self.calculate_overall_completion_rate(),
        }
    
    def get_course_performance_report(self):
        """Reporte de rendimiento por curso"""
        courses = Course.objects.annotate(
            total_enrollments=Count('enrollment'),
            completed_enrollments=Count('enrollment', filter=Q(enrollment__status='completed')),
            avg_progress=Avg('enrollment__progress_percentage'),
            avg_rating=Avg('enrollment__rating')  # Si tienes sistema de rating
        ).order_by('-total_enrollments')[:10]
        
        course_data = []
        for course in courses:
            completion_rate = 0
            if course.total_enrollments > 0:
                completion_rate = (course.completed_enrollments / course.total_enrollments) * 100
            
            course_data.append({
                'course': course,
                'completion_rate': round(completion_rate, 2),
                'avg_progress': round(course.avg_progress or 0, 2),
                'performance_score': self.calculate_course_performance_score(course),
            })
        
        return course_data
    
    def get_student_analytics(self):
        """Analytics de estudiantes"""
        return {
            'most_active_students': self.get_most_active_students(),
            'completion_leaders': self.get_completion_leaders(),
            'engagement_metrics': self.calculate_engagement_metrics(),
        }
    
    def get_certification_reports(self):
        """Reportes de certificaciones"""
        certificates = Certificate.objects.select_related('enrollment__course', 'enrollment__applicant__user')
        
        return {
            'total_certificates': certificates.count(),
            'certificates_this_month': certificates.filter(
                issued_at__gte=timezone.now().replace(day=1)
            ).count(),
            'top_certified_courses': self.get_top_certified_courses(),
            'certification_rate_by_category': self.get_certification_rate_by_category(),
        }
    
    def get_temporal_trends(self):
        """Tendencias temporales"""
        # Últimos 12 meses
        monthly_data = []
        for i in range(12):
            month_start = (timezone.now().replace(day=1) - timedelta(days=i*30)).replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            enrollments = Enrollment.objects.filter(
                enrolled_at__date__range=[month_start, month_end]
            ).count()
            
            completions = Enrollment.objects.filter(
                completed_at__date__range=[month_start, month_end]
            ).count()
            
            monthly_data.append({
                'month': month_start.strftime('%b %Y'),
                'enrollments': enrollments,
                'completions': completions,
            })
        
        return {
            'monthly_trends': list(reversed(monthly_data)),
            'growth_rate': self.calculate_growth_rate(),
            'seasonal_patterns': self.identify_seasonal_patterns(),
        }
    
    def calculate_overall_completion_rate(self):
        """Calcular tasa de completación general"""
        total_enrollments = Enrollment.objects.count()
        if total_enrollments == 0:
            return 0
        
        completed_enrollments = Enrollment.objects.filter(status='completed').count()
        return round((completed_enrollments / total_enrollments) * 100, 2)
    
    def calculate_course_performance_score(self, course):
        """Calcular puntuación de rendimiento del curso"""
        # Algoritmo simple basado en múltiples factores
        enrollments = course.total_enrollments
        completion_rate = (course.completed_enrollments / enrollments * 100) if enrollments > 0 else 0
        avg_progress = course.avg_progress or 0
        
        # Puntuación ponderada
        score = (completion_rate * 0.4) + (avg_progress * 0.3) + (min(enrollments, 100) * 0.3)
        return round(score, 2)
    
    def get_most_active_students(self):
        """Obtener estudiantes más activos"""
        return User.objects.filter(user_type='applicant').annotate(
            total_enrollments=Count('applicantprofile__enrollment'),
            completed_courses=Count('applicantprofile__enrollment', filter=Q(applicantprofile__enrollment__status='completed'))
        ).order_by('-total_enrollments')[:5]
    
    def get_completion_leaders(self):
        """Obtener líderes en completaciones"""
        return User.objects.filter(user_type='applicant').annotate(
            completed_count=Count('applicantprofile__enrollment', filter=Q(applicantprofile__enrollment__status='completed'))
        ).filter(completed_count__gt=0).order_by('-completed_count')[:5]
    
    def calculate_engagement_metrics(self):
        """Calcular métricas de engagement"""
        total_students = User.objects.filter(user_type='applicant').count()
        active_students = User.objects.filter(
            user_type='applicant',
            applicantprofile__enrollment__last_accessed__gte=timezone.now() - timedelta(days=30)
        ).distinct().count()
        
        return {
            'active_student_rate': round((active_students / total_students * 100), 2) if total_students > 0 else 0,
            'avg_courses_per_student': Enrollment.objects.count() / total_students if total_students > 0 else 0,
            'avg_study_time_per_student': self.calculate_avg_study_time_per_student(),
        }
    
    def get_top_certified_courses(self):
        """Obtener cursos con más certificaciones"""
        return Course.objects.annotate(
            certificate_count=Count('enrollment__certificate')
        ).filter(certificate_count__gt=0).order_by('-certificate_count')[:5]
    
    def get_certification_rate_by_category(self):
        """Tasa de certificación por categoría"""
        categories = Course.objects.values('category').annotate(
            total_completions=Count('enrollment', filter=Q(enrollment__status='completed')),
            total_certificates=Count('enrollment__certificate')
        ).order_by('-total_certificates')
        
        for category in categories:
            if category['total_completions'] > 0:
                category['certification_rate'] = round(
                    (category['total_certificates'] / category['total_completions']) * 100, 2
                )
            else:
                category['certification_rate'] = 0
        
        return list(categories)
    
    def calculate_growth_rate(self):
        """Calcular tasa de crecimiento"""
        current_month = timezone.now().replace(day=1)
        previous_month = (current_month - timedelta(days=1)).replace(day=1)
        
        current_enrollments = Enrollment.objects.filter(
            enrolled_at__gte=current_month
        ).count()
        
        previous_enrollments = Enrollment.objects.filter(
            enrolled_at__gte=previous_month,
            enrolled_at__lt=current_month
        ).count()
        
        if previous_enrollments > 0:
            growth_rate = ((current_enrollments - previous_enrollments) / previous_enrollments) * 100
            return round(growth_rate, 2)
        
        return 0
    
    def identify_seasonal_patterns(self):
        """Identificar patrones estacionales"""
        # Simplificado - análisis por trimestre
        quarterly_data = []
        current_year = timezone.now().year
        
        for quarter in range(1, 5):
            start_month = (quarter - 1) * 3 + 1
            end_month = quarter * 3
            
            start_date = datetime(current_year, start_month, 1)
            end_date = datetime(current_year, end_month, 1) + timedelta(days=32)
            end_date = end_date.replace(day=1) - timedelta(days=1)
            
            enrollments = Enrollment.objects.filter(
                enrolled_at__date__range=[start_date.date(), end_date.date()]
            ).count()
            
            quarterly_data.append({
                'quarter': f'Q{quarter}',
                'enrollments': enrollments
            })
        
        return quarterly_data
    
    def calculate_avg_study_time_per_student(self):
        """Calcular tiempo promedio de estudio por estudiante"""
        total_time = LessonProgress.objects.aggregate(
            total_time=Sum('time_spent')
        )['total_time'] or 0
        
        total_students = User.objects.filter(user_type='applicant').count()
        
        if total_students > 0:
            avg_hours = (total_time / 60) / total_students
            return round(avg_hours, 2)
        
        return 0
    
    def prepare_report_data(self):
        """Preparar datos para exportación/gráficos"""
        return {
            'chart_data': {},
            'export_ready': True,
            'last_updated': timezone.now(),
        }

class LeaderboardView(TemplateView):
    """Vista del leaderboard/tabla de posiciones"""
    template_name = 'courses/leaderboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Diferentes tipos de leaderboards
        completion_leaders = self.get_completion_leaders()
        study_time_leaders = self.get_study_time_leaders()
        consistency_leaders = self.get_consistency_leaders()
        category_leaders = self.get_category_leaders()
        
        # Posición del usuario actual si está autenticado
        user_position = None
        if self.request.user.is_authenticated and hasattr(self.request.user, 'applicantprofile'):
            user_position = self.get_user_position(self.request.user.applicantprofile)
        
        context.update({
            'completion_leaders': completion_leaders,
            'study_time_leaders': study_time_leaders,
            'consistency_leaders': consistency_leaders,
            'category_leaders': category_leaders,
            'user_position': user_position,
            'leaderboard_type': self.request.GET.get('type', 'completion'),
            'time_period': self.request.GET.get('period', 'all_time'),
        })
        
        return context
    
    def get_completion_leaders(self):
        """Obtener líderes por cursos completados"""
        return User.objects.filter(user_type='applicant').annotate(
            completed_count=Count('applicantprofile__enrollment', filter=Q(applicantprofile__enrollment__status='completed')),
            total_certificates=Count('applicantprofile__enrollment__certificate'),
            total_study_hours=Sum('applicantprofile__enrollment__lessonprogress__time_spent') / 60
        ).filter(completed_count__gt=0).order_by('-completed_count')[:20]
    
    def get_study_time_leaders(self):
        """Obtener líderes por tiempo de estudio"""
        return User.objects.filter(user_type='applicant').annotate(
            total_study_time=Sum('applicantprofile__enrollment__lessonprogress__time_spent'),
            completed_count=Count('applicantprofile__enrollment', filter=Q(applicantprofile__enrollment__status='completed'))
        ).filter(total_study_time__gt=0).order_by('-total_study_time')[:20]
    
    def get_consistency_leaders(self):
        """Obtener líderes por consistencia"""
        # Simplificado - basado en actividad reciente y completaciones
        recent_date = timezone.now() - timedelta(days=30)
        
        return User.objects.filter(user_type='applicant').annotate(
            recent_activity=Count('applicantprofile__enrollment__lessonprogress', 
                                filter=Q(applicantprofile__enrollment__lessonprogress__completed_at__gte=recent_date)),
            total_completed=Count('applicantprofile__enrollment', filter=Q(applicantprofile__enrollment__status='completed'))
        ).filter(recent_activity__gt=0).order_by('-recent_activity', '-total_completed')[:20]
    
    def get_category_leaders(self):
        """Obtener líderes por categoría"""
        category_leaders = {}
        
        for category_code, category_name in Course.CATEGORY_CHOICES:
            leaders = User.objects.filter(user_type='applicant').annotate(
                category_completions=Count('applicantprofile__enrollment', 
                                         filter=Q(applicantprofile__enrollment__course__category=category_code,
                                                 applicantprofile__enrollment__status='completed'))
            ).filter(category_completions__gt=0).order_by('-category_completions')[:5]
            
            if leaders:
                category_leaders[category_name] = leaders
        
        return category_leaders
    
    def get_user_position(self, applicant_profile):
        """Obtener posición del usuario actual"""
        user_completed = Enrollment.objects.filter(
            applicant=applicant_profile,
            status='completed'
        ).count()
        
        better_users = User.objects.filter(user_type='applicant').annotate(
            completed_count=Count('applicantprofile__enrollment', filter=Q(applicantprofile__enrollment__status='completed'))
        ).filter(completed_count__gt=user_completed).count()
        
        return {
            'position': better_users + 1,
            'completed_courses': user_completed,
            'percentile': self.calculate_user_percentile(applicant_profile),
        }
    
    def calculate_user_percentile(self, applicant_profile):
        """Calcular percentil del usuario"""
        user_completed = Enrollment.objects.filter(
            applicant=applicant_profile,
            status='completed'
        ).count()
        
        total_users = User.objects.filter(user_type='applicant').count()
        better_users = User.objects.filter(user_type='applicant').annotate(
            completed_count=Count('applicantprofile__enrollment', filter=Q(applicantprofile__enrollment__status='completed'))
        ).filter(completed_count__gt=user_completed).count()
        
        if total_users > 0:
            percentile = ((total_users - better_users) / total_users) * 100
            return round(percentile, 1)
        
        return 0

# 7. Vistas de Recursos
class CourseResourcesView(ApplicantRequiredMixin, DetailView):
    """Vista para mostrar recursos de un curso"""
    model = Course
    template_name = 'courses/course_resources.html'
    context_object_name = 'course'
    pk_url_kwarg = 'course_id'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object
        
        # Verificar inscripción
        try:
            enrollment = Enrollment.objects.get(
                course=course,
                applicant=self.request.user.applicantprofile,
                status='enrolled'
            )
        except Enrollment.DoesNotExist:
            raise PermissionDenied("No estás inscrito en este curso")
        
        # Obtener recursos del curso (necesitarías crear modelo CourseResource)
        # Por ahora estructura básica
        context.update({
            'enrollment': enrollment,
            'resources': [],  # CourseResource.objects.filter(course=course, is_active=True)
            'resource_categories': [],
            'downloadable_resources': [],
            'external_links': [],
        })
        
        return context

class DownloadResourceView(ApplicantRequiredMixin, View):
    """Vista para descargar un recurso del curso"""
    
    def get(self, request, pk):
        # Necesitarías crear modelo CourseResource
        # resource = get_object_or_404(CourseResource, pk=pk)
        
        # Por ahora, placeholder que redirige
        messages.info(request, "Función de descarga de recursos en desarrollo")
        return redirect('courses:course_list')

# Servicios auxiliares que podrían ser útiles
class CourseProgressService:
    """Servicio para manejar el progreso de cursos"""
    
    @staticmethod
    def get_student_progress_summary(enrollment):
        """Obtener resumen completo del progreso de un estudiante"""
        course = enrollment.course
        
        # Progreso de lecciones
        total_lessons = course.lesson_set.filter(is_active=True).count()
        lesson_progress = LessonProgress.objects.filter(enrollment=enrollment)
        completed_lessons = lesson_progress.filter(is_completed=True).count()
        
        # Progreso de quizzes
        total_quizzes = course.quiz_set.filter(is_active=True).count()
        quiz_attempts = QuizAttempt.objects.filter(enrollment=enrollment)
        passed_quizzes = quiz_attempts.filter(is_passed=True).values('quiz').distinct().count()
        
        # Tiempo total de estudio
        total_study_time = lesson_progress.aggregate(
            total_time=Sum('time_spent')
        )['total_time'] or 0
        
        # Calcular progreso general
        lesson_progress_pct = (completed_lessons / total_lessons * 100) if total_lessons > 0 else 0
        quiz_progress_pct = (passed_quizzes / total_quizzes * 100) if total_quizzes > 0 else 0
        
        # Promedio ponderado (lecciones 70%, quizzes 30%)
        overall_progress = (lesson_progress_pct * 0.7) + (quiz_progress_pct * 0.3)
        
        return {
            'overall_progress': round(overall_progress, 2),
            'lesson_progress': round(lesson_progress_pct, 2),
            'quiz_progress': round(quiz_progress_pct, 2),
            'total_lessons': total_lessons,
            'completed_lessons': completed_lessons,
            'total_quizzes': total_quizzes,
            'passed_quizzes': passed_quizzes,
            'total_study_hours': round(total_study_time / 60, 1),
            'is_completed': enrollment.status == 'completed',
            'can_complete': overall_progress >= 100 and enrollment.status == 'enrolled',
        }
    
    @staticmethod
    def update_enrollment_progress(enrollment):
        """Actualizar el progreso de una inscripción"""
        summary = CourseProgressService.get_student_progress_summary(enrollment)
        
        enrollment.progress_percentage = summary['overall_progress']
        enrollment.last_accessed = timezone.now()
        enrollment.save(update_fields=['progress_percentage', 'last_accessed'])
        
        return summary
    
    @staticmethod
    def get_course_completion_requirements(course):
        """Obtener requisitos para completar un curso"""
        requirements = {
            'lessons': {
                'total': course.lesson_set.filter(is_active=True).count(),
                'required': course.lesson_set.filter(is_active=True, is_required=True).count() if hasattr(course.lesson_set.first(), 'is_required') else course.lesson_set.filter(is_active=True).count(),
            },
            'quizzes': {
                'total': course.quiz_set.filter(is_active=True).count(),
                'required': course.quiz_set.filter(is_active=True, is_required=True).count() if hasattr(course.quiz_set.first(), 'is_required') else course.quiz_set.filter(is_active=True).count(),
                'min_score': 70,  # Puntuación mínima por defecto
            },
            'minimum_time_hours': getattr(course, 'minimum_time_hours', None),
            'additional_requirements': getattr(course, 'completion_requirements', None),
        }
        
        return requirements

# Mixins adicionales que podrían ser útiles
class CourseAccessMixin:
    """Mixin para verificar acceso a un curso"""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Obtener curso
        course_id = kwargs.get('course_id') or kwargs.get('pk')
        if course_id:
            try:
                course = Course.objects.get(id=course_id)
                
                # Verificar si el curso está activo
                if not course.is_active:
                    messages.error(request, "Este curso no está disponible actualmente.")
                    return redirect('courses:course_list')
                
                # Verificar inscripción para estudiantes
                if request.user.user_type == 'applicant':
                    try:
                        enrollment = Enrollment.objects.get(
                            course=course,
                            applicant=request.user.applicantprofile,
                            status__in=['enrolled', 'completed']
                        )
                        # Agregar enrollment al request para uso en la vista
                        request.enrollment = enrollment
                    except Enrollment.DoesNotExist:
                        messages.error(request, "No tienes acceso a este curso.")
                        return redirect('courses:course_detail', pk=course.id)
                
            except Course.DoesNotExist:
                messages.error(request, "Curso no encontrado.")
                return redirect('courses:course_list')
        
        return super().dispatch(request, *args, **kwargs)

class PaginationMixin:
    """Mixin para paginación personalizada"""
    
    def get_paginate_by(self, queryset):
        """Permitir paginación personalizada por parámetro GET"""
        paginate_by = self.request.GET.get('per_page', self.paginate_by)
        
        try:
            paginate_by = int(paginate_by)
            # Limitar a valores razonables
            if paginate_by > 100:
                paginate_by = 100
            elif paginate_by < 5:
                paginate_by = 5
        except (ValueError, TypeError):
            paginate_by = self.paginate_by
        
        return paginate_by

# Decoradores útiles
def course_enrollment_required(view_func):
    """Decorador para verificar inscripción en curso"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        course_id = kwargs.get('course_id')
        if course_id:
            try:
                enrollment = Enrollment.objects.get(
                    course_id=course_id,
                    applicant=request.user.applicantprofile,
                    status__in=['enrolled', 'completed']
                )
                request.enrollment = enrollment
            except Enrollment.DoesNotExist:
                messages.error(request, "No tienes acceso a este curso.")
                return redirect('courses:course_detail', pk=course_id)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper

def instructor_or_admin_required(view_func):
    """Decorador para verificar permisos de instructor o admin"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if request.user.user_type not in ['admin', 'instructor']:
            raise PermissionDenied("No tienes permisos para acceder a esta página.")
        
        return view_func(request, *args, **kwargs)
    
    return wrapper

# Utilidades adicionales
class CourseUtils:
    """Utilidades para cursos"""
    
    @staticmethod
    def calculate_estimated_completion_time(course, current_progress=0):
        """Calcular tiempo estimado de completación"""
        base_hours = course.duration_hours
        
        if current_progress > 0:
            remaining_progress = 100 - current_progress
            remaining_hours = (base_hours * remaining_progress) / 100
            return max(remaining_hours, 0.5)  # Mínimo 30 minutos
        
        return base_hours
    
    @staticmethod
    def get_course_difficulty_color(difficulty):
        """Obtener color para nivel de dificultad"""
        colors = {
            'beginner': 'green',
            'intermediate': 'yellow',
            'advanced': 'red'
        }
        return colors.get(difficulty, 'gray')
    
    @staticmethod
    def format_duration(hours):
        """Formatear duración en formato legible"""
        if hours < 1:
            minutes = int(hours * 60)
            return f"{minutes} min"
        elif hours < 24:
            return f"{hours:.1f} h"
        else:
            days = int(hours / 24)
            remaining_hours = hours % 24
            if remaining_hours > 0:
                return f"{days}d {remaining_hours:.1f}h"
            return f"{days} días"
    
    @staticmethod
    def get_course_status_badge(enrollment):
        """Obtener badge de estado del curso"""
        status_badges = {
            'enrolled': {'text': 'En Progreso', 'class': 'badge-primary'},
            'completed': {'text': 'Completado', 'class': 'badge-success'},
            'cancelled': {'text': 'Cancelado', 'class': 'badge-secondary'},
        }
        
        return status_badges.get(enrollment.status, {'text': 'Desconocido', 'class': 'badge-light'})
    
    @staticmethod
    def generate_course_slug(title):
        """Generar slug para curso"""
        import re
        from django.utils.text import slugify
        
        slug = slugify(title)
        # Asegurar que no sea muy largo
        if len(slug) > 50:
            slug = slug[:50]
        
        return slug

# Context processors adicionales que podrían ser útiles
def course_stats_context(request):
    """Context processor para estadísticas de cursos"""
    if request.user.is_authenticated and hasattr(request.user, 'applicantprofile'):
        enrollments = Enrollment.objects.filter(applicant=request.user.applicantprofile)
        
        return {
            'user_course_stats': {
                'total_enrollments': enrollments.count(),
                'active_courses': enrollments.filter(status='enrolled').count(),
                'completed_courses': enrollments.filter(status='completed').count(),
                'certificates_earned': Certificate.objects.filter(
                    enrollment__applicant=request.user.applicantprofile
                ).count(),
            }
        }
    
    return {}

# API Views
class EnrollCourseAPIView(ApplicantRequiredMixin, View):
    def post(self, request):
        course_id = request.POST.get('course_id')
        
        try:
            course = Course.objects.get(id=course_id, is_active=True)
            applicant = request.user.applicantprofile
            
            # Verificar si ya está inscrito
            if Enrollment.objects.filter(course=course, applicant=applicant).exists():
                return JsonResponse({
                    'success': False,
                    'message': 'Ya estás inscrito en este curso'
                })
            
            # Crear inscripción
            enrollment = Enrollment.objects.create(
                course=course,
                applicant=applicant,
                status='enrolled'
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Inscripción exitosa en "{course.title}"',
                'enrollment_id': enrollment.id,
                'enrollment_url': reverse('courses:enrollment_detail', kwargs={'pk': enrollment.pk})
            })
            
        except Course.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Curso no encontrado'
            })
        except Exception as e:
            logger.error(f"Error enrolling in course: {e}")
            return JsonResponse({
                'success': False,
                'message': 'Error al procesar la inscripción'
            })

class CourseProgressAPIView(ApplicantRequiredMixin, View):
    def get(self, request):
        enrollments = Enrollment.objects.filter(
            applicant=request.user.applicantprofile,
            status='enrolled'
        ).select_related('course')
        
        progress_data = []
        for enrollment in enrollments:
            progress_data.append({
                'course_id': enrollment.course.id,
                'course_title': enrollment.course.title,
                'progress_percentage': enrollment.progress_percentage,
                'enrolled_at': enrollment.enrolled_at.isoformat(),
                'estimated_completion': self.calculate_estimated_completion(enrollment),
            })
        
        return JsonResponse({
            'courses': progress_data,
            'total_courses': len(progress_data)
        })
    
    def calculate_estimated_completion(self, enrollment):
        # Implementar lógica para calcular tiempo estimado de completación
        # basado en progreso actual y duración del curso
        if enrollment.progress_percentage > 0:
            remaining_percentage = 100 - enrollment.progress_percentage
            # Estimación simple basada en progreso actual
            days_since_start = (timezone.now() - enrollment.enrolled_at).days
            if days_since_start > 0 and enrollment.progress_percentage > 0:
                days_per_percent = days_since_start / enrollment.progress_percentage
                estimated_days = remaining_percentage * days_per_percent
                estimated_completion = timezone.now() + timedelta(days=estimated_days)
                return estimated_completion.isoformat()
        
        return None

class GenerateCertificateAPIView(InstructorRequiredMixin, View):
    def post(self, request):
        enrollment_id = request.POST.get('enrollment_id')
        
        try:
            enrollment = Enrollment.objects.get(
                id=enrollment_id,
                status='completed'
            )
            
            # Verificar si ya existe un certificado
            if Certificate.objects.filter(enrollment=enrollment).exists():
                return JsonResponse({
                    'success': False,
                    'message': 'El certificado ya fue generado para esta inscripción'
                })
            
            # Generar certificado
            certificate = CertificateGenerator.create_certificate_record(enrollment)
            
            return JsonResponse({
                'success': True,
                'message': 'Certificado generado exitosamente',
                'certificate_id': certificate.certificate_id,
                'download_url': reverse('courses:download_certificate', kwargs={'pk': certificate.pk})
            })
            
        except Enrollment.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Inscripción no encontrada o no completada'
            })
        except Exception as e:
            logger.error(f"Error generating certificate: {e}")
            return JsonResponse({
                'success': False,
                'message': 'Error al generar el certificado'
            })