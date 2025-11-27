from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import datetime, timedelta

class Doctor(models.Model):
    SPECIALIZATION_CHOICES = [
        ('cardiology', 'Cardiology'),
        ('dermatology', 'Dermatology'),
        ('pediatrics', 'Pediatrics'),
        ('orthopedics', 'Orthopedics'),
        ('neurology', 'Neurology'),
        ('gynecology', 'Gynecology'),
        ('psychiatry', 'Psychiatry'),
        ('dentistry', 'Dentistry'),
        ('ophthalmology', 'Ophthalmology'),
        ('general', 'General Medicine'),
    ]

    name = models.CharField(max_length=100)
    specialization = models.CharField(max_length=50, choices=SPECIALIZATION_CHOICES, default='general')
    experience = models.PositiveIntegerField(default=0)
    hospital = models.CharField(max_length=200)
    address = models.TextField()
    city = models.CharField(max_length=100)
    fee = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])
    image = models.ImageField(upload_to='doctors/', blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    is_available = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Dr. {self.name} - {self.get_specialization_display()}"

    @property
    def avg_rating(self):
        """Calculate average rating from reviews"""
        from django.db.models import Avg
        if hasattr(self, 'reviews'):
            result = self.reviews.aggregate(avg_rating=Avg('rating'))
            return result['avg_rating'] or 0
        return 0
    
    @property
    def review_count(self):
        """Get total number of reviews"""
        if hasattr(self, 'reviews'):
            return self.reviews.count()
        return 0
    
    @property
    def display_fee(self):
        """Display fee in rupees"""
        return f"₹{self.fee}"
    
    def get_recent_reviews(self, count=3):
        """Get recent reviews for this doctor"""
        if hasattr(self, 'reviews'):
            return self.reviews.all().order_by('-created_at')[:count]
        return []

class Appointment(models.Model):
    STATUS_CHOICES = [
        ('pending_payment', 'Pending Payment'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='appointments')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='appointments')
    patient_name = models.CharField(max_length=100)
    date = models.DateField()
    time = models.TimeField()
    fee = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_payment')
    
    razorpay_order_id = models.CharField(max_length=255, blank=True, null=True)
    payment_id = models.CharField(max_length=255, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-time']

    def __str__(self):
        return f"Appointment #{self.id} - {self.patient_name} with Dr. {self.doctor.name}"

    def save(self, *args, **kwargs):
        if not self.fee and self.doctor:
            self.fee = self.doctor.fee
        super().save(*args, **kwargs)

    @property
    def is_completed(self):
        """Check if appointment should be marked as completed"""
        appointment_datetime = datetime.combine(self.date, self.time)
        current_datetime = datetime.now()
        return current_datetime > appointment_datetime
    
    def mark_completed_if_due(self):
        """Mark appointment as completed if time has passed"""
        if self.status == 'confirmed' and self.is_completed:
            self.status = 'completed'
            self.save()
            return True
        return False

    @property
    def can_cancel(self):
        """Check if appointment can be cancelled (until 2 hours before)"""
        if self.status != 'confirmed':
            return False
        
        # Create naive appointment datetime
        appointment_datetime = datetime.combine(self.date, self.time)
        
        # Get current naive datetime
        current_datetime = datetime.now()
        
        # Calculate 2 hours before appointment
        two_hours_before = appointment_datetime - timedelta(hours=2)
        
        # Compare both naive datetimes
        return current_datetime <= two_hours_before

    @property
    def can_download_receipt(self):
        """Check if receipt can be downloaded (1 hour before appointment)"""
        if self.status not in ['confirmed', 'completed']:
            return False
            
        # Create naive appointment datetime
        appointment_datetime = datetime.combine(self.date, self.time)
        
        # Get current naive datetime
        current_datetime = datetime.now()
        
        # Calculate 1 hour before appointment
        one_hour_before = appointment_datetime - timedelta(hours=1)
        
        # Compare both naive datetimes
        return current_datetime >= one_hour_before

    @property
    def has_reviewed(self):
        """Check if user has already reviewed this doctor"""
        return Review.objects.filter(
            user=self.user, 
            doctor=self.doctor
        ).exists()

class Review(models.Model):
    RATING_CHOICES = [
        (1, '1 Star'),
        (2, '2 Stars'),
        (3, '3 Stars'),
        (4, '4 Stars'),
        (5, '5 Stars'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(choices=RATING_CHOICES, validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['user', 'doctor']

    def __str__(self):
        return f"Review by {self.user.username} for Dr. {self.doctor.name}"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile of {self.user.username}"