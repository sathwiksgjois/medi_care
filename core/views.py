from django.shortcuts import render, get_object_or_404, redirect, HttpResponse
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import datetime, date, time, timedelta
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.contrib import messages
import razorpay
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
import json
from .forms import UserProfileForm
from .models import UserProfile, Review
from django.contrib.auth import get_user_model
from django.db import models
from .models import Doctor, Appointment
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas 
from reportlab.lib.utils import ImageReader
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import io
import os
from django.conf import settings

# Initialize Razorpay client
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

def home(request):
    doctors = Doctor.objects.all().order_by('-created_at')[:6]
    
    if request.user.is_authenticated:
        # Get user's previous appointments to suggest similar doctors
        user_specializations = Appointment.objects.filter(
            user=request.user
        ).values_list('doctor__specialization', flat=True).distinct()
        
        if user_specializations:
            featured_doctors = Doctor.objects.filter(
                is_available=True,
                specialization__in=user_specializations
            ).order_by('-rating', '-experience')[:3]
        else:
            # Fallback for new users
            featured_doctors = Doctor.objects.filter(
                is_available=True
            ).order_by('-rating', '-experience')[:3]
    else:
        # For non-logged in users
        featured_doctors = Doctor.objects.filter(
            is_available=True
        ).order_by('-rating', '-experience')[:3]
    
    return render(request, 'home.html', {
        'doctors': doctors,
        'featured_doctors': featured_doctors
    })

def doctors(request):
    doctors = Doctor.objects.all().order_by('name')
    return render(request, 'doctors.html', {'doctors': doctors})

def doctor_detail(request, id):
    doctor = get_object_or_404(Doctor, id=id)
    has_consulted = False
    
    if request.user.is_authenticated:
        has_consulted = Appointment.objects.filter(
            user=request.user, 
            doctor=doctor, 
            status='completed'
        ).exists()
    
    context = {
        'doctor': doctor,
        'has_consulted': has_consulted,
    }
    return render(request, 'doctor_detail.html', context)
    
def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful! Welcome to MediCare+.')
            return redirect('home')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserCreationForm()
    
    return render(request, 'register.html', {'form': form})

@login_required
def book_appointment(request, doctor_id):
    doctor = get_object_or_404(Doctor, id=doctor_id)
    
    if request.method == 'POST':
        date_str = request.POST.get('date')
        time_str = request.POST.get('time')
        patient_name = request.POST.get('patient_name', '').strip()
        notes = request.POST.get('notes', '')
        
        # Validate patient name
        if not patient_name:
            messages.error(request, 'Patient name is required.')
            return render(request, 'book_appointment.html', {
                'doctor': doctor,
                'error': 'Patient name is required'
            })
        
        # Validate date and time
        try:
            appointment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            appointment_time = datetime.strptime(time_str, '%H:%M').time()
        except (ValueError, TypeError):
            messages.error(request, 'Please select a valid date and time.')
            return render(request, 'book_appointment.html', {
                'doctor': doctor,
                'error': 'Invalid date or time format'
            })
        
        # Check if date is in the past
        if appointment_date < timezone.now().date():
            messages.error(request, 'Cannot book appointment for past dates.')
            return render(request, 'book_appointment.html', {
                'doctor': doctor,
                'error': 'Please select a future date'
            })
        
        # Check minimum 2 hours booking constraint
        current_datetime = timezone.now()
        appointment_datetime_aware = timezone.make_aware(
            datetime.combine(appointment_date, appointment_time)
        )
        time_difference = appointment_datetime_aware - current_datetime
        if time_difference.total_seconds() < 7200:  # 2 hours in seconds
            messages.error(request, 'Appointment must be booked at least 2 hours in advance.')
            return render(request, 'book_appointment.html', {
                'doctor': doctor,
                'error': 'Appointment must be booked at least 2 hours in advance'
            })
        
        # Check for existing appointment at same date and time
        existing_appointment = Appointment.objects.filter(
            doctor=doctor,
            date=appointment_date,
            time=appointment_time,
            status__in=['confirmed', 'pending_payment']
        ).exists()
        
        if existing_appointment:
            messages.error(request, 'This time slot is already booked. Please choose another time.')
            return render(request, 'book_appointment.html', {
                'doctor': doctor,
                'error': 'Time slot not available'
            })
        
        # Create the appointment
        try:
            appointment = Appointment.objects.create(
                user=request.user,
                doctor=doctor,
                date=appointment_date,
                time=appointment_time,
                patient_name=patient_name,
                fee=doctor.fee,
                notes=notes,
                status='confirmed'
            )
            
            messages.success(request, f'Appointment booked successfully for {appointment_date} at {appointment_time}!')
            return redirect('appointment_success', appointment_id=appointment.id)
            
        except Exception as e:
            messages.error(request, 'An error occurred while booking the appointment. Please try again.')
            return render(request, 'book_appointment.html', {
                'doctor': doctor,
                'error': 'Booking failed. Please try again.'
            })
    
    # GET request - show booking form
    return render(request, 'book_appointment.html', {
        'doctor': doctor
    })

