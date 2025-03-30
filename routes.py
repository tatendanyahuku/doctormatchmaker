import os
import json
from datetime import datetime, timedelta
from functools import wraps
from flask import render_template, url_for, flash, redirect, request, jsonify, session, abort, make_response
from flask_login import login_user, current_user, logout_user, login_required
from sqlalchemy import func, desc
from werkzeug.security import generate_password_hash, check_password_hash

from app import app, db
from models import User, Patient, Doctor, Consultation, Message, Prescription, PrescriptionMedication, Payment, SpecialtyFeeRange, SystemMetrics
from forms import (RegistrationForm, LoginForm, PatientProfileForm, DoctorProfileForm, SearchDoctorForm,
                  ConsultationRequestForm, PrescriptionForm, MessageForm, DoctorVerificationForm, SpecialtyFeeRangeForm)

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
        'Cardiologist': (80, 150),
        'Dermatologist': (50, 120),
        'Neurologist': (90, 160),
        'Pediatrician': (60, 130),
        'Psychiatrist': (70, 140),
        'Orthopedist': (75, 145),
        'Gynecologist': (65, 135),
        'Ophthalmologist': (55, 125),
        'General Practitioner': (40, 100)
    }
    
    for specialty, (min_fee, max_fee) in specialties.items():
        if not SpecialtyFeeRange.query.filter_by(specialty=specialty).first():
            fee_range = SpecialtyFeeRange(
                specialty=specialty,
                min_fee=min_fee,
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
    # Get upcoming consultations
    upcoming_consultations = Consultation.query.filter_by(
        patient_id=current_user.patient.id,
        status='accepted'
    ).filter(
        Consultation.scheduled_time > datetime.utcnow()
    ).order_by(Consultation.scheduled_time).all()
    
    # Get recent prescriptions
    recent_prescriptions = Prescription.query.join(Consultation).filter(
        Consultation.patient_id == current_user.patient.id
    ).order_by(Prescription.created_at.desc()).limit(5).all()
    
    return render_template('patient/dashboard.html', 
                          title='Patient Dashboard',
                          upcoming_consultations=upcoming_consultations,
                          recent_prescriptions=recent_prescriptions,
                          now=datetime.utcnow,
                          timedelta=timedelta)

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
    
    doctors = []
    error_message = None
    
    if form.validate_on_submit():
        specialty = form.specialty.data
        proposed_fee = form.proposed_fee.data
        
        # Get fee range for the selected specialty
        fee_range = SpecialtyFeeRange.query.filter_by(specialty=specialty).first()
        
        if proposed_fee < fee_range.min_fee:
            error_message = f"Proposed fee must be at least ${fee_range.min_fee} for {specialty}"
        else:
            doctors = Doctor.query.filter_by(
                specialty=specialty,
                is_verified=True
            ).all()
    
    return render_template('patient/find_doctor.html',
                          title='Find a Doctor',
                          form=form,
                          doctors=doctors,
                          error_message=error_message)

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
                          now=datetime.utcnow,
                          timedelta=timedelta)
                          
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
                          now=datetime.utcnow,
                          timedelta=timedelta)

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
    
    return render_template('patient/wallet.html',
                          title='My Wallet',
                          wallet_balance=current_user.patient.wallet_balance,
                          payments=payments)

@app.route('/patient/pay-consultation/<int:consultation_id>', methods=['GET', 'POST'])
@login_required
@patient_required
def patient_pay_consultation(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)
    
    # Ensure the consultation belongs to the current patient
    if consultation.patient_id != current_user.patient.id:
        abort(403)
    
    # Get payment
    payment = Payment.query.filter_by(consultation_id=consultation.id).first()
    
    if not payment:
        flash('Payment not found for this consultation', 'danger')
        return redirect(url_for('patient_consultations'))
    
    if payment.status == 'completed':
        # Payment already completed, redirect to consultation room
        return redirect(url_for('patient_consultation_room', consultation_id=consultation_id))
    
    # Process payment
    if request.method == 'POST':
        # Check if patient has enough balance
        if current_user.patient.wallet_balance < consultation.final_fee:
            flash('Insufficient wallet balance. Please add funds to your wallet.', 'danger')
            return redirect(url_for('patient_wallet'))
        
        # In a real application, this would integrate with a payment gateway
        # For now, we'll just mark the payment as completed and transfer funds
        
        # Deduct from patient's wallet
        current_user.patient.wallet_balance -= consultation.final_fee
        
        # Complete the payment
        payment.status = 'completed'
        
        # Update system metrics (if it exists for today)
        today = datetime.utcnow().date()
        metrics = SystemMetrics.query.filter_by(date=today).first()
        if metrics:
            metrics.total_revenue += consultation.final_fee
        
        db.session.commit()
        
        flash('Payment successful! You can now join the consultation.', 'success')
        return redirect(url_for('patient_consultation_room', consultation_id=consultation_id))
    
    return render_template('patient/pay_consultation.html',
                          title='Pay for Consultation',
                          consultation=consultation,
                          payment=payment)

