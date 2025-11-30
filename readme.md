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

Book a Spot: Browse available parking lots and book a specific spot instantly or schedule for later.

My Bookings: View current and past bookings.

Release Spot: Manually vacate a spot to calculate final cost and free it up for others.

Export History: Trigger an asynchronous CSV export of booking history sent via email.

🛡️ Admin Features

Admin Dashboard: View live statistics (Revenue, Occupancy, User counts) and charts.

Manage Lots: Create, Edit, and Delete parking lots.

Capacity Management: Increase or decrease lot capacity dynamically.

View Users: Monitor registered users.

Reports: Automated monthly activity reports generated and emailed via Celery Beat.
--------------------------------------------------------------

🚀 Installation & Setup (One-Time)

Prerequisites: Python 3.8+, Node.js & npm, Redis Server (Must be installed and running).

1. Backend Setup

Navigate to the backend folder and set up the Python virtual environment.

cd backend
python -m venv venv
# Activate the environment (Windows):
.\venv\Scripts\Activate
# Install dependencies:
pip install -r requirements.txt
--------------------------------------------------------------

2. Database Initialization

If this is your first time running it, or if you deleted parking.db:

# Ensure you are in the /backend folder with venv activated
flask shell
>>> db.create_all()
>>> exit()
--------------------------------------------------------------
# Create the admin user
python create_admin.py


3. Frontend Setup

Navigate to the frontend folder and install dependencies.

cd ../frontend
npm install

--------------------------------------------------------------
🏃‍♂️ Run Guide (The 5 Terminals)

This application requires 5 separate terminals to simulate the full production environment.

📥 How to Download & Run (From Portal Zip)

If you have just downloaded the project zip file from the submission portal:

1. Unzip the file to a location on your computer (e.g., Desktop).

2. Open VS Code and select File > Open Folder.... Choose the unzipped folder (it should contain backend and frontend).

3. Open 5 Terminals in VS Code (Terminal -> New Terminal) and run the following commands in order:
--------------------------------------------------------------

Terminal 1: Email Server

What it does: Catches emails sent by the app (e.g., CSV exports) and prints them to the console.

python -m aiosmtpd -n -l localhost:1025
--------------------------------------------------------------

Terminal 2: Flask Backend API

What it does: Runs the core API server at http://localhost:5000.

cd backend
.\venv\Scripts\Activate
# If venv doesn't exist (fresh download), recreate it:
# python -m venv venv
# .\venv\Scripts\Activate
# pip install -r requirements.txt

python app.py

--------------------------------------------------------------

Terminal 3: Celery Worker

What it does: Processes background tasks (CSV generation).

cd backend
.\venv\Scripts\Activate
celery -A celery_worker.celery worker --loglevel=info -P solo
--------------------------------------------------------------

Terminal 4: Celery Beat Scheduler

What it does: Triggers scheduled tasks (Daily Reminders, Monthly Reports).

cd backend
.\venv\Scripts\Activate
celery -A celery_worker.celery beat --loglevel=info

--------------------------------------------------------------

Terminal 5: Vue.js Frontend

What it does: Runs the user interface at http://localhost:8080.

cd frontend
# If node_modules is missing (fresh download), install it:
# npm install

npm run serve

--------------------------------------------------------------

🧪 Testing & Login Credentials

Once all terminals are running, open your browser and go to: http://localhost:8080/

Admin Login

Username: admin

Password: adminpassword

User Login

Username: testuser

Password: securepassword

(Or register a new user via the "Register here" link)
--------------------------------------------------------------

How to Test CSV Export (Background Job)

Log in as a User.

Go to the User Dashboard.

Click the "Export History (CSV)" button.

Go to Terminal 1 (Email Server). You will see the email content printed there with the CSV attachment code.

🆘 Troubleshooting (Panic Button)

If the database gets corrupted or you want a fresh start:

Stop Terminal 2, 3, and 4 (Ctrl+C).

Go to the backend folder and delete the file parking.db.
--------------------------------------------------------------

Run these commands in Terminal 2:

flask shell
>>> db.create_all()
>>> exit()
python create_admin.py
python app.py
--------------------------------------------------------------

Restart Terminals 3 and 4.

If "venv" errors appear:
Run this command in PowerShell to allow scripts:

Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
--------------------------------------------------------------

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
