# apps/courses/services.py
import uuid
from datetime import datetime
from io import BytesIO
from django.core.files.base import ContentFile
from django.conf import settings
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib import colors
import os

class CertificateGenerator:
    
    @staticmethod
    def generate_certificate(enrollment):
        """
        Genera un certificado PDF para un enrollment completado
        """
        if enrollment.status != 'completed':
            raise ValueError("El curso debe estar completado para generar certificado")
        
        # Generar ID único del certificado
        certificate_id = f"MERAKI-{uuid.uuid4().hex[:8].upper()}"
        
        # Crear buffer para el PDF
        buffer = BytesIO()
        
        # Configurar documento
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Crear estilos
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=28,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#2D3748')
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=16,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#4A5568')
        )
        
        content_style = ParagraphStyle(
            'CustomContent',
            parent=styles['Normal'],
            fontSize=14,
            spaceAfter=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#2D3748')
        )
        
        # Contenido del certificado
        story = []
        
        # Logo (si existe)
        logo_path = os.path.join(settings.STATIC_ROOT or settings.STATICFILES_DIRS[0], 'img', 'logo.png')
        if os.path.exists(logo_path):
            logo = Image(logo_path, width=2*inch, height=1*inch)
            logo.hAlign = 'CENTER'
            story.append(logo)
            story.append(Spacer(1, 20))
        
        # Título
        story.append(Paragraph("CERTIFICADO DE FINALIZACIÓN", title_style))
        story.append(Spacer(1, 30))
        
        # Texto principal
        story.append(Paragraph("Se certifica que", subtitle_style))
        
        # Nombre del participante
        participant_name = f"{enrollment.applicant.first_name} {enrollment.applicant.last_name}"
        name_style = ParagraphStyle(
            'ParticipantName',
            parent=styles['Normal'],
            fontSize=24,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1A365D'),
            fontName='Helvetica-Bold'
        )
        story.append(Paragraph(participant_name, name_style))
        
        # Texto del curso
        story.append(Paragraph("ha completado satisfactoriamente el curso", content_style))
        
        # Nombre del curso
        course_style = ParagraphStyle(
            'CourseName',
            parent=styles['Normal'],
            fontSize=20,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#2B6CB0'),
            fontName='Helvetica-Bold'
        )
        story.append(Paragraph(enrollment.course.title, course_style))
        
        # Duración
        story.append(Paragraph(
            f"con una duración de {enrollment.course.duration_hours} horas académicas",
            content_style
        ))
        
        story.append(Spacer(1, 40))
        
        # Fecha y lugar
        completion_date = enrollment.completed_at.strftime("%d de %B de %Y")
        story.append(Paragraph(f"Emitido el {completion_date}", content_style))
        
        story.append(Spacer(1, 30))
        
        # ID del certificado
        id_style = ParagraphStyle(
            'CertificateID',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#718096')
        )
        story.append(Paragraph(f"ID del Certificado: {certificate_id}", id_style))
        
        # Firma digital (imagen)
        signature_path = os.path.join(settings.STATIC_ROOT or settings.STATICFILES_DIRS[0], 'img', 'signature.png')
        if os.path.exists(signature_path):
            story.append(Spacer(1, 40))
            signature = Image(signature_path, width=2*inch, height=0.8*inch)
            signature.hAlign = 'CENTER'
            story.append(signature)
            story.append(Paragraph("Director Académico", content_style))
            story.append(Paragraph("Sistema Meraki", content_style))
        
        # Generar PDF
        doc.build(story)
        
        # Crear archivo
        pdf_content = ContentFile(buffer.getvalue())
        filename = f"certificado_{certificate_id}.pdf"
        
        return certificate_id, pdf_content, filename
    
    @staticmethod
    def create_certificate_record(enrollment):
        """
        Crea un registro de certificado en la base de datos
        """
        from .models import Certificate
        
        certificate_id, pdf_content, filename = CertificateGenerator.generate_certificate(enrollment)
        
        certificate = Certificate.objects.create(
            enrollment=enrollment,
            certificate_id=certificate_id
        )
        
        certificate.pdf_file.save(filename, pdf_content, save=True)
        
        return certificate