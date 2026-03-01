# routes/student_routes.py
from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from model import Notification, UserNotification
from model import QuestionPaper
from extensions import db
from model import (
    User, Student, Subject, StudentPerformance, 
    AcademicYear, Department
)
from datetime import datetime
import json

student_bp = Blueprint('student', __name__, url_prefix='/student')

def student_required(f):
    """Decorator to restrict access to students only"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print(f"\n🔍 [DEBUG] student_required decorator check")
        print(f"  - User authenticated: {current_user.is_authenticated}")
        
        if not current_user.is_authenticated:
            print(f"  - User not authenticated, redirecting to login")
            flash('Please login first', 'warning')
            return redirect(url_for('auth.login'))
        
        print(f"  - User role: {current_user.role}")
        print(f"  - Expected role: student")
        
        if current_user.role != 'student':
            print(f"  - Role mismatch, redirecting to login")
            flash('Access denied. Student privileges required.', 'danger')
            return redirect(url_for('auth.login'))
        
        print(f"  - ✅ Student access granted")
        return f(*args, **kwargs)
    return decorated_function

# =====================================================
# HELPER FUNCTIONS
# =====================================================

def calculate_grade(final_marks):
    """Calculate grade based on final marks (out of 20)"""
    if final_marks >= 18:
        return 'A+'
    elif final_marks >= 15:
        return 'A'
    elif final_marks >= 12:
        return 'B'
    elif final_marks >= 10:
        return 'C'
    else:
        return 'D'

def calculate_percentage(final_marks):
    """Calculate percentage from final marks"""
    return int((final_marks / 20) * 100)

def get_student_record(user_id):
    """Get student record for current user"""
    return Student.query.filter_by(user_id=user_id).first()

def get_feedback_by_risk(risk):
    """Get feedback message based on risk status"""
    feedback = {
        'Critical': {
            'message': 'You are in Critical level. Please concentrate more on your studies. Attend classes regularly.',
            'color': 'danger',
            'bg': '#dc3545',
            'text': 'white',
            'icon': 'exclamation-triangle'
        },
        'Average': {
            'message': 'You are Average. Try harder to improve. Focus on weak subjects.',
            'color': 'warning',
            'bg': '#ffc107',
            'text': '#2c3e50',
            'icon': 'exclamation-circle'
        },
        'Safe': {
            'message': 'You are Safe. Keep studying regularly. Maintain consistency.',
            'color': 'success',
            'bg': '#28a745',
            'text': 'white',
            'icon': 'check-circle'
        },
        'Best': {
            'message': 'Excellent Performance! Keep it up and aim higher.',
            'color': 'best',
            'bg': '#6f42c1',
            'text': 'white',
            'icon': 'star'
        }
    }
    return feedback.get(risk, feedback['Safe'])

# =====================================================
# MAIN DASHBOARD ROUTE
# =====================================================

@student_bp.route('/dashboard')
@login_required
@student_required
def dashboard():
    """Student dashboard with notifications and question papers"""
    print(f"\n🔍 [DEBUG] Entered dashboard route")
    print(f"  - User: {current_user.username}")
    print(f"  - User ID: {current_user.id}")
    
    try:
        student = get_student_record(current_user.id)
        print(f"  - Student record found: {student is not None}")
        
        if not student:
            print(f"  - ❌ No student record found!")
            flash('Student record not found', 'danger')
            return redirect(url_for('auth.logout'))
        
        print(f"  - Student ID: {student.id}")
        print(f"  - Student Name: {student.name}")
        print(f"  - Department ID: {student.department_id}")
        
        # Check if department exists
        if student.department_id:
            dept = Department.query.get(student.department_id)
            print(f"  - Department: {dept.name if dept else 'Not found'}")
        
        # Get all performances for this student
        performances = StudentPerformance.query.filter_by(
            student_id=student.id
        ).all()
        print(f"  - Performances found: {len(performances)}")
        
        # Calculate overall statistics
        total_attendance = 0
        total_marks = 0
        subject_count = len(performances)
        
        risk_counts = {'Critical': 0, 'Average': 0, 'Safe': 0, 'Best': 0}
        
        for perf in performances:
            total_attendance += perf.attendance
            total_marks += perf.final_internal
            risk_counts[perf.risk_status] = risk_counts.get(perf.risk_status, 0) + 1
        
        avg_attendance = round(total_attendance / subject_count, 1) if subject_count > 0 else 0
        avg_marks = round(total_marks / subject_count, 1) if subject_count > 0 else 0
        overall_grade = calculate_grade(avg_marks)
        
        # Determine overall risk based on average
        if avg_attendance < 70 or avg_marks < 10:
            overall_risk = 'Critical'
        elif avg_marks < 12:
            overall_risk = 'Average'
        elif avg_marks >= 18 and avg_attendance >= 90:
            overall_risk = 'Best'
        else:
            overall_risk = 'Safe'
        
        # Get notifications for student
        today = datetime.now().date()
        notifications = Notification.query.filter(
            Notification.is_active == True,
            Notification.start_date <= today,
            Notification.end_date >= today,
            db.or_(
                Notification.target_role == 'all',
                Notification.target_role == 'student'
            )
        ).order_by(Notification.created_at.desc()).limit(10).all()
        
        # Get unread count using UserNotification
        unread_count = 0
        for notif in notifications:
            user_notif = UserNotification.query.filter_by(
                user_id=current_user.id,
                notification_id=notif.id
            ).first()
            if not user_notif or not user_notif.is_read:
                unread_count += 1
        
        # Get question papers for student's subjects
        current_semester = student.current_semester
        department_id = student.department_id
        
        subjects_in_semester = Subject.query.filter_by(
            department_id=department_id,
            semester_id=current_semester
        ).all()
        
        subject_ids = [s.id for s in subjects_in_semester]
        
        recent_papers = []
        if subject_ids:
            recent_papers = QuestionPaper.query.filter(
                QuestionPaper.subject_id.in_(subject_ids),
                QuestionPaper.is_active == True
            ).order_by(QuestionPaper.uploaded_at.desc()).limit(6).all()
        
        # Prepare chart data
        chart_labels = []
        chart_data = []
        chart_colors = []
        
        for perf in performances[:10]:
            subject = Subject.query.get(perf.subject_id)
            if subject:
                chart_labels.append(subject.name[:15] + ('...' if len(subject.name) > 15 else ''))
                chart_data.append(perf.final_internal)
                
                if perf.risk_status == 'Critical':
                    chart_colors.append('#dc3545')
                elif perf.risk_status == 'Average':
                    chart_colors.append('#ffc107')
                elif perf.risk_status == 'Safe':
                    chart_colors.append('#28a745')
                else:
                    chart_colors.append('#6f42c1')
        
        print(f"  - ✅ Rendering dashboard template")
        return render_template('student/dashboard.html',
                             student=student,
                             avg_attendance=avg_attendance,
                             avg_marks=avg_marks,
                             overall_grade=overall_grade,
                             overall_risk=overall_risk,
                             risk_counts=risk_counts,
                             notifications=notifications,
                             unread_count=unread_count,
                             recent_papers=recent_papers,
                             chart_labels=json.dumps(chart_labels),
                             chart_data=json.dumps(chart_data),
                             chart_colors=json.dumps(chart_colors),
                             now=datetime.now())
    
    except Exception as e:
        print(f"  - ❌ ERROR in dashboard: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Error loading dashboard: {str(e)}', 'danger')
        return redirect(url_for('student.simple_dashboard'))

# =====================================================
# PERFORMANCE DETAILS ROUTE
# =====================================================

@student_bp.route('/performance')
@login_required
@student_required
def performance():
    """Detailed performance view with subject-wise feedback"""
    try:
        student = get_student_record(current_user.id)
        
        if not student:
            flash('Student record not found', 'danger')
            return redirect(url_for('auth.logout'))
        
        # Get all performances for this student
        performances = StudentPerformance.query.filter_by(
            student_id=student.id
        ).order_by(StudentPerformance.semester).all()
        
        # Prepare performance data with subject details and feedback
        performance_data = []
        for perf in performances:
            subject = Subject.query.get(perf.subject_id)
            if subject:
                percentage = calculate_percentage(perf.final_internal)
                grade = calculate_grade(perf.final_internal)
                
                # Get feedback based on risk
                feedback = get_feedback_by_risk(perf.risk_status)
                
                # Calculate marks needed for next grade
                if perf.final_internal >= 18:
                    next_grade = "A+ (Max)"
                    marks_needed = 0
                elif perf.final_internal >= 15:
                    next_grade = "A+"
                    marks_needed = round(18 - perf.final_internal, 1)
                elif perf.final_internal >= 12:
                    next_grade = "A"
                    marks_needed = round(15 - perf.final_internal, 1)
                elif perf.final_internal >= 10:
                    next_grade = "B"
                    marks_needed = round(12 - perf.final_internal, 1)
                else:
                    next_grade = "C (Pass)"
                    marks_needed = round(10 - perf.final_internal, 1)
                
                performance_data.append({
                    'id': perf.id,
                    'subject': subject,
                    'internal1': perf.internal1,
                    'internal2': perf.internal2,
                    'seminar': perf.seminar,
                    'assessment': perf.assessment,
                    'attendance': perf.attendance,
                    'final_marks': perf.final_internal,
                    'percentage': percentage,
                    'grade': grade,
                    'risk_status': perf.risk_status,
                    'semester': perf.semester,
                    'feedback': feedback,
                    'next_grade': next_grade,
                    'marks_needed': marks_needed
                })
        
        # Group by semester
        performances_by_semester = {}
        for perf in performance_data:
            sem = perf['semester']
            if sem not in performances_by_semester:
                performances_by_semester[sem] = []
            performances_by_semester[sem].append(perf)
        
        return render_template('student/performance.html',
                             student=student,
                             performances=performance_data,
                             performances_by_semester=performances_by_semester,
                             now=datetime.now())
    
    except Exception as e:
        print(f"❌ Error in performance route: {e}")
        flash('Error loading performance data', 'danger')
        return redirect(url_for('student.dashboard'))

# =====================================================
# MY PERFORMANCE ROUTE (ALL SEMESTERS)
# =====================================================

@student_bp.route('/my-performance')
@login_required
@student_required
def my_performance():
    """Student view all semesters performance"""
    try:
        student = get_student_record(current_user.id)
        
        if not student:
            flash('Student record not found', 'danger')
            return redirect(url_for('auth.logout'))
        
        current_semester = student.current_semester
        
        # Get ALL performances
        performances = StudentPerformance.query.filter_by(
            student_id=student.id
        ).order_by(StudentPerformance.semester).all()
        
        # Group by semester
        performances_by_semester = {}
        for perf in performances:
            subject = Subject.query.get(perf.subject_id)
            if perf.semester not in performances_by_semester:
                performances_by_semester[perf.semester] = []
            
            grade = 'A+'
            if perf.final_internal >= 18:
                grade = 'A+'
            elif perf.final_internal >= 15:
                grade = 'A'
            elif perf.final_internal >= 12:
                grade = 'B'
            elif perf.final_internal >= 10:
                grade = 'C'
            else:
                grade = 'D'
            
            performances_by_semester[perf.semester].append({
                'subject': subject,
                'marks': perf.final_internal,
                'attendance': perf.attendance,
                'grade': grade,
                'risk': perf.risk_status,
                'is_current': perf.semester == current_semester
            })
        
        # Calculate semester summaries
        semester_summaries = []
        for sem in range(1, current_semester + 1):
            if sem in performances_by_semester:
                sem_marks = [p['marks'] for p in performances_by_semester[sem]]
                avg_marks = sum(sem_marks) / len(sem_marks)
                sgpa = (avg_marks / 20) * 10
                semester_summaries.append({
                    'semester': sem,
                    'avg_marks': round(avg_marks, 2),
                    'sgpa': round(sgpa, 2),
                    'subjects': len(sem_marks),
                    'is_current': sem == current_semester
                })
        
        # Calculate CGPA
        all_marks = [p.final_internal for p in performances]
        cgpa = (sum(all_marks) / len(all_marks) / 20) * 10 if all_marks else 0
        
        return render_template('student/my_performance.html',
                             student=student,
                             current_semester=current_semester,
                             performances_by_semester=performances_by_semester,
                             semester_summaries=semester_summaries,
                             cgpa=round(cgpa, 2))
    
    except Exception as e:
        print(f"❌ Error in my_performance route: {e}")
        flash('Error loading performance data', 'danger')
        return redirect(url_for('student.dashboard'))

# =====================================================
# QUESTION PAPERS ROUTES
# =====================================================

@student_bp.route('/question-papers')
@login_required
@student_required
def question_papers():
    """View all question papers for student's subjects"""
    try:
        student = get_student_record(current_user.id)
        
        if not student:
            flash('Student record not found', 'danger')
            return redirect(url_for('auth.logout'))
        
        # Get student's department and semester
        department_id = student.department_id
        current_semester = student.current_semester
        
        # Get all semesters the student has studied (1 to current)
        semesters = range(1, current_semester + 1)
        
        # Get subjects for these semesters
        subjects = Subject.query.filter(
            Subject.department_id == department_id,
            Subject.semester_id.in_(semesters)
        ).all()
        
        subject_ids = [s.id for s in subjects]
        
        # Get question papers for these subjects
        papers = QuestionPaper.query.filter(
            QuestionPaper.subject_id.in_(subject_ids),
            QuestionPaper.is_active == True
        ).order_by(QuestionPaper.uploaded_at.desc()).all()
        
        # Group by subject
        papers_by_subject = {}
        for paper in papers:
            subject = Subject.query.get(paper.subject_id)
            if subject:
                if subject.id not in papers_by_subject:
                    papers_by_subject[subject.id] = {
                        'subject': subject,
                        'papers': []
                    }
                papers_by_subject[subject.id]['papers'].append(paper)
        
        return render_template('student/question_papers.html',
                             student=student,
                             papers_by_subject=papers_by_subject,
                             subjects=subjects)
    
    except Exception as e:
        print(f"❌ Error in question_papers route: {e}")
        flash('Error loading question papers', 'danger')
        return redirect(url_for('student.dashboard'))

