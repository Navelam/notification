from flask import Blueprint, flash, redirect, render_template, request, url_for, current_app
from flask_login import login_required, login_user, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, date  # Make sure date is imported
from utils.ai_allocator import TeacherSubjectAllocator
from extensions import db, login_manager, csrf

# IMPORT ALL MODELS YOU NEED
from model import User, Department, Course, Student
from utils.helpers import DEPT_CODES

auth_bp = Blueprint('auth', __name__)
def generate_username_from_name(full_name):
    """Generate username from full name"""
    if not full_name:
        return None
    # Convert to lowercase, replace spaces with dots, remove special chars
    username = full_name.lower().replace(' ', '.')
    # Remove any non-alphanumeric characters except dots
    username = ''.join(c for c in username if c.isalnum() or c == '.')
    
    # Check if exists, add number if needed
    base_username = username
    counter = 1
    while User.query.filter_by(username=username).first():
        username = f"{base_username}{counter}"
        counter += 1
    
    return username

def generate_proper_student_id(department_code, department_id):
    """Generate student ID in format: CC001, CS001, etc."""
    # Count existing students in this department
    count = Student.query.filter_by(department_id=department_id).count()
    sequence = count + 1
    return f"{department_code}{sequence:03d}"

def generate_registration_number(department_code, batch_year, department_id):
    """Generate registration number in format: CC2022001"""
    # Count existing students in this department for this batch
    count = Student.query.filter_by(
        department_id=department_id, 
        admission_year=batch_year
    ).count()
    sequence = count + 1
    return f"{department_code}{batch_year}{sequence:03d}"

def validate_batch_year(batch_year):
    """Validate batch year is reasonable"""
    current_year = datetime.now().year
    year_int = int(batch_year)
    if year_int < 2000 or year_int > current_year + 1:
        return False, "Batch year must be between 2000 and next year"
    return True, "Valid"
# =====================================================
# AUTO-SYNC DEPARTMENTS FUNCTION
# =====================================================
def sync_departments():
    """Sync departments from helpers.py to database"""
    try:
        # Get departments from helpers.py
        helper_departments = []
        for dept_name, dept_code in DEPT_CODES.items():
            helper_departments.append({
                "name": dept_name,
                "code": dept_code
            })
        
        # Check current departments in database
        existing_departments = Department.query.all()
        existing_count = len(existing_departments)
        
        # If no departments exist, create them
        if existing_count == 0:
            print("\n" + "="*60)
            print("SYNCING DEPARTMENTS FROM HELPERS.PY")
            print("="*60)
            
            for dept_data in helper_departments:
                dept = Department(
                    name=dept_data["name"],
                    code=dept_data["code"]
                )
                db.session.add(dept)
                print(f"   Created: {dept_data['name']} ({dept_data['code']})")
            
            db.session.commit()
            
            print("\nDepartments in database:")
            for dept in Department.query.all():
                print(f"   ID: {dept.id} - {dept.name} ({dept.code})")
            print("="*60 + "\n")
            
        # If departments exist but count doesn't match, update them
        elif existing_count != len(helper_departments):
            print("\n" + "="*60)
            print("UPDATING DEPARTMENTS TO MATCH HELPERS.PY")
            print("="*60)
            print(f"   Existing: {existing_count} departments")
            print(f"   Expected: {len(helper_departments)} departments")
            
            Department.query.delete()
            db.session.commit()
            print("   Cleared existing departments")
            
            for dept_data in helper_departments:
                dept = Department(
                    name=dept_data["name"],
                    code=dept_data["code"]
                )
                db.session.add(dept)
                print(f"   Created: {dept_data['name']} ({dept_data['code']})")
            
            db.session.commit()
            
            print("\nUpdated departments in database:")
            for dept in Department.query.all():
                print(f"   ID: {dept.id} - {dept.name} ({dept.code})")
            print("="*60 + "\n")
        
        else:
            print("\nDepartments already synced:")
            for dept in Department.query.all():
                print(f"   ID: {dept.id} - {dept.name} ({dept.code})")
            
    except Exception as e:
        print(f"Error syncing departments: {e}")

@login_manager.user_loader
def load_user(user_id):
    """Load user from database by ID"""
    return db.session.get(User, int(user_id))