@login_required
def appointment_success(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id, user=request.user)
    
    context = {
        "appointment": appointment,
    }
    return render(request, "appointment_success.html", context)

@login_required
def my_appointments(request):
    appointments = Appointment.objects.filter(user=request.user).order_by("-date", "-time")
    
    # Auto-complete past appointments
    for appointment in appointments:
        if appointment.status == 'confirmed':
            appointment.mark_completed_if_due()
    
    today = timezone.now().date()
    upcoming_count = appointments.filter(status='confirmed', date__gte=today).count()
    completed_count = appointments.filter(status='completed').count()
    cancelled_count = appointments.filter(status='cancelled').count()
    
    context = {
        "appointments": appointments,
        "upcoming_count": upcoming_count,
        "completed_count": completed_count,
        "cancelled_count": cancelled_count,
        "today": today,
    }
    return render(request, "my_appointments.html", context)

@login_required
def cancel_appointment_confirmation(request, appointment_id):
    """Show cancellation confirmation page"""
    appointment = get_object_or_404(Appointment, id=appointment_id, user=request.user)
    
    # Check if appointment can be cancelled using the model property
    if not appointment.can_cancel:
        messages.error(request, "Cannot cancel this appointment. It may be already completed, cancelled, or the cancellation period has passed.")
        return redirect("my_appointments")
    
    context = {
        "appointment": appointment,
    }
    return render(request, "cancel_confirmation.html", context)

@login_required
def cancel_appointment(request, appointment_id):
    """Confirm and process cancellation"""
    appointment = get_object_or_404(Appointment, id=appointment_id, user=request.user)
    
    if request.method == 'POST':
        # Check if appointment can be cancelled using the model property
        if appointment.can_cancel:
            appointment.status = "cancelled"
            appointment.save()
            messages.success(request, "Appointment cancelled successfully.")
        elif appointment.status == 'pending_payment':
            appointment.status = "cancelled"
            appointment.save()
            messages.success(request, "Appointment cancelled successfully.")
        else:
            messages.error(request, "Cannot cancel this appointment. It may be already completed, cancelled, or the cancellation period has passed.")
        
        return redirect("my_appointments")
    
    # If not POST, redirect to confirmation page
    return redirect('cancel_appointment_confirmation', appointment_id=appointment_id)

def unified_search(request):
    query = request.GET.get("q", "").strip()
    doctors = Doctor.objects.all()

    if query:
        doctors = doctors.filter(
            Q(name__icontains=query) |
            Q(specialization__icontains=query) |
            Q(hospital__icontains=query) |
            Q(city__icontains=query) |
            Q(address__icontains=query)
        ).distinct().order_by('name')

    context = {
        "q": query,
        "doctors": doctors,
    }
    return render(request, "unified_search.html", context)

@login_required
def create_payment_order(request, appointment_id):
    """
    REAL PAYMENT: Create Razorpay order for payment
    """
    appointment = get_object_or_404(Appointment, id=appointment_id, user=request.user)
    
    # If already confirmed, redirect to success
    if appointment.status == 'confirmed':
        return redirect('appointment_success', appointment_id=appointment.id)
    
    # If already has a payment order, use it
    if appointment.razorpay_order_id:
        try:
            order_data = client.order.fetch(appointment.razorpay_order_id)
            if order_data['status'] == 'paid':
                appointment.status = 'confirmed'
                appointment.save()
                return redirect('appointment_success', appointment_id=appointment.id)
        except:
            # Order expired, create new one
            pass

    # Create REAL Razorpay order
    amount = int(appointment.fee * 100)  # Convert to paise
    currency = "INR"
    
    try:
        order_data = client.order.create({
            'amount': amount,
            'currency': currency,
            'payment_capture': 1,  # Auto capture payment
            'notes': {
                'appointment_id': str(appointment.id),
                'doctor_name': appointment.doctor.name,
            }
        })
        
        appointment.razorpay_order_id = order_data['id']
        appointment.status = 'pending_payment'
        appointment.save()
        
    except Exception as e:
        messages.error(request, f"Payment gateway error: {str(e)}")
        return redirect('doctor_detail', id=appointment.doctor.id)

    context = {
        "appointment": appointment,
        "razorpay_order_id": order_data['id'],
        "amount": amount,
        "currency": currency,
        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        "user": {
            "name": request.user.get_full_name() or request.user.username,
            "email": request.user.email,
            "contact": getattr(request.user, 'phone_number', '9999999999')
        }
    }
    return render(request, "appointment_payment.html", context)

