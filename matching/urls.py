from django.urls import path
from . import views

app_name = 'matching'

urlpatterns = [
    # Recomendaciones para aspirantes
    path('recommendations/', views.ApplicantRecommendationsView.as_view(), name='applicant_recommendations'),
    path('matches/', views.ApplicantMatchesView.as_view(), name='applicant_matches'),
    path('job/<int:job_id>/match/', views.JobMatchDetailView.as_view(), name='job_match_detail'),
    
    # Matching para empresas
    path('candidates/<int:job_id>/', views.JobCandidatesMatchView.as_view(), name='job_candidates_match'),
    path('candidate/<int:applicant_id>/jobs/', views.CandidateJobMatchesView.as_view(), name='candidate_job_matches'),
    path('job/<int:job_id>/candidates/export/', views.ExportCandidatesMatchView.as_view(), name='export_candidates_match'),
    
    # Análisis de compatibilidad
    path('compatibility/<int:job_id>/<int:applicant_id>/', views.CompatibilityAnalysisView.as_view(), name='compatibility_analysis'),
    path('skills-gap/<int:job_id>/<int:applicant_id>/', views.SkillsGapAnalysisView.as_view(), name='skills_gap_analysis'),
    
    # Configuración de matching
    path('settings/', views.MatchingSettingsView.as_view(), name='matching_settings'),
    path('preferences/', views.MatchingPreferencesView.as_view(), name='matching_preferences'),
    
    # Estadísticas de matching
    path('stats/', views.MatchingStatsView.as_view(), name='matching_stats'),
    path('analytics/', views.MatchingAnalyticsView.as_view(), name='matching_analytics'),
    path('effectiveness/', views.MatchingEffectivenessView.as_view(), name='matching_effectiveness'),
    
    # API endpoints
    path('api/recalculate/', views.RecalculateMatchAPIView.as_view(), name='recalculate_match_api'),
    path('api/bulk-match/', views.BulkMatchAPIView.as_view(), name='bulk_match_api'),
    path('api/match-score/', views.MatchScoreAPIView.as_view(), name='match_score_api'),
    path('api/recommendations/', views.RecommendationsAPIView.as_view(), name='recommendations_api'),
    
    # Herramientas administrativas
    path('admin/recalculate-all/', views.RecalculateAllMatchesView.as_view(), name='recalculate_all_matches'),
    path('admin/optimize/', views.OptimizeMatchingView.as_view(), name='optimize_matching'),
    path('admin/debug/<int:job_id>/<int:applicant_id>/', views.DebugMatchView.as_view(), name='debug_match'),
]