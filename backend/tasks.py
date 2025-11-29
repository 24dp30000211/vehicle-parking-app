# tasks.py
import csv
import io
from app import app, db  # We need app for mail configuration
from models import Booking, User, ParkingSpot, ParkingLot
from flask_mail import Mail, Message
from celery_worker import celery
from models import User
import time

@celery.task
def add(x, y):
    """A simple test task that adds two numbers."""
    time.sleep(5)  # Simulate a 5-second job
    return x + y

@celery.task
def hello_world():
    """A simple test task to make sure Celery is running."""
    print("Hello from Celery!")
    return "Hello from Celery!"

# tasks.py

# ... (other imports and tasks) ...

@celery.task
def generate_csv_task(user_id):
    """Generates a CSV of all bookings for a user and emails it."""

    # We must create a 'mail' instance *inside* the task
    with app.app_context():
        mail = Mail(app)

        user = User.query.get(user_id)
        if not user:
            return "User not found"

        # Fetch all user bookings
        bookings = Booking.query.filter_by(user_id=user_id).order_by(Booking.check_in_time.desc()).all()

        if not bookings:
            # You could email the user "No bookings found" or just log it
            return "No bookings found for user"

        # --- Create CSV in memory ---
        # io.StringIO is a way to create a text file in memory
        si = io.StringIO()
        writer = csv.writer(si)

        # Write header
        writer.writerow([
            'Booking ID', 'Lot Name', 'Spot Number', 
            'Check-In Time', 'Check-Out Time', 'Total Cost'
        ])

        # Write data rows
        for booking in bookings:
            spot = ParkingSpot.query.get(booking.spot_id)
            lot = ParkingLot.query.get(spot.lot_id)
            writer.writerow([
                booking.id,
                lot.name,
                spot.spot_number,
                booking.check_in_time,
                booking.check_out_time,
                booking.total_cost
            ])

        # --- Email the CSV ---
        # Reset the file "cursor" to the beginning
        si.seek(0)

        msg = Message(
            subject="Your Parking History Export",
            recipients=[user.email],
            body="Here is your parking history, attached as a CSV file."
        )

        # Attach the file
        msg.attach(
            "parking_history.csv",
            "text/csv",
            si.getvalue()
        )

        mail.send(msg)

        return f"Successfully generated and emailed report to {user.email}"

# tasks.py
# ... (other imports)

@celery.task
def send_daily_reminders():
    """
    Finds all users and sends them a promotional "reminder" email.
    """
    with app.app_context():
        mail = Mail(app)
        users = User.query.filter_by(role='user').all()

        if not users:
            print("No users found to remind.")
            return "No users."

        print(f"Sending reminders to {len(users)} user(s)...")

        # In a real app, you'd check if they booked today
        # For this, we'll just email everyone.
        for user in users:
            msg = Message(
                subject="We've got a spot for you!",
                recipients=[user.email],
                body=f"Hi {user.username},\n\n"
                     f"Just a friendly reminder that we have plenty of parking spots "
                     f"available. Book your spot today!\n\n"
                     f"- The Vehicle Parking App Team"
            )
            mail.send(msg)
            print(f"Sent reminder to {user.email}")
            
        return f"Sent reminders to {len(users)} users."

# --- We will add our real tasks here later ---
# @celery.task
# def send_daily_reminders():
#     # ... logic to find active bookings and send emails
#     print("Sending daily reminders...")

# @celery.task
# def generate_monthly_report():
#     # ... logic to generate a report
#     print("Generating monthly report...")