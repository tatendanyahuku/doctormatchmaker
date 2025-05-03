from app import db
from models import Consultation, Payment, Patient, Doctor

def process_payment(consultation_id):
    # Retrieve the consultation
    consultation = Consultation.query.get(consultation_id)

    if not consultation:
        return "Consultation not found."

    # Retrieve the patient and doctor
    patient = consultation.patient
    doctor = consultation.doctor

    if not patient or not doctor:
        return "Patient or doctor not found."

    # Check if the patient has enough balance
    if patient.wallet_balance < consultation.final_fee:
        return "Insufficient wallet balance."

    # Deduct the fee from the patient's wallet
    patient.wallet_balance -= consultation.final_fee

    # Add the fee to the doctor's wallet
    doctor.wallet_balance += consultation.final_fee

    # Mark the payment as completed
    payment = Payment(
        consultation_id=consultation.id,
        amount=consultation.final_fee,
        status='completed'
    )
    db.session.add(payment)

    # Update consultation status
    consultation.status = 'upcoming'

    # Commit the changes to the database
    db.session.commit()

    return "Payment processed successfully."