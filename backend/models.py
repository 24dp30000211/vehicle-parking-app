#models.py
from database import db # Importing the database instance
from werkzeug.security import generate_password_hash, check_password_hash
import datetime

#User Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80),unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=True) # <-- FIX 1
    role = db.Column(db.String(50), nullable=False, default='user')
    bookings = db.relationship('Booking', backref='user', lazy=True)    

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password) # <-- FIX 2

class ParkingLot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    pincode = db.Column(db.String(10), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    price_per_hour = db.Column(db.Float, nullable=False)
    spots = db.relationship('ParkingSpot', backref='parking_lot', lazy=True, cascade="all, delete-orphan")

class ParkingSpot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    spot_number = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='available') # 'available' or 'occupied'

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id'), nullable=False)
    check_in_time = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    check_out_time = db.Column(db.DateTime, nullable=True)
    
    # --- THIS IS THE NEW LINE ---
    total_cost = db.Column(db.Float, nullable=True) # Add this
    
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    spot = db.relationship('ParkingSpot')

