🚗 ParkPrime - Vehicle Parking Management System

A full-stack web application for managing vehicle parking lots, bookings, and analytics. Built with a Flask (Python) backend and a Vue.js frontend, featuring role-based access control, real-time availability tracking, and automated background reporting.

🛠️ Tech Stack

Backend

Framework: Flask (Python)

Database: SQLite (with SQLAlchemy ORM)

Authentication: Flask-JWT-Extended (JSON Web Tokens)

Task Queue: Celery

Message Broker & Caching: Redis

Email: Flask-Mail

Frontend

Framework: Vue.js 3

Styling: Bootstrap 5 & Bootstrap-Vue-3

Routing: Vue Router

HTTP Client: Axios (with Interceptors)

Icons: Bootstrap Icons

✨ Features

👤 User Features

User Dashboard: View active bookings, total spending, and parking history.

Book a Spot: Browse available parking lots and book a specific spot instantly.

My Bookings: View current and past bookings.

Release Spot: Manually vacate a spot to calculate final cost and free it up for others.

Export History: Trigger an asynchronous CSV export of booking history sent via email.

🛡️ Admin Features

Admin Dashboard: View live statistics (Revenue, Occupancy, User counts) and charts.

Manage Lots: Create, Edit, and Delete parking lots.

Capacity Management: Increase or decrease lot capacity dynamically.

View Users: Monitor registered users.

Reports: Automated monthly activity reports generated and emailed via Celery Beat.

🚀 Installation & Setup

Prerequisites

Python 3.8+

Node.js & npm

Redis Server (Must be installed and running)

1. Backend Setup

Navigate to the backend folder and set up the Python environment.

cd backend
python -m venv venv
# Windows:
.\venv\Scripts\Activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt


2. Database Initialization

Initialize the SQLite database and create the admin user.

# Ensure you are in the /backend folder with venv activated
flask shell
>>> db.create_all()
>>> exit()

python create_admin.py


3. Frontend Setup

Navigate to the frontend folder and install dependencies.

cd ../frontend
npm install


🏃‍♂️ How to Run the Application

This application requires 5 separate terminals to simulate the full production environment (Server, Worker, Scheduler, Email, Client).

Terminal 1: Dummy Email Server

Catches emails sent by the app (e.g., CSV exports) and prints them to the console.

python -m aiosmtpd -n -l localhost:1025


Terminal 2: Flask Backend API

Runs the core API server at http://localhost:5000.

cd backend
.\venv\Scripts\Activate
python app.py


Terminal 3: Celery Worker

Processes background tasks (CSV generation).

cd backend
.\venv\Scripts\Activate
celery -A celery_worker.celery worker --loglevel=info -P solo


Terminal 4: Celery Beat Scheduler

Triggers scheduled tasks (Daily Reminders, Monthly Reports).

cd backend
.\venv\Scripts\Activate
celery -A celery_worker.celery beat --loglevel=info


Terminal 5: Vue.js Frontend

Runs the user interface at http://localhost:8080.

cd frontend
npm run serve


🧪 Testing the App

Open your browser and go to http://localhost:8080/.

Admin Login:
Username: admin
Password: adminpassword

User Login:
Register a new account via the UI, or use:
Username: testuser
Password: securepassword

📂 Project Structure

ParkingApp-Project/
├── backend/               # Flask API
│   ├── app.py             # Main Application Entry
│   ├── models.py          # Database Models
│   ├── tasks.py           # Celery Background Tasks
│   ├── celery_worker.py   # Celery Configuration
│   └── parking.db         # SQLite Database
│
└── frontend/              # Vue.js UI
    ├── src/
    │   ├── views/         # Page Components (Dashboard, Login, etc.)
    │   ├── router/        # Navigation Logic
    │   └── store.js       # Global State Management
    └── package.json