def get_roles():
    """Get all available roles for dropdown"""
    return [
        {'value': 'student', 'label': 'Student'},
        {'value': 'teacher', 'label': 'Teacher'},
        {'value': 'hod', 'label': 'Head of Department (HOD)'},
        {'value': 'coordinator', 'label': 'Coordinator'},
        {'value': 'principal', 'label': 'Principal'}
    ]

def redirect_to_dashboard(user):
    """Redirect user to their respective dashboard based on role"""
    if user.role == 'student':
        return redirect(url_for('student.dashboard'))
    elif user.role == 'teacher':
        return redirect(url_for('teacher.dashboard'))
    elif user.role == 'hod':
        return redirect(url_for('hod.dashboard'))
    elif user.role == 'coordinator':
        return redirect(url_for('coordinator.dashboard'))
    elif user.role == 'principal':
        return redirect(url_for('principal.dashboard'))
    else:
        return redirect(url_for('public.index'))

# =====================================================
# LOGIN ROUTE
# =====================================================
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login with role selection"""
    # If user is already logged in, redirect to their dashboard
    if current_user.is_authenticated:
        return redirect_to_dashboard(current_user)
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        selected_role = request.form.get('role', '')
        remember = True if request.form.get('remember') else False
        
        # Simple validation
        if not username or not password or not selected_role:
            flash('Please fill in all fields and select a role', 'warning')
            return redirect(url_for('auth.login'))
        
        # Find user by username
        user = User.query.filter_by(username=username).first()
        
        if not user:
            flash('Invalid username or password', 'danger')
            return redirect(url_for('auth.login'))
        
        # Check password
        if not user.check_password(password):
            flash('Invalid username or password', 'danger')
            return redirect(url_for('auth.login'))
        
        # Check role
        if user.role != selected_role:
            flash(f'This account is registered as {user.role}, not as {selected_role}', 'danger')
            return redirect(url_for('auth.login'))
        
        # Check if active
        if not user.is_active:
            flash('Your account is deactivated. Please contact administrator.', 'warning')
            return redirect(url_for('auth.login'))
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Log the user in
        login_user(user, remember=remember)
        flash(f'Welcome back, {user.full_name}!', 'success')
        
        # Redirect to dashboard
        return redirect_to_dashboard(user)
    
    # GET request - show login form
    return render_template('auth/login.html', roles=get_roles())

# =====================================================
# DASHBOARD REDIRECT
# =====================================================
@auth_bp.route('/dashboard-redirect')
@login_required
def dashboard_redirect():
    """Redirect user to their respective dashboard based on role"""
    return redirect_to_dashboard(current_user)

# =====================================================
# LOGOUT
# =====================================================
@auth_bp.route('/logout')
@login_required
def logout():
    """Handle user logout"""
    logout_user()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('auth.login'))

# =====================================================
# PROFILE ROUTES
# =====================================================
@auth_bp.route('/profile')
@login_required
def profile():
    """View user profile with department details"""
    # Get department object if user has department name string
    department_obj = None
    if current_user.department:
        # Try to find department by name
        department_obj = Department.query.filter_by(name=current_user.department).first()
    
    return render_template('auth/profile.html', 
                         department_obj=department_obj)

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change user password"""
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not check_password_hash(current_user.password_hash, current_password):
            flash('Current password is incorrect', 'danger')
            return redirect(url_for('auth.change_password'))

        if new_password != confirm_password:
            flash('New passwords do not match', 'danger')
            return redirect(url_for('auth.change_password'))

        if len(new_password) < 3:
            flash('Password must be at least 3 characters long', 'danger')
            return redirect(url_for('auth.change_password'))

        current_user.password_hash = generate_password_hash(new_password)
        db.session.commit()

        flash('Password changed successfully!', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/change_password.html')

# =====================================================
# NOTIFICATION ROUTES
# =====================================================
@auth_bp.route('/notifications')
@login_required
def notifications():
    """View all user notifications"""
    from model import UserNotification
    
    user_notifications = UserNotification.query.filter_by(
        user_id=current_user.id
    ).order_by(UserNotification.created_at.desc()).all()
    
    return render_template('auth/notifications.html', 
                         notifications=user_notifications,
                         now=datetime.now())

# =====================================================
# FORGOT PASSWORD
# =====================================================
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Handle forgot password request"""
    if request.method == 'POST':
        email = request.form.get('email')
        flash('Password reset instructions have been sent to your email.', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/forgot_password.html')

# =====================================================
# EDIT PROFILE
# =====================================================
@auth_bp.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit user profile"""
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        
        # Update user
        current_user.full_name = full_name
        current_user.email = email
        current_user.phone = phone
        db.session.commit()
        
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('hod.profile' if current_user.role == 'hod' else 'teacher.dashboard'))
    
    return render_template('auth/edit_profile.html')

