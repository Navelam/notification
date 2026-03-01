#!/usr/bin/env python
"""
Create Coordinator User Script
Run this script to create a coordinator user for the exam timetable module
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from extensions import db
from model import User, Department
from datetime import datetime

def create_coordinator():
    """Create a coordinator user"""
    
    app = create_app('development')
    
    with app.app_context():
        print("\n" + "="*60)
        print("CREATE COORDINATOR USER")
        print("="*60)
        
        # Get or create department
        department = Department.query.first()
        if not department:
            print("\nNo departments found. Creating default department...")
            department = Department(
                name='Computer Science',
                code='CS'
            )
            db.session.add(department)
            db.session.commit()
            print("Created Computer Science department")
        else:
            print(f"\nUsing department: {department.name}")
        
        # Check if coordinator already exists
        existing = User.query.filter_by(username='coordinator').first()
        if existing:
            print("\nCoordinator already exists:")
            print(f"  Username: {existing.username}")
            print(f"  Name: {existing.full_name}")
            print(f"  Email: {existing.email}")
            
            choice = input("\nDo you want to create another coordinator? (y/n): ")
            if choice.lower() != 'y':
                print("\nExiting...")
                return
            
            username = input("Enter new username: ")
        else:
            username = 'coordinator'
        
        # Get coordinator details
        print("\n" + "-"*40)
        print("Enter Coordinator Details")
        print("-"*40)
        
        full_name = input("Full Name [Exam Coordinator]: ") or 'Exam Coordinator'
        email = input(f"Email [{username}@spas.edu]: ") or f"{username}@spas.edu"
        phone = input("Phone [1234567890]: ") or '1234567890'
        password = input("Password [coord123]: ") or 'coord123'
        
        # Check if username exists
        if User.query.filter_by(username=username).first():
            print(f"\nUsername '{username}' already exists!")
            return
        
        try:
            # Create coordinator user
            coordinator = User(
                username=username,
                email=email,
                full_name=full_name,
                phone=phone,
                role='coordinator',
                department_id=department.id,
                is_active=True,
                created_at=datetime.utcnow()
            )
            coordinator.set_password(password)
            
            db.session.add(coordinator)
            db.session.commit()
            
            print("\n" + "="*60)
            print("COORDINATOR CREATED SUCCESSFULLY")
            print("="*60)
            print(f"\nCoordinator Details:")
            print(f"  Username: {username}")
            print(f"  Password: {password}")
            print(f"  Name: {full_name}")
            print(f"  Email: {email}")
            print(f"  Department: {department.name}")
            print(f"  Role: Coordinator")
            
            print("\n" + "-"*40)
            print("Login URL: http://localhost:5000/coordinator/dashboard")
            print("-"*40)
            
        except Exception as e:
            db.session.rollback()
            print(f"\nError creating coordinator: {str(e)}")

def create_multiple_coordinators():
    """Create multiple coordinator users"""
    
    app = create_app('development')
    
    with app.app_context():
        print("\n" + "="*60)
        print("CREATE MULTIPLE COORDINATORS")
        print("="*60)
        
        # Get all departments
        departments = Department.query.all()
        if not departments:
            print("No departments found. Please create a department first.")
            return
        
        print(f"\nAvailable Departments:")
        for i, dept in enumerate(departments, 1):
            print(f"  {i}. {dept.name}")
        
        count_input = input("\nHow many coordinators to create? [1]: ")
        try:
            count = int(count_input) if count_input else 1
        except ValueError:
            count = 1
        
        created = []
        
        for i in range(count):
            print(f"\n--- Coordinator {i+1} ---")
            
            # Select department
            dept_choice = input(f"Select department number (1-{len(departments)}) [1]: ")
            try:
                dept_index = int(dept_choice) - 1 if dept_choice else 0
                if dept_index < 0 or dept_index >= len(departments):
                    dept_index = 0
                department = departments[dept_index]
            except ValueError:
                department = departments[0]
            
            username = input(f"Username [coord{i+1}]: ") or f"coord{i+1}"
            full_name = input(f"Full Name [Coordinator {i+1}]: ") or f"Coordinator {i+1}"
            email = input(f"Email [{username}@spas.edu]: ") or f"{username}@spas.edu"
            password = input("Password [coord123]: ") or 'coord123'
            
            # Check if username exists
            if User.query.filter_by(username=username).first():
                print(f"Username '{username}' already exists, skipping...")
                continue
            
            try:
                coordinator = User(
                    username=username,
                    email=email,
                    full_name=full_name,
                    role='coordinator',
                    department_id=department.id,
                    is_active=True,
                    created_at=datetime.utcnow()
                )
                coordinator.set_password(password)
                
                db.session.add(coordinator)
                created.append({
                    'username': username,
                    'password': password,
                    'name': full_name,
                    'department': department.name
                })
                
            except Exception as e:
                print(f"Error creating coordinator {username}: {str(e)}")
        
        if created:
            db.session.commit()
            
            print("\n" + "="*60)
            print(f"CREATED {len(created)} COORDINATORS")
            print("="*60)
            
            for i, coord in enumerate(created, 1):
                print(f"\n{i}. {coord['name']}")
                print(f"   Username: {coord['username']}")
                print(f"   Password: {coord['password']}")
                print(f"   Department: {coord['department']}")

def reset_coordinator_password():
    """Reset coordinator password"""
    
    app = create_app('development')
    
    with app.app_context():
        print("\n" + "="*60)
        print("RESET COORDINATOR PASSWORD")
        print("="*60)
        
        username = input("\nEnter coordinator username: ")
        
        coordinator = User.query.filter_by(username=username, role='coordinator').first()
        if not coordinator:
            print(f"Coordinator '{username}' not found!")
            return
        
        print(f"\nFound: {coordinator.full_name} ({coordinator.email})")
        
        new_password = input("Enter new password: ")
        confirm = input("Confirm password: ")
        
        if new_password != confirm:
            print("Passwords do not match!")
            return
        
        coordinator.set_password(new_password)
        db.session.commit()
        
        print(f"\nPassword reset successfully for {username}")

def list_coordinators():
    """List all coordinator users"""
    
    app = create_app('development')
    
    with app.app_context():
        print("\n" + "="*60)
        print("COORDINATOR USERS")
        print("="*60)
        
        coordinators = User.query.filter_by(role='coordinator').all()
        
        if not coordinators:
            print("\nNo coordinator users found.")
            return
        
        print(f"\nFound {len(coordinators)} coordinator(s):\n")
        print(f"{'#':<3} {'Username':<15} {'Name':<25} {'Department':<20} {'Status'}")
        print("-" * 80)
        
        for i, coord in enumerate(coordinators, 1):
            dept_name = coord.department.name if coord.department else 'N/A'
            status = "Active" if coord.is_active else "Inactive"
            print(f"{i:<3} {coord.username:<15} {coord.full_name:<25} {dept_name:<20} {status}")

def check_database():
    """Check database connection and tables"""
    
    app = create_app('development')
    
    with app.app_context():
        print("\n" + "="*60)
        print("DATABASE CHECK")
        print("="*60)
        
        try:
            # Test connection
            db.session.execute('SELECT 1')
            print("Database connection: OK")
            
            # Check tables
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            print(f"\nTables in database ({len(tables)}):")
            for table in sorted(tables):
                print(f"  - {table}")
            
            # Check if required tables exist
            required_tables = ['users', 'departments', 'academic_years']
            missing = [t for t in required_tables if t not in tables]
            
            if missing:
                print(f"\nMissing tables: {', '.join(missing)}")
                print("Run 'python scripts/init_db.py' to create tables")
            else:
                print("\nAll required tables exist")
            
        except Exception as e:
            print(f"Database error: {str(e)}")

if __name__ == "__main__":
    print("\nCOORDINATOR MANAGEMENT SCRIPT")
    print("1. Create single coordinator")
    print("2. Create multiple coordinators")
    print("3. Reset coordinator password")
    print("4. List all coordinators")
    print("5. Check database")
    
    choice = input("\nSelect option [1]: ") or '1'
    
    if choice == '1':
        create_coordinator()
    elif choice == '2':
        create_multiple_coordinators()
    elif choice == '3':
        reset_coordinator_password()
    elif choice == '4':
        list_coordinators()
    elif choice == '5':
        check_database()
    else:
        print("Invalid option!")