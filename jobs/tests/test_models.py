# apps/jobs/tests/test_models.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.jobs.models import JobPost, Skill, Application
from apps.companies.models import Company
from apps.applicants.models import ApplicantProfile

User = get_user_model()

class JobPostModelTest(TestCase):
    def setUp(self):
        # Crear usuario empresa
        self.company_user = User.objects.create_user(
            username='testcompany',
            email='company@test.com',
            password='testpass123',
            user_type='company'
        )
        
        # Crear empresa
        self.company = Company.objects.create(
            user=self.company_user,
            name='Test Company',
            description='Test Description'
        )
        
        # Crear skills
        self.skill = Skill.objects.create(
            name='Python',
            category='Programación'
        )
    
    def test_job_post_creation(self):
        """Test creación de vacante"""
        job = JobPost.objects.create(
            company=self.company,
            title='Desarrollador Python',
            description='Descripción de la vacante',
            requirements='Requisitos de la vacante',
            experience_level='mid',
            location='Bogotá',
            deadline='2025-12-31'
        )
        
        self.assertEqual(job.title, 'Desarrollador Python')
        self.assertEqual(job.status, 'draft')
        self.assertTrue(job.is_active)
    
    def test_job_post_skills(self):
        """Test relación con skills"""
        job = JobPost.objects.create(
            company=self.company,
            title='Desarrollador Python',
            description='Descripción',
            requirements='Requisitos',
            experience_level='mid',
            location='Bogotá',
            deadline='2025-12-31'
        )
        
        job.skills_required.add(self.skill)
        self.assertIn(self.skill, job.skills_required.all())

class ApplicationModelTest(TestCase):
    def setUp(self):
        # Setup similar al anterior
        self.company_user = User.objects.create_user(
            username='company',
            email='company@test.com',
            password='pass',
            user_type='company'
        )
        
        self.applicant_user = User.objects.create_user(
            username='applicant',
            email='applicant@test.com',
            password='pass',
            user_type='applicant'
        )
        
        self.company = Company.objects.create(
            user=self.company_user,
            name='Test Company'
        )
        
        self.applicant = ApplicantProfile.objects.create(
            user=self.applicant_user,
            first_name='Test',
            last_name='Applicant'
        )
        
        self.job = JobPost.objects.create(
            company=self.company,
            title='Test Job',
            description='Description',
            requirements='Requirements',
            experience_level='entry',
            location='Test City',
            deadline='2025-12-31'
        )
    
    def test_application_creation(self):
        """Test creación de postulación"""
        application = Application.objects.create(
            job_post=self.job,
            applicant=self.applicant,
            cover_letter='Test cover letter'
        )
        
        self.assertEqual(application.status, 'applied')
        self.assertEqual(application.job_post, self.job)
        self.assertEqual(application.applicant, self.applicant)
    
    def test_unique_application(self):
        """Test que no se pueda aplicar dos veces a la misma vacante"""
        Application.objects.create(
            job_post=self.job,
            applicant=self.applicant
        )
        
        with self.assertRaises(Exception):
            Application.objects.create(
                job_post=self.job,
                applicant=self.applicant
            )