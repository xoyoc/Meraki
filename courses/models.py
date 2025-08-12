# apps/courses/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

from applicants.models import ApplicantProfile

User = get_user_model()

class Course(models.Model):
    DIFFICULTY_CHOICES = [
        ('beginner', 'Principiante'),
        ('intermediate', 'Intermedio'),
        ('advanced', 'Avanzado'),
    ]
    
    CATEGORY_CHOICES = [
        ('tecnologia', 'Tecnología'),
        ('marketing', 'Marketing'),
        ('negocios', 'Negocios'),
        ('diseno', 'Diseño'),
        ('desarrollo_personal', 'Desarrollo Personal'),
        ('idiomas', 'Idiomas'),
        ('salud', 'Salud y Bienestar'),
        ('finanzas', 'Finanzas'),
    ]
    
    title = models.CharField(max_length=200, verbose_name="Título")
    description = models.TextField(verbose_name="Descripción")
    duration_hours = models.IntegerField(
        verbose_name="Duración (horas)",
        validators=[MinValueValidator(1)]
    )
    instructor = models.CharField(max_length=200, verbose_name="Instructor")
    category = models.CharField(
        max_length=50, 
        choices=CATEGORY_CHOICES,
        verbose_name="Categoría"
    )
    difficulty_level = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default='beginner',
        verbose_name="Nivel de Dificultad"
    )
    prerequisites = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Requisitos Previos"
    )
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    is_featured = models.BooleanField(default=False, verbose_name="Destacado")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")
    
    class Meta:
        verbose_name = "Curso"
        verbose_name_plural = "Cursos"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    @property
    def total_lessons(self):
        return self.lesson_set.count()
    
    @property
    def total_enrollments(self):
        return self.enrollment_set.count()
    
    @property
    def completion_rate(self):
        total = self.enrollment_set.count()
        if total == 0:
            return 0
        completed = self.enrollment_set.filter(status='completed').count()
        return (completed / total) * 100

class Lesson(models.Model):
    LESSON_TYPE_CHOICES = [
        ('video', 'Video'),
        ('text', 'Texto'),
        ('quiz', 'Quiz'),
        ('assignment', 'Tarea'),
        ('resource', 'Recurso'),
    ]
    
    course = models.ForeignKey(
        Course, 
        on_delete=models.CASCADE,
        verbose_name="Curso"
    )
    title = models.CharField(max_length=200, verbose_name="Título")
    description = models.TextField(blank=True, verbose_name="Descripción")
    content = models.TextField(verbose_name="Contenido")
    lesson_type = models.CharField(
        max_length=20,
        choices=LESSON_TYPE_CHOICES,
        default='text',
        verbose_name="Tipo de Lección"
    )
    duration = models.IntegerField(
        help_text="Duración en minutos",
        validators=[MinValueValidator(1)],
        verbose_name="Duración (minutos)"
    )
    order = models.PositiveIntegerField(
        default=1,
        verbose_name="Orden"
    )
    video_url = models.URLField(
        blank=True, 
        null=True,
        verbose_name="URL del Video"
    )
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    
    class Meta:
        verbose_name = "Lección"
        verbose_name_plural = "Lecciones"
        ordering = ['course', 'order']
        unique_together = ['course', 'order']
    
    def __str__(self):
        return f"{self.course.title} - {self.title}"

class LessonProgress(models.Model):
    """Modelo para trackear el progreso de lecciones por estudiante"""
    enrollment = models.ForeignKey(
        'Enrollment', 
        on_delete=models.CASCADE,
        verbose_name="Inscripción"
    )
    lesson = models.ForeignKey(
        Lesson, 
        on_delete=models.CASCADE,
        verbose_name="Lección"
    )
    is_completed = models.BooleanField(default=False, verbose_name="Completada")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Completación")
    time_spent = models.IntegerField(
        default=0,
        help_text="Tiempo gastado en minutos",
        verbose_name="Tiempo Invertido"
    )
    
    class Meta:
        verbose_name = "Progreso de Lección"
        verbose_name_plural = "Progreso de Lecciones"
        unique_together = ['enrollment', 'lesson']
    
    def __str__(self):
        status = "✓" if self.is_completed else "○"
        return f"{status} {self.enrollment.applicant.user.username} - {self.lesson.title}"

