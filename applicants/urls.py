from django.urls import path
from applicants import views

app_name = 'applicants'

urlpatterns = [
    # Dashboard y perfil
    path('dashboard/', views.ApplicantDashboardView.as_view(), name='dashboard'),
    path('profile/', views.ApplicantProfileView.as_view(), name='profile'),
    path('profile/edit/', views.ApplicantProfileEditView.as_view(), name='profile_edit'),
    path('profile/complete/', views.CompleteProfileView.as_view(), name='complete_profile'),
    
    # Gestión de CV y documentos
    path('profile/cv/', views.CVUploadView.as_view(), name='cv_upload'),
    path('profile/cv/delete/', views.CVDeleteView.as_view(), name='cv_delete'),
    path('profile/portfolio/', views.PortfolioUploadView.as_view(), name='portfolio_upload'),
    path('profile/portfolio/delete/', views.PortfolioDeleteView.as_view(), name='portfolio_delete'),
    
    # Gestión de skills
    path('skills/', views.SkillsManagementView.as_view(), name='skills_management'),
    path('skills/add/', views.AddSkillView.as_view(), name='add_skill'),
    path('skills/<int:pk>/edit/', views.EditSkillView.as_view(), name='edit_skill'),
    path('skills/<int:pk>/delete/', views.DeleteSkillView.as_view(), name='delete_skill'),
    
    # Postulaciones
    path('applications/', views.MyApplicationsView.as_view(), name='my_applications'),
    path('applications/<int:pk>/', views.ApplicationDetailView.as_view(), name='application_detail'),
    path('applications/<int:pk>/withdraw/', views.WithdrawApplicationView.as_view(), name='withdraw_application'),
    path('applications/export/', views.ExportApplicationsView.as_view(), name='export_applications'),
    
    # Recomendaciones y matching
    path('recommendations/', views.RecommendationsView.as_view(), name='recommendations'),
    path('matches/', views.MatchesView.as_view(), name='matches'),
    path('profile/score/', views.ProfileScoreView.as_view(), name='profile_score'),
    
    # Alertas de empleo
    path('alerts/', views.JobAlertsView.as_view(), name='job_alerts'),
    path('alerts/create/', views.CreateJobAlertView.as_view(), name='create_job_alert'),
    path('alerts/<int:pk>/edit/', views.EditJobAlertView.as_view(), name='edit_job_alert'),
    path('alerts/<int:pk>/delete/', views.DeleteJobAlertView.as_view(), name='delete_job_alert'),
    path('alerts/<int:pk>/toggle/', views.ToggleJobAlertView.as_view(), name='toggle_job_alert'),
    
    # Cursos y certificaciones
    path('courses/', views.MyCoursesView.as_view(), name='my_courses'),
    path('certificates/', views.MyCertificatesView.as_view(), name='my_certificates'),
    path('certificates/<int:pk>/download/', views.DownloadCertificateView.as_view(), name='download_certificate'),
    
    # Configuraciones de privacidad
    path('privacy/', views.PrivacySettingsView.as_view(), name='privacy_settings'),
    path('notifications/', views.NotificationSettingsView.as_view(), name='notification_settings'),
    
    # Estadísticas personales
    path('stats/', views.PersonalStatsView.as_view(), name='personal_stats'),
    path('activity/', views.ActivityLogView.as_view(), name='activity_log'),
    
    # API endpoints
    path('api/profile/score/', views.ProfileScoreAPIView.as_view(), name='profile_score_api'),
    path('api/skills/search/', views.SkillSearchAPIView.as_view(), name='skill_search_api'),
    path('api/applications/status/', views.ApplicationStatusAPIView.as_view(), name='application_status_api'),
    
    # Exportar datos
    path('export/profile/', views.ExportProfileView.as_view(), name='export_profile'),
    path('export/data/', views.ExportPersonalDataView.as_view(), name='export_personal_data'),
]