@student_bp.route('/download-question-paper/<int:paper_id>')
@login_required
@student_required
def download_question_paper(paper_id):
    """Download a question paper"""
    try:
        paper = QuestionPaper.query.get_or_404(paper_id)
        
        # Verify student has access to this subject
        student = get_student_record(current_user.id)
        
        if not student:
            flash('Student record not found', 'danger')
            return redirect(url_for('auth.logout'))
        
        subject = Subject.query.get(paper.subject_id)
        
        # Check if this subject belongs to student's department and semester <= current
        if (subject.department_id != student.department_id or 
            subject.semester_id > student.current_semester):
            flash('You are not authorized to download this paper', 'danger')
            return redirect(url_for('student.dashboard'))
        
        from flask import send_file
        import os
        
        if not os.path.exists(paper.file_path):
            flash('File not found', 'danger')
            return redirect(url_for('student.question_papers'))
        
        return send_file(
            paper.file_path,
            as_attachment=True,
            download_name=paper.file_name,
            mimetype='application/octet-stream'
        )
    
    except Exception as e:
        print(f"❌ Error downloading paper: {e}")
        flash('Error downloading file', 'danger')
        return redirect(url_for('student.question_papers'))

# =====================================================
# NOTIFICATIONS ROUTE
# =====================================================

