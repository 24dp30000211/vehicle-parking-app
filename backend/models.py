from database import db
from werkzeug.security import generate_password_hash, check_password_hash
import datetime

# This file contains the schema for the SQLite database.
# I am using SQLAlchemy ORM to map Python classes to SQL tables.

class User(db.Model):
    """
    Table to store user login details and their role (Admin vs User).
    """
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=True)
    role = db.Column(db.String(50), nullable=False, default='user')
    
    # Link to the Booking table to track user history
    bookings = db.relationship('Booking', backref='user', lazy=True)    

    def set_password(self, password):
        # Hashes the password before storing it for security reasons
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        # Compares the provided password with the stored hash during login
        return check_password_hash(self.password_hash, password)

class ParkingLot(db.Model):
    """
    Represents a physical parking location with specific capacity.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    pincode = db.Column(db.String(10), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    price_per_hour = db.Column(db.Float, nullable=False)
    
    # If a lot is deleted, all its spots should be deleted too (cascade delete)
    spots = db.relationship('ParkingSpot', backref='parking_lot', lazy=True, cascade="all, delete-orphan")

class ParkingSpot(db.Model):
    """
    Individual spots inside a parking lot. 
    Status can be 'available' or 'occupied'.
    """
    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    spot_number = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='available')

class Booking(db.Model):
    """
    Records the transaction history: who parked where and when.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id'), nullable=False)
    
    # --- NEW: Scheduled Times ---
    scheduled_start_time = db.Column(db.DateTime, nullable=True)
    scheduled_end_time = db.Column(db.DateTime, nullable=True)
    
    # Actual timestamps (for billing)
    check_in_time = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    check_out_time = db.Column(db.DateTime, nullable=True)
    
    total_cost = db.Column(db.Float, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    
    spot = db.relationship('ParkingSpot')