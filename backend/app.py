import csv
import io
from flask_mail import Mail, Message
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime
from database import db
from models import User, ParkingLot, ParkingSpot, Booking
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, JWTManager
import json
import redis # <-- NEW: Import Redis

# --- App and DB Setup ---
base_dir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'parking.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- JWT Config ---
app.config["JWT_SECRET_KEY"] = "your-super-secret-key"

# --- Mail Config ---
app.config['MAIL_SERVER'] = 'localhost'
app.config['MAIL_PORT'] = 1025
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USERNAME'] = None
app.config['MAIL_PASSWORD'] = None
app.config['MAIL_DEFAULT_SENDER'] = 'parking-app@localhost'

# --- NEW: Redis Cache Config ---
try:
    cache = redis.StrictRedis(host='localhost', port=6379, db=1, decode_responses=True)
    cache.ping()
    print("Connected to Redis cache successfully!")
except Exception as e:
    print(f"Could not connect to Redis cache: {e}")
    cache = None

# --- Initialize Extensions ---
mail = Mail(app)
jwt = JWTManager(app)
db.init_app(app)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- NEW: Cache Clearing Helper ---
def clear_cache(keys):
    """Helper function to clear one or more cache keys."""
    if cache:
        for key in keys:
            cache.delete(key)
        print(f"Cache cleared for keys: {keys}")

# --- Admin Decorator ---
from functools import wraps
def admin_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            user_id = int(get_jwt_identity())
            user = User.query.get(user_id)
            if user and user.role == 'admin':
                return fn(*args, **kwargs)
            else:
                return jsonify({"message": "Admins only!"}), 403
        return decorator
    return wrapper

# --- === Authentication API === ---

@app.route('/api/register', methods=['POST'])
def register_user():
    # ... (existing code, no changes) ...
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify({'message': 'Missing required fields'}), 400

    if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
        return jsonify({'message': 'Username already exists'}), 409

    new_user = User(username=username, email=email, role='user')
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    
    # --- NEW: Clear admin's user list cache ---
    clear_cache(['/api/admin/users', '/api/admin/summary'])
    
    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/api/login', methods=['POST'])
def login_user():
    # ... (existing code, no changes) ...
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Missing username or password'}), 400

    user = User.query.filter_by(username=username).first()

    if user and user.check_password(password):
        access_token = create_access_token(identity=str(user.id))
        return jsonify({
            'message': 'Login successful',
            'access_token': access_token,
            'role': user.role
        }), 200
    
    return jsonify({'message': 'Invalid username or password'}), 401

# --- === User API === ---

@app.route('/api/lots', methods=['GET'])
@jwt_required()
def get_available_lots():
    # --- NEW: Caching Logic ---
    cache_key = '/api/lots'
    if cache:
        cached_data = cache.get(cache_key)
        if cached_data:
            print(f"Cache HIT for {cache_key}")
            return jsonify(json.loads(cached_data)), 200
    print(f"Cache MISS for {cache_key}")
    
    # ... (existing code) ...
    available_lots = db.session.query(ParkingLot).join(ParkingSpot).filter(
        ParkingSpot.status == 'available'
    ).group_by(ParkingLot.id).all()

    results = []
    for lot in available_lots:
        results.append({
            'id': lot.id,
            'name': lot.name,
            'address': lot.address,
            'pincode': lot.pincode,
            'price_per_hour': lot.price_per_hour
        })
    
    # --- NEW: Save to cache ---
    if cache:
        # Cache for 5 minutes
        cache.setex(cache_key, 300, json.dumps(results))

    return jsonify(results), 200

@app.route('/api/book', methods=['POST'])
@jwt_required()
def book_spot():
    # ... (existing code) ...
    user_id = int(get_jwt_identity())
    data = request.get_json()
    lot_id = data.get('lot_id')

    if not lot_id:
        return jsonify({"message": "Missing lot_id"}), 400

    available_spot = ParkingSpot.query.filter_by(
        lot_id=lot_id,
        status='available'
    ).first()

    if not available_spot:
        return jsonify({"message": "No available spots in this lot"}), 404

    available_spot.status = 'occupied'
    
    new_booking = Booking(
        user_id=user_id,
        spot_id=available_spot.id,
        check_in_time=datetime.datetime.utcnow(),
        is_active=True
    )

    db.session.add(new_booking)
    db.session.add(available_spot)
    db.session.commit()
    
    # --- NEW: Clear all relevant caches ---
    clear_cache([
        '/api/lots', '/api/admin/lots', '/api/admin/summary', 
        f'/api/user/summary/{user_id}', f'/api/bookings/{user_id}',
        f'/api/admin/lots/{lot_id}'
    ])

    return jsonify({
        "message": "Spot booked successfully",
        "booking_id": new_booking.id,
        "spot_number": available_spot.spot_number,
        "check_in_time": new_booking.check_in_time
    }), 201

