# Signals que podrían ser útiles (para signals.py)
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from courses.models import Enrollment, LessonProgress, QuizAttempt

@receiver(post_save, sender=LessonProgress)
def update_course_progress_on_lesson_complete(sender, instance, **kwargs):
    if instance.is_completed and kwargs.get('created', False):
        CourseProgressService.update_enrollment_progress(instance.enrollment)

@receiver(post_save, sender=QuizAttempt)
def update_course_progress_on_quiz_complete(sender, instance, **kwargs):
    if kwargs.get('created', False):
        CourseProgressService.update_enrollment_progress(instance.enrollment)

@receiver(post_save, sender=Enrollment)
def create_initial_lesson_progress(sender, instance, created, **kwargs):
    if created and instance.status == 'enrolled':
        # Crear registros de progreso iniciales para todas las lecciones
        lessons = instance.course.lesson_set.filter(is_active=True)
        for lesson in lessons:
            LessonProgress.objects.get_or_create(
                enrollment=instance,
                lesson=lesson,
                defaults={'time_spent': 0, 'is_completed': False}
            )