@student_bp.route('/notifications')
@login_required
@student_required
def notifications():
    """View all student notifications"""
    try:
        student = get_student_record(current_user.id)
        
        if not student:
            flash('Student record not found', 'danger')
            return redirect(url_for('auth.logout'))
        
        today = datetime.now().date()
        
        # Get notifications for student
        notifications = Notification.query.filter(
            Notification.is_active == True,
            Notification.start_date <= today,
            Notification.end_date >= today,
            db.or_(
                Notification.target_role == 'all',
                Notification.target_role == 'student'
            )
        ).order_by(Notification.created_at.desc()).all()
        
        return render_template('student/notifications.html',
                             student=student,
                             notifications=notifications,
                             now=datetime.now())
    
    except Exception as e:
        print(f"❌ Error in notifications route: {e}")
        flash('Error loading notifications', 'danger')
        return redirect(url_for('student.dashboard'))

# =====================================================
# API ENDPOINTS
# =====================================================

@student_bp.route('/api/performance-summary')
@login_required
@student_required
def performance_summary():
    """API endpoint for performance summary charts"""
    try:
        student = get_student_record(current_user.id)
        
        if not student:
            return jsonify({'error': 'Student not found'}), 404
        
        # Get performances
        performances = StudentPerformance.query.filter_by(
            student_id=student.id
        ).all()
        
        # Prepare data
        subjects = []
        marks = []
        attendance = []
        colors = []
        
        for perf in performances[:10]:
            subject = Subject.query.get(perf.subject_id)
            if subject:
                subjects.append(subject.name[:15])
                marks.append(perf.final_internal)
                attendance.append(perf.attendance)
                
                if perf.risk_status == 'Critical':
                    colors.append('#dc3545')
                elif perf.risk_status == 'Average':
                    colors.append('#ffc107')
                elif perf.risk_status == 'Safe':
                    colors.append('#28a745')
                else:
                    colors.append('#6f42c1')
        
        return jsonify({
            'subjects': subjects,
            'marks': marks,
            'attendance': attendance,
            'colors': colors
        })
    
    except Exception as e:
        print(f"❌ API error: {e}")
        return jsonify({'error': str(e)}), 500

