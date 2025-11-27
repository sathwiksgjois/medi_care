from django.contrib import admin
from .models import Doctor, Appointment, Review, UserProfile

@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = [
        'name', 
        'specialization', 
        'experience', 
        'hospital', 
        'city', 
        'fee', 
        'is_available',
        'created_at'
    ]
    list_filter = [
        'specialization', 
        'city', 
        'is_available',
        'created_at'
    ]
    search_fields = [
        'name', 
        'specialization', 
        'hospital', 
        'city'
    ]
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 20

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'user', 
        'doctor', 
        'date', 
        'time', 
        'fee', 
        'status',
        'created_at'
    ]
    list_filter = [
        'status', 
        'date',
        'doctor',
        'created_at'
    ]
    search_fields = [
        'user__username', 
        'doctor__name', 
        'user__email'
    ]
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 20
    
    # Optional: Add custom method to show doctor specialization
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'doctor')

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = [
        'user', 
        'doctor', 
        'rating', 
        'created_at'
    ]
    list_filter = [
        'rating', 
        'created_at',
        'doctor'
    ]
    search_fields = [
        'user__username', 
        'doctor__name', 
        'comment'
    ]
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 20

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user', 
        'phone_number', 
        'date_of_birth', 
        'created_at'
    ]
    search_fields = [
        'user__username', 
        'user__email', 
        'phone_number'
    ]
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 20

# Optional: You can also customize the admin site header and title
admin.site.site_header = "MediCare+ Administration"
admin.site.site_title = "MediCare+ Admin Portal"
admin.site.index_title = "Welcome to MediCare+ Admin Portal"