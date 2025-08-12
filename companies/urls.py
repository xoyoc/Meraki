from django.urls import path
from . import views

app_name = 'companies'

urlpatterns = [
    # Dashboard y perfil de empresa
    path('dashboard/', views.CompanyDashboardView.as_view(), name='dashboard'),
    path('profile/', views.CompanyProfileView.as_view(), name='profile'),
    path('profile/edit/', views.CompanyProfileEditView.as_view(), name='profile_edit'),
    path('profile/complete/', views.CompleteCompanyProfileView.as_view(), name='complete_profile'),
    
    # Gestión de logo y documentos
    path('profile/logo/', views.LogoUploadView.as_view(), name='logo_upload'),
    path('profile/logo/delete/', views.LogoDeleteView.as_view(), name='logo_delete'),
    path('profile/documents/', views.DocumentsManagementView.as_view(), name='documents_management'),
    
    # Gestión de vacantes
    path('jobs/', views.CompanyJobsView.as_view(), name='jobs'),
    path('jobs/create/', views.CreateJobView.as_view(), name='create_job'),
    path('jobs/<int:pk>/edit/', views.EditJobView.as_view(), name='edit_job'),
    path('jobs/<int:pk>/delete/', views.DeleteJobView.as_view(), name='delete_job'),
    path('jobs/<int:pk>/clone/', views.CloneJobView.as_view(), name='clone_job'),
    path('jobs/<int:pk>/close/', views.CloseJobView.as_view(), name='close_job'),
    path('jobs/<int:pk>/reopen/', views.ReopenJobView.as_view(), name='reopen_job'),
    
    # Gestión de candidatos
    path('jobs/<int:pk>/candidates/', views.JobCandidatesView.as_view(), name='job_candidates'),
    path('candidates/', views.AllCandidatesView.as_view(), name='all_candidates'),
    path('candidates/<int:pk>/', views.CandidateDetailView.as_view(), name='candidate_detail'),
    path('candidates/search/', views.CandidateSearchView.as_view(), name='candidate_search'),
    path('candidates/saved/', views.SavedCandidatesView.as_view(), name='saved_candidates'),
    path('candidates/<int:pk>/save/', views.SaveCandidateView.as_view(), name='save_candidate'),
    path('candidates/<int:pk>/unsave/', views.UnsaveCandidateView.as_view(), name='unsave_candidate'),
    
    # Gestión de aplicaciones
    path('applications/', views.AllApplicationsView.as_view(), name='all_applications'),
    path('applications/<int:pk>/', views.ApplicationDetailView.as_view(), name='application_detail'),
    path('applications/<int:pk>/status/', views.UpdateApplicationStatusView.as_view(), name='update_application_status'),
    path('applications/<int:pk>/notes/', views.ApplicationNotesView.as_view(), name='application_notes'),
    path('applications/bulk-action/', views.BulkApplicationActionView.as_view(), name='bulk_application_action'),
    
    # Entrevistas y evaluaciones
    path('interviews/', views.InterviewsView.as_view(), name='interviews'),
    path('interviews/schedule/', views.ScheduleInterviewView.as_view(), name='schedule_interview'),
    path('interviews/<int:pk>/', views.InterviewDetailView.as_view(), name='interview_detail'),
    path('interviews/<int:pk>/edit/', views.EditInterviewView.as_view(), name='edit_interview'),
    path('interviews/<int:pk>/cancel/', views.CancelInterviewView.as_view(), name='cancel_interview'),
    
    # Estadísticas y reportes
    path('analytics/', views.CompanyAnalyticsView.as_view(), name='analytics'),
    path('reports/', views.CompanyReportsView.as_view(), name='reports'),
    path('reports/export/', views.ExportReportsView.as_view(), name='export_reports'),
    path('stats/jobs/', views.JobStatsView.as_view(), name='job_stats'),
    path('stats/hiring/', views.HiringStatsView.as_view(), name='hiring_stats'),
    
    # Configuraciones de empresa
    path('settings/', views.CompanySettingsView.as_view(), name='settings'),
    path('settings/team/', views.TeamManagementView.as_view(), name='team_management'),
    path('settings/permissions/', views.PermissionsView.as_view(), name='permissions'),
    path('settings/billing/', views.BillingView.as_view(), name='billing'),
    path('settings/notifications/', views.NotificationSettingsView.as_view(), name='notification_settings'),
    
    # Planes y suscripciones
    path('subscription/', views.SubscriptionView.as_view(), name='subscription'),
    path('subscription/upgrade/', views.UpgradeSubscriptionView.as_view(), name='upgrade_subscription'),
    path('subscription/cancel/', views.CancelSubscriptionView.as_view(), name='cancel_subscription'),
    
    # API endpoints
    path('api/stats/', views.CompanyStatsAPIView.as_view(), name='company_stats_api'),
    path('api/candidates/search/', views.CandidateSearchAPIView.as_view(), name='candidate_search_api'),
    path('api/applications/status/', views.ApplicationStatusAPIView.as_view(), name='application_status_api'),
    
    # Directorio público de empresas
    path('directory/', views.CompanyDirectoryView.as_view(), name='directory'),
    path('directory/<int:pk>/', views.PublicCompanyProfileView.as_view(), name='public_profile'),
]