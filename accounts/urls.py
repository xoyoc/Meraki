from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    # Autenticación básica
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('signup/', views.SignUpView.as_view(), name='signup'),
    
    # Gestión de perfil
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.ProfileEditView.as_view(), name='profile_edit'),
    path('profile/avatar/', views.AvatarUpdateView.as_view(), name='avatar_update'),
    
    # Cambio de contraseña
    path('password/change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('password/change/done/', views.CustomPasswordChangeDoneView.as_view(), name='password_change_done'),
    
    # Recuperación de contraseña
    path('password/reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password/reset/done/', views.CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password/reset/confirm/<uidb64>/<token>/', views.CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password/reset/complete/', views.CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
    
    # Verificación de email
    path('email/verify/', views.EmailVerificationSentView.as_view(), name='email_verification_sent'),
    path('email/verify/<uidb64>/<token>/', views.EmailVerifyView.as_view(), name='email_verify'),
    
    # Configuraciones de cuenta
    path('settings/', views.AccountSettingsView.as_view(), name='settings'),
    path('settings/privacy/', views.PrivacySettingsView.as_view(), name='privacy_settings'),
    path('settings/notifications/', views.NotificationSettingsView.as_view(), name='notification_settings'),
    
    # Eliminación de cuenta
    path('delete/', views.AccountDeleteView.as_view(), name='account_delete'),
    path('delete/confirm/', views.AccountDeleteConfirmView.as_view(), name='account_delete_confirm'),
    
    # AJAX para validaciones
    path('ajax/validate-email/', views.validate_email_ajax, name='validate_email_ajax'),
    path('ajax/check-password/', views.check_password_strength, name='check_password_strength'),

    # Django Allauth URLs (para autenticación social)
    # path('social/', include('allauth.urls')),  # Descomentar cuando se instale allauth
]