# =====================================================
# DEBUG ROUTES
# =====================================================

@student_bp.route('/test-login/<username>')
def test_student_login(username):
    """Test route to check student login without redirects"""
    from flask_login import login_user
    from model import User, Student
    
    user = User.query.filter_by(username=username).first()
    if not user:
        return f"❌ User {username} not found"
    
    if user.role != 'student':
        return f"❌ User {username} is a {user.role}, not student"
    
    student = Student.query.filter_by(user_id=user.id).first()
    if not student:
        return f"❌ No student record for {username}"
    
    # Log the user in
    login_user(user)
    
    return f"""
    <html>
    <head>
        <title>Login Test</title>
        <style>
            body {{ font-family: Arial; margin: 40px; background: #f5f5f5; }}
            .container {{ max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 10px; }}
            .success {{ color: green; }}
            .btn {{ display: inline-block; padding: 10px 20px; background: #6f42c1; color: white; text-decoration: none; border-radius: 5px; margin: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2 class="success">✅ Login Successful!</h2>
            <p><strong>User:</strong> {user.username}</p>
            <p><strong>Name:</strong> {user.full_name}</p>
            <p><strong>Role:</strong> {user.role}</p>
            <p><strong>Student ID:</strong> {student.student_id}</p>
            <p><strong>Department:</strong> {student.department.name if student.department else 'N/A'}</p>
            <p><strong>Current Semester:</strong> {student.current_semester}</p>
            <hr>
            <a href="/student/simple-dashboard" class="btn">Try Simple Dashboard</a>
            <a href="/student/dashboard" class="btn">Try Real Dashboard</a>
            <a href="/student/check-template" class="btn">Check Template</a>
            <a href="/auth/logout" class="btn" style="background: #dc3545;">Logout</a>
        </div>
    </body>
    </html>
    """

