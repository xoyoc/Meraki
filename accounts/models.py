# apps/accounts/models.py
from django.contrib.auth.models import AbstractUser, Permission, Group
from django.db import models

class User(AbstractUser):
    USER_TYPES = (
        ('admin', 'Administrador'),
        ('company', 'Empresa'),
        ('applicant', 'Aspirante'),
    )
    user_type = models.CharField(max_length=20, choices=USER_TYPES)
    user_permissions = models.ManyToManyField(Permission, related_name='User', blank=True)
    groups = models.ManyToManyField(Group, related_name='User', blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    email = models.EmailField(unique=True)
    
    # Usar email como username
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']
    
    def get_user_type_display(self):
        return dict(self.USER_TYPES).get(self.user_type, self.user_type)
    
    def __str__(self):
        return self.email

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to='avatars/', blank=True)
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=100, blank=True)