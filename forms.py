from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField, TextAreaField, FloatField, DateField, BooleanField, EmailField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from models import User, Doctor, SpecialtyFeeRange
from datetime import date

class RegistrationForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired(), Email()])
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Register as', choices=[('patient', 'Patient'), ('doctor', 'Doctor')])
    submit = SubmitField('Sign Up')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please use a different one.')


class LoginForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')


class PatientProfileForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=50)])
    date_of_birth = DateField('Date of Birth', validators=[DataRequired()])
    phone_number = StringField('Phone Number', validators=[Length(max=20)])
    address = StringField('Address', validators=[Length(max=200)])
    submit = SubmitField('Update Profile')


class DoctorProfileForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=50)])
    specialty = SelectField('Specialty', validators=[DataRequired()], choices=[
        ('Cardiologist', 'Cardiologist'),
        ('Dermatologist', 'Dermatologist'),
        ('Neurologist', 'Neurologist'),
        ('Pediatrician', 'Pediatrician'),
        ('Psychiatrist', 'Psychiatrist'),
        ('Orthopedist', 'Orthopedist'),
        ('Gynecologist', 'Gynecologist'),
        ('Ophthalmologist', 'Ophthalmologist'),
        ('General Practitioner', 'General Practitioner')
    ])
    license_number = StringField('License Number', validators=[DataRequired(), Length(max=50)])
    qualifications = TextAreaField('Qualifications', validators=[DataRequired()])
    submit = SubmitField('Update Profile')


class SearchDoctorForm(FlaskForm):
    specialty = SelectField('Specialty', validators=[DataRequired()], choices=[
        ('Cardiologist', 'Cardiologist'),
        ('Dermatologist', 'Dermatologist'),
        ('Neurologist', 'Neurologist'),
        ('Pediatrician', 'Pediatrician'),
        ('Psychiatrist', 'Psychiatrist'),
        ('Orthopedist', 'Orthopedist'),
        ('Gynecologist', 'Gynecologist'),
        ('Ophthalmologist', 'Ophthalmologist'),
        ('General Practitioner', 'General Practitioner')
    ])
    proposed_fee = FloatField('Proposed Fee ($)', validators=[DataRequired()])
    submit = SubmitField('Search')


class ConsultationRequestForm(FlaskForm):
    proposed_fee = FloatField('Proposed Fee ($)', validators=[DataRequired()])
    submit = SubmitField('Request Consultation')


class MedicationForm(FlaskForm):
    medication = StringField('Medication', validators=[DataRequired(), Length(max=100)])
    dosage = StringField('Dosage', validators=[DataRequired(), Length(max=100)])
    frequency = StringField('Frequency', validators=[DataRequired(), Length(max=100)])
    duration = StringField('Duration', validators=[DataRequired(), Length(max=100)])

class PrescriptionForm(FlaskForm):
    instructions = TextAreaField('Instructions')
    signature = TextAreaField('Signature', validators=[DataRequired()])
    submit = SubmitField('Submit Prescription')


class MessageForm(FlaskForm):
    content = TextAreaField('Message', validators=[DataRequired()])
    submit = SubmitField('Send')


class DoctorVerificationForm(FlaskForm):
    is_verified = BooleanField('Verify Doctor')
    submit = SubmitField('Update Verification Status')


class SpecialtyFeeRangeForm(FlaskForm):
    specialty = StringField('Specialty', validators=[DataRequired(), Length(max=100)])
    min_fee = FloatField('Minimum Fee ($)', validators=[DataRequired()])
    max_fee = FloatField('Maximum Fee ($)', validators=[DataRequired()])
    submit = SubmitField('Update Fee Range')