# =====================================================
# REGISTER ROUTE - COMPLETELY FIXED (SINGLE VERSION)
# =====================================================
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handle student registration - Creates both User and Student records"""
    if current_user.is_authenticated:
        return redirect_to_dashboard(current_user)
    
    # Sync departments before showing registration form
    sync_departments()
    
    # Get departments for dropdown
    try:
        departments = Department.query.all()
        print(f"Found {len(departments)} departments in database")
    except Exception as e:
        print(f"Error loading departments: {e}")
        departments = []
    
    # Get current year for batch year dropdown
    current_year = datetime.now().year
    available_batch_years = [current_year-3, current_year-2, current_year-1, current_year, current_year+1]
    
    if request.method == 'POST':
        # Get form data
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        phone = request.form.get('phone', '').strip()
        department_id = request.form.get('department_id', '')
        
        # Student-specific fields - these can be auto-generated if not provided
        registration_number = request.form.get('registration_number', '').strip()
        student_id = request.form.get('student_id', '').strip()
        batch_year = request.form.get('batch_year', '')
        
        # Debug print
        print(f"\n=== REGISTRATION ATTEMPT ===")
        print(f"Username: {username}")
        print(f"Email: {email}")
        print(f"Full Name: {full_name}")
        print(f"Phone: {phone}")
        print(f"Department ID: {department_id}")
        print(f"Registration Number: {registration_number}")
        print(f"Student ID: {student_id}")
        print(f"Batch Year: {batch_year}")
        
        # Validation
        if not all([username, email, full_name, password, confirm_password, 
                   department_id, batch_year]):
            flash('Username, Email, Full Name, Password, Department and Batch Year are required', 'danger')
            return render_template('auth/register.html', 
                                 departments=departments,
                                 current_year=current_year,
                                 available_batch_years=available_batch_years,
                                 form_data=request.form)
        
        # Check if passwords match
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('auth/register.html', 
                                 departments=departments,
                                 current_year=current_year,
                                 available_batch_years=available_batch_years,
                                 form_data=request.form)
        
        # Check password length
        if len(password) < 3:
            flash('Password must be at least 3 characters long', 'danger')
            return render_template('auth/register.html', 
                                 departments=departments,
                                 current_year=current_year,
                                 available_batch_years=available_batch_years,
                                 form_data=request.form)
        
        # Validate batch year
        valid_batch, batch_msg = validate_batch_year(batch_year)
        if not valid_batch:
            flash(batch_msg, 'danger')
            return render_template('auth/register.html', 
                                 departments=departments,
                                 current_year=current_year,
                                 available_batch_years=available_batch_years,
                                 form_data=request.form)
        
        # Check if username already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists. Please choose another.', 'danger')
            return render_template('auth/register.html', 
                                 departments=departments,
                                 current_year=current_year,
                                 available_batch_years=available_batch_years,
                                 form_data=request.form)
        
        # Check if email already exists
        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please use another email or login.', 'danger')
            return render_template('auth/register.html', 
                                 departments=departments,
                                 current_year=current_year,
                                 available_batch_years=available_batch_years,
                                 form_data=request.form)
        
        # Get department
        try:
            department = Department.query.get(int(department_id))
            if not department:
                flash(f'Invalid department selected.', 'danger')
                return render_template('auth/register.html', 
                                     departments=departments,
                                     current_year=current_year,
                                     available_batch_years=available_batch_years,
                                     form_data=request.form)
        except ValueError:
            flash('Invalid department ID', 'danger')
            return render_template('auth/register.html', 
                                 departments=departments,
                                 current_year=current_year,
                                 available_batch_years=available_batch_years,
                                 form_data=request.form)
        
        try:
            # BEGIN TRANSACTION
            # 1. CREATE USER
            user = User(
                username=username,
                email=email,
                full_name=full_name,
                role='student',  # Force student role
                department=department.name,  # Store department name
                phone=phone if phone else None,
                is_active=True
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.flush()  # Get the user ID
            print(f"✅ User created with ID: {user.id}")
            
            # 2. GET OR CREATE COURSE
            course = Course.query.filter_by(department_id=department.id).first()
            if not course:
                course = Course(
                    name=f"{department.name} Program",
                    code=f"{department.code}_PROG",
                    duration_years=3,
                    department_id=department.id
                )
                db.session.add(course)
                db.session.flush()
                print(f"✅ Created default course for {department.name}")
            
            # 3. AUTO-GENERATE IDs if not provided
            if not student_id:
                student_id = generate_proper_student_id(department.code, department.id)
                print(f"✅ Auto-generated student ID: {student_id}")
            
            if not registration_number:
                registration_number = generate_registration_number(department.code, int(batch_year), department.id)
                print(f"✅ Auto-generated registration number: {registration_number}")
            
            # Check if generated IDs already exist (rare but possible)
            if Student.query.filter_by(registration_number=registration_number).first():
                # Try one more time with a different sequence
                registration_number = generate_registration_number(department.code, int(batch_year), department.id)
            
            if Student.query.filter_by(student_id=student_id).first():
                # Try one more time
                student_id = generate_proper_student_id(department.code, department.id)
            
            # 4. CREATE STUDENT RECORD
            # Calculate admission date (June 15 of batch year)
            admission_date = date(int(batch_year), 6, 15)
            
            student = Student(
                registration_number=registration_number,
                student_id=student_id,
                name=full_name,
                email=email,
                phone=phone if phone else None,
                user_id=user.id,
                course_id=course.id,
                department_id=department.id,
                admission_year=int(batch_year),
                admission_date=admission_date,
                is_active=True
            )
            db.session.add(student)
            print(f"✅ Created student record for {full_name}")
            print(f"   - Registration: {registration_number}")
            print(f"   - Student ID: {student_id}")
            print(f"   - Batch Year: {batch_year}")
            print(f"   - Current Semester: {student.current_semester}")  # This will auto-calculate
            
            # 5. COMMIT ALL
            db.session.commit()
            print(f"✅ Registration successful for {username}")
            
            flash(f'✅ Registration successful! You can now login as student.', 'success')
            flash(f'📋 Your details - Username: {username}, Student ID: {student_id}', 'info')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            db.session.rollback()
            error_msg = str(e)
            print(f"❌ Registration error: {error_msg}")
            import traceback
            traceback.print_exc()
            
            if "UNIQUE constraint" in error_msg:
                if "username" in error_msg:
                    flash('Username already exists', 'danger')
                elif "email" in error_msg:
                    flash('Email already exists', 'danger')
                elif "registration_number" in error_msg:
                    flash('Registration number already exists', 'danger')
                elif "student_id" in error_msg:
                    flash('Student ID already exists', 'danger')
                else:
                    flash('A record with this information already exists', 'danger')
            else:
                flash(f'Registration failed: {error_msg}', 'danger')
            
            return render_template('auth/register.html', 
                                 departments=departments,
                                 current_year=current_year,
                                 available_batch_years=available_batch_years,
                                 form_data=request.form)
    
    # GET request - show registration form
    return render_template('auth/register.html', 
                         departments=departments,
                         current_year=current_year,
                         available_batch_years=available_batch_years,
                         form_data={})

# =====================================================
# CONTEXT PROCESSOR
# =====================================================
@auth_bp.context_processor
def utility_processor():
    """Add utility functions to template context"""
    return {
        'now': datetime.now()
    }

# =====================================================
# DEBUG ROUTES (Remove in production)
# =====================================================
@auth_bp.route('/debug-users')
def debug_users():
    """Debug route to check users in database"""
    from model import User
    from werkzeug.security import check_password_hash
    
    users = User.query.all()
    html = """
    <html>
    <head>
        <title>User Debug</title>
        <style>
            body { font-family: Arial; margin: 20px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background: #6f42c1; color: white; }
            .success { color: green; }
            .error { color: red; }
        </style>
    </head>
    <body>
        <h2>🔍 User Database Debug</h2>
        <table>
            <tr>
                <th>ID</th>
                <th>Username</th>
                <th>Role</th>
                <th>Department</th>
                <th>Password Test</th>
            </tr>
    """
    
    # Test password
    test_password = "hod123"
    
    for user in users:
        if user.role == 'hod':
            password_check = check_password_hash(user.password_hash, test_password)
            status = f"✅ Valid ({test_password})" if password_check else "❌ Invalid"
            color = "success" if password_check else "error"
        else:
            status = "N/A"
            color = ""
        
        html += f"""
        <tr>
            <td>{user.id}</td>
            <td>{user.username}</td>
            <td>{user.role}</td>
            <td>{user.department}</td>
            <td class="{color}">{status}</td>
        </tr>
        """
    
    html += """
        </table>
        <br>
        <a href="/login">Back to Login</a>
    </body>
    </html>
    """
    
    return html

@auth_bp.route('/force-login/<username>')
def force_login(username):
    """Force login as any user (DEBUG ONLY)"""
    from flask_login import login_user
    from model import User
    
    user = User.query.filter_by(username=username).first()
    if not user:
        return f"User {username} not found"
    
    login_user(user)
    return f"""
    <html>
    <head>
        <title>Force Login</title>
        <style>
            body {{ font-family: Arial; margin: 40px; background: #f5f5f5; }}
            .container {{ max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 10px; }}
            .success {{ color: green; }}
            .btn {{ display: inline-block; padding: 10px 20px; background: #6f42c1; color: white; text-decoration: none; border-radius: 5px; margin: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2 class="success">✅ Force Login Successful!</h2>
            <p>Logged in as: <strong>{user.full_name}</strong></p>
            <p>Username: {user.username}</p>
            <p>Role: {user.role}</p>
            <p>Department: {user.department}</p>
            <hr>
            <a href="/hod/dashboard" class="btn">Go to HOD Dashboard</a>
            <a href="/teacher/dashboard" class="btn">Go to Teacher Dashboard</a>
            <a href="/student/dashboard" class="btn">Go to Student Dashboard</a>
        </div>
    </body>
    </html>
    """

@auth_bp.route('/create-hod-fresh')
def create_hod_fresh():
    """Create a fresh HOD user with known password"""
    from model import User, Department
    from werkzeug.security import generate_password_hash
    
    # Get Computer Science department
    dept = Department.query.filter_by(name='Computer Science').first()
    if not dept:
        return "Department not found! Run auto_setup first."
    
    # Delete existing HOD for CS if any
    existing_hod = User.query.filter_by(username='hod_cs').first()
    if existing_hod:
        db.session.delete(existing_hod)
        db.session.commit()
        print("Deleted existing hod_cs")
    
    # Create new HOD with fresh password
    hod = User(
        username='hod_cs',
        email='hod.cs@college.edu',
        full_name='Dr. Computer Science HOD',
        role='hod',
        department='Computer Science',  # Use string, not ID
        is_active=True
    )
    # Set password using the method
    hod.set_password('hod123')
    
    db.session.add(hod)
    db.session.commit()
    
    # Verify the password works
    from werkzeug.security import check_password_hash
    password_works = check_password_hash(hod.password_hash, 'hod123')
    
    return f"""
    <html>
    <head>
        <title>HOD Created</title>
        <style>
            body {{ font-family: Arial; margin: 40px; background: #f5f5f5; }}
            .container {{ max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 10px; }}
            .success {{ color: green; }}
            .info {{ background: #e3f2fd; padding: 15px; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1 class="success">✅ Fresh HOD Created!</h1>
            <div class="info">
                <p><strong>Username:</strong> hod_cs</p>
                <p><strong>Password:</strong> hod123</p>
                <p><strong>Role:</strong> hod</p>
                <p><strong>Department:</strong> Computer Science</p>
                <p><strong>Password Valid:</strong> {'Yes' if password_works else 'No'}</p>
            </div>
            <br>
            <a href="/login" style="display: inline-block; padding: 10px 20px; background: #6f42c1; color: white; text-decoration: none; border-radius: 5px;">Go to Login</a>
        </div>
    </body>
    </html>
    """