"""
URL configuration for sistema project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),  # Home y páginas principales
    path('accounts/', include('accounts.urls')),  # Aplicación de cuentas de usuario
    path('jobs/', include('jobs.urls')),  # Descomentar cuando exista
    path('applicants/', include('applicants.urls')),  # Descomentar cuando exista
    path('companies/', include('companies.urls')),  # Descomentar cuando exista
    path('courses/', include('courses.urls')),  # Descomentar cuando exista
    path('matching/', include('matching.urls')),  # Descomentar cuando exista
    path('notifications/', include('notifications.urls')), 
    # path('ckeditor/', include('ckeditor_uploader.urls')),  # Descomentar cuando se instale CKEditor
]

# Servir archivos media en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Configurar títulos del admin
admin.site.site_header = 'Administración Meraki'
admin.site.site_title = 'Meraki Admin'
admin.site.index_title = 'Panel de Administración'