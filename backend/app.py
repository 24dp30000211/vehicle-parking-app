import csv
import io
import os
import datetime
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_mail import Mail, Message
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, JWTManager
from functools import wraps
import redis

# Custom imports for database and models
from database import db
from models import User, ParkingLot, ParkingSpot, Booking

# Setup file paths
base_dir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

# --- Application Configuration ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'parking.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["JWT_SECRET_KEY"] = "super-secret-key-change-in-prod"

# Email Configuration (Using localhost debugging server for dev)
app.config['MAIL_SERVER'] = 'localhost'
app.config['MAIL_PORT'] = 1025
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USERNAME'] = None
app.config['MAIL_PASSWORD'] = None
app.config['MAIL_DEFAULT_SENDER'] = 'no-reply@parkprime.local'

# Initialize plugins
mail = Mail(app)
jwt = JWTManager(app)
db.init_app(app)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Initialize Redis for Caching
# If Redis is not running, this might raise a ConnectionError later.
try:
    cache = redis.Redis(host='localhost', port=6379, db=0)
    # Check connection cheaply
    # cache.ping() 
except:
    cache = None

# --- Helper Decorator ---
# This custom decorator checks if the current user has 'admin' privileges
def admin_access_only():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            current_id = get_jwt_identity()
            user = User.query.get(int(current_id))
            
            if user and user.role == 'admin':
                return fn(*args, **kwargs)
            else:
                return jsonify({"message": "Access Denied: Admins Only"}), 403
        return decorator
    return wrapper

# --- Helper Function for Caching ---
def clear_cache(patterns):
    """Clears Redis cache keys matching the given patterns."""
    if not cache: return
    try:
        keys_to_delete = []
        for pattern in patterns:
            keys = cache.keys(pattern)
            keys_to_delete.extend(keys)
        
        if keys_to_delete:
            cache.delete(*keys_to_delete)
            print(f"DEBUG: Cache cleared for keys: {keys_to_delete}")
    except Exception as e:
        print(f"WARNING: Redis cache clear failed: {e}")

# ==========================================
# AUTHENTICATION ROUTES
# ==========================================

@app.route('/api/register', methods=['POST'])
def process_registration():
    data = request.get_json()
    # Extract fields
    u_name = data.get('username')
    u_email = data.get('email')
    u_pass = data.get('password')

    if not u_name or not u_email or not u_pass:
        return jsonify({'message': 'Validation Error: Missing required fields'}), 400

    # Check for duplicate users
    existing = User.query.filter_by(username=u_name).first()
    if existing:
        return jsonify({'message': 'Username taken'}), 409

    # Create new user record
    new_entry = User(username=u_name, email=u_email, role='user')
    new_entry.set_password(u_pass)
    
    db.session.add(new_entry)
    db.session.commit()
    print(f"DEBUG: New user registered: {u_name}")
    
    return jsonify({'message': 'Registration successful'}), 201

@app.route('/api/login', methods=['POST'])
def perform_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()

    if user and user.check_password(password):
        # Generate token with user ID as string identity
        token = create_access_token(identity=str(user.id))
        print(f"DEBUG: Login successful for {username}")
        
        return jsonify({
            'message': 'Login successful',
            'access_token': token,
            'role': user.role
        }), 200
    
    print(f"DEBUG: Failed login attempt for {username}")
    return jsonify({'message': 'Bad credentials'}), 401

# ==========================================
# ADMIN ROUTES (Parking Lots)
# ==========================================

@app.route('/api/admin/lots', methods=['GET'])
@jwt_required()
@admin_access_only()
def fetch_all_lots_admin():
    # Attempt to fetch from cache first
    if cache:
        cache_key = "admin_all_lots"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            print("DEBUG: Cache HIT for admin lots list")
            return jsonify(json.loads(cached_data)), 200

    print("DEBUG: Cache MISS for admin lots list. Querying DB.")
    all_lots = ParkingLot.query.all()
    output = []
    
    for lot in all_lots:
        # Calculate current availability for each lot
        free_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='available').count()
        
        output.append({
            'id': lot.id,
            'name': lot.name,
            'address': lot.address,
            'capacity': lot.capacity,
            'price_per_hour': lot.price_per_hour,
            'available_spots': free_spots
        })
    
    # Store result in cache for 60 seconds
    if cache:
        cache.setex(cache_key, 60, json.dumps(output))
    
    return jsonify(output), 200