@app.route('/api/bookings', methods=['GET'])
@jwt_required()
def get_user_bookings():
    user_id = int(get_jwt_identity())
    
    # --- NEW: Caching Logic ---
    cache_key = f'/api/bookings/{user_id}'
    if cache:
        cached_data = cache.get(cache_key)
        if cached_data:
            print(f"Cache HIT for {cache_key}")
            return jsonify(json.loads(cached_data)), 200
    print(f"Cache MISS for {cache_key}")
    
    # ... (existing code) ...
    bookings = Booking.query.filter_by(user_id=user_id).order_by(Booking.check_in_time.desc()).all()

    if not bookings:
        return jsonify([]), 200

    results = []
    for booking in bookings:
        spot = ParkingSpot.query.get(booking.spot_id)
        lot = ParkingLot.query.get(spot.lot_id)
        results.append({
            'booking_id': booking.id,
            'lot_name': lot.name,
            'spot_number': spot.spot_number,
            'check_in_time': str(booking.check_in_time),
            'check_out_time': str(booking.check_out_time) if booking.check_out_time else None,
            'is_active': booking.is_active,
            'total_cost': booking.total_cost
        })
        
    # --- NEW: Save to cache ---
    if cache:
        cache.setex(cache_key, 300, json.dumps(results))

    return jsonify(results), 200

@app.route('/api/release/<int:booking_id>', methods=['PUT'])
@jwt_required()
def release_spot(booking_id):
    # ... (existing code) ...
    user_id = int(get_jwt_identity())
    booking = Booking.query.filter_by(id=booking_id, user_id=user_id, is_active=True).first()

    if not booking:
        return jsonify({"message": "Active booking not found or you do not have permission"}), 404

    check_out_time = datetime.datetime.utcnow()
    duration = check_out_time - booking.check_in_time
    duration_in_hours = duration.total_seconds() / 3600
    spot = ParkingSpot.query.get(booking.spot_id)
    lot = ParkingLot.query.get(spot.lot_id)
    total_cost = duration_in_hours * lot.price_per_hour

    booking.is_active = False
    booking.check_out_time = check_out_time
    booking.total_cost = round(total_cost, 2)
    spot.status = 'available'

    db.session.add(booking)
    db.session.add(spot)
    db.session.commit()
    
    # --- NEW: Clear all relevant caches ---
    clear_cache([
        '/api/lots', '/api/admin/lots', '/api/admin/summary',
        f'/api/user/summary/{user_id}', f'/api/bookings/{user_id}',
        f'/api/admin/lots/{spot.lot_id}'
    ])

    return jsonify({
        "message": "Spot released successfully",
        "booking_id": booking.id,
        "total_cost": booking.total_cost,
        "duration_in_hours": round(duration_in_hours, 2)
    }), 200

@app.route('/api/export-csv', methods=['POST'])
@jwt_required()
def trigger_csv_export():
    from tasks import generate_csv_task
    user_id = int(get_jwt_identity())
    generate_csv_task.delay(user_id) 
    return jsonify({
        "message": "CSV generation has started. You will receive an email shortly."
    }), 202

@app.route('/api/user/summary', methods=['GET'])
@jwt_required()
def get_user_summary():
    user_id = int(get_jwt_identity())
    
    # --- NEW: Caching Logic ---
    cache_key = f'/api/user/summary/{user_id}'
    if cache:
        cached_data = cache.get(cache_key)
        if cached_data:
            print(f"Cache HIT for {cache_key}")
            return jsonify(json.loads(cached_data)), 200
    print(f"Cache MISS for {cache_key}")
    
    # ... (existing code) ...
    total_bookings = Booking.query.filter_by(user_id=user_id).count()
    active_bookings = Booking.query.filter_by(
        user_id=user_id, 
        is_active=True
    ).count()
    total_spent = db.session.query(
        db.func.sum(Booking.total_cost)
    ).filter(
        Booking.user_id == user_id,
        Booking.is_active == False
    ).scalar()
    
    result = {
        'total_bookings': total_bookings,
        'active_bookings': active_bookings,
        'total_spent': round(total_spent or 0, 2) 
    }
    
    # --- NEW: Save to cache ---
    if cache:
        cache.setex(cache_key, 300, json.dumps(result))

    return jsonify(result), 200

# --- === Admin API === ---

@app.route('/api/admin/lots', methods=['POST'])
@jwt_required()
@admin_required()
def create_parking_lot():
    # ... (existing code) ...
    data = request.get_json()
    name = data.get('name')
    address = data.get('address')
    pincode = data.get('pincode')
    capacity = data.get('capacity')
    price = data.get('price_per_hour')

    if not all([name, address, pincode, capacity, price]):
        return jsonify({"message": "Missing required fields"}), 400

    new_lot = ParkingLot(
        name=name,
        address=address,
        pincode=pincode,
        capacity=capacity,
        price_per_hour=price
    )
    db.session.add(new_lot)
    db.session.commit() 

    for i in range(1, capacity + 1):
        spot = ParkingSpot(
            lot_id=new_lot.id,
            spot_number=i,
            status='available'
        )
        db.session.add(spot)
    
    db.session.commit()
    
    # --- NEW: Clear relevant caches ---
    clear_cache(['/api/lots', '/api/admin/lots', '/api/admin/summary'])

    return jsonify({"message": f"Parking lot '{name}' created with {capacity} spots"}), 201

@app.route('/api/admin/lots', methods=['GET'])
@jwt_required()
@admin_required()
def get_all_lots():
    # --- NEW: Caching Logic ---
    cache_key = '/api/admin/lots'
    if cache:
        cached_data = cache.get(cache_key)
        if cached_data:
            print(f"Cache HIT for {cache_key}")
            return jsonify(json.loads(cached_data)), 200
    print(f"Cache MISS for {cache_key}")

    # ... (existing code) ...
    lots = ParkingLot.query.all()
    if not lots:
        return jsonify([]), 200

    results = []
    for lot in lots:
        available_spots = ParkingSpot.query.filter_by(
            lot_id=lot.id,
            status='available'
        ).count()
        results.append({
            'id': lot.id,
            'name': lot.name,
            'address': lot.address,
            'capacity': lot.capacity,
            'price_per_hour': lot.price_per_hour,
            'available_spots': available_spots
        })
        
    # --- NEW: Save to cache ---
    if cache:
        cache.setex(cache_key, 300, json.dumps(results))

    return jsonify(results), 200

@app.route('/api/admin/lots/<int:lot_id>', methods=['GET'])
@jwt_required()
@admin_required()
def get_lot_details(lot_id):
    # --- NEW: Caching Logic ---
    cache_key = f'/api/admin/lots/{lot_id}'
    if cache:
        cached_data = cache.get(cache_key)
        if cached_data:
            print(f"Cache HIT for {cache_key}")
            return jsonify(json.loads(cached_data)), 200
    print(f"Cache MISS for {cache_key}")

    # ... (existing code) ...
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
                spot_info['check_in_time'] = str(active_booking.check_in_time)
        spot_details.append(spot_info)

    result = {
        'lot_id': lot.id,
        'lot_name': lot.name,
        'capacity': lot.capacity,
        'spots': spot_details
    }
    
    # --- NEW: Save to cache ---
    if cache:
        cache.setex(cache_key, 300, json.dumps(result))
    
    return jsonify(result), 200

@app.route('/api/admin/lots/<int:lot_id>', methods=['DELETE'])
@jwt_required()
@admin_required()
def delete_lot(lot_id):
    # ... (existing code) ...
    lot = ParkingLot.query.get(lot_id)
    if not lot:
        return jsonify({"message": "Lot not found"}), 404

    occupied_spots = ParkingSpot.query.filter_by(
        lot_id=lot_id, 
        status='occupied'
    ).count()

    if occupied_spots > 0:
        return jsonify({
            "message": f"Cannot delete lot. {occupied_spots} spot(s) are still occupied."
        }), 409

    db.session.delete(lot)
    db.session.commit()
    
    # --- NEW: Clear relevant caches ---
    clear_cache([
        '/api/lots', '/api/admin/lots', '/api/admin/summary',
        f'/api/admin/lots/{lot_id}'
    ])

    return jsonify({"message": f"Lot '{lot.name}' and all its spots have been deleted."}), 200

@app.route('/api/admin/lots/<int:lot_id>', methods=['PUT'])
@jwt_required()
@admin_required()
def update_lot(lot_id):
    # ... (existing code) ...
    lot = ParkingLot.query.get(lot_id)
    if not lot:
        return jsonify({"message": "Lot not found"}), 404

    data = request.get_json()
    
    if 'capacity' in data:
        new_capacity = int(data.get('capacity'))
        current_capacity = lot.capacity
        if new_capacity < 0:
            return jsonify({"message": "Capacity cannot be negative"}), 400
        occupied_spots_count = ParkingSpot.query.filter_by(
            lot_id=lot_id, 
            status='occupied'
        ).count()
        if new_capacity < occupied_spots_count:
            return jsonify({
                "message": f"Cannot reduce capacity to {new_capacity}. "
                           f"{occupied_spots_count} spots are currently occupied."
            }), 409
        if new_capacity > current_capacity:
            for i in range(current_capacity + 1, new_capacity + 1):
                spot = ParkingSpot(lot_id=lot.id, spot_number=i, status='available')
                db.session.add(spot)
        elif new_capacity < current_capacity:
            spots_to_remove = ParkingSpot.query.filter(
                ParkingSpot.lot_id == lot_id,
                ParkingSpot.status == 'available'
            ).order_by(ParkingSpot.spot_number.desc()).limit(current_capacity - new_capacity).all()
            for spot in spots_to_remove:
                db.session.delete(spot)
        lot.capacity = new_capacity

    if 'name' in data:
        lot.name = data.get('name')
    if 'address' in data:
        lot.address = data.get('address')
    if 'pincode' in data:
        lot.pincode = data.get('pincode')
    if 'price_per_hour' in data:
        lot.price_per_hour = data.get('price_per_hour')

    db.session.commit()
    
    # --- NEW: Clear relevant caches ---
    clear_cache([
        '/api/lots', '/api/admin/lots', '/api/admin/summary',
        f'/api/admin/lots/{lot_id}'
    ])
    
    return jsonify({
        "message": "Lot updated successfully",
        "lot_id": lot.id,
        "new_capacity": lot.capacity
    }), 200

@app.route('/api/admin/summary', methods=['GET'])
@jwt_required()
@admin_required()
def get_admin_summary():
    # --- NEW: Caching Logic ---
    cache_key = '/api/admin/summary'
    if cache:
        cached_data = cache.get(cache_key)
        if cached_data:
            print(f"Cache HIT for {cache_key}")
            return jsonify(json.loads(cached_data)), 200
    print(f"Cache MISS for {cache_key}")
    
    # ... (existing code) ...
    total_users = User.query.filter_by(role='user').count()
    total_lots = ParkingLot.query.count()
    total_spots = ParkingSpot.query.count()
    spots_available = ParkingSpot.query.filter_by(status='available').count()
    spots_occupied = ParkingSpot.query.filter_by(status='occupied').count()
    total_revenue = db.session.query(
        db.func.sum(Booking.total_cost)
    ).filter(Booking.is_active == False).scalar()

    result = {
        'total_users': total_users,
        'total_lots': total_lots,
        'total_spots': total_spots,
        'spots_available': spots_available,
        'spots_occupied': spots_occupied,
        'total_revenue': round(total_revenue or 0, 2) 
    }
    
    # --- NEW: Save to cache ---
    if cache:
        cache.setex(cache_key, 300, json.dumps(result))

    return jsonify(result), 200

@app.route('/api/admin/users', methods=['GET'])
@jwt_required()
@admin_required()
def get_all_users():
    # --- NEW: Caching Logic ---
    cache_key = '/api/admin/users'
    if cache:
        cached_data = cache.get(cache_key)
        if cached_data:
            print(f"Cache HIT for {cache_key}")
            return jsonify(json.loads(cached_data)), 200
    print(f"Cache MISS for {cache_key}")

    # ... (existing code) ...
    users = User.query.filter_by(role='user').all()
    if not users:
        return jsonify([]), 200

    results = []
    for user in users:
        results.append({
            'id': user.id,
            'username': user.username,
            'email': user.email
        })
        
    # --- NEW: Save to cache ---
    if cache:
        cache.setex(cache_key, 300, json.dumps(results))
    
    return jsonify(results), 200

# --- Routes (for testing) ---
@app.route('/')
def home():
    return "Our API is running! We have /api/register and /api/login."

# --- Run the App ---
if __name__ == '__main__':
    app.run(debug=True)