class Quiz(models.Model):
    course = models.ForeignKey(
        Course, 
        on_delete=models.CASCADE,
        verbose_name="Curso"
    )
    title = models.CharField(max_length=200, verbose_name="Título")
    description = models.TextField(blank=True, verbose_name="Descripción")
    passing_score = models.IntegerField(
        default=70,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Puntuación mínima para aprobar (%)",
        verbose_name="Puntuación Mínima"
    )
    time_limit = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Tiempo límite en minutos (opcional)",
        verbose_name="Tiempo Límite (minutos)"
    )
    max_attempts = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1)],
        verbose_name="Intentos Máximos"
    )
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    
    class Meta:
        verbose_name = "Quiz"
        verbose_name_plural = "Quizzes"
        ordering = ['course', 'title']
    
    def __str__(self):
        return f"{self.course.title} - {self.title}"
    
    @property
    def total_questions(self):
        return self.question_set.count()

class Question(models.Model):
    QUESTION_TYPE_CHOICES = [
        ('multiple_choice', 'Opción Múltiple'),
        ('true_false', 'Verdadero/Falso'),
        ('short_answer', 'Respuesta Corta'),
    ]
    
    quiz = models.ForeignKey(
        Quiz, 
        on_delete=models.CASCADE,
        verbose_name="Quiz"
    )
    question_text = models.TextField(verbose_name="Pregunta")
    question_type = models.CharField(
        max_length=20,
        choices=QUESTION_TYPE_CHOICES,
        default='multiple_choice',
        verbose_name="Tipo de Pregunta"
    )
    points = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Puntos"
    )
    order = models.PositiveIntegerField(default=1, verbose_name="Orden")
    explanation = models.TextField(
        blank=True,
        help_text="Explicación de la respuesta correcta",
        verbose_name="Explicación"
    )
    
    class Meta:
        verbose_name = "Pregunta"
        verbose_name_plural = "Preguntas"
        ordering = ['quiz', 'order']
        unique_together = ['quiz', 'order']
    
    def __str__(self):
        return f"{self.quiz.title} - Pregunta {self.order}"

class Answer(models.Model):
    question = models.ForeignKey(
        Question, 
        on_delete=models.CASCADE,
        verbose_name="Pregunta"
    )
    answer_text = models.CharField(max_length=500, verbose_name="Respuesta")
    is_correct = models.BooleanField(default=False, verbose_name="Es Correcta")
    order = models.PositiveIntegerField(default=1, verbose_name="Orden")
    
    class Meta:
        verbose_name = "Respuesta"
        verbose_name_plural = "Respuestas"
        ordering = ['question', 'order']
    
    def __str__(self):
        correct = "✓" if self.is_correct else "✗"
        return f"{correct} {self.answer_text[:50]}"

class QuizAttempt(models.Model):
    enrollment = models.ForeignKey(
        'Enrollment', 
        on_delete=models.CASCADE,
        verbose_name="Inscripción"
    )
    quiz = models.ForeignKey(
        Quiz, 
        on_delete=models.CASCADE,
        verbose_name="Quiz"
    )
    score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Puntuación"
    )
    is_passed = models.BooleanField(default=False, verbose_name="Aprobado")
    attempt_number = models.PositiveIntegerField(verbose_name="Número de Intento")
    started_at = models.DateTimeField(verbose_name="Iniciado en")
    attempted_at = models.DateTimeField(verbose_name="Completado en")
    time_taken = models.IntegerField(
        help_text="Tiempo tomado en segundos",
        verbose_name="Tiempo Utilizado"
    )
    
    class Meta:
        verbose_name = "Intento de Quiz"
        verbose_name_plural = "Intentos de Quiz"
        ordering = ['-attempted_at']
        unique_together = ['enrollment', 'quiz', 'attempt_number']
    
    def __str__(self):
        return f"{self.enrollment.applicant.user.username} - {self.quiz.title} (Intento {self.attempt_number})"
    
    def save(self, *args, **kwargs):
        # Determinar si pasó el quiz
        self.is_passed = self.score >= self.quiz.passing_score
        super().save(*args, **kwargs)

class QuizResponse(models.Model):
    """Respuestas específicas del estudiante en un intento de quiz"""
    attempt = models.ForeignKey(
        QuizAttempt, 
        on_delete=models.CASCADE,
        verbose_name="Intento"
    )
    question = models.ForeignKey(
        Question, 
        on_delete=models.CASCADE,
        verbose_name="Pregunta"
    )
    selected_answer = models.ForeignKey(
        Answer, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        verbose_name="Respuesta Seleccionada"
    )
    text_response = models.TextField(
        blank=True,
        help_text="Para preguntas de respuesta corta",
        verbose_name="Respuesta de Texto"
    )
    is_correct = models.BooleanField(default=False, verbose_name="Es Correcta")
    points_earned = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        verbose_name="Puntos Obtenidos"
    )
    
    class Meta:
        verbose_name = "Respuesta de Quiz"
        verbose_name_plural = "Respuestas de Quiz"
        unique_together = ['attempt', 'question']
    
    def __str__(self):
        return f"{self.attempt} - {self.question}"