@student_bp.route('/list-routes')
def list_routes():
    """List all student routes for debugging"""
    from flask import current_app
    
    output = []
    for rule in current_app.url_map.iter_rules():
        if 'student.' in rule.endpoint:
            output.append({
                'endpoint': rule.endpoint,
                'url': str(rule),
                'methods': list(rule.methods)
            })
    
    html = "<h1>📋 Student Routes</h1><ul>"
    for route in sorted(output, key=lambda x: x['url']):
        html += f"<li><strong>{route['url']}</strong> → {route['endpoint']} ({', '.join(route['methods'])})</li>"
    html += "</ul>"
    html += "<p><a href='/student/test-login/hy_student138'>Back to Test</a></p>"
    
    return html

@student_bp.route('/simple-dashboard')
@login_required
@student_required
def simple_dashboard():
    """Simple dashboard for testing"""
    from model import Student, Department
    
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        return "❌ No student record found"
    
    dept = Department.query.get(student.department_id) if student.department_id else None
    
    return f"""
    <html>
    <head>
        <title>Simple Dashboard</title>
        <style>
            body {{ font-family: Arial; margin: 40px; background: #f5f5f5; }}
            .container {{ max-width: 800px; margin: auto; background: white; padding: 30px; border-radius: 10px; }}
            h1 {{ color: #6f42c1; }}
            .info {{ background: #f3e9ff; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .btn {{ display: inline-block; padding: 10px 20px; background: #6f42c1; color: white; text-decoration: none; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎓 Simple Student Dashboard</h1>
            <div class="info">
                <p><strong>Name:</strong> {student.name}</p>
                <p><strong>Student ID:</strong> {student.student_id}</p>
                <p><strong>Registration:</strong> {student.registration_number}</p>
                <p><strong>Department:</strong> {dept.name if dept else 'N/A'}</p>
                <p><strong>Current Semester:</strong> {student.current_semester}</p>
            </div>
            <a href="/student/test-login/{current_user.username}" class="btn">Back to Test</a>
            <a href="/auth/logout" class="btn" style="background: #dc3545;">Logout</a>
        </div>
    </body>
    </html>
    """

