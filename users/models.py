import random #otp
from django.utils import timezone #otp
from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('others', 'Others'),
    ]
    
    mobile_number = models.CharField(max_length=15, unique=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    date_of_birth = models.DateField(null=True, blank=True)
    

    #2FA fields
    otp=models.CharField(max_length=6, null=True, blank=True)
    otp_expiry =models.DateTimeField(null=True,blank=True)
    
    def __str__(self):
        return self.username
    
    #Method to generate and save OTP
    def generate_otp(self):
        """Generates a 6-digit OTP, sets its expiry time, and saves the user."""
        self.otp = str(random.randint(100000, 999999))
        self.otp_expiry = timezone.now() + timezone.timedelta(minutes=5) # OTP is valid for 5 minutes
        self.save()
        return self.otp