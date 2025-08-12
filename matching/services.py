# apps/matching/services.py
from decimal import Decimal
from django.db.models import Q, Count
from jobs.models import JobPost
from applicants.models import ApplicantProfile
from matching.models import MatchScore

class MatchingService:
    
    @staticmethod
    def calculate_match_score(job_post, applicant):
        """
        Calcula el score de matching entre una vacante y un aspirante
        """
        # Inicializar scores
        skills_score = MatchingService._calculate_skills_score(job_post, applicant)
        experience_score = MatchingService._calculate_experience_score(job_post, applicant)
        location_score = MatchingService._calculate_location_score(job_post, applicant)
        education_score = MatchingService._calculate_education_score(job_post, applicant)
        
        # Pesos para cada componente
        weights = {
            'skills': 0.4,
            'experience': 0.3,
            'location': 0.2,
            'education': 0.1
        }
        
        # Calcular score total
        total_score = (
            skills_score * weights['skills'] +
            experience_score * weights['experience'] +
            location_score * weights['location'] +
            education_score * weights['education']
        ) * 100  # Convertir a porcentaje
        
        # Crear o actualizar MatchScore
        match_score, created = MatchScore.objects.update_or_create(
            job_post=job_post,
            applicant=applicant,
            defaults={
                'skills_score': skills_score * 100,
                'experience_score': experience_score * 100,
                'location_score': location_score * 100,
                'education_score': education_score * 100,
                'total_score': total_score,
            }
        )
        
        return match_score
    
    @staticmethod
    def _calculate_skills_score(job_post, applicant):
        """Calcula el score basado en skills"""
        job_skills = set(job_post.skills_required.values_list('id', flat=True))
        if not job_skills:
            return Decimal('0.5')  # Score neutro si no hay skills definidos
        
        applicant_skills = set(applicant.skills.values_list('id', flat=True))
        
        if not applicant_skills:
            return Decimal('0.0')
        
        # Calcular intersección
        matching_skills = job_skills.intersection(applicant_skills)
        match_ratio = len(matching_skills) / len(job_skills)
        
        return Decimal(str(match_ratio))
    
    @staticmethod
    def _calculate_experience_score(job_post, applicant):
        """Calcula el score basado en experiencia"""
        experience_mapping = {
            'entry': (0, 2),
            'mid': (2, 5),
            'senior': (5, 100)
        }
        
        required_range = experience_mapping.get(job_post.experience_level, (0, 100))
        applicant_exp = applicant.years_experience
        
        if required_range[0] <= applicant_exp <= required_range[1]:
            return Decimal('1.0')
        elif applicant_exp < required_range[0]:
            # Penalizar falta de experiencia
            diff = required_range[0] - applicant_exp
            return max(Decimal('0.0'), Decimal('1.0') - Decimal(str(diff * 0.2)))
        else:
            # Sobreexperiencia no penaliza tanto
            return Decimal('0.9')
    
    @staticmethod
    def _calculate_location_score(job_post, applicant):
        """Calcula el score basado en ubicación"""
        if not job_post.location or not applicant.user.profile.location:
            return Decimal('0.5')  # Score neutro
        
        # Simplificado: coincidencia exacta o parcial
        job_location = job_post.location.lower()
        applicant_location = applicant.user.profile.location.lower()
        
        if job_location in applicant_location or applicant_location in job_location:
            return Decimal('1.0')
        else:
            return Decimal('0.3')  # Penalización por ubicación diferente
    
    @staticmethod
    def _calculate_education_score(job_post, applicant):
        """Calcula el score basado en educación"""
        education_weights = {
            'high_school': 1,
            'technical': 2,
            'bachelor': 3,
            'master': 4,
            'phd': 5
        }
        
        # Por ahora, score neutro - se puede mejorar según requisitos específicos
        return Decimal('0.7')
    
    @staticmethod
    def get_best_matches_for_job(job_post, limit=10):
        """Obtiene los mejores candidatos para una vacante"""
        matches = MatchScore.objects.filter(
            job_post=job_post
        ).select_related(
            'applicant__user'
        ).order_by('-total_score')[:limit]
        
        return matches
    
    @staticmethod
    def get_recommended_jobs_for_applicant(applicant, limit=10):
        """Obtiene las mejores vacantes para un aspirante"""
        matches = MatchScore.objects.filter(
            applicant=applicant
        ).select_related(
            'job_post__company'
        ).order_by('-total_score')[:limit]
        
        return matches
    
    @staticmethod
    def recalculate_all_matches():
        """Recalcula todos los matches - para ejecutar periódicamente"""
        active_jobs = JobPost.objects.filter(status='approved', is_active=True)
        active_applicants = ApplicantProfile.objects.filter(
            user__is_active=True
        )
        
        for job in active_jobs:
            for applicant in active_applicants:
                MatchingService.calculate_match_score(job, applicant)