@student_bp.route('/real-dashboard')
@login_required
@student_required
def real_dashboard():
    """Try to render the real dashboard template"""
    from model import Student, Department
    
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        return "❌ No student record found"
    
    try:
        # Try to render the actual template with minimal data
        return render_template('student/dashboard.html', 
                             student=student,
                             avg_attendance=0,
                             avg_marks=0,
                             overall_grade='N/A',
                             overall_risk='Safe',
                             risk_counts={'Critical':0, 'Average':0, 'Safe':0, 'Best':0},
                             notifications=[],
                             unread_count=0,
                             recent_papers=[],
                             chart_labels='[]',
                             chart_data='[]',
                             chart_colors='[]',
                             now=datetime.now())
    
    except Exception as e:
        import traceback
        return f"""
        <html>
        <head>
            <title>Template Error</title>
            <style>
                body {{ font-family: Arial; margin: 40px; background: #f5f5f5; }}
                .container {{ max-width: 800px; margin: auto; background: white; padding: 30px; border-radius: 10px; }}
                pre {{ background: #f8f9fa; padding: 20px; border-radius: 5px; overflow: auto; }}
                .error {{ color: #dc3545; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1 class="error">❌ Template Error</h1>
                <pre>{str(e)}</pre>
                <h3>Traceback:</h3>
                <pre>{traceback.format_exc()}</pre>
                <a href="/student/test-login/{current_user.username}" class="btn">Back to Test</a>
            </div>
        </body>
        </html>
        """

@student_bp.route('/check-template')
@login_required
@student_required
def check_template():
    """Check if template exists and can be rendered"""
    from flask import render_template_string
    
    try:
        # First check if base template exists by trying to render a simple string
        return render_template_string("""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Template Test</title>
                <style>
                    body { font-family: Arial; margin: 40px; background: #f5f5f5; }
                    .container { max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 10px; }
                    .success { color: green; }
                    .btn { display: inline-block; padding: 10px 20px; background: #6f42c1; color: white; text-decoration: none; border-radius: 5px; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1 class="success">✅ Basic Template Test Passed!</h1>
                    <p>This proves that Flask's template rendering is working.</p>
                    <p>Now let's test with your base template...</p>
                    <a href="/student/test-base-template" class="btn">Test Base Template</a>
                    <a href="/student/test-login/{{ current_user.username }}" class="btn">Back</a>
                </div>
            </body>
            </html>
        """)
    except Exception as e:
        return f"❌ Basic template failed: {str(e)}"

@student_bp.route('/test-base-template')
@login_required
@student_required
def test_base_template():
    """Test if base_student.html exists"""
    try:
        return render_template('student/base_student.html')
    except Exception as e:
        return f"""
        <html>
        <head><title>Base Template Error</title></head>
        <body>
            <h1>❌ Base Template Error</h1>
            <p>Could not find or render student/base_student.html</p>
            <pre>{str(e)}</pre>
            <a href="/student/check-template">Back</a>
        </body>
        </html>
        """