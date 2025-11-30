import csv
import io
import datetime
from celery_worker import celery
from app import app
from models import User, Booking, ParkingSpot, ParkingLot
from flask_mail import Mail, Message
from dateutil.relativedelta import relativedelta

# This task simulates a long calculation (adding numbers)
# just to verify that Celery workers are active.
@celery.task
def test_task_add(x, y):
    return x + y

@celery.task
def generate_csv_task(user_id):
    """
    Triggered by the user from the dashboard. Fetches their history, 
    converts it to CSV format, and emails it as an attachment.
    """
    print(f"DEBUG: Starting CSV export job for user_id: {user_id}")
    
    with app.app_context():
        mail = Mail(app)
        current_user = User.query.get(user_id)
        
        if not current_user:
            print("ERROR: User ID not found in database during export.")
            return "Failed: User not found"

        # Get booking history sorted by newest first
        user_history = Booking.query.filter_by(user_id=user_id).order_by(Booking.check_in_time.desc()).all()

        if not user_history:
            print("DEBUG: No history found for this user. Nothing to export.")
            return "No bookings to export."

        # Create the file in memory (RAM) using StringIO instead of saving to disk
        output_buffer = io.StringIO()
        csv_writer = csv.writer(output_buffer)
        
        # Add column headers
        csv_writer.writerow([
            'Booking Ref', 'Location Name', 'Spot Number', 
            'Start Time', 'End Time', 'Billed Amount'
        ])
        
        # Populate rows
        for record in user_history:
            spot_data = ParkingSpot.query.get(record.spot_id)
            lot_data = ParkingLot.query.get(spot_data.lot_id)
            
            csv_writer.writerow([
                record.id,
                lot_data.name,
                spot_data.spot_number,
                record.check_in_time,
                record.check_out_time,
                record.total_cost
            ])
        
        # Rewind buffer to start so it can be read
        output_buffer.seek(0)
        
        # Prepare email
        email_msg = Message(
            subject="ParkPrime: Your Requested Booking History",
            recipients=[current_user.email],
            body=f"Hello {current_user.username},\n\nPlease find attached the parking history you requested from your dashboard.\n\nRegards,\nParkPrime Team"
        )
        
        # Attach the CSV file
        email_msg.attach(
            "my_parking_history.csv",
            "text/csv",
            output_buffer.getvalue()
        )
        
        mail.send(email_msg)
        print(f"DEBUG: CSV email successfully sent to {current_user.email}")
        
        return "Export task completed successfully."

@celery.task
def send_daily_reminders():
    """
    Scheduled Task: Runs every day to remind users about the service availability.
    """
    print("DEBUG: Starting daily reminder batch process...")
    
    with app.app_context():
        mail = Mail(app)
        # Get all regular users (exclude admins)
        all_users = User.query.filter_by(role='user').all()

        if not all_users:
            return "No users found to remind."

        for u in all_users:
            msg = Message(
                subject="Need a parking spot?",
                recipients=[u.email],
                body=f"Hey {u.username},\n\nDon't forget to book your spot ahead of time to avoid the rush! Check out our available lots.\n\n- ParkPrime"
            )
            mail.send(msg)
            print(f"DEBUG: Daily reminder sent to {u.email}")
            
        return f"Batch complete. Reminded {len(all_users)} users."

@celery.task
def send_monthly_reports():
    """
    Scheduled Task: Calculates total spending for the previous month and emails a summary report.
    """
    print("DEBUG: Calculating monthly statistics...")
    
    with app.app_context():
        mail = Mail(app)
        users = User.query.filter_by(role='user').all()
        
        # Calculate date range for "Last Month"
        today = datetime.date.today()
        this_month_start = today.replace(day=1)
        prev_month_start = this_month_start - relativedelta(months=1)
        prev_month_end = this_month_start - datetime.timedelta(days=1)
        
        month_name = prev_month_start.strftime('%B %Y')
        print(f"DEBUG: Processing reports for period: {month_name}")

        for user in users:
            # SQL query to find bookings in date range
            month_bookings = Booking.query.filter(
                Booking.user_id == user.id,
                Booking.check_in_time >= prev_month_start,
                Booking.check_in_time <= prev_month_end
            ).all()

            count = len(month_bookings)
            # Sum up costs, handling None values
            total_bill = sum(b.total_cost for b in month_bookings if b.total_cost)
            
            # Simple HTML template for the email
            html_content = f"""
            <h3>Monthly Activity Report: {month_name}</h3>
            <p>Dear {user.username},</p>
            <p>Here is your usage summary for last month:</p>
            <ul>
                <li><strong>Total Parkings:</strong> {count}</li>
                <li><strong>Amount Spent:</strong> ${round(total_bill, 2)}</li>
            </ul>
            <p>Thank you for using ParkPrime!</p>
            """
            
            msg = Message(
                subject=f"ParkPrime Activity Report - {month_name}",
                recipients=[user.email],
                html=html_content
            )
            
            mail.send(msg)
            
        return f"Monthly reports sent to {len(users)} users."
