import os
import json
from datetime import datetime, timedelta
from functools import wraps
from flask import render_template, url_for, flash, redirect, request, jsonify, session, abort, make_response
from flask_login import login_user, current_user, logout_user, login_required
from sqlalchemy import func, desc
from werkzeug.security import generate_password_hash, check_password_hash
import pytz
from pytz import timezone
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from flask_socketio import emit

from app import app, db, socketio
from models import User, Patient, Doctor, Consultation, Message, Prescription, PrescriptionMedication, Payment, SpecialtyFeeRange, SystemMetrics, ConsultationOffer, OfferResponse, Rating
from forms import (RegistrationForm, LoginForm, PatientProfileForm, DoctorProfileForm, SearchDoctorForm,
                  ConsultationRequestForm, PrescriptionForm, MessageForm, DoctorVerificationForm, SpecialtyFeeRangeForm)

import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime%s - %(levelname)s - %(message)s')

# Ensure app.logger is properly configured
import logging
app.logger.setLevel(logging.INFO)

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Define the timezone for Africa/Harare
HARARE_TZ = pytz.timezone('Africa/Harare')

# Get the current date and time in Harare timezone
current_time_harare = datetime.now(HARARE_TZ)
current_date_harare = current_time_harare.date()

# Decorator functions for role-based access control
def patient_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'patient':
            flash('Access denied: Patient access required', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def doctor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'doctor':
            flash('Access denied: Doctor access required', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def verified_doctor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'doctor':
            flash('Access denied: Doctor access required', 'danger')
            return redirect(url_for('login'))
        if not current_user.doctor.is_verified:
            flash('Access denied: Your account needs to be verified by an administrator before you can access this feature', 'warning')
            return redirect(url_for('doctor_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Access denied: Admin access required', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Initialize specialty fee ranges if not exist
def initialize_data():
    # Create admin user if it doesn't exist
    admin = User.query.filter_by(email='admin@medconsult.com').first()
    if not admin:
        admin_user = User(
            email='admin@medconsult.com',
            username='admin',
            role='admin'
        )
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        db.session.commit()
    
    # Create specialty fee ranges if they don't exist
    specialties = {
        'Cardiologist': (80, 115, 150),
        'Dermatologist': (50, 85, 120),
        'Neurologist': (90, 125, 160),
        'Pediatrician': (60, 95, 130),
        'Psychiatrist': (70, 105, 140),
        'Orthopedist': (75, 110, 145),
        'Gynecologist': (65, 100, 135),
        'Ophthalmologist': (55, 90, 125),
        'General Practitioner': (40, 70, 100)
    }

    for specialty, (min_fee, recommended_fee, max_fee) in specialties.items():
        if not SpecialtyFeeRange.query.filter_by(specialty=specialty).first():
            fee_range = SpecialtyFeeRange(
                specialty=specialty,
                min_fee=min_fee,
                recommended_fee=recommended_fee,
                max_fee=max_fee
            )
            db.session.add(fee_range)

    db.session.commit()

# Route for home page
@app.route('/')
def index():
    return render_template('index.html')

# Routes for authentication
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            email=form.email.data,
            username=form.username.data,
            role=form.role.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        flash('Your account has been created! You can now log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html', title='Register', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'patient':
            return redirect(url_for('patient_dashboard'))
        elif current_user.role == 'doctor':
            return redirect(url_for('doctor_dashboard'))
        elif current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            
            if user.role == 'patient' and not user.patient:
                return redirect(url_for('patient_profile'))
            elif user.role == 'doctor' and not user.doctor:
                return redirect(url_for('doctor_profile'))
            
            if user.role == 'patient':
                return redirect(next_page or url_for('patient_dashboard'))
            elif user.role == 'doctor':
                return redirect(next_page or url_for('doctor_dashboard'))
            elif user.role == 'admin':
                return redirect(next_page or url_for('admin_dashboard'))
        else:
            flash('Login unsuccessful. Please check email and password', 'danger')
    
    return render_template('login.html', title='Login', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

# Patient routes
@app.route('/patient/dashboard')
@login_required
@patient_required
def patient_dashboard():
    # Fetch upcoming consultations for the patient
    upcoming_consultations = Consultation.query.filter_by(
        patient_id=current_user.patient.id,
        status='upcoming'  # Ensure only 'upcoming' consultations are fetched
    ).filter(
        Consultation.scheduled_time > current_time_harare  # Ensure scheduled time is in the future
    ).order_by(Consultation.scheduled_time).all()

    return render_template('patient/dashboard.html', 
                           title='Patient Dashboard',
                           upcoming_consultations=upcoming_consultations,
                           now=current_time_harare)

@app.route('/patient/profile', methods=['GET', 'POST'])
@login_required
@patient_required
def patient_profile():
    form = PatientProfileForm()
    
    # If user already has a profile, populate the form
    if current_user.patient:
        if request.method == 'GET':
            form.first_name.data = current_user.patient.first_name
            form.last_name.data = current_user.patient.last_name
            form.date_of_birth.data = current_user.patient.date_of_birth
            form.phone_number.data = current_user.patient.phone_number
            form.address.data = current_user.patient.address
    
    if form.validate_on_submit():
        if current_user.patient:
            # Update existing profile
            current_user.patient.first_name = form.first_name.data
            current_user.patient.last_name = form.last_name.data
            current_user.patient.date_of_birth = form.date_of_birth.data
            current_user.patient.phone_number = form.phone_number.data
            current_user.patient.address = form.address.data
        else:
            # Create new profile
            patient = Patient(
                user_id=current_user.id,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                date_of_birth=form.date_of_birth.data,
                phone_number=form.phone_number.data,
                address=form.address.data
            )
            db.session.add(patient)
        
        db.session.commit()
        flash('Your profile has been updated!', 'success')
        return redirect(url_for('patient_dashboard'))
    
    return render_template('patient/profile.html', title='Profile', form=form)

@app.route('/patient/find-doctor', methods=['GET', 'POST'])
@login_required
@patient_required
def find_doctor():
    form = SearchDoctorForm()

    # Populate specialty choices from the database
    specialties = SpecialtyFeeRange.query.all()
    form.specialty.choices = [(s.specialty, s.specialty) for s in specialties]

    if request.method == 'POST':
        data = request.json if request.is_json else request.form
        specialty = data.get('specialty')
        proposed_fee = float(data.get('proposed_fee'))

        # Fetch the recommended fee range for the selected specialty
        fee_range = SpecialtyFeeRange.query.filter_by(specialty=specialty).first()
        if not fee_range:
            return jsonify({'error': 'Specialty not found'}), 404

        # Ensure the proposed fee is within the allowed range
        if proposed_fee < fee_range.min_fee or proposed_fee > fee_range.max_fee:
            return jsonify({'error': f'Proposed fee must be between ${fee_range.min_fee} and ${fee_range.max_fee}'}), 400

        expires_at = current_time_harare + timedelta(hours=24)
        offer = ConsultationOffer(
            patient_id=current_user.patient.id,
            specialty=specialty,
            proposed_fee=proposed_fee,
            expires_at=expires_at
        )
        db.session.add(offer)
        db.session.commit()

        # Notify all doctors in the chosen specialty about the offer
        doctors = Doctor.query.filter_by(specialty=offer.specialty, is_verified=True).all()
        for doctor in doctors:
            # Logic to notify doctors (e.g., via email or in-app notification)
            pass

        if request.is_json:
            return jsonify({
                'status': 'success',
                'offer_id': offer.id
            })

        flash('Your offer has been sent to available doctors!', 'success')
        return redirect(url_for('patient_view_offers', offer_id=offer.id))

    return render_template('patient/find_doctor.html',
                          title='Find a Doctor',
                          form=form,
                          specialties=specialties)

@app.route('/patient/view-offers/<int:offer_id>')
@login_required
@patient_required
def patient_view_offers(offer_id):
    offer = ConsultationOffer.query.get_or_404(offer_id)

    # Ensure the offer belongs to the current patient
    if offer.patient_id != current_user.patient.id:
        abort(403)

    # Get responses for this offer that have been accepted
    responses = OfferResponse.query.filter(
        OfferResponse.offer_id == offer_id,
        OfferResponse.status == 'ACCEPTED'
    ).order_by(OfferResponse.created_at.desc()).all()

    form = CSRFForm()

    responses_with_counts = []
    for response in responses:
        doctor = Doctor.query.get(response.doctor_id)
        completed_consultations_count = Consultation.query.filter_by(doctor_id=doctor.id, status='completed').count()
        responses_with_counts.append({
            'response': response,
            'doctor': doctor,
            'completed_consultations_count': completed_consultations_count
        })

    return render_template('patient/view_offers.html', offer=offer, responses=responses_with_counts, form=form)

@app.route('/patient/request-consultation/<int:doctor_id>', methods=['GET', 'POST'])
@login_required
@patient_required
def request_consultation(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    form = ConsultationRequestForm()
    
    # Pre-populate fee range information
    fee_range = SpecialtyFeeRange.query.filter_by(specialty=doctor.specialty).first()
    
    if form.validate_on_submit():
        proposed_fee = form.proposed_fee.data
        
        if proposed_fee < fee_range.min_fee:
            flash(f"Proposed fee must be at least ${fee_range.min_fee} for {doctor.specialty}", 'danger')
        else:
            consultation = Consultation(
                patient_id=current_user.patient.id,
                doctor_id=doctor.id,
                proposed_fee=proposed_fee,
                status='requested'
            )
            db.session.add(consultation)
            db.session.commit()
            
            flash('Consultation request sent successfully!', 'success')
            return redirect(url_for('patient_consultations'))
    
    return render_template('patient/request_consultation.html',
                          title='Request Consultation',
                          doctor=doctor,
                          form=form,
                          fee_range=fee_range)

@app.route('/patient/consultations')
@login_required
@patient_required
def patient_consultations():
    consultations = Consultation.query.filter_by(
        patient_id=current_user.patient.id
    ).order_by(Consultation.created_at.desc()).all()
    
    return render_template('patient/consultations.html',
                          title='My Consultations',
                          consultations=consultations,
                          now=current_time_harare,
                          timedelta=timedelta)

@app.route('/patient/scheduled-consultations')
@login_required
@patient_required
def patient_scheduled_consultations():
    # Display consultation details scheduled by the patient
    scheduled_consultations = Consultation.query.filter_by(
        patient_id=current_user.patient.id,
        status='scheduled'
    ).order_by(Consultation.scheduled_time).all()

    return render_template('patient/scheduled_consultations.html', 
                           title='Scheduled Consultations',
                           scheduled_consultations=scheduled_consultations)
                          
@app.route('/patient/consultation/<int:consultation_id>/cancel', methods=['POST'])
@login_required
@patient_required
def patient_cancel_consultation(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)
    
    # Ensure the consultation belongs to the current patient
    if consultation.patient_id != current_user.patient.id:
        abort(403)
    
    # Only allow cancellation of requested or accepted consultations
    if consultation.status not in ['requested', 'accepted']:
        flash('This consultation cannot be cancelled.', 'danger')
        return redirect(url_for('patient_consultations'))
    
    # Cancel the consultation
    consultation.status = 'cancelled'
    
    # If there is a payment, refund the patient
    payment = Payment.query.filter_by(consultation_id=consultation.id).first()
    if payment and payment.status == 'completed':
        payment.status = 'refunded'
        current_user.patient.wallet_balance += consultation.final_fee
    
    db.session.commit()
    
    flash('Consultation has been cancelled successfully.', 'success')
    return redirect(url_for('patient_consultations'))

@app.route('/patient/messages')
@login_required
@patient_required
def patient_messages():
    consultations = Consultation.query.filter_by(
        patient_id=current_user.patient.id
    ).filter(Consultation.status.in_(['accepted', 'completed'])).all()
    
    return render_template('patient/messages.html',
                          title='Messages',
                          consultations=consultations)

@app.route('/patient/consultation/<int:consultation_id>/messages', methods=['GET', 'POST'])
@login_required
@patient_required
def patient_consultation_messages(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)

    # Ensure the consultation belongs to the current patient
    if consultation.patient_id != current_user.patient.id:
        abort(403)

    form = MessageForm()

    if form.validate_on_submit():
        message = Message(
            consultation_id=consultation.id,
            sender_id=current_user.id,
            content=form.content.data
        )
        db.session.add(message)
        db.session.commit()

        return redirect(url_for('patient_consultation_messages', consultation_id=consultation.id))

    messages = Message.query.filter_by(
        consultation_id=consultation.id
    ).order_by(Message.timestamp).all()

    return render_template('patient/consultation_messages.html',
                          title='Consultation Messages',
                          consultation=consultation,
                          messages=messages,
                          form=form,
                          current_time_harare=current_time_harare)

@app.route('/patient/prescriptions')
@login_required
@patient_required
def patient_prescriptions():
    prescriptions = Prescription.query.join(Consultation).filter(
        Consultation.patient_id == current_user.patient.id
    ).order_by(Prescription.created_at.desc()).all()
    
    return render_template('patient/prescriptions.html',
                          title='My Prescriptions',
                          prescriptions=prescriptions)

@app.route('/patient/wallet', methods=['GET', 'POST'])
@login_required
@patient_required
def patient_wallet():
    # Get payment history
    payments = Payment.query.join(Consultation).filter(
        Consultation.patient_id == current_user.patient.id
    ).order_by(Payment.timestamp.desc()).all()
    
    # Process adding funds to wallet (simple implementation with dummy payment)
    if request.method == 'POST':
        amount = float(request.form.get('amount', 0))
        if amount > 0:
            # Add funds to patient's wallet balance (dummy transaction)
            current_user.patient.wallet_balance += amount
            db.session.commit()
            flash(f'Successfully added ${amount:.2f} to your wallet!', 'success')
            return redirect(url_for('patient_wallet'))
        else:
            flash('Please enter a valid amount.', 'danger')
    
    form = CSRFForm()

    return render_template('patient/wallet.html',
                          title='My Wallet',
                          wallet_balance=current_user.patient.wallet_balance,
                          payments=payments,
                          form=form)

@app.route('/patient/pay-consultation/<int:consultation_id>', methods=['GET', 'POST'])
@login_required
@patient_required
def patient_pay_consultation(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)

    # Ensure the consultation belongs to the current patient
    if consultation.patient_id != current_user.patient.id:
        abort(403)

    # Ensure the consultation has a valid final_fee
    if consultation.final_fee is None:
        consultation.final_fee = consultation.proposed_fee
        db.session.commit()

    # Deduct the consultation fee from the patient's wallet
    current_user.patient.wallet_balance -= consultation.final_fee

    # Mark the payment as completed
    payment = Payment(
        consultation_id=consultation.id,
        amount=consultation.final_fee,
        status='completed'
    )
    db.session.add(payment)

    # Update consultation status
    consultation.status = 'upcoming'
    db.session.commit()

    flash('Payment successful! Consultation has been confirmed and added to your upcoming consultations.', 'success')
    return redirect(url_for('patient_dashboard'))

@app.route('/patient/consultation-room/<int:consultation_id>')
@login_required
@patient_required
def patient_consultation_room(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)

    # Ensure the consultation belongs to the current patient
    if consultation.patient_id != current_user.patient.id:
        abort(403)

    # Allow patient to join if the consultation is active or has started
    if consultation.status not in ['accepted', 'upcoming']:
        flash('This consultation is not currently active or has not started yet.', 'danger')
        return redirect(url_for('patient_consultations'))

    # Check if payment is completed
    payment = Payment.query.filter_by(consultation_id=consultation.id).first()

    if not payment or payment.status != 'completed':
        flash('You need to complete payment before joining the consultation', 'warning')
        return redirect(url_for('patient_pay_consultation', consultation_id=consultation_id))

    # Ensure consultation.scheduled_time is timezone-aware
    scheduled_time_aware = HARARE_TZ.localize(consultation.scheduled_time) if consultation.scheduled_time.tzinfo is None else consultation.scheduled_time

    # Allow access to the consultation room without time restrictions
    return render_template('patient/consultation_room.html',
                          title='Consultation Room',
                          consultation=consultation,
                          now=current_time_harare,
                          timedelta=timedelta)

@app.route('/patient/cancel-offer/<int:offer_id>', methods=['GET', 'POST'])
@login_required
@patient_required
def cancel_offer(offer_id):
    if request.method == 'GET':
        flash('This action requires a POST request.', 'warning')
        return redirect(url_for('patient_dashboard'))

    offer = ConsultationOffer.query.get_or_404(offer_id)

    # Ensure the offer belongs to the current patient
    if offer.patient_id != current_user.patient.id:
        abort(403)

    # Mark the offer as canceled
    offer.status = 'CANCELED'
    db.session.commit()

    flash('Your offer has been canceled.', 'success')
    return redirect(url_for('patient_dashboard'))

@app.route('/patient/rate-doctor/<int:consultation_id>', methods=['GET', 'POST'])
@login_required
def rate_doctor(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)

    # Ensure the consultation belongs to the current patient
    if consultation.patient_id != current_user.patient.id:
        abort(403)

    # Ensure the consultation is completed
    if consultation.status != 'completed':
        flash('You can only rate doctors for completed consultations.', 'danger')
        return redirect(url_for('patient_dashboard'))

    if request.method == 'POST':
        rating_value = int(request.form.get('rating'))
        feedback = request.form.get('feedback')

        # Save the rating
        rating = Rating(
            consultation_id=consultation.id,
            doctor_id=consultation.doctor_id,
            patient_id=current_user.patient.id,
            rating=rating_value,
            feedback=feedback
        )
        db.session.add(rating)
        db.session.commit()

        flash('Thank you for rating your doctor!', 'success')
        return redirect(url_for('patient_dashboard'))

    return render_template('patient/rate_doctor.html', consultation=consultation)

@app.route('/patient/view-accepted-offers/<int:offer_id>')
@login_required
@patient_required
def view_accepted_offers(offer_id):
    offer = ConsultationOffer.query.get_or_404(offer_id)

    # Ensure the offer belongs to the current patient
    if offer.patient_id != current_user.patient.id:
        abort(403)

    # Get responses for this offer that have been accepted
    accepted_responses = OfferResponse.query.filter(
        OfferResponse.offer_id == offer_id,
        OfferResponse.status == 'ACCEPTED'
    ).order_by(OfferResponse.created_at.desc()).all()

    responses_with_details = []
    for response in accepted_responses:
        doctor = Doctor.query.get(response.doctor_id)
        completed_consultations_count = Consultation.query.filter_by(doctor_id=doctor.id, status='completed').count()
        responses_with_details.append({
            'response': response,
            'doctor': doctor,
            'completed_consultations_count': completed_consultations_count
        })

    return render_template('patient/view_accepted_offers.html', 
                           title='Accepted Offers', 
                           offer=offer, 
                           responses=responses_with_details)

# Doctor routes
@app.route('/doctor/dashboard')
@login_required
@doctor_required
def doctor_dashboard():
    is_verified = current_user.doctor.is_verified
    
    # Check if doctor is verified
    if not is_verified:
        flash('Your account is pending verification by an administrator. You will not be able to manage consultations until your account is verified.', 'warning')
    
    # Initialize variables
    upcoming_consultations = []
    pending_requests = []
    recent_payments = []
    total_prescriptions = 0
    total_earnings = 0
    total_consultations = 0
    completed_consultations = 0
    
    recent_payments_with_details = []  # Initialize as an empty list

    if is_verified:
        # Fetch upcoming consultations for the doctor
        upcoming_consultations = Consultation.query.filter_by(
            doctor_id=current_user.doctor.id,
            status='upcoming'  # Ensure only 'upcoming' consultations are fetched
        ).filter(
            Consultation.scheduled_time > current_time_harare  # Ensure scheduled time is in the future
        ).order_by(Consultation.scheduled_time).all()

        # Fetch pending requests
        pending_requests = Consultation.query.filter_by(
            doctor_id=current_user.doctor.id,
            status='requested'
        ).order_by(Consultation.created_at.desc()).all()
        
        # Fetch recent payments with consultation details
        recent_payments = Payment.query.join(Consultation).filter(
            Consultation.doctor_id == current_user.doctor.id,
            Payment.status == 'completed'
        ).order_by(Payment.timestamp.desc()).limit(1).all()

        recent_payments_with_details = [
            {
                'payment': payment,
                'scheduled_time': payment.consultation.scheduled_time.strftime('%B %d, %Y at %I:%M %p') if payment.consultation.scheduled_time else 'Not Scheduled',
                'patient_name': f"{payment.consultation.patient.first_name} {payment.consultation.patient.last_name}" if payment.consultation and payment.consultation.patient else 'Unknown'
            }
            for payment in recent_payments
        ]
        
        # Calculate total earnings
        earnings_result = db.session.query(func.sum(Payment.amount)).join(Consultation).filter(
            Consultation.doctor_id == current_user.doctor.id,
            Payment.status == 'completed'
        ).scalar()
        total_earnings = earnings_result if earnings_result else 0
        
        # Count prescriptions
        prescription_count = db.session.query(func.count(Prescription.id)).join(
            Consultation, Prescription.consultation_id == Consultation.id
        ).filter(
            Consultation.doctor_id == current_user.doctor.id
        ).scalar()
        total_prescriptions = prescription_count if prescription_count else 0
        
        # Count total consultations
        total_consultations_count = db.session.query(func.count(Consultation.id)).filter(
            Consultation.doctor_id == current_user.doctor.id
        ).scalar()
        total_consultations = total_consultations_count if total_consultations_count else 0
        
        # Count completed consultations
        completed_consultations_count = db.session.query(func.count(Consultation.id)).filter(
            Consultation.doctor_id == current_user.doctor.id,
            Consultation.status == 'completed'
        ).scalar()
        completed_consultations = completed_consultations_count if completed_consultations_count else 0

    return render_template('doctor/dashboard.html',
                          title='Doctor Dashboard',
                          upcoming_consultations=upcoming_consultations,
                          pending_requests=pending_requests,
                          recent_payments=recent_payments_with_details,
                          total_prescriptions=total_prescriptions,
                          total_earnings=total_earnings,
                          total_consultations=total_consultations,
                          completed_consultations=completed_consultations,
                          is_verified=is_verified,
                          now=current_time_harare,
                          timedelta=timedelta)

@app.route('/doctor/profile', methods=['GET', 'POST'])
@login_required
@doctor_required
def doctor_profile():
    form = DoctorProfileForm()
    
    # Populate specialty choices from the database
    specialties = SpecialtyFeeRange.query.all()
    form.specialty.choices = [(s.specialty, s.specialty) for s in specialties]
    
    # If user already has a profile, populate the form
    if current_user.doctor:
        if request.method == 'GET':
            form.first_name.data = current_user.doctor.first_name
            form.last_name.data = current_user.doctor.last_name
            form.specialty.data = current_user.doctor.specialty
            form.license_number.data = current_user.doctor.license_number
            form.qualifications.data = current_user.doctor.qualifications
    
    if form.validate_on_submit():
        # Get fee range for the selected specialty
        fee_range = SpecialtyFeeRange.query.filter_by(specialty=form.specialty.data).first()
        
        if current_user.doctor:
            # Update existing profile
            current_user.doctor.first_name = form.first_name.data
            current_user.doctor.last_name = form.last_name.data
            current_user.doctor.specialty = form.specialty.data
            current_user.doctor.license_number = form.license_number.data
            current_user.doctor.qualifications = form.qualifications.data
            current_user.doctor.min_fee = fee_range.min_fee
            current_user.doctor.max_fee = fee_range.max_fee
        else:
            # Create new profile
            doctor = Doctor(
                user_id=current_user.id,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                specialty=form.specialty.data,
                license_number=form.license_number.data,
                qualifications=form.qualifications.data,
                min_fee=fee_range.min_fee,
                max_fee=fee_range.max_fee,
                is_verified=False
            )
            db.session.add(doctor)
        
        db.session.commit()
        flash('Your profile has been updated! It will be reviewed by admin for verification.', 'success')
        return redirect(url_for('doctor_dashboard'))
    
    return render_template('doctor/profile.html', title='Profile', form=form)

@app.route('/doctor/pending-requests')
@login_required
@verified_doctor_required
def doctor_pending_requests():
    pending_requests = Consultation.query.filter_by(
        doctor_id=current_user.doctor.id,
        status='requested'
    ).order_by(Consultation.created_at.desc()).all()
    
    return render_template('doctor/pending_requests.html',
                          title='Pending Requests',
                          pending_requests=pending_requests,
                          now=current_time_harare)

@app.route('/doctor/consultation/<int:consultation_id>/respond', methods=['POST'])
@login_required
@verified_doctor_required
def respond_to_consultation(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)
    
    # Ensure the consultation is for the current doctor
    if consultation.doctor_id != current_user.doctor.id:
        abort(403)
    
    action = request.form.get('action')
    
    if action == 'accept':
        consultation.status = 'accepted'
        consultation.final_fee = consultation.proposed_fee
        consultation.scheduled_time = datetime.strptime(
            request.form.get('scheduled_time'),
            '%Y-%m-%dT%H:%M'
        )
        
        # Create payment record
        payment = Payment(
            consultation_id=consultation.id,
            amount=consultation.final_fee,
            status='pending'
        )
        db.session.add(payment)
        
        flash('Consultation request accepted!', 'success')
    elif action == 'reject':
        consultation.status = 'rejected'
        flash('Consultation request rejected', 'info')
    
    db.session.commit()
    return redirect(url_for('doctor_pending_requests'))

@app.route('/doctor/scheduled-consultations')
@login_required
@verified_doctor_required
def doctor_scheduled_consultations():
    consultations = Consultation.query.filter_by(
        doctor_id=current_user.doctor.id,
        status='accepted'
    ).order_by(Consultation.scheduled_time).all()
    
    return render_template('doctor/scheduled_consultations.html',
                          title='Scheduled Consultations',
                          consultations=consultations,
                          now=current_time_harare,
                          timedelta=timedelta)

@app.route('/doctor/messages')
@login_required
@verified_doctor_required
def doctor_messages():
    consultations = Consultation.query.filter_by(
        doctor_id=current_user.doctor.id
    ).filter(Consultation.status.in_(['accepted', 'completed'])).all()
    
    return render_template('doctor/messages.html',
                          title='Messages',
                          consultations=consultations)

@app.route('/doctor/consultation/<int:consultation_id>/messages', methods=['GET', 'POST'])
@login_required
@verified_doctor_required
def doctor_consultation_messages(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)
    
    # Ensure the consultation belongs to the current doctor
    if consultation.doctor_id != current_user.doctor.id:
        abort(403)
    
    form = MessageForm()
    
    if form.validate_on_submit():
        message = Message(
            consultation_id=consultation.id,
            sender_id=current_user.id,
            content=form.content.data
        )
        db.session.add(message)
        db.session.commit()
        
        return redirect(url_for('doctor_consultation_messages', consultation_id=consultation.id))
    
    messages = Message.query.filter_by(
        consultation_id=consultation.id
    ).order_by(Message.timestamp).all()
    
    return render_template('doctor/consultation_messages.html',
                          title='Consultation Messages',
                          consultation=consultation,
                          messages=messages,
                          form=form,
                          current_time_harare=current_time_harare)

@app.route('/doctor/earnings')
@login_required
@verified_doctor_required
def doctor_earnings():
    # Get all payments for completed consultations
    payments = Payment.query.join(Consultation).filter(
        Consultation.doctor_id == current_user.doctor.id,
        Payment.status == 'completed'
    ).order_by(Payment.timestamp.desc()).all()

    # Calculate total earnings
    total_earnings = sum(payment.amount for payment in payments)

    return render_template('doctor/earnings.html',
                          title='My Earnings',
                          payments=payments,
                          total_earnings=total_earnings)

@app.route('/doctor/prescriptions')
@login_required
@verified_doctor_required
def doctor_prescriptions():
    # Get all prescriptions for this doctor
    prescriptions = Prescription.query.join(Consultation).filter(
        Consultation.doctor_id == current_user.doctor.id
    ).order_by(Prescription.created_at.desc()).all()
    
    # Get all consultations for this doctor
    consultations = Consultation.query.filter(
        Consultation.doctor_id == current_user.doctor.id
    ).all()
    
    return render_template('doctor/prescriptions.html',
                          title='Prescriptions',
                          prescriptions=prescriptions,
                          consultations=consultations)

@app.route('/doctor/consultation/<int:consultation_id>/prescribe', methods=['GET', 'POST'])
@login_required
@verified_doctor_required
def create_prescription(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)
    
    # Ensure the consultation belongs to the current doctor
    if consultation.doctor_id != current_user.doctor.id:
        abort(403)
    
    # Ensure the consultation is completed or accepted
    if consultation.status not in ['accepted', 'completed']:
        flash('You can only create prescriptions for accepted or completed consultations', 'danger')
        return redirect(url_for('doctor_prescriptions'))
    
    form = PrescriptionForm()
    
    if request.method == 'POST':
        if form.validate_on_submit():
            # Validate the signature field
            if not form.signature.data:
                flash('Digital signature is required to create a prescription.', 'danger')
                return render_template('doctor/create_prescription.html',
                                      title='Create Prescription',
                                      form=form,
                                      consultation=consultation,
                                      prescription=prescription,
                                      now=current_time_harare)

            # Create the main prescription
            prescription = Prescription(
                consultation_id=consultation.id,
                instructions=form.instructions.data,
                signature=form.signature.data
            )
            db.session.add(prescription)
            db.session.flush()  # Get the prescription ID
            
            # Get the medication count from the form
            medication_count = int(request.form.get('medication_count', 1))
            
            # Add all medications
            for i in range(medication_count):
                medication_name = request.form.get(f'medication-{i}')
                dosage = request.form.get(f'dosage-{i}')
                frequency = request.form.get(f'frequency-{i}')
                duration = request.form.get(f'duration-{i}')
                
                if medication_name and dosage and frequency and duration:
                    medication = PrescriptionMedication(
                        prescription_id=prescription.id,
                        medication=medication_name,
                        dosage=dosage,
                        frequency=frequency,
                        duration=duration
                    )
                    db.session.add(medication)
            
            db.session.commit()
            
            flash('Prescription created successfully!', 'success')
            return redirect(url_for('doctor_prescriptions'))
    
    # Check if a prescription already exists for this consultation
    prescription = Prescription.query.filter_by(consultation_id=consultation.id).first()

    # If no prescription exists, create a new one
    if not prescription:
        prescription = Prescription(consultation_id=consultation.id, signature='Placeholder Signature')
        db.session.add(prescription)
        db.session.commit()

    # Pass the prescription object to the template
    return render_template('doctor/create_prescription.html',
                          title='Create Prescription',
                          form=form,
                          consultation=consultation,
                          prescription=prescription,
                          now=current_time_harare)

@app.route('/prescription/<int:prescription_id>/download')
@login_required
def download_prescription(prescription_id):
    prescription = Prescription.query.options(db.joinedload(Prescription.medications)).get_or_404(prescription_id)
    consultation = prescription.consultation
    
    # Ensure the user has access to the prescription
    if current_user.role == 'doctor':
        if consultation.doctor_id != current_user.doctor.id:
            abort(403)
    elif current_user.role == 'patient':
        if consultation.patient_id != current_user.patient.id:
            abort(403)
    
    # Generate HTML for the prescription
    html = render_template('prescription_pdf.html',
                          prescription=prescription,
                          consultation=consultation,
                          now=current_time_harare)
    
    # Create a response with the HTML content
    response = make_response(html)
    
    # Set appropriate headers to make the browser download the file
    response.headers['Content-Type'] = 'text/html'
    response.headers['Content-Disposition'] = f'attachment; filename=prescription_{prescription.id}.html'
    
    return response

@app.route('/doctor/consultation-room/<int:consultation_id>')
@login_required
@verified_doctor_required
def doctor_consultation_room(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)

    # Ensure the consultation belongs to the current doctor
    if consultation.doctor_id != current_user.doctor.id:
        abort(403)

    # Allow doctor to join if the consultation is active or has started
    if consultation.status not in ['accepted', 'upcoming']:
        flash('This consultation is not currently active or has not started yet.', 'danger')
        return redirect(url_for('doctor_dashboard'))

    # Ensure consultation.scheduled_time is timezone-aware
    scheduled_time_aware = HARARE_TZ.localize(consultation.scheduled_time) if consultation.scheduled_time.tzinfo is None else consultation.scheduled_time

    form = CSRFForm()  # Initialize the form to avoid UndefinedError

    # Generate a unique room ID for the video call
    room_id = f"consultation_{consultation_id}"

    return render_template('doctor/consultation_room.html',
                          title='Consultation Room',
                          consultation=consultation,
                          now=current_time_harare,
                          timedelta=timedelta,
                          form=form,
                          room_id=room_id)

@app.route('/doctor/consultation/<int:consultation_id>/complete', methods=['POST'])
@login_required
@verified_doctor_required
def complete_consultation(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)
    
    # Ensure the consultation belongs to the current doctor
    if consultation.doctor_id != current_user.doctor.id:
        abort(403)
    
    consultation.status = 'completed'
    consultation.completed_at = current_time_harare

    # Update the doctor's completed consultations count
    completed_consultations_count = Consultation.query.filter_by(doctor_id=consultation.doctor_id, status='completed').count()
    consultation.doctor.completed_consultations_count = completed_consultations_count

    # Update payment status
    payment = Payment.query.filter_by(consultation_id=consultation.id).first()
    if payment:
        payment.status = 'completed'

    # Update system metrics
    today = current_date_harare
    metrics = SystemMetrics.query.filter_by(date=today).first()

    if metrics:
        metrics.completed_consultations += 1
        metrics.total_revenue += consultation.final_fee
    else:
        metrics = SystemMetrics(
            date=today,
            completed_consultations=1,
            total_revenue=consultation.final_fee
        )
        db.session.add(metrics)

    db.session.commit()
    
    flash('Consultation marked as completed! Please create a prescription.', 'success')
    
    # Check if there's already a prescription for this consultation
    has_prescription = Prescription.query.filter_by(consultation_id=consultation.id).first() is not None
    
    if has_prescription:
        return redirect(url_for('doctor_scheduled_consultations'))
    else:
        # Redirect to create prescription
        return redirect(url_for('create_prescription', consultation_id=consultation.id))

@app.route('/doctor/consultation/<int:consultation_id>/submit-prescription', methods=['POST'])
@login_required
@verified_doctor_required
def submit_prescription(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)

    # Ensure the consultation belongs to the current doctor
    if consultation.doctor_id != current_user.doctor.id:
        abort(403)

    # Ensure the consultation is completed
    if consultation.status != 'completed':
        flash('You can only submit prescriptions for completed consultations.', 'danger')
        return redirect(url_for('doctor_dashboard'))

    # Check if a prescription exists for this consultation
    prescription = Prescription.query.filter_by(consultation_id=consultation.id).first()
    if not prescription:
        flash('No prescription found for this consultation.', 'danger')
        return redirect(url_for('create_prescription', consultation_id=consultation.id))

    # Ensure the prescription is properly linked to the patient
    if prescription not in consultation.patient.prescriptions:
        consultation.patient.prescriptions.append(prescription)

    # Commit the changes to save the prescription for the patient
    db.session.commit()

    flash('Prescription successfully submitted to the patient.', 'success')
    app.logger.info(f"Redirecting to doctor dashboard after sending prescription for consultation {consultation_id}")
    return redirect(url_for('doctor_dashboard'))

@app.route('/doctor/consultation/<int:consultation_id>/send-prescription', methods=['POST'])
@login_required
@verified_doctor_required
def send_prescription(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)

    # Ensure the consultation belongs to the current doctor
    if consultation.doctor_id != current_user.doctor.id:
        abort(403)

    # Ensure the consultation is completed
    if consultation.status != 'completed':
        flash('You can only send prescriptions for completed consultations.', 'danger')
        return redirect(url_for('doctor_dashboard'))

    # Check if a prescription exists for this consultation
    prescription = Prescription.query.filter_by(consultation_id=consultation.id).first()
    if not prescription:
        flash('No prescription found for this consultation.', 'danger')
        return redirect(url_for('create_prescription', consultation_id=consultation.id))

    # Link the prescription to the patient
    if prescription not in consultation.patient.prescriptions:
        consultation.patient.prescriptions.append(prescription)

    # Commit the changes to save the prescription for the patient
    db.session.commit()

    flash('Prescription successfully sent to the patient.', 'success')
    return redirect(url_for('doctor_dashboard'))

@app.route('/prescription/<int:prescription_id>/send', methods=['POST'])
@login_required
def send_prescription_to_patient(prescription_id):
    prescription = Prescription.query.get_or_404(prescription_id)
    consultation = prescription.consultation

    # Ensure the user is the doctor for this consultation
    if current_user.role != 'doctor' or consultation.doctor_id != current_user.doctor.id:
        return jsonify({'error': 'Unauthorized access'}), 403

    # Ensure the consultation is completed
    if consultation.status != 'completed':
        return jsonify({'error': 'You can only send prescriptions for completed consultations'}), 400

    # Link the prescription to the patient
    if prescription not in consultation.patient.prescriptions:
        consultation.patient.prescriptions.append(prescription)

    db.session.commit()

    # Notify the patient (e.g., via email or in-app notification)
    logging.info(f"Prescription {prescription.id} sent to patient {consultation.patient.id}")

    flash('Prescription successfully sent to the patient.', 'success')
    return redirect(url_for('doctor_dashboard'))

# Admin routes
@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    # Get counts for dashboard metrics
    patient_count = Patient.query.count()
    doctor_count = Doctor.query.count()
    verified_doctor_count = Doctor.query.filter_by(is_verified=True).count()
    pending_doctor_count = Doctor.query.filter_by(is_verified=False).count()
    total_consultations = Consultation.query.count()
    completed_consultations = Consultation.query.filter_by(status='completed').count()
    
    # Get total revenue
    total_revenue = db.session.query(func.sum(Payment.amount)).filter_by(status='completed').scalar() or 0
    
    # Get weekly metrics for charts
    today = current_date_harare
    one_week_ago = today - timedelta(days=7)
    
    daily_metrics = SystemMetrics.query.filter(
        SystemMetrics.date >= one_week_ago,
        SystemMetrics.date <= today
    ).order_by(SystemMetrics.date).all()
    
    # Get specialty distribution data
    specialty_data = db.session.query(
        Doctor.specialty, 
        func.count(Doctor.id).label('count')
    ).group_by(Doctor.specialty).all()
    
    specialties = [item[0] for item in specialty_data]
    counts = [item[1] for item in specialty_data]
    
    return render_template('admin/dashboard.html',
                          title='Admin Dashboard',
                          patient_count=patient_count,
                          doctor_count=doctor_count,
                          verified_doctor_count=verified_doctor_count,
                          pending_doctor_count=pending_doctor_count,
                          total_consultations=total_consultations,
                          completed_consultations=completed_consultations,
                          total_revenue=total_revenue,
                          daily_metrics=daily_metrics,
                          specialties=specialties,
                          counts=counts)

@app.route('/admin/doctor-verification')
@login_required
@admin_required
def doctor_verification():
    pending_doctors = Doctor.query.filter_by(is_verified=False).all()
    verified_doctors = Doctor.query.filter_by(is_verified=True).all()
    form = DoctorVerificationForm()
    
    return render_template('admin/doctor_verification.html',
                          title='Doctor Verification',
                          pending_doctors=pending_doctors,
                          verified_doctors=verified_doctors,
                          form=form)

@app.route('/admin/doctor/<int:doctor_id>/verify', methods=['POST'])
@login_required
@admin_required
def verify_doctor(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    form = DoctorVerificationForm()
    
    if form.validate_on_submit():
        doctor.is_verified = form.is_verified.data
        db.session.commit()
        
        # Update system metrics if verifying a new doctor
        if form.is_verified.data:
            today = current_date_harare
            metrics = SystemMetrics.query.filter_by(date=today).first()
            
            if metrics:
                metrics.new_doctors += 1
            else:
                metrics = SystemMetrics(
                    date=today,
                    new_doctors=1
                )
                db.session.add(metrics)
            
            db.session.commit()
        
        flash(f"Doctor {doctor.first_name} {doctor.last_name}'s verification status updated!", 'success')
    
    return redirect(url_for('doctor_verification'))

@app.route('/admin/metrics')
@login_required
@admin_required
def admin_metrics():
    # Get last 30 days of metrics
    today = current_date_harare
    thirty_days_ago = today - timedelta(days=30)
    
    daily_metrics = SystemMetrics.query.filter(
        SystemMetrics.date >= thirty_days_ago,
        SystemMetrics.date <= today
    ).order_by(SystemMetrics.date).all()
    
    # Prepare data for charts
    dates = [metric.date.strftime('%Y-%m-%d') for metric in daily_metrics]
    new_patients = [metric.new_patients for metric in daily_metrics]
    new_doctors = [metric.new_doctors for metric in daily_metrics]
    consultations = [metric.completed_consultations for metric in daily_metrics]
    revenue = [metric.total_revenue for metric in daily_metrics]
    
    # Get specialty distribution data
    specialty_data = db.session.query(
        Doctor.specialty, 
        func.count(Doctor.id).label('count')
    ).group_by(Doctor.specialty).all()
    
    specialties = [item[0] for item in specialty_data]
    counts = [item[1] for item in specialty_data]
    
    return render_template('admin/metrics.html',
                          title='System Metrics',
                          daily_metrics=daily_metrics,
                          dates=dates,
                          new_patients=new_patients,
                          new_doctors=new_doctors,
                          consultations=consultations,
                          revenue=revenue,
                          specialties=specialties,
                          counts=counts)

@app.route('/admin/specialty-fee-ranges', methods=['GET', 'POST'])
@login_required
@admin_required
def specialty_fee_ranges():
    form = SpecialtyFeeRangeForm()
    
    if form.validate_on_submit():
        # Check if specialty already exists
        fee_range = SpecialtyFeeRange.query.filter_by(specialty=form.specialty.data).first()
        
        if fee_range:
            # Update existing fee range
            fee_range.min_fee = form.min_fee.data
            fee_range.max_fee = form.max_fee.data
        else:
            # Create new fee range
            fee_range = SpecialtyFeeRange(
                specialty=form.specialty.data,
                min_fee=form.min_fee.data,
                max_fee=form.max_fee.data
            )
            db.session.add(fee_range)
        
        db.session.commit()
        flash('Specialty fee range updated successfully!', 'success')
        return redirect(url_for('specialty_fee_ranges'))
    
    fee_ranges = SpecialtyFeeRange.query.order_by(SpecialtyFeeRange.specialty).all()
    
    return render_template('admin/specialty_fee_ranges.html',
                          title='Specialty Fee Ranges',
                          form=form,
                          fee_ranges=fee_ranges)

# API routes for WebRTC video call and chat functionality
@app.route('/api/consultation/<int:consultation_id>/join', methods=['POST'])
@login_required
def join_consultation(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)
    
    # Ensure the user is part of this consultation
    is_doctor = current_user.role == 'doctor' and current_user.doctor.id == consultation.doctor_id
    is_patient = current_user.role == 'patient' and current_user.patient.id == consultation.patient_id
    
    if not (is_doctor or is_patient):
        return jsonify({'error': 'Unauthorized access'}), 403
        
    # Ensure doctor is verified if user is a doctor
    if is_doctor and not current_user.doctor.is_verified:
        return jsonify({'error': 'Your account needs to be verified before you can join consultations'}), 403
    
    # Only check if the consultation is accepted
    if consultation.status != 'accepted':
        return jsonify({'error': 'Consultation is not currently active'}), 400
    
    # Generate a unique room ID based on consultation ID
    room_id = f"consultation_{consultation_id}"
    
    # Store the user's role in the session
    session['user_role'] = 'doctor' if is_doctor else 'patient'
    
    return jsonify({
        'success': True,
        'room_id': room_id,
        'user_role': session['user_role']
    })

@app.route('/api/consultation/<int:consultation_id>/messages', methods=['GET'])
@login_required
def get_consultation_messages(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)

    # Ensure the user is part of this consultation
    is_doctor = current_user.role == 'doctor' and current_user.doctor.id == consultation.doctor_id
    is_patient = current_user.role == 'patient' and current_user.patient.id == consultation.patient_id

    if not (is_doctor or is_patient):
        return jsonify({'error': 'Unauthorized access'}), 403

    # Ensure doctor is verified if user is a doctor
    if is_doctor and not current_user.doctor.is_verified:
        return jsonify({'error': 'Your account needs to be verified before you can access consultation messages'}), 403

    # Get all messages for this consultation
    messages = Message.query.filter_by(consultation_id=consultation_id).order_by(Message.timestamp).all()

    # Format messages for JSON response
    messages_data = []
    for message in messages:
        sender = User.query.get(message.sender_id)
        messages_data.append({
            'id': message.id,
            'sender_id': message.sender_id,
            'sender_name': sender.username,
            'sender_role': sender.role,
            'content': message.content,
            'timestamp': message.timestamp.astimezone(HARARE_TZ).strftime('%Y-%m-%d %H:%M:%S')
        })

    return jsonify({
        'success': True,
        'messages': messages_data
    })

@app.route('/api/consultation/<int:consultation_id>/send-message', methods=['POST'])
@login_required
def send_consultation_message(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)
    
    # Ensure the user is part of this consultation
    is_doctor = current_user.role == 'doctor' and current_user.doctor.id == consultation.doctor_id
    is_patient = current_user.role == 'patient' and current_user.patient.id == consultation.patient_id
    
    if not (is_doctor or is_patient):
        return jsonify({'error': 'Unauthorized access'}), 403
        
    # Ensure doctor is verified if user is a doctor
    if is_doctor and not current_user.doctor.is_verified:
        return jsonify({'error': 'Your account needs to be verified before you can send messages'}), 403
    
    data = request.json
    content = data.get('content')
    
    if not content:
        return jsonify({'error': 'Message content is required'}), 400
    
    # Create and save the message
    message = Message(
        consultation_id=consultation_id,
        sender_id=current_user.id,
        content=content
    )
    db.session.add(message)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': {
            'id': message.id,
            'sender_id': message.sender_id,
            'sender_name': current_user.username,
            'sender_role': current_user.role,
            'content': message.content,
            'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }
    })

@app.route('/api/consultation/<int:consultation_id>/offer', methods=['POST'])
@login_required
def create_offer(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)
    
    # Ensure the user is part of this consultation
    is_doctor = current_user.role == 'doctor' and current_user.doctor.id == consultation.doctor_id
    is_patient = current_user.role == 'patient' and current_user.patient.id == consultation.patient_id
    
    if not (is_doctor or is_patient):
        return jsonify({'error': 'Unauthorized access'}), 403
        
    # Ensure doctor is verified if user is a doctor
    if is_doctor and not current_user.doctor.is_verified:
        return jsonify({'error': 'Your account needs to be verified before you can participate in video consultations'}), 403
    
    data = request.json
    offer = data.get('offer')
    
    if not offer:
        return jsonify({'error': 'WebRTC offer is required'}), 400
    
    logging.info(f"Received offer for consultation {consultation_id}: {offer}")
    
    return jsonify({
        'success': True,
        'offer': offer
    })

@app.route('/api/consultation/<int:consultation_id>/answer', methods=['POST'])
@login_required
def create_answer(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)
    
    # Ensure the user is part of this consultation
    is_doctor = current_user.role == 'doctor' and current_user.doctor.id == consultation.doctor_id
    is_patient = current_user.role == 'patient' and current_user.patient.id == consultation.patient_id
    
    if not (is_doctor or is_patient):
        return jsonify({'error': 'Unauthorized access'}), 403
        
    # Ensure doctor is verified if user is a doctor
    if is_doctor and not current_user.doctor.is_verified:
        return jsonify({'error': 'Your account needs to be verified before you can participate in video consultations'}), 403
    
    data = request.json
    answer = data.get('answer')
    
    if not answer:
        return jsonify({'error': 'WebRTC answer is required'}), 400
    
    logging.info(f"Received answer for consultation {consultation_id}: {answer}")
    
    return jsonify({
        'success': True,
        'answer': answer
    })

@app.route('/api/consultation/<int:consultation_id>/ice-candidate', methods=['POST'])
@login_required
def add_ice_candidate(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)
    
    # Ensure the user is part of this consultation
    is_doctor = current_user.role == 'doctor' and current_user.doctor.id == consultation.doctor_id
    is_patient = current_user.role == 'patient' and current_user.patient.id == consultation.patient_id
    
    if not (is_doctor or is_patient):
        return jsonify({'error': 'Unauthorized access'}), 403
        
    # Ensure doctor is verified if user is a doctor
    if is_doctor and not current_user.doctor.is_verified:
        return jsonify({'error': 'Your account needs to be verified before you can participate in video consultations'}), 403
    
    data = request.json
    candidate = data.get('candidate')
    
    if not candidate:
        return jsonify({'error': 'ICE candidate is required'}), 400
    
    logging.info(f"Received ICE candidate for consultation {consultation_id}: {candidate}")
    
    return jsonify({
        'success': True,
        'candidate': candidate
    })

@app.route('/api/specialties', methods=['GET'])
def get_specialties():
    specialties = SpecialtyFeeRange.query.all()
    return jsonify([
        {
            'name': s.specialty,
            'min_fee': s.min_fee,
            'recommended_fee': (s.min_fee + s.max_fee) / 2,
            'max_fee': s.max_fee
        } for s in specialties
    ])

class CSRFForm(FlaskForm):
    pass

@app.route('/doctor/available-offers')
@login_required
@verified_doctor_required
def doctor_available_offers():
    # Remove past offers from the doctor's dashboard
    current_time = datetime.now(HARARE_TZ)
    ConsultationOffer.query.filter(ConsultationOffer.expires_at < current_time).delete()
    db.session.commit()

    # Fetch recent offers for the doctor
    recent_offers = ConsultationOffer.query.filter(
        ConsultationOffer.specialty == current_user.doctor.specialty,
        ConsultationOffer.expires_at >= current_time
    ).order_by(ConsultationOffer.expires_at).all()

    form = CSRFForm()

    return render_template('doctor/available_offers.html',
                          title='Available Patient Offers',
                          offers=recent_offers,
                          form=form)

@app.route('/api/offer/<int:offer_id>/respond', methods=['POST'])
@login_required
@verified_doctor_required
def respond_to_offer(offer_id):
    offer = ConsultationOffer.query.get_or_404(offer_id)

    if offer.status != 'PENDING':
        flash('This offer is no longer active.', 'danger')
        return redirect(url_for('doctor_available_offers'))

    data = request.form
    response_type = data.get('response')

    if response_type not in ['ACCEPTED', 'DECLINED']:
        return jsonify({'error': 'Invalid response type'}), 400

    # Ensure the offer_id is correctly assigned
    response = OfferResponse(
        offer_id=offer.id,
        doctor_id=current_user.doctor.id,
        status=response_type
    )
    db.session.add(response)

    if response_type == 'ACCEPTED':
        flash('You have successfully accepted the offer. The patient will review all responses.', 'success')
    elif response_type == 'DECLINED':
        flash('You have declined the offer.', 'info')

    # Do not delete the offer to keep it available for other doctors
    db.session.commit()

    return redirect(url_for('doctor_available_offers'))

@app.route('/api/offer/<int:offer_id>/accept-response/<int:response_id>', methods=['POST'])
@login_required
@patient_required
def accept_doctor_response(offer_id, response_id):
    offer = ConsultationOffer.query.get_or_404(offer_id)
    response = OfferResponse.query.get_or_404(response_id)

    if offer.patient_id != current_user.patient.id:
        abort(403)

    if offer.status != 'PENDING':
        flash('This offer is no longer active.', 'danger')
        return redirect(url_for('patient_view_offers', offer_id=offer_id))

    # Fetch the doctor and their completed consultations count
    doctor = Doctor.query.get(response.doctor_id)
    completed_consultations_count = Consultation.query.filter_by(doctor_id=doctor.id, status='completed').count()

    # Create consultation
    consultation = Consultation(
        patient_id=current_user.patient.id,
        doctor_id=response.doctor_id,
        status='scheduled',
        proposed_fee=offer.proposed_fee
    )
    db.session.add(consultation)

    # Update offer status
    offer.status = 'ACCEPTED'

    # Flag all other doctors
    other_responses = OfferResponse.query.filter(
        OfferResponse.offer_id == offer_id,
        OfferResponse.id != response_id
    ).all()
    for other_response in other_responses:
        other_response.status = 'FLAGGED'

    db.session.commit()

    flash(f"Dr. {doctor.first_name} {doctor.last_name} has {completed_consultations_count} completed consultation(s).", 'info')

    # Redirect to schedule consultation page
    return redirect(url_for('patient_schedule_consultation', consultation_id=consultation.id))

@app.route('/api/offer/<int:offer_id>/decline-response/<int:response_id>', methods=['POST'])
@login_required
@patient_required
def decline_doctor_response(offer_id, response_id):
    offer = ConsultationOffer.query.get_or_404(offer_id)
    response = OfferResponse.query.get_or_404(response_id)

    # Ensure the offer belongs to the current patient
    if offer.patient_id != current_user.patient.id:
        abort(403)

    # Mark the response as declined
    response.status = 'DECLINED'
    db.session.commit()

    flash('You have declined the doctor response.', 'info')
    return redirect(url_for('patient_view_offers', offer_id=offer_id))

@app.route('/patient/schedule-consultation/<int:consultation_id>', methods=['GET', 'POST'])
@login_required
@patient_required
def patient_schedule_consultation(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)

    if consultation.patient_id != current_user.patient.id:
        abort(403)

    doctor = Doctor.query.get_or_404(consultation.doctor_id)
    form = FlaskForm()  # Initialize a form object

    if request.method == 'POST':
        # Get the selected date and time from the form
        date = request.form.get('date')
        time = request.form.get('time')

        if date and time:
            # Combine date and time into a datetime object
            scheduled_time = datetime.strptime(f"{date} {time}", '%Y-%m-%d %H:%M')
            consultation.scheduled_time = scheduled_time
            consultation.status = 'upcoming'  # Mark as upcoming

            # Commit changes to the database
            db.session.commit()

            flash('Consultation scheduled successfully! Please proceed to payment.', 'success')

            # Redirect to the pay consultation page
            return redirect(url_for('patient_pay_consultation', consultation_id=consultation.id))

    return render_template('patient/schedule_consultation.html',
                           title='Schedule Consultation',
                           consultation=consultation,
                           doctor=doctor,
                           form=form)

@app.route('/patient/pay-consultation-direct/<int:consultation_id>', methods=['POST'])
@login_required
@patient_required
def patient_pay_consultation_direct(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)

    # Ensure the consultation belongs to the current patient
    if consultation.patient_id != current_user.patient.id:
        abort(403)

    # Check if the patient has enough balance in their wallet
    if current_user.patient.wallet_balance < consultation.proposed_fee:
        flash('Insufficient wallet balance. Please add funds to your wallet.', 'danger')
        return redirect(url_for('patient_wallet'))

    # Deduct the fee from the patient's wallet
    current_user.patient.wallet_balance -= consultation.proposed_fee

    # Mark the consultation as confirmed
    consultation.status = 'confirmed'

    # Reflect the payment on the doctor's dashboard
    payment = Payment(
        consultation_id=consultation.id,
        amount=consultation.proposed_fee,
        status='completed'
    )
    db.session.add(payment)
    
    # After successful payment, mark the consultation as an upcoming consultation
    consultation.status = 'upcoming'
    db.session.commit()

    flash('Payment successful! Consultation has been confirmed and added to your upcoming consultations.', 'success')
    return redirect(url_for('patient_dashboard'))

@app.route('/doctor/schedule-consultation/<int:consultation_id>', methods=['POST'])
@login_required
@verified_doctor_required
def schedule_consultation(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)

    if not consultation.scheduled_time:
        # Automatically schedule the consultation for the next available slot
        consultation.scheduled_time = current_time_harare.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        db.session.commit()

        # Notify the patient about the scheduled date
        message = Message(
            consultation_id=consultation.id,
            sender_id=current_user.id,
            content=f"Your consultation with Dr. {consultation.doctor.first_name} {consultation.doctor.last_name} has been scheduled for {consultation.scheduled_time.strftime('%B %d, %Y at %I:%M %p')}."
        )
        db.session.add(message)
        db.session.commit()

        flash('Consultation has been scheduled and the patient has been notified.', 'success')

    return redirect(url_for('doctor_dashboard'))

@app.route('/update_consultation_status', methods=['POST'])
def update_consultation_status():
    # Fetch all consultations with completed payments but not marked as scheduled
    consultations = Consultation.query.join(Payment).filter(
        Payment.status == 'completed',
        Consultation.status != 'upcoming',
        Consultation.scheduled_time.isnot(None)
    ).all()

    for consultation in consultations:
        # Update the consultation status to 'upcoming'
        consultation.status = 'upcoming'

    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Consultation statuses updated successfully'})

# Add a scheduled task to update consultation statuses
from apscheduler.schedulers.background import BackgroundScheduler

# Function to update consultation statuses
def update_consultation_statuses():
    consultations = Consultation.query.join(Payment).filter(
        Payment.status == 'completed',
        Consultation.status != 'upcoming',
        Consultation.scheduled_time.isnot(None)
    ).all()

    for consultation in consultations:
        consultation.status = 'upcoming'

    db.session.commit()

# Initialize the scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(update_consultation_statuses, 'interval', minutes=10)
scheduler.start()

# Ensure the scheduler shuts down when the app exits
import atexit
atexit.register(lambda: scheduler.shutdown())

@app.route('/doctor/start-video-call/<int:consultation_id>', methods=['GET', 'POST'])
@login_required
@verified_doctor_required
def start_video_call(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)

    # Ensure the consultation belongs to the current doctor
    if consultation.doctor_id != current_user.doctor.id:
        abort(403)

    # Allow doctor to join if the consultation is active or has started
    if consultation.status not in ['accepted', 'upcoming']:
        flash('This consultation is not currently active or has not started yet.', 'danger')
        return redirect(url_for('doctor_dashboard'))

    # Check if payment is completed
    payment = Payment.query.filter_by(consultation_id=consultation.id).first()

    if not payment or payment.status != 'completed':
        flash('The patient needs to complete payment before the consultation can proceed.', 'warning')
        return redirect(url_for('doctor_dashboard'))

    # Generate a unique room ID for the video call
    room_id = f"consultation_{consultation_id}"

    return render_template('doctor/consultation_room.html',
                          title='Consultation Room',
                          consultation=consultation,
                          room_id=room_id)

# WebSocket event handlers for WebRTC signaling
@socketio.on('send_offer')
def handle_send_offer(data):
    consultation_id = data.get('consultation_id')
    offer = data.get('offer')
    emit('receive_offer', {'consultation_id': consultation_id, 'offer': offer}, broadcast=True)

@socketio.on('send_answer')
def handle_send_answer(data):
    consultation_id = data.get('consultation_id')
    answer = data.get('answer')
    emit('receive_answer', {'consultation_id': consultation_id, 'answer': answer}, broadcast=True)

@socketio.on('send_ice_candidate')
def handle_send_ice_candidate(data):
    consultation_id = data.get('consultation_id')
    candidate = data.get('candidate')
    emit('receive_ice_candidate', {'consultation_id': consultation_id, 'candidate': candidate}, broadcast=True)

@socketio.on('start_call')
def start_call(data):
    consultation_id = data.get('consultation_id')
    caller_id = data.get('caller_id')
    app.logger.info(f"[WebRTC] Start call initiated by user {caller_id} for consultation {consultation_id}")
    # Fetch the consultation
    consultation = Consultation.query.get(consultation_id)
    if not consultation:
        emit('error', {'message': 'Consultation not found'}, room=request.sid)
        return

    # Determine the recipient
    if consultation.doctor.user.id == caller_id:
        recipient_id = consultation.patient.user.id
    elif consultation.patient.user.id == caller_id:
        recipient_id = consultation.doctor.user.id
    else:
        emit('error', {'message': 'Unauthorized access'}, room=request.sid)
        return

    # Notify the recipient of the incoming call
    emit('incoming_call', {'consultation_id': consultation_id, 'caller_id': caller_id}, room=f'user_{recipient_id}')

@socketio.on('accept_call')
def accept_call(data):
    consultation_id = data.get('consultation_id')
    user_id = data.get('user_id')
    app.logger.info(f"[WebRTC] Call accepted by user {user_id} for consultation {consultation_id}")
    # Notify both participants that the call has started
    emit('call_started', {'consultation_id': consultation_id}, room=f'consultation_{consultation_id}')

@socketio.on('reject_call')
def reject_call(data):
    consultation_id = data.get('consultation_id')
    caller_id = data.get('caller_id')
    app.logger.info(f"[WebRTC] Call rejected by user {caller_id} for consultation {consultation_id}")
    # Notify the caller that the call was rejected
    emit('call_rejected', {'consultation_id': consultation_id}, room=f'user_{caller_id}')

@socketio.on('initiate_call')
def initiate_call(data):
    consultation_id = data.get('consultation_id')
    caller_id = data.get('caller_id')

    # Fetch the consultation
    consultation = Consultation.query.get(consultation_id)
    if not consultation:
        emit('error', {'message': 'Consultation not found'}, room=request.sid)
        return

    # Determine the recipient
    if consultation.doctor.user.id == caller_id:
        recipient_id = consultation.patient.user.id
    elif consultation.patient.user.id == caller_id:
        recipient_id = consultation.doctor.user.id
    else:
        emit('error', {'message': 'Unauthorized access'}, room=request.sid)
        return

    # Notify the recipient of the incoming call
    emit('incoming_call', {'consultation_id': consultation_id, 'caller_id': caller_id}, room=f'user_{recipient_id}')

@socketio.on('accept_call')
def accept_call(data):
    consultation_id = data.get('consultation_id')
    user_id = data.get('user_id')

    # Notify both participants that the call has started
    emit('call_started', {'consultation_id': consultation_id}, room=f'consultation_{consultation_id}')

@socketio.on('reject_call')
def reject_call(data):
    consultation_id = data.get('consultation_id')
    caller_id = data.get('caller_id')

    # Notify the caller that the call was rejected
    emit('call_rejected', {'consultation_id': consultation_id}, room=f'user_{caller_id}')

# Add video consultation functionality for both doctor and patient

@app.route('/video-consultation/<int:consultation_id>')
@login_required
def video_consultation(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)

    # Ensure the user is either the doctor or the patient for this consultation
    if current_user.role == 'doctor' and consultation.doctor_id != current_user.doctor.id:
        abort(403)
    elif current_user.role == 'patient' and consultation.patient_id != current_user.patient.id:
        abort(403)

    # Ensure the consultation is active or upcoming
    if consultation.status not in ['accepted', 'upcoming']:
        flash('This consultation is not currently active or has not started yet.', 'danger')
        return redirect(url_for('patient_dashboard' if current_user.role == 'patient' else 'doctor_dashboard'))

    # Generate a unique room ID for the video call
    room_id = f"consultation_{consultation_id}"

    return render_template('video_call.html',
                           title='Video Consultation',
                           consultation=consultation,
                           room_id=room_id)

from flask import Blueprint, request, jsonify
from flask_login import login_required
from models import db, ConsultationSignaling

consultation_bp = Blueprint("consultation", __name__)

@consultation_bp.route("/consultation/api/signaling/<int:consultation_id>", methods=["POST"])
@login_required
def send_signaling_message(consultation_id):
    data = request.get_json()
    msg = ConsultationSignaling(
        consultation_id=consultation_id,
        sender=data["sender"],
        receiver=data["receiver"],
        type=data["type"],
        data=data["data"],
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify({"status": "ok"}), 200

@consultation_bp.route("/consultation/api/signaling/<int:consultation_id>/<receiver>", methods=["GET"])
@login_required
def get_signaling_messages(consultation_id, receiver):
    messages = ConsultationSignaling.query.filter_by(
        consultation_id=consultation_id, receiver=receiver
    ).all()

    messages_data = [
        {
            "id": msg.id,
            "sender": msg.sender,
            "receiver": msg.receiver,
            "type": msg.type,
            "data": msg.data,
        }
        for msg in messages
    ]

    # Delete messages after delivery (optional for stateless signaling)
    for msg in messages:
        db.session.delete(msg)
    db.session.commit()

    return jsonify(messages_data), 200
