from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager


@login_manager.user_loader
def load_user(user_id):
    user = User.query.get(int(user_id))
    if user:
        return user
    return None


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(64), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'patient', 'doctor', 'admin'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = db.relationship('Patient', backref='user', uselist=False, lazy=True)
    doctor = db.relationship('Doctor', backref='user', uselist=False, lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Patient(db.Model):
    __tablename__ = 'patients'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=True)
    phone_number = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    
    # Relationships
    consultations = db.relationship('Consultation', backref='patient', lazy=True)
    wallet_balance = db.Column(db.Float, default=0.0)
    
    def __repr__(self):
        return f"Patient('{self.first_name} {self.last_name}')"


class Doctor(db.Model):
    __tablename__ = 'doctors'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    specialty = db.Column(db.String(100), nullable=False)
    license_number = db.Column(db.String(50), nullable=False)
    qualifications = db.Column(db.Text, nullable=True)
    min_fee = db.Column(db.Float, nullable=False)
    max_fee = db.Column(db.Float, nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    
    # Relationships
    consultations = db.relationship('Consultation', backref='doctor', lazy=True)
    
    def __repr__(self):
        return f"Doctor('{self.first_name} {self.last_name}', '{self.specialty}')"


class Consultation(db.Model):
    __tablename__ = 'consultations'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    status = db.Column(db.String(50), default='requested')  # requested, accepted, rejected, completed, cancelled
    proposed_fee = db.Column(db.Float, nullable=False)
    final_fee = db.Column(db.Float, nullable=True)
    scheduled_time = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    messages = db.relationship('Message', backref='consultation', lazy=True)
    prescriptions = db.relationship('Prescription', backref='consultation', lazy=True)
    
    def __repr__(self):
        return f"Consultation(Patient: {self.patient_id}, Doctor: {self.doctor_id}, Status: {self.status})"


class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    consultation_id = db.Column(db.Integer, db.ForeignKey('consultations.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship for sender
    sender = db.relationship('User', foreign_keys=[sender_id])
    
    def __repr__(self):
        return f"Message(Sender: {self.sender_id}, Time: {self.timestamp})"


class Prescription(db.Model):
    __tablename__ = 'prescriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    consultation_id = db.Column(db.Integer, db.ForeignKey('consultations.id'), nullable=False)
    medication = db.Column(db.String(100), nullable=False)
    dosage = db.Column(db.String(100), nullable=False)
    frequency = db.Column(db.String(100), nullable=False)
    duration = db.Column(db.String(100), nullable=False)
    instructions = db.Column(db.Text, nullable=True)
    signature = db.Column(db.Text, nullable=False)  # Doctor's electronic signature
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"Prescription(Consultation: {self.consultation_id}, Medication: {self.medication})"


class Payment(db.Model):
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    consultation_id = db.Column(db.Integer, db.ForeignKey('consultations.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='pending')  # pending, completed, refunded
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"Payment(Consultation: {self.consultation_id}, Amount: {self.amount}, Status: {self.status})"


class SpecialtyFeeRange(db.Model):
    __tablename__ = 'specialty_fee_ranges'
    
    id = db.Column(db.Integer, primary_key=True)
    specialty = db.Column(db.String(100), unique=True, nullable=False)
    min_fee = db.Column(db.Float, nullable=False)
    max_fee = db.Column(db.Float, nullable=False)
    
    def __repr__(self):
        return f"SpecialtyFeeRange('{self.specialty}', ${self.min_fee}-${self.max_fee})"


class SystemMetrics(db.Model):
    __tablename__ = 'system_metrics'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    new_patients = db.Column(db.Integer, default=0)
    new_doctors = db.Column(db.Integer, default=0)
    total_consultations = db.Column(db.Integer, default=0)
    completed_consultations = db.Column(db.Integer, default=0)
    total_revenue = db.Column(db.Float, default=0.0)
    
    def __repr__(self):
        return f"SystemMetrics(Date: {self.date}, Revenue: ${self.total_revenue})"
