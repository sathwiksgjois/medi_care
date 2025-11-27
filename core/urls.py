from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from django.conf import settings
from django.conf.urls.static import static

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.home, name='home'),
    path('doctors/', views.doctors, name='doctors'),
    path('doctor/<int:id>/', views.doctor_detail, name='doctor_detail'),
    path('book-appointment/<int:doctor_id>/', views.book_appointment, name='book_appointment'),
    path('appointment/success/<int:appointment_id>/', views.appointment_success, name='appointment_success'),
    path('my-appointments/', views.my_appointments, name='my_appointments'),
    path('appointment/cancel/<int:appointment_id>/', views.cancel_appointment, name='cancel_appointment'),
    path('appointment/receipt/<int:appointment_id>/', views.download_receipt, name='download_receipt'),
    path('appointment/cancel-confirm/<int:appointment_id>/', views.cancel_appointment_confirmation, name='cancel_appointment_confirmation'),
    
    # Payment URLs - Use consistent naming
    path('create-payment-order/<int:appointment_id>/', views.create_payment_order, name='create_payment_order'),
    path('verify-payment/', views.verify_payment, name='verify_payment'),

    path('search/', views.unified_search, name='unified_search'),
    
    # Authentication
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    
    # Profile and Reviews
    path('profile/', views.profile, name='profile'),
    path('doctor/<int:doctor_id>/review/', views.submit_review, name='submit_review'),
    path('doctor/<int:doctor_id>/reviews/', views.doctor_reviews, name='doctor_reviews'),
    path('reviews/', views.all_reviews, name='all_reviews'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