@app.route('/api/admin/lots', methods=['POST'])
@jwt_required()
@admin_access_only()
def add_new_lot():
    data = request.get_json()
    
    # Simple validation
    if not data.get('name') or not data.get('capacity'):
        return jsonify({"message": "Name and Capacity are required"}), 400

    lot = ParkingLot(
        name=data.get('name'),
        address=data.get('address'),
        pincode=data.get('pincode'),
        capacity=int(data.get('capacity')),
        price_per_hour=float(data.get('price_per_hour'))
    )
    
    db.session.add(lot)
    db.session.commit() # Commit first to get the Lot ID
    
    # Auto-generate the individual spots based on capacity
    print(f"DEBUG: Generating {lot.capacity} spots for Lot {lot.id}")
    for i in range(1, lot.capacity + 1):
        spot = ParkingSpot(lot_id=lot.id, spot_number=i)
        db.session.add(spot)
        
    db.session.commit()
    
    # Invalidate caches because data changed
    clear_cache(["admin_all_lots", "user_available_lots", "admin_dashboard_stats"])
    
    return jsonify({"message": "Lot created successfully"}), 201

@app.route('/api/admin/lots/<int:lot_id>', methods=['PUT'])
@jwt_required()
@admin_access_only()
def modify_lot(lot_id):
    lot = ParkingLot.query.get(lot_id)
    if not lot:
        return jsonify({"message": "Lot not found"}), 404

    data = request.get_json()
    
    # Logic to handle capacity changes is complex, so we verify safety first
    if 'capacity' in data:
        new_cap = int(data.get('capacity'))
        occupied = ParkingSpot.query.filter_by(lot_id=lot_id, status='occupied').count()
        
        if new_cap < occupied:
            return jsonify({"message": "Cannot reduce capacity below occupied count"}), 409
            
        # Add or remove spots based on new capacity
        if new_cap > lot.capacity:
            for i in range(lot.capacity + 1, new_cap + 1):
                db.session.add(ParkingSpot(lot_id=lot.id, spot_number=i))
        elif new_cap < lot.capacity:
            # Find empty spots at the end and remove them
            to_remove = ParkingSpot.query.filter(
                ParkingSpot.lot_id == lot_id, 
                ParkingSpot.status == 'available'
            ).order_by(ParkingSpot.spot_number.desc()).limit(lot.capacity - new_cap).all()
            for s in to_remove:
                db.session.delete(s)
                
        lot.capacity = new_cap

    # Update basic fields
    if 'name' in data: lot.name = data['name']
    if 'price_per_hour' in data: lot.price_per_hour = data['price_per_hour']
    
    db.session.commit()
    
    # Invalidate caches
    clear_cache(["admin_all_lots", "user_available_lots", f"lot_details_{lot_id}"])
    
    return jsonify({"message": "Lot updated"}), 200

@app.route('/api/admin/lots/<int:lot_id>', methods=['DELETE'])
@jwt_required()
@admin_access_only()
def remove_lot(lot_id):
    lot = ParkingLot.query.get(lot_id)
    if not lot: return jsonify({"message": "Not found"}), 404
    
    # Safety check: Prevent deletion if spots are in use
    if ParkingSpot.query.filter_by(lot_id=lot_id, status='occupied').count() > 0:
        return jsonify({"message": "Cannot delete: Lot has active bookings"}), 409
        
    db.session.delete(lot)
    db.session.commit()
    
    # Invalidate caches
    clear_cache(["admin_all_lots", "user_available_lots", "admin_dashboard_stats"])
    
    return jsonify({"message": "Lot deleted"}), 200

@app.route('/api/admin/lots/<int:lot_id>', methods=['GET'])
@jwt_required()
@admin_access_only()
def get_lot_details(lot_id):
    # This detail view is also cacheable
    if cache:
        cache_key = f"lot_details_{lot_id}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return jsonify(json.loads(cached_data)), 200

    lot = ParkingLot.query.get(lot_id)
    if not lot:
        return jsonify({"message": "Lot not found"}), 404

    spots = ParkingSpot.query.filter_by(lot_id=lot_id).order_by(ParkingSpot.spot_number).all()

    spot_details = []
    for spot in spots:
        spot_info = {
            'spot_id': spot.id,
            'spot_number': spot.spot_number,
            'status': spot.status
        }
        
        if spot.status == 'occupied':
            active_booking = Booking.query.filter_by(
                spot_id=spot.id, 
                is_active=True
            ).first()
            
            if active_booking:
                user = User.query.get(active_booking.user_id)
                spot_info['booked_by_user'] = user.username
                spot_info['check_in_time'] = active_booking.check_in_time.isoformat()
            
        spot_details.append(spot_info)

    result = {
        'lot_id': lot.id,
        'lot_name': lot.name,
        'capacity': lot.capacity,
        'spots': spot_details
    }
    
    if cache:
        cache.setex(cache_key, 30, json.dumps(result))
    return jsonify(result), 200