class Enrollment(models.Model):
    STATUS_CHOICES = (
        ('enrolled', 'Inscrito'),
        ('completed', 'Completado'),
        ('cancelled', 'Cancelado'),
    )
    
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name="Curso")
    applicant = models.ForeignKey(
        ApplicantProfile, 
        on_delete=models.CASCADE,
        verbose_name="Estudiante"
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='enrolled',
        verbose_name="Estado"
    )
    enrolled_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Inscripción")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Completación")
    
    # Campos adicionales para tracking de progreso
    progress_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Porcentaje de Progreso"
    )
    last_accessed = models.DateTimeField(null=True, blank=True, verbose_name="Último Acceso")
    
    class Meta:
        verbose_name = "Inscripción"
        verbose_name_plural = "Inscripciones"
        unique_together = ['course', 'applicant']
        ordering = ['-enrolled_at']
    
    def __str__(self):
        return f"{self.applicant.user.username} - {self.course.title}"
    
    def update_progress(self):
        """Calcular y actualizar el progreso basado en lecciones completadas"""
        total_lessons = self.course.lesson_set.count()
        if total_lessons == 0:
            self.progress_percentage = 0
        else:
            completed_lessons = LessonProgress.objects.filter(
                enrollment=self,
                is_completed=True
            ).count()
            self.progress_percentage = (completed_lessons / total_lessons) * 100
        
        self.last_accessed = timezone.now()
        self.save()
    
    @property
    def completed_lessons(self):
        return LessonProgress.objects.filter(
            enrollment=self, 
            is_completed=True
        )
    
    @property
    def next_lesson(self):
        completed_lesson_ids = self.completed_lessons.values_list('lesson_id', flat=True)
        return self.course.lesson_set.exclude(
            id__in=completed_lesson_ids
        ).order_by('order').first()

class Certificate(models.Model):
    enrollment = models.OneToOneField(
        Enrollment, 
        on_delete=models.CASCADE,
        verbose_name="Inscripción"
    )
    certificate_id = models.CharField(
        max_length=50, 
        unique=True,
        verbose_name="ID del Certificado"
    )
    pdf_file = models.FileField(
        upload_to='certificates/',
        verbose_name="Archivo PDF"
    )
    issued_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Emisión")
    is_public = models.BooleanField(
        default=True,
        help_text="Si el certificado puede ser verificado públicamente",
        verbose_name="Público"
    )
    verification_url = models.URLField(
        blank=True,
        verbose_name="URL de Verificación"
    )
    
    class Meta:
        verbose_name = "Certificado"
        verbose_name_plural = "Certificados"
        ordering = ['-issued_at']
    
    def __str__(self):
        return f"Certificado {self.certificate_id} - {self.enrollment.applicant.user.username}"
    
    def save(self, *args, **kwargs):
        if not self.certificate_id:
            # Generar ID único para el certificado
            self.certificate_id = f"MERAKI-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

class CourseResource(models.Model):
    """Recursos adicionales del curso (documentos, enlaces, etc.)"""
    RESOURCE_TYPE_CHOICES = [
        ('pdf', 'Documento PDF'),
        ('video', 'Video'),
        ('link', 'Enlace Externo'),
        ('document', 'Documento'),
        ('image', 'Imagen'),
    ]
    
    course = models.ForeignKey(
        Course, 
        on_delete=models.CASCADE,
        verbose_name="Curso"
    )
    title = models.CharField(max_length=200, verbose_name="Título")
    description = models.TextField(blank=True, verbose_name="Descripción")
    resource_type = models.CharField(
        max_length=20,
        choices=RESOURCE_TYPE_CHOICES,
        verbose_name="Tipo de Recurso"
    )
    file = models.FileField(
        upload_to='course_resources/',
        blank=True,
        null=True,
        verbose_name="Archivo"
    )
    url = models.URLField(blank=True, verbose_name="URL")
    is_downloadable = models.BooleanField(default=True, verbose_name="Descargable")
    order = models.PositiveIntegerField(default=1, verbose_name="Orden")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    
    class Meta:
        verbose_name = "Recurso del Curso"
        verbose_name_plural = "Recursos del Curso"
        ordering = ['course', 'order']
    
    def __str__(self):
        return f"{self.course.title} - {self.title}"