@app.route('/patient/consultation-room/<int:consultation_id>')
@login_required
@patient_required
def patient_consultation_room(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)
    
    # Ensure the consultation belongs to the current patient
    if consultation.patient_id != current_user.patient.id:
        abort(403)
    
    # Only check if the consultation is accepted
    if consultation.status != 'accepted':
        flash('This consultation is not currently active', 'danger')
        return redirect(url_for('patient_consultations'))
    
    # Check if payment is completed
    payment = Payment.query.filter_by(consultation_id=consultation.id).first()
    
    if not payment or payment.status != 'completed':
        flash('You need to complete payment before joining the consultation', 'warning')
        return redirect(url_for('patient_pay_consultation', consultation_id=consultation_id))
    
    return render_template('patient/consultation_room.html',
                          title='Consultation Room',
                          consultation=consultation,
                          now=datetime.utcnow,
                          timedelta=timedelta)

# Doctor routes
@app.route('/doctor/dashboard')
@login_required
@doctor_required
def doctor_dashboard():
    is_verified = current_user.doctor.is_verified
    
    # Check if doctor is verified
    if not is_verified:
        flash('Your account is pending verification by an administrator. You will not be able to manage consultations until your account is verified.', 'warning')
    
    # Get upcoming consultations
    upcoming_consultations = []
    pending_requests = []
    recent_payments = []
    total_prescriptions = 0
    total_earnings = 0
    total_consultations = 0
    completed_consultations = 0
    
    # Only fetch data if doctor is verified
    if is_verified:
        # Get upcoming consultations
        upcoming_consultations = Consultation.query.filter_by(
            doctor_id=current_user.doctor.id,
            status='accepted'
        ).filter(
            Consultation.scheduled_time > datetime.utcnow()
        ).order_by(Consultation.scheduled_time).all()
        
        # Get pending requests
        pending_requests = Consultation.query.filter_by(
            doctor_id=current_user.doctor.id,
            status='requested'
        ).order_by(Consultation.created_at.desc()).all()
        
        # Get recent earnings
        recent_payments = Payment.query.join(Consultation).filter(
            Consultation.doctor_id == current_user.doctor.id,
            Payment.status == 'completed'
        ).order_by(Payment.timestamp.desc()).limit(5).all()
        
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
                          recent_payments=recent_payments,
                          total_prescriptions=total_prescriptions,
                          total_earnings=total_earnings,
                          total_consultations=total_consultations,
                          completed_consultations=completed_consultations,
                          is_verified=is_verified,
                          now=datetime.utcnow,
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
                          now=datetime.utcnow)

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
                          now=datetime.utcnow,
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
                          now=datetime.utcnow,
                          timedelta=timedelta)

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
    
    return render_template('doctor/create_prescription.html',
                          title='Create Prescription',
                          form=form,
                          consultation=consultation,
                          now=datetime.utcnow)

@app.route('/prescription/<int:prescription_id>/download')
@login_required
def download_prescription(prescription_id):
    prescription = Prescription.query.get_or_404(prescription_id)
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
                          now=datetime.utcnow)
    
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
    
    # Only check if the consultation is accepted
    if consultation.status != 'accepted':
        flash('This consultation is not currently active', 'danger')
        return redirect(url_for('doctor_scheduled_consultations'))
    
    # Check if there's already a prescription for this consultation
    has_prescription = Prescription.query.filter_by(consultation_id=consultation.id).first() is not None
    
    return render_template('doctor/consultation_room.html',
                          title='Consultation Room',
                          consultation=consultation,
                          has_prescription=has_prescription,
                          now=datetime.utcnow,
                          timedelta=timedelta)

@app.route('/doctor/consultation/<int:consultation_id>/complete', methods=['POST'])
@login_required
@verified_doctor_required
def complete_consultation(consultation_id):
    consultation = Consultation.query.get_or_404(consultation_id)
    
    # Ensure the consultation belongs to the current doctor
    if consultation.doctor_id != current_user.doctor.id:
        abort(403)
    
    consultation.status = 'completed'
    consultation.completed_at = datetime.utcnow()
    
    # Update payment status
    payment = Payment.query.filter_by(consultation_id=consultation.id).first()
    if payment:
        payment.status = 'completed'
    
    # Update system metrics
    today = datetime.utcnow().date()
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
    today = datetime.utcnow().date()
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
            today = datetime.utcnow().date()
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
    today = datetime.utcnow().date()
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
            'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M:%S')
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
    
    # In a real application, you would store this offer and notify the other party
    # For simplicity, we'll just echo it back in this example
    
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
    
    # In a real application, you would store this answer and notify the other party
    # For simplicity, we'll just echo it back in this example
    
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
    
    # In a real application, you would store this candidate and notify the other party
    # For simplicity, we'll just echo it back in this example
    
    return jsonify({
        'success': True,
        'candidate': candidate
    })