@csrf_exempt
def verify_payment(request):
    """
    REAL PAYMENT: Verify Razorpay payment
    """
    if request.method == "POST":
        try:
            # Handle direct payment success callback
            appointment_id = request.POST.get("appointment_id")
            razorpay_payment_id = request.POST.get("razorpay_payment_id")
            razorpay_order_id = request.POST.get("razorpay_order_id")
            razorpay_signature = request.POST.get("razorpay_signature")
            
            if all([appointment_id, razorpay_payment_id, razorpay_order_id, razorpay_signature]):
                appointment = get_object_or_404(Appointment, id=appointment_id)
                
                # REAL signature verification
                params_dict = {
                    'razorpay_order_id': razorpay_order_id,
                    'razorpay_payment_id': razorpay_payment_id,
                    'razorpay_signature': razorpay_signature
                }
                
                client.utility.verify_payment_signature(params_dict)
                
                # Payment verified - update appointment
                appointment.status = 'confirmed'
                appointment.payment_id = razorpay_payment_id
                appointment.razorpay_order_id = razorpay_order_id
                appointment.save()
                
                return JsonResponse({
                    "success": True,
                    "redirect_url": f"/appointment/success/{appointment.id}/"
                })
            
            return JsonResponse({"success": False, "error": "Missing payment parameters"})
            
        except razorpay.errors.SignatureVerificationError:
            return JsonResponse({"success": False, "error": "Payment signature verification failed"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    
    return JsonResponse({"error": "POST method required"}, status=400)

@login_required
def profile(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        # Create profile if it doesn't exist
        profile = UserProfile.objects.create(user=request.user)
    
    user_reviews = Review.objects.filter(user=request.user)
    user_appointments = Appointment.objects.filter(user=request.user).order_by('-date')[:5]
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
        else:
            # Show form errors if any
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserProfileForm(instance=profile)
    
    context = {
        'form': form,
        'user_reviews': user_reviews,
        'user_appointments': user_appointments,
    }
    return render(request, 'profile.html', context)

@login_required
def submit_review(request, doctor_id):
    doctor = get_object_or_404(Doctor, id=doctor_id)
    
    # Check if user has a COMPLETED appointment with this doctor
    has_consulted = Appointment.objects.filter(
        user=request.user, 
        doctor=doctor, 
        status='completed'
    ).exists()
    
    if not has_consulted:
        messages.error(request, 'You can only review doctors after you have completed your consultation.')
        return redirect('doctor_detail', id=doctor_id)
    
    # Check if user already reviewed this doctor
    existing_review = Review.objects.filter(user=request.user, doctor=doctor).first()
    
    if request.method == 'POST':
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '')
        
        if not rating:
            messages.error(request, 'Please select a rating.')
            return render(request, 'submit_review.html', {
                'doctor': doctor,
                'existing_review': existing_review,
            })
        
        if existing_review:
            # Update existing review
            existing_review.rating = rating
            existing_review.comment = comment
            existing_review.save()
            messages.success(request, 'Review updated successfully!')
        else:
            # Create new review
            Review.objects.create(
                user=request.user,
                doctor=doctor,
                rating=rating,
                comment=comment
            )
            messages.success(request, 'Review submitted successfully!')
        
        return redirect('doctor_detail', id=doctor_id)
    
    context = {
        'doctor': doctor,
        'existing_review': existing_review,
    }
    return render(request, 'submit_review.html', context)

def doctor_reviews(request, doctor_id):
    doctor = get_object_or_404(Doctor, id=doctor_id)
    reviews = Review.objects.filter(doctor=doctor).order_by('-created_at')
    
    avg_rating = reviews.aggregate(models.Avg('rating'))['rating__avg'] or 0
    
    context = {
        'doctor': doctor,
        'reviews': reviews,
        'avg_rating': round(avg_rating, 1),
        'total_reviews': reviews.count(),
    }
    return render(request, 'doctor_reviews.html', context)

@login_required
def all_reviews(request):
    """Show only the logged-in user's reviews"""
    user_reviews = Review.objects.filter(user=request.user).order_by('-created_at')
    featured_doctors = Doctor.objects.filter(reviews__user=request.user).distinct()[:6]
    
    context = {
        'reviews': user_reviews,
        'featured_doctors': featured_doctors,
    }
    return render(request, 'all_reviews.html', context)

@login_required
def download_receipt(request, appointment_id):
    """Generate professional appointment receipt as PDF"""
    appointment = get_object_or_404(Appointment, id=appointment_id, user=request.user)
    
    # Check if receipt can be downloaded using the model property
    if not appointment.can_download_receipt:
        messages.error(request, "Receipt can only be downloaded 1 hour before the appointment time.")
        return redirect('my_appointments')
    
    # Create a file-like buffer to receive PDF data
    buffer = io.BytesIO()
    
    # Create the PDF object
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = []
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1,
        textColor=colors.HexColor('#1e40af')
    )
    
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.HexColor('#1e40af')
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6
    )
    
    # Title
    title = Paragraph("MEDICARE+ - APPOINTMENT RECEIPT", title_style)
    story.append(title)
    
    # Header section
    header_data = [
        [Paragraph("<b>Receipt No:</b>", normal_style), Paragraph(f"<b>#{appointment.id}</b>", normal_style)],
        [Paragraph("<b>Issue Date:</b>", normal_style), Paragraph(f"<b>{timezone.now().strftime('%d-%m-%Y %H:%M')}</b>", normal_style)],
        [Paragraph("<b>Status:</b>", normal_style), Paragraph(f"<b>{appointment.get_status_display().upper()}</b>", normal_style)],
    ]
    
    header_table = Table(header_data, colWidths=[2*inch, 3*inch])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 20))
    
    # Patient Information
    story.append(Paragraph("PATIENT INFORMATION", header_style))
    patient_data = [
        ["Full Name:", f"{appointment.patient_name}"],
        ["Email:", request.user.email],
        ["Appointment Date:", f"{appointment.date}"],
        ["Appointment Time:", f"{appointment.time.strftime('%I:%M %p')}"],
    ]
    
    patient_table = Table(patient_data, colWidths=[2*inch, 4*inch])
    patient_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e0f2fe')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(patient_table)
    story.append(Spacer(1, 15))
    
    # Doctor Information
    story.append(Paragraph("DOCTOR & APPOINTMENT DETAILS", header_style))
    doctor_data = [
        ["Doctor Name:", f"Dr. {appointment.doctor.name}"],
        ["Specialization:", f"{appointment.doctor.get_specialization_display()}"],
        ["Hospital/Clinic:", f"{appointment.doctor.hospital}"],
        ["Address:", f"{appointment.doctor.address}"],
        ["Experience:", f"{appointment.doctor.experience}+ years"],
    ]
    
    doctor_table = Table(doctor_data, colWidths=[2*inch, 4*inch])
    doctor_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0fdf4')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(doctor_table)
    story.append(Spacer(1, 15))
    
    # Payment Information - IN RUPEES
    story.append(Paragraph("PAYMENT DETAILS", header_style))
    payment_data = [
        ["Description", "Amount"],
        ["Consultation Fee", f"₹{appointment.fee}"],
        ["Total Amount", f"<b>₹{appointment.fee}</b>"],
    ]
    
    payment_table = Table(payment_data, colWidths=[3.5*inch, 2.5*inch])
    payment_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),
    ]))
    story.append(payment_table)
    story.append(Spacer(1, 20))
    
    # Terms and Conditions Section
    story.append(Paragraph("TERMS & CONDITIONS", header_style))
    terms_text = """
    <b>1. Appointment Policy:</b> Appointments must be booked at least 2 hours in advance.<br/>
    <b>2. Receipt Download:</b> Receipts can be downloaded only 1 hour before the appointment time.<br/>
    <b>3. Cancellation Policy:</b> Cancellations must be made at least 2 hours before the appointment.<br/>
    <b>4. Late Arrivals:</b> Late arrivals may result in reduced consultation time.<br/>
    <b>5. No-shows:</b> No-shows will be charged the full consultation fee.<br/>
    <b>6. Refund Policy:</b> Refunds are processed within 5-7 business days.<br/>
    """
    terms_paragraph = Paragraph(terms_text, normal_style)
    story.append(terms_paragraph)
    story.append(Spacer(1, 15))
    
    # Important Notes
    notes_style = ParagraphStyle(
        'NotesStyle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.gray,
        alignment=1
    )
    
    story.append(Paragraph("This is a computer-generated receipt. No signature required.", notes_style))
    story.append(Spacer(1, 5))
    story.append(Paragraph("For any queries, contact: support@medicare.com | 1-800-MEDICARE", notes_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Thank you for choosing MediCare+!", notes_style))
    
    # Build PDF
    doc.build(story)
    
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="medicare_receipt_{appointment.id}.pdf"'
    
    return response