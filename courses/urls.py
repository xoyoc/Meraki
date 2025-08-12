from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    # Listado y búsqueda de cursos
    path('', views.CourseListView.as_view(), name='course_list'),
    path('search/', views.CourseSearchView.as_view(), name='course_search'),
    path('categories/', views.CourseCategoriesView.as_view(), name='course_categories'),
    path('category/<str:category>/', views.CoursesByCategory.as_view(), name='courses_by_category'),
    path('<int:pk>/', views.CourseDetailView.as_view(), name='course_detail'),

    # Inscripciones
    path('<int:course_id>/enroll/', views.EnrollCourseView.as_view(), name='enroll_course'),
    path('enrollment/<int:pk>/', views.EnrollmentDetailView.as_view(), name='enrollment_detail'),
    path('enrollment/<int:pk>/complete/', views.CompleteEnrollmentView.as_view(), name='complete_enrollment'),
    path('enrollment/<int:pk>/cancel/', views.CancelEnrollmentView.as_view(), name='cancel_enrollment'),

    # Mis cursos (para estudiantes)
    path('my-courses/', views.MyCoursesView.as_view(), name='my_courses'),
    path('my-courses/active/', views.ActiveCoursesView.as_view(), name='active_courses'),
    path('my-courses/completed/', views.CompletedCoursesView.as_view(), name='completed_courses'),
    path('my-courses/progress/', views.CourseProgressView.as_view(), name='course_progress'),

    # Certificados
    path('certificates/', views.MyCertificatesView.as_view(), name='my_certificates'),
    path('certificates/<int:pk>/', views.CertificateDetailView.as_view(), name='certificate_detail'),
    path('certificates/<int:pk>/download/', views.DownloadCertificateView.as_view(), name='download_certificate'),
    path('certificates/<int:pk>/verify/', views.VerifyCertificateView.as_view(), name='verify_certificate'),
    path('certificates/public/<str:certificate_id>/', views.PublicCertificateView.as_view(), name='public_certificate'),

    # Gestión de cursos (para instructores/admin)
    path('manage/', views.ManageCoursesView.as_view(), name='manage_courses'),
    path('manage/create/', views.CreateCourseView.as_view(), name='create_course'),
    path('manage/<int:pk>/edit/', views.EditCourseView.as_view(), name='edit_course'),
    path('manage/<int:pk>/delete/', views.DeleteCourseView.as_view(), name='delete_course'),
    path('manage/<int:pk>/students/', views.CourseStudentsView.as_view(), name='course_students'),
    path('manage/<int:pk>/analytics/', views.CourseAnalyticsView.as_view(), name='course_analytics'),

    # Lecciones y contenido
    path('<int:course_id>/lessons/', views.CourseLessonsView.as_view(), name='course_lessons'),
    path('<int:course_id>/lessons/<int:lesson_id>/', views.LessonDetailView.as_view(), name='lesson_detail'),
    path('lessons/<int:pk>/complete/', views.CompleteLessonView.as_view(), name='complete_lesson'),

    # Evaluaciones y quizzes
    path('<int:course_id>/quiz/', views.CourseQuizView.as_view(), name='course_quiz'),
    path('quiz/<int:pk>/attempt/', views.QuizAttemptView.as_view(), name='quiz_attempt'),
    path('quiz/<int:pk>/results/', views.QuizResultsView.as_view(), name='quiz_results'),

    # Foros y discusiones
    path('<int:course_id>/forum/', views.CourseForumView.as_view(), name='course_forum'),
    path('forum/<int:pk>/topic/', views.ForumTopicView.as_view(), name='forum_topic'),
    path('forum/topic/create/', views.CreateForumTopicView.as_view(), name='create_forum_topic'),

    # Estadísticas y reportes
    path('stats/', views.CourseStatsView.as_view(), name='course_stats'),
    path('reports/', views.CourseReportsView.as_view(), name='course_reports'),
    path('leaderboard/', views.LeaderboardView.as_view(), name='leaderboard'),

    # API endpoints
    path('api/enroll/', views.EnrollCourseAPIView.as_view(), name='enroll_course_api'),
    path('api/progress/', views.CourseProgressAPIView.as_view(), name='course_progress_api'),
    path('api/certificates/generate/', views.GenerateCertificateAPIView.as_view(), name='generate_certificate_api'),

    # Recursos y descargas
    path('<int:course_id>/resources/', views.CourseResourcesView.as_view(), name='course_resources'),
    path('resources/<int:pk>/download/', views.DownloadResourceView.as_view(), name='download_resource'),
]