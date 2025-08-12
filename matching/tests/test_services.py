# apps/matching/tests/test_services.py
from django.test import TestCase
from decimal import Decimal
from matching.services import MatchingService
from jobs.models import JobPost, Skill
from companies.models import Company
from applicants.models import ApplicantProfile, ApplicantSkill
from django.contrib.auth import get_user_model

User = get_user_model()

class MatchingServiceTest(TestCase):
    def setUp(self):
        # Crear usuarios
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
        
        # Crear empresa
        self.company = Company.objects.create(
            user=self.company_user,
            name='Test Company'
        )
        
        # Crear aspirante
        self.applicant = ApplicantProfile.objects.create(
            user=self.applicant_user,
            first_name='Test',
            last_name='Applicant',
            years_experience=3
        )
        
        # Crear skills
        self.python_skill = Skill.objects.create(name='Python', category='Programación')
        self.django_skill = Skill.objects.create(name='Django', category='Backend')
        
        # Agregar skills al aspirante
        ApplicantSkill.objects.create(
            applicant=self.applicant,
            skill=self.python_skill,
            proficiency_level=3,
            years_experience=2
        )
        
        # Crear vacante
        self.job = JobPost.objects.create(
            company=self.company,
            title='Python Developer',
            description='Python developer position',
            requirements='Python experience required',
            experience_level='mid',
            location='Bogotá',
            deadline='2025-12-31'
        )
        
        self.job.skills_required.add(self.python_skill, self.django_skill)
    
    def test_calculate_skills_score(self):
        """Test cálculo de score de skills"""
        score = MatchingService._calculate_skills_score(self.job, self.applicant)
        
        # Aspirante tiene 1 de 2 skills requeridos = 50%
        expected_score = Decimal('0.5')
        self.assertEqual(score, expected_score)
    
    def test_calculate_experience_score(self):
        """Test cálculo de score de experiencia"""
        score = MatchingService._calculate_experience_score(self.job, self.applicant)
        
        # Vacante requiere mid (2-5 años), aspirante tiene 3 años = 100%
        expected_score = Decimal('1.0')
        self.assertEqual(score, expected_score)
    
    def test_calculate_match_score(self):
        """Test cálculo de match score completo"""
        match_score = MatchingService.calculate_match_score(self.job, self.applicant)
        
        self.assertIsNotNone(match_score)
        self.assertEqual(match_score.job_post, self.job)
        self.assertEqual(match_score.applicant, self.applicant)
        self.assertGreaterEqual(match_score.skills_score, Decimal('0.5'))