# ==========================================
# USER ROUTES (Booking)
# ==========================================

@app.route('/api/lots', methods=['GET'])
@jwt_required()
def browse_available_lots():
    # Cache key for user view of lots
    if cache:
        cache_key = "user_available_lots"
        cached = cache.get(cache_key)
        if cached:
            return jsonify(json.loads(cached)), 200

    # Only return lots that have at least one 'available' spot
    # Using a JOIN query for efficiency
    active_lots = db.session.query(ParkingLot).join(ParkingSpot).filter(
        ParkingSpot.status == 'available'
    ).group_by(ParkingLot.id).all()

    response = []
    for l in active_lots:
        response.append({
            'id': l.id,
            'name': l.name,
            'address': l.address,
            'price_per_hour': l.price_per_hour
        })
    
    if cache:    
        cache.setex(cache_key, 60, json.dumps(response))
    return jsonify(response), 200

@app.route('/api/book', methods=['POST'])
@jwt_required()
def create_booking():
    """Books the first available spot in a chosen lot."""
    user_id = int(get_jwt_identity())
    req = request.get_json()
    target_lot_id = req.get('lot_id')
    
    # --- NEW: Get scheduled times from request ---
    start_str = req.get('start_time') # Expected format: ISO 8601 string
    end_str = req.get('end_time')
    
    scheduled_start = None
    scheduled_end = None
    estimated_cost = 0.0
    
    if start_str and end_str:
        try:
            # Parse the date strings
            scheduled_start = datetime.datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            scheduled_end = datetime.datetime.fromisoformat(end_str.replace('Z', '+00:00'))
            
            # Basic validation
            if scheduled_start < datetime.datetime.utcnow():
                return jsonify({"message": "Start time cannot be in the past"}), 400
            if scheduled_end <= scheduled_start:
                return jsonify({"message": "End time must be after start time"}), 400
                
        except ValueError:
            return jsonify({"message": "Invalid date format"}), 400

    # Find the first empty spot in the requested lot
    spot = ParkingSpot.query.filter_by(lot_id=target_lot_id, status='available').first()
    
    if not spot:
        print(f"DEBUG: User {user_id} tried to book full lot {target_lot_id}")
        return jsonify({"message": "Lot is full"}), 404

    # Lock the spot
    spot.status = 'occupied'
    
    # --- NEW: Calculate Estimated Cost ---
    if scheduled_start and scheduled_end:
        duration = scheduled_end - scheduled_start
        hours = duration.total_seconds() / 3600
        lot = ParkingLot.query.get(target_lot_id)
        estimated_cost = round(hours * lot.price_per_hour, 2)
    
    # Create booking record
    new_booking = Booking(
        user_id=user_id,
        spot_id=spot.id,
        check_in_time=datetime.datetime.utcnow(),
        scheduled_start_time=scheduled_start,      # --- NEW
        scheduled_end_time=scheduled_end,          # --- NEW
        is_active=True
    )
    
    db.session.add(new_booking)
    db.session.add(spot)
    db.session.commit()
    
    # Invalidate relevant caches
    clear_cache([
        "admin_all_lots", 
        "user_available_lots", 
        f"lot_details_{target_lot_id}",
        "admin_dashboard_stats",
        f"user_stats_{user_id}",
        f"user_bookings_{user_id}"
    ])
    
    print(f"DEBUG: Booking #{new_booking.id} created for User {user_id}")
    return jsonify({
        "message": "Booking confirmed", 
        "spot_number": spot.spot_number,
        "estimated_cost": estimated_cost # --- NEW
    }), 201

@app.route('/api/release/<int:booking_id>', methods=['PUT'])
@jwt_required()
def end_booking(booking_id):
    """Ends a booking and calculates the cost."""
    user_id = int(get_jwt_identity())
    
    # Verify the booking belongs to this user and is active
    booking = Booking.query.filter_by(id=booking_id, user_id=user_id, is_active=True).first()
    
    if not booking:
        return jsonify({"message": "Booking not found or already closed"}), 404

    # Calculate duration
    now = datetime.datetime.utcnow()
    duration = now - booking.check_in_time
    hours = duration.total_seconds() / 3600
    
    # Calculate final cost
    spot = ParkingSpot.query.get(booking.spot_id)
    lot = ParkingLot.query.get(spot.lot_id)
    cost = round(hours * lot.price_per_hour, 2)
    
    # Update DB records
    booking.is_active = False
    booking.check_out_time = now
    booking.total_cost = cost
    spot.status = 'available'
    
    db.session.commit()
    
    # Invalidate caches
    clear_cache([
        "admin_all_lots", 
        "user_available_lots", 
        f"lot_details_{spot.lot_id}",
        "admin_dashboard_stats",
        f"user_stats_{user_id}",
        f"user_bookings_{user_id}"
    ])

    return jsonify({
        "message": "Booking ended", 
        "cost": cost
    }), 200

@app.route('/api/bookings', methods=['GET'])
@jwt_required()
def my_bookings_history():
    """Fetches booking history for the current user."""
    user_id = int(get_jwt_identity())
    
    if cache:
        cache_key = f"user_bookings_{user_id}"
        cached = cache.get(cache_key)
        if cached:
            return jsonify(json.loads(cached)), 200

    history = Booking.query.filter_by(user_id=user_id).order_by(Booking.check_in_time.desc()).all()
    
    data = []
    for h in history:
        spot = ParkingSpot.query.get(h.spot_id)
        lot = ParkingLot.query.get(spot.lot_id)
        data.append({
            'booking_id': h.id,
            'lot_name': lot.name,
            'spot_number': spot.spot_number,
            'check_in_time': h.check_in_time.isoformat(),
            'total_cost': h.total_cost,
            'is_active': h.is_active
        })
    
    if cache:    
        cache.setex(cache_key, 30, json.dumps(data))
    return jsonify(data), 200

# ==========================================
# DASHBOARD & ANALYTICS
# ==========================================

@app.route('/api/user/summary', methods=['GET'])
@jwt_required()
def user_dashboard_stats():
    """Returns aggregated stats for the user dashboard."""
    uid = int(get_jwt_identity())
    
    if cache:
        cache_key = f"user_stats_{uid}"
        cached = cache.get(cache_key)
        if cached: return jsonify(json.loads(cached)), 200
    
    # Simple counters
    count = Booking.query.filter_by(user_id=uid).count()
    active = Booking.query.filter_by(user_id=uid, is_active=True).count()
    
    # SQLAlchemy aggregation for total spent
    spent = db.session.query(db.func.sum(Booking.total_cost)).filter(
        Booking.user_id == uid, Booking.is_active == False
    ).scalar() or 0.0

    result = {
        'total_bookings': count,
        'active_bookings': active,
        'total_spent': round(spent, 2)
    }
    
    if cache:
        cache.setex(cache_key, 60, json.dumps(result))
    return jsonify(result), 200

@app.route('/api/admin/summary', methods=['GET'])
@jwt_required()
@admin_access_only()
def admin_dashboard_stats():
    """Returns aggregated stats for the admin dashboard."""
    if cache:
        cache_key = "admin_dashboard_stats"
        cached = cache.get(cache_key)
        if cached: return jsonify(json.loads(cached)), 200

    # Global counters
    users = User.query.filter_by(role='user').count()
    lots = ParkingLot.query.count()
    
    # Spot usage counters
    occupied = ParkingSpot.query.filter_by(status='occupied').count()
    free = ParkingSpot.query.filter_by(status='available').count()
    
    revenue = db.session.query(db.func.sum(Booking.total_cost)).filter(
        Booking.is_active == False
    ).scalar() or 0.0

    result = {
        'total_users': users,
        'total_lots': lots,
        'total_spots': occupied + free,
        'spots_available': free,
        'spots_occupied': occupied,
        'total_revenue': round(revenue, 2)
    }
    
    if cache:
        cache.setex(cache_key, 120, json.dumps(result))
    return jsonify(result), 200

@app.route('/api/admin/users', methods=['GET'])
@jwt_required()
@admin_access_only()
def list_registered_users():
    """Lists all registered users for the admin."""
    users = User.query.filter_by(role='user').all()
    return jsonify([{
        'id': u.id, 
        'username': u.username, 
        'email': u.email
    } for u in users]), 200

@app.route('/api/export-csv', methods=['POST'])
@jwt_required()
def trigger_export_job():
    """Starts the background CSV export job."""
    # Import locally to avoid circular dependency with celery_worker
    from tasks import generate_csv_task
    
    uid = int(get_jwt_identity())
    print(f"DEBUG: Queueing CSV export for user {uid}")
    
    # Send task to Redis queue
    generate_csv_task.delay(uid)
    
    return jsonify({"message": "Export started. Check your email."}), 202

# Health Check Route
@app.route('/')
def health_check():
    return "ParkPrime API is running."

if __name__ == '__main__':
    app.run(debug=True)