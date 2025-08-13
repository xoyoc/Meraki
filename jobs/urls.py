from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from . import views

app_name = 'jobs'

urlpatterns = [
    # Listado y búsqueda de vacantes
    path('', views.JobListView.as_view(), name='job_list'),
    path('search/', views.JobSearchView.as_view(), name='job_search'),
    path('filter/', views.JobFilterView.as_view(), name='job_filter'),
    path('<int:pk>/', views.JobDetailView.as_view(), name='job_detail'),
    
    # Postulaciones
    path('<int:job_id>/apply/', views.ApplyJobView.as_view(), name='apply'),
    path('application/<int:pk>/', views.ApplicationDetailView.as_view(), name='application_detail'),
    path('application/<int:pk>/withdraw/', views.WithdrawApplicationView.as_view(), name='withdraw_application'),
    
    # Para empresas - Gestión de vacantes
    path('create/', views.CreateJobView.as_view(), name='create_job'),
    path('<int:pk>/edit/', views.EditJobView.as_view(), name='edit_job'),
    path('<int:pk>/delete/', views.DeleteJobView.as_view(), name='delete_job'),
    path('<int:pk>/clone/', views.CloneJobView.as_view(), name='clone_job'),
    path('my-jobs/', views.MyJobsView.as_view(), name='my_jobs'),
    path('my-jobs/drafts/', views.DraftJobsView.as_view(), name='draft_jobs'),
    path('my-jobs/active/', views.ActiveJobsView.as_view(), name='active_jobs'),
    path('my-jobs/closed/', views.ClosedJobsView.as_view(), name='closed_jobs'),
    
    # Gestión de postulaciones (para empresas)
    path('<int:pk>/applicants/', views.JobApplicantsView.as_view(), name='job_applicants'),
    path('<int:pk>/applicants/export/', views.ExportApplicantsView.as_view(), name='export_applicants'),
    path('application/<int:pk>/update-status/', views.UpdateApplicationStatusView.as_view(), name='update_application_status'),
    path('application/<int:pk>/shortlist/', views.ShortlistApplicationView.as_view(), name='shortlist_application'),
    path('application/<int:pk>/reject/', views.RejectApplicationView.as_view(), name='reject_application'),
    path('application/<int:pk>/notes/', views.ApplicationNotesView.as_view(), name='application_notes'),
    
    # Para administradores - Aprobación de vacantes
    path('admin/pending/', views.PendingJobsView.as_view(), name='pending_approval'),
    path('admin/all/', views.AllJobsAdminView.as_view(), name='all_jobs_admin'),
    path('<int:pk>/approve/', views.ApproveJobView.as_view(), name='approve_job'),
    path('<int:pk>/reject-admin/', views.RejectJobAdminView.as_view(), name='reject_job_admin'),
    path('<int:pk>/feature/', views.FeatureJobView.as_view(), name='feature_job'),
    
    # Estadísticas y reportes
    path('stats/', views.JobStatsView.as_view(), name='job_stats'),
    path('reports/', views.JobReportsView.as_view(), name='job_reports'),
    path('analytics/', views.JobAnalyticsView.as_view(), name='job_analytics'),
    
    # API endpoints
    path('api/skills/', views.SkillsAPIView.as_view(), name='skills_api'),
    path('api/search/', views.JobSearchAPIView.as_view(), name='job_search_api'),
    path('api/<int:pk>/apply/', views.ApplyJobAPIView.as_view(), name='apply_job_api'),
    path('api/saved/', views.SavedJobsAPIView.as_view(), name='saved_jobs_api'),
    
    # Vacantes guardadas
    path('saved/', views.SavedJobsView.as_view(), name='saved_jobs'),
    path('<int:pk>/save/', views.SaveJobView.as_view(), name='save_job'),
    path('<int:pk>/unsave/', views.UnsaveJobView.as_view(), name='unsave_job'),
    
    # RSS Feed
    path('feed/', views.JobsFeedView, name='jobs_feed'),
]

# Para archivos estáticos y media (en desarrollo)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)