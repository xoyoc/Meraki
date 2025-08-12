# apps/courses/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Course, Enrollment, Certificate, Lesson, LessonProgress,
    Quiz, Question, Answer, QuizAttempt, QuizResponse, CourseResource
)

# apps/courses/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Course, Enrollment, Certificate, Lesson, LessonProgress,
    Quiz, Question, Answer, QuizAttempt, QuizResponse, CourseResource
)

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'instructor', 'category', 'difficulty_level', 'duration_hours', 'enrollment_count', 'is_active', 'is_featured', 'created_at']
    list_filter = ['category', 'difficulty_level', 'is_active', 'is_featured', 'created_at']
    search_fields = ['title', 'instructor', 'description']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('title', 'description', 'instructor')
        }),
        ('Configuración del Curso', {
            'fields': ('category', 'difficulty_level', 'duration_hours', 'prerequisites')
        }),
        ('Estado', {
            'fields': ('is_active', 'is_featured')
        }),
    )
    
    def enrollment_count(self, obj):
        count = obj.enrollment_set.count()
        url = reverse('admin:courses_enrollment_changelist') + f'?course__id__exact={obj.id}'
        return format_html('<a href="{}">{} inscripciones</a>', url, count)
    
    enrollment_count.short_description = 'Inscripciones'

class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0
    fields = ['title', 'lesson_type', 'duration', 'order', 'is_active']
    ordering = ['order']

class QuizInline(admin.TabularInline):
    model = Quiz
    extra = 0
    fields = ['title', 'passing_score', 'max_attempts', 'is_active']

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'lesson_type', 'duration', 'order', 'is_active']
    list_filter = ['course', 'lesson_type', 'is_active']
    search_fields = ['title', 'course__title']
    ordering = ['course', 'order']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('course', 'title', 'description')
        }),
        ('Contenido', {
            'fields': ('content', 'lesson_type', 'video_url')
        }),
        ('Configuración', {
            'fields': ('duration', 'order', 'is_active')
        }),
    )

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'course_title', 'status', 'progress_percentage', 'enrolled_at', 'completed_at']
    list_filter = ['status', 'enrolled_at', 'completed_at', 'course__category']
    search_fields = ['applicant__user__username', 'applicant__user__first_name', 'applicant__user__last_name', 'course__title']
    ordering = ['-enrolled_at']
    date_hierarchy = 'enrolled_at'
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('course', 'applicant', 'status')
        }),
        ('Progreso', {
            'fields': ('progress_percentage', 'last_accessed')
        }),
        ('Fechas', {
            'fields': ('enrolled_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['enrolled_at']
    
    def student_name(self, obj):
        return f"{obj.applicant.user.get_full_name()} ({obj.applicant.user.username})"
    student_name.short_description = 'Estudiante'
    
    def course_title(self, obj):
        return obj.course.title
    course_title.short_description = 'Curso'

@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'lesson_title', 'course_title', 'is_completed', 'completed_at', 'time_spent']
    list_filter = ['is_completed', 'completed_at', 'lesson__course']
    search_fields = ['enrollment__applicant__user__username', 'lesson__title', 'lesson__course__title']
    ordering = ['-completed_at']
    
    def student_name(self, obj):
        return obj.enrollment.applicant.user.get_full_name() or obj.enrollment.applicant.user.username
    student_name.short_description = 'Estudiante'
    
    def lesson_title(self, obj):
        return obj.lesson.title
    lesson_title.short_description = 'Lección'
    
    def course_title(self, obj):
        return obj.lesson.course.title
    course_title.short_description = 'Curso'

class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 2
    fields = ['answer_text', 'is_correct', 'order']
    ordering = ['order']

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['question_preview', 'quiz', 'question_type', 'points', 'order']
    list_filter = ['quiz', 'question_type']
    search_fields = ['question_text', 'quiz__title']
    ordering = ['quiz', 'order']
    inlines = [AnswerInline]
    
    def question_preview(self, obj):
        return obj.question_text[:50] + "..." if len(obj.question_text) > 50 else obj.question_text
    question_preview.short_description = 'Pregunta'

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'passing_score', 'time_limit', 'max_attempts', 'question_count', 'is_active']
    list_filter = ['course', 'is_active', 'created_at']
    search_fields = ['title', 'course__title']
    ordering = ['course', 'title']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('course', 'title', 'description')
        }),
        ('Configuración', {
            'fields': ('passing_score', 'time_limit', 'max_attempts', 'is_active')
        }),
    )
    
    def question_count(self, obj):
        count = obj.question_set.count()
        url = reverse('admin:courses_question_changelist') + f'?quiz__id__exact={obj.id}'
        return format_html('<a href="{}">{} preguntas</a>', url, count)
    question_count.short_description = 'Preguntas'

@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'quiz_title', 'attempt_number', 'score', 'is_passed', 'attempted_at', 'time_taken_display']
    list_filter = ['is_passed', 'attempted_at', 'quiz__course']
    search_fields = ['enrollment__applicant__user__username', 'quiz__title']
    ordering = ['-attempted_at']
    date_hierarchy = 'attempted_at'
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('enrollment', 'quiz', 'attempt_number')
        }),
        ('Resultados', {
            'fields': ('score', 'is_passed', 'time_taken')
        }),
        ('Fechas', {
            'fields': ('started_at', 'attempted_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['started_at', 'attempted_at', 'is_passed']
    
    def student_name(self, obj):
        return obj.enrollment.applicant.user.get_full_name() or obj.enrollment.applicant.user.username
    student_name.short_description = 'Estudiante'
    
    def quiz_title(self, obj):
        return obj.quiz.title
    quiz_title.short_description = 'Quiz'
    
    def time_taken_display(self, obj):
        minutes = obj.time_taken // 60
        seconds = obj.time_taken % 60
        return f"{minutes}m {seconds}s"
    time_taken_display.short_description = 'Tiempo'

@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ['certificate_id', 'student_name', 'course_title', 'issued_at', 'is_public', 'download_link']
    list_filter = ['issued_at', 'is_public', 'enrollment__course__category']
    search_fields = ['certificate_id', 'enrollment__applicant__user__username', 'enrollment__course__title']
    ordering = ['-issued_at']
    date_hierarchy = 'issued_at'
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('enrollment', 'certificate_id')
        }),
        ('Configuración', {
            'fields': ('is_public', 'verification_url')
        }),
        ('Archivo', {
            'fields': ('pdf_file',)
        }),
    )
    
    readonly_fields = ['certificate_id', 'issued_at']
    
    def student_name(self, obj):
        return obj.enrollment.applicant.user.get_full_name() or obj.enrollment.applicant.user.username
    student_name.short_description = 'Estudiante'
    
    def course_title(self, obj):
        return obj.enrollment.course.title
    course_title.short_description = 'Curso'
    
    def download_link(self, obj):
        if obj.pdf_file:
            return format_html('<a href="{}" target="_blank">Descargar PDF</a>', obj.pdf_file.url)
        return "No disponible"
    download_link.short_description = 'Descargar'

@admin.register(CourseResource)
class CourseResourceAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'resource_type', 'is_downloadable', 'order', 'created_at']
    list_filter = ['resource_type', 'is_downloadable', 'course']
    search_fields = ['title', 'course__title']
    ordering = ['course', 'order']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('course', 'title', 'description')
        }),
        ('Recurso', {
            'fields': ('resource_type', 'file', 'url')
        }),
        ('Configuración', {
            'fields': ('is_downloadable', 'order')
        }),
    )

@admin.register(QuizResponse)
class QuizResponseAdmin(admin.ModelAdmin):
    list_display = ['student_name', 'question_preview', 'is_correct', 'points_earned']
    list_filter = ['is_correct', 'attempt__quiz', 'attempt__attempted_at']
    search_fields = ['attempt__enrollment__applicant__user__username', 'question__question_text']
    
    def student_name(self, obj):
        return obj.attempt.enrollment.applicant.user.get_full_name() or obj.attempt.enrollment.applicant.user.username
    student_name.short_description = 'Estudiante'
    
    def question_preview(self, obj):
        return obj.question.question_text[:50] + "..." if len(obj.question.question_text) > 50 else obj.question.question_text
    question_preview.short_description = 'Pregunta'

# Configuración adicional del admin
admin.site.site_header = "Meraki - Administración de Cursos"
admin.site.site_title = "Meraki Admin"
admin.site.index_title = "Panel de Administración"