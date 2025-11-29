#creating admin.py
import os
from app import app, db
from models import User

with app.app_context():
    #configure admin user details
    admin_username = 'admin'
    admin_email = 'admin@example.com'
    admin_password = 'adminpassword'

    #check if admin user already exists
    admin = User.query.filter_by(username=admin_username).first()

    if not admin:
        print("Creating admin user...")
        #create new admin user
        admin_user = User(
            username = admin_username,
            email = admin_email,
            role = 'admin'
        )

        #setting the password securely
        admin_user.set_password(admin_password)
        
        #Add to the database session and commit
        db.session.add(admin_user)
        db.session.commit()

        print("Admin user created successfully.")
        print(f"Username: {admin_username}")
        print(f"Password: {admin_password}")
    else:
        print(f"Admin user '{admin_username}' already exists.")
        