# routes/hod_routes.py
from flask import Blueprint, render_template, flash, redirect, url_for, jsonify, request
from flask_login import login_required, current_user
from functools import wraps
from extensions import db
from model import User, Department, Subject, TeacherSubject, Student, StudentPerformance, Course, AcademicYear, Notification, UserNotification
from datetime import datetime
import random
from utils.ai_allocator import TeacherSubjectAllocator

hod_bp = Blueprint('hod', __name__, url_prefix='/hod')

def hod_required(f):
    """Decorator to restrict access to HOD only"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'hod':
            flash('Access denied. HOD privileges required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@hod_bp.context_processor
def utility_processor():
    """Add utility functions to template context"""
    return {
        'now': datetime.now()
    }

# =====================================================
# DASHBOARD
# =====================================================

@hod_bp.route('/dashboard')
@login_required
@hod_required
def dashboard():
    """HOD Dashboard"""
    # Get HOD's department
    department = Department.query.filter_by(name=current_user.department).first()
    
    if not department:
        flash('Department not found', 'danger')
        return redirect(url_for('hod.profile'))
    
    # Get department statistics
    total_teachers = User.query.filter_by(role='teacher', department=department.name).count()
    total_students = Student.query.filter_by(department_id=department.id).count()
    total_subjects = Subject.query.filter_by(department_id=department.id).count()
    
    # Get teacher assignments
    teacher_assignments = db.session.query(
        TeacherSubject, User, Subject
    ).join(
        User, TeacherSubject.teacher_id == User.id
    ).join(
        Subject, TeacherSubject.subject_id == Subject.id
    ).filter(
        User.department == department.name,
        TeacherSubject.is_active == True
    ).limit(10).all()
    
    # Get recent student performances
    recent_performances = db.session.query(
        StudentPerformance, Student, Subject
    ).join(
        Student, StudentPerformance.student_id == Student.id
    ).join(
        Subject, StudentPerformance.subject_id == Subject.id
    ).filter(
        Student.department_id == department.id
    ).order_by(
        StudentPerformance.created_at.desc()
    ).limit(10).all()
    
    # Get notifications for HOD
    today = datetime.now().date()
    notifications = Notification.query.filter(
        Notification.is_active == True,
        Notification.start_date <= today,
        Notification.end_date >= today,
        db.or_(
            Notification.target_role == 'all',
            Notification.target_role == 'hod'  
        )
    ).order_by(Notification.created_at.desc()).limit(10).all()
    
    return render_template('hod/dashboard.html',
                         department=department,
                         total_teachers=total_teachers,
                         total_students=total_students,
                         total_subjects=total_subjects,
                         teacher_assignments=teacher_assignments,
                         recent_performances=recent_performances,
                         notifications=notifications)

# =====================================================
# ASSIGN TEACHERS
# =====================================================

@hod_bp.route('/assign-teachers', methods=['GET', 'POST'])
@login_required
@hod_required
def assign_teachers():
    """Assign teachers to subjects"""
    department = Department.query.filter_by(name=current_user.department).first()
    
    if not department:
        flash('Department not found', 'danger')
        return redirect(url_for('hod.dashboard'))
    
    # Handle POST request for manual assignment
    if request.method == 'POST':
        teacher_id = request.form.get('teacher_id')
        subject_id = request.form.get('subject_id')
        semester_id = request.form.get('semester_id')
        academic_year = request.form.get('academic_year')
        
        # Get academic year object
        academic_year_obj = AcademicYear.query.filter_by(year=academic_year).first()
        
        if not academic_year_obj:
            flash('Academic year not found', 'danger')
            return redirect(url_for('hod.assign_teachers'))
        
        # Check if assignment already exists
        existing = TeacherSubject.query.filter(
            TeacherSubject.teacher_id == teacher_id,
            TeacherSubject.subject_id == subject_id,
            TeacherSubject.academic_year_id == academic_year_obj.id,
            TeacherSubject.is_active == True
        ).first()
        
        if existing:
            flash('This teacher is already assigned to this subject', 'warning')
        else:
            assignment = TeacherSubject(
                teacher_id=teacher_id,
                subject_id=subject_id,
                academic_year_id=academic_year_obj.id,
                semester_id=semester_id,
                is_active=True
            )
            db.session.add(assignment)
            db.session.commit()
            flash('Teacher assigned successfully!', 'success')
        
        return redirect(url_for('hod.assign_teachers'))
    
    # GET request - display the form
    # Get data for dropdowns
    teachers = User.query.filter_by(role='teacher', department=department.name).all()
    subjects = Subject.query.filter_by(department_id=department.id).all()
    
    # Get unique semesters from subjects
    semesters = db.session.query(Subject.semester_id).distinct().filter_by(
        department_id=department.id
    ).order_by(Subject.semester_id).all()
    semesters = [s[0] for s in semesters]
    
    # Get current assignments
    assignments = db.session.query(
        TeacherSubject, User, Subject
    ).join(
        User, TeacherSubject.teacher_id == User.id
    ).join(
        Subject, TeacherSubject.subject_id == Subject.id
    ).filter(
        User.department == department.name,
        TeacherSubject.is_active == True
    ).all()
    
    return render_template('hod/assign_teachers.html',
                         department=department,
                         teachers=teachers,
                         subjects=subjects,
                         semesters=semesters,
                         assignments=assignments,
                         now=datetime.now())

# =====================================================
# REMOVE ASSIGNMENT
# =====================================================

@hod_bp.route('/remove-assignment/<int:assignment_id>')
@login_required
@hod_required
def remove_assignment(assignment_id):
    """Remove teacher assignment"""
    assignment = TeacherSubject.query.get_or_404(assignment_id)
    assignment.is_active = False
    db.session.commit()
    flash('Assignment removed successfully!', 'success')
    return redirect(url_for('hod.assign_teachers'))

# =====================================================
# AI ASSIGN TEACHERS
# =====================================================

@hod_bp.route('/ai-assign-teachers', methods=['POST'])
@login_required
@hod_required
def ai_assign_teachers():
    """AI-based automatic teacher assignment"""
    department = Department.query.filter_by(name=current_user.department).first()
    
    if not department:
        flash('Department not found', 'danger')
        return redirect(url_for('hod.dashboard'))
    
    try:
        # Initialize AI allocator
        allocator = TeacherSubjectAllocator(
            department_id=department.id,
            academic_year="2025-2026"
        )
        
        # Run AI assignment
        result = allocator.assign_teachers_fast()
        
        if result['success']:
            # Save assignments to database
            if result['assignments']:
                added_count = 0
                for assignment in result['assignments']:
                    # Check if already exists to avoid duplicates
                    existing = TeacherSubject.query.filter_by(
                        teacher_id=assignment.teacher_id,
                        subject_id=assignment.subject_id,
                        academic_year_id=assignment.academic_year_id,
                        is_active=True
                    ).first()
                    
                    if not existing:
                        db.session.add(assignment)
                        added_count += 1
                
                # Commit all changes
                db.session.commit()
                
                message = f"✅ AI Assignment Complete!\n"
                message += f"   • Created {added_count} new assignments\n"
                message += f"   • Total subjects assigned: {result.get('total_assigned', 0)}\n"
                
                # Add teacher distribution
                if 'teacher_distribution' in result:
                    message += f"\n   📊 Teacher Workload:\n"
                    for teacher, count in result['teacher_distribution'].items():
                        message += f"      - {teacher}: {count}/5 subjects\n"
                
                if result.get('failed_subjects'):
                    message += f"\n   ⚠️ Failed to assign: {len(result['failed_subjects'])} subjects"
                
                flash(message, 'success')
            else:
                flash('No new assignments were created', 'warning')
        else:
            flash(f"❌ {result['message']}", 'danger')
            
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error in AI assignment: {str(e)}', 'danger')
        print(f"AI Assignment Error: {str(e)}")
        
    return redirect(url_for('hod.assign_teachers'))

# =====================================================
# ULTRA FAST ASSIGN
# =====================================================

@hod_bp.route('/ultra-fast-assign', methods=['POST'])
@login_required
@hod_required
def ultra_fast_assign():
    """Ultra fast AI assignment"""
    department = Department.query.filter_by(name=current_user.department).first()
    
    if not department:
        flash('Department not found', 'danger')
        return redirect(url_for('hod.dashboard'))
    
    try:
        from utils.ultra_fast_allocator import UltraFastAllocator
        allocator = UltraFastAllocator(department_id=department.id)
        result = allocator.assign_now()
        
        if result['success']:
            flash(f'✓ Assigned {result["assigned"]} subjects instantly!', 'success')
        else:
            flash(f'Error: {result["message"]}', 'danger')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('hod.assign_teachers'))

# =====================================================
# RESET ASSIGNMENTS
# =====================================================

@hod_bp.route('/reset-assignments', methods=['POST'])
@login_required
@hod_required
def reset_assignments():
    """Reset all teacher assignments"""
    department = Department.query.filter_by(name=current_user.department).first()
    
    if not department:
        flash('Department not found', 'danger')
        return redirect(url_for('hod.dashboard'))
    
    try:
        # Get current academic year
        academic_year = AcademicYear.query.filter_by(is_current=True).first()
        if not academic_year:
            flash('No current academic year found', 'danger')
            return redirect(url_for('hod.assign_teachers'))
        
        # Soft delete - set is_active to False
        result = TeacherSubject.query.filter_by(
            academic_year_id=academic_year.id,
            is_active=True
        ).update({'is_active': False}, synchronize_session=False)
        
        db.session.commit()
        
        flash(f'✅ Reset {result} teacher assignments successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error resetting assignments: {str(e)}', 'danger')
        
    return redirect(url_for('hod.assign_teachers'))

# =====================================================
# ASSIGNMENT STATS API
# =====================================================

@hod_bp.route('/assignment-stats')
@login_required
@hod_required
def assignment_stats():
    """Get assignment statistics as JSON"""
    department = Department.query.filter_by(name=current_user.department).first()
    
    if not department:
        return jsonify({'error': 'Department not found'}), 404
    
    allocator = TeacherSubjectAllocator(department_id=department.id)
    stats = allocator.get_assignment_stats_fast()
    
    return jsonify(stats)

# =====================================================
# TEACHER DETAILS
# =====================================================

@hod_bp.route('/teacher-details')
@login_required
@hod_required
def teacher_details():
    """View all teachers in department"""
    department = Department.query.filter_by(name=current_user.department).first()
    
    if not department:
        flash('Department not found', 'danger')
        return redirect(url_for('hod.dashboard'))
    
    teachers = User.query.filter_by(role='teacher', department=department.name).all()
    
    # Get subject counts and names for each teacher
    teacher_data = []
    for teacher in teachers:
        # Get all active assignments for this teacher
        assignments = TeacherSubject.query.filter(
            TeacherSubject.teacher_id == teacher.id,
            TeacherSubject.is_active == True
        ).all()
        
        # Get subject names
        subject_names = []
        for assignment in assignments:
            subject = Subject.query.get(assignment.subject_id)
            if subject:
                subject_names.append(subject.name)
        
        teacher_data.append({
            'teacher': teacher,
            'subject_count': len(assignments),
            'subject_names': subject_names,
            'db_user': teacher
        })
    
    return render_template('hod/teacher_details.html',
                         department=department,
                         teacher_data=teacher_data)

# =====================================================
# TEACHER PROFILE
# =====================================================

@hod_bp.route('/teacher-profile/<int:teacher_id>')
@login_required
@hod_required
def teacher_profile(teacher_id):
    """View individual teacher profile"""
    teacher = User.query.get_or_404(teacher_id)
    
    # Check if teacher belongs to HOD's department
    if teacher.department != current_user.department:
        flash('Access denied', 'danger')
        return redirect(url_for('hod.teacher_details'))
    
    department = Department.query.filter_by(name=teacher.department).first()
    
    # Get teacher's subjects
    subjects = db.session.query(
        TeacherSubject, Subject
    ).join(
        Subject, TeacherSubject.subject_id == Subject.id
    ).filter(
        TeacherSubject.teacher_id == teacher.id,
        TeacherSubject.is_active == True
    ).all()
    
    return render_template('hod/teacher_profile.html',
                         teacher=teacher,
                         department=department,
                         subjects=subjects)

# =====================================================
# PERFORMANCE ANALYSIS - UPDATED WITH STUDENT COUNTS
# =====================================================
# =====================================================
# PERFORMANCE ANALYSIS - COMPLETELY FIXED
# =====================================================

@hod_bp.route('/performance-analysis')
@login_required
@hod_required
def performance_analysis():
    """Subject-wise performance analysis with student counts"""
    department = Department.query.filter_by(name=current_user.department).first()
    
    if not department:
        flash('Department not found', 'danger')
        return redirect(url_for('hod.dashboard'))
    
    # Get ALL subjects in department
    subjects = Subject.query.filter_by(department_id=department.id).order_by(Subject.semester_id, Subject.name).all()
    
    # Get all students in department for total counts
    all_students = Student.query.filter_by(department_id=department.id).all()
    
    # Group students by semester
    students_by_semester = {}
    for student in all_students:
        sem = student.current_semester
        if sem not in students_by_semester:
            students_by_semester[sem] = []
        students_by_semester[sem].append(student)
    
    # Calculate subject-wise analysis
    subject_analysis = []
    total_subjects_with_data = 0
    total_performance_records = 0
    total_risk_count = 0  # Add this for the summary card
    
    for subject in subjects:
        # Get all performances for this subject
        performances = StudentPerformance.query.filter_by(subject_id=subject.id).all()
        
        if performances:
            # Calculate averages
            avg_marks = sum(p.final_internal for p in performances) / len(performances)
            avg_attendance = sum(p.attendance for p in performances) / len(performances)
            
            # Count unique students with data
            students_with_data = len(set(p.student_id for p in performances))
            
            # Count risk levels
            risk_counts = {
                'Critical': sum(1 for p in performances if p.risk_status == 'Critical'),
                'High Risk': sum(1 for p in performances if p.risk_status == 'High Risk'),
                'Average': sum(1 for p in performances if p.risk_status == 'Average'),
                'Safe': sum(1 for p in performances if p.risk_status == 'Safe'),
                'Best': sum(1 for p in performances if p.risk_status == 'Best')
            }
            
            # Calculate total risk count (Critical + High Risk)
            risk_count = risk_counts['Critical'] + risk_counts['High Risk']
            total_risk_count += risk_count
            
            total_subjects_with_data += 1
            total_performance_records += len(performances)
        else:
            avg_marks = 0
            avg_attendance = 0
            students_with_data = 0
            risk_counts = {'Critical': 0, 'High Risk': 0, 'Average': 0, 'Safe': 0, 'Best': 0}
            risk_count = 0
        
        # Get total students in this semester
        total_students_in_semester = len(students_by_semester.get(subject.semester_id, []))
        
        # Calculate data coverage percentage
        if total_students_in_semester > 0:
            data_coverage = (students_with_data / total_students_in_semester) * 100
        else:
            data_coverage = 0
        
        subject_analysis.append({
            'subject': subject,
            'avg_marks': round(avg_marks, 2),
            'avg_attendance': round(avg_attendance, 2),
            'students_with_data': students_with_data,
            'total_students': total_students_in_semester,
            'data_coverage': round(data_coverage, 1),
            'risk_counts': risk_counts,
            'risk_count': risk_count,  # Add this for the template
            'performance_percent': round((avg_marks / 20 * 100) if avg_marks > 0 else 0, 1)
        })
    
    # Calculate overall statistics
    total_students = len(all_students)
    total_subjects = len(subjects)
    
    print(f"\n{'='*60}")
    print(f"PERFORMANCE ANALYSIS SUMMARY:")
    print(f"Total subjects: {total_subjects}")
    print(f"Subjects with data: {total_subjects_with_data}")
    print(f"Total students: {total_students}")
    print(f"Total performance records: {total_performance_records}")
    print(f"Total at risk students: {total_risk_count}")
    print(f"{'='*60}")
    
    return render_template('hod/performance_analysis.html',
                         department=department,
                         subject_analysis=subject_analysis,
                         total_students=total_students,
                         total_subjects=total_subjects,
                         subjects_with_data=total_subjects_with_data,
                         total_risk_count=total_risk_count)  # Pass this to template

# =====================================================
# RISK LEVELS
# =====================================================

@hod_bp.route('/risk-levels')
@login_required
@hod_required
def risk_levels():
    """View students by risk level"""
    department = Department.query.filter_by(name=current_user.department).first()
    
    if not department:
        flash('Department not found', 'danger')
        return redirect(url_for('hod.dashboard'))
    
    # Get filter parameters
    selected_semester = request.args.get('semester', 'all')
    selected_subject = request.args.get('subject', 'all')
    
    # Get all students in department
    students_query = Student.query.filter_by(department_id=department.id)
    
    # Apply semester filter
    if selected_semester != 'all':
        all_students = students_query.all()
        filtered_students = []
        for student in all_students:
            if student.current_semester == int(selected_semester):
                filtered_students.append(student)
        students = filtered_students
    else:
        students = students_query.all()
    
    total_students = len(students)
    
    # Initialize all categories
    critical = []
    high_risk = []
    average = []
    safe = []
    best = []
    
    # Initialize counters
    total_critical = 0
    total_high_risk = 0
    total_average = 0
    total_safe = 0
    total_best = 0
    
    # Semester-wise data
    semester_data = {}
    for sem in range(1, 9):
        semester_data[sem] = {
            'total': 0,
            'critical': 0,
            'high_risk': 0,
            'average': 0,
            'safe': 0,
            'best': 0,
            'avg_marks': 0,
            'avg_attendance': 0,
            'marks_total': 0,
            'attendance_total': 0
        }
    
    # Subject-wise risk data
    all_subjects = Subject.query.filter_by(department_id=department.id).order_by(Subject.semester_id, Subject.name).all()
    subject_risk_data = {}
    
    for subject in all_subjects:
        subject_risk_data[subject.id] = {
            'total': 0,
            'critical': 0,
            'high_risk': 0,
            'average': 0,
            'safe': 0,
            'best': 0,
            'avg_marks': 0,
            'avg_attendance': 0,
            'marks_total': 0,
            'attendance_total': 0
        }
    
    for student in students:
        # Get performances
        performances_query = StudentPerformance.query.filter_by(student_id=student.id)
        
        if selected_subject != 'all':
            performances_query = performances_query.filter_by(subject_id=int(selected_subject))
        
        performances = performances_query.all()
        
        if performances:
            # Get the most recent performance
            latest = performances[-1]
            subject = Subject.query.get(latest.subject_id)
            
            if not subject or subject.department_id != department.id:
                continue
            
            # Get data
            marks = latest.final_internal
            attendance = latest.attendance
            
            # Calculate grade
            if marks >= 18:
                grade = 'A+'
            elif marks >= 15:
                grade = 'A'
            elif marks >= 12:
                grade = 'B'
            elif marks >= 10:
                grade = 'C'
            else:
                grade = 'D'
            
            student_data = {
                'student': student,
                'subject': subject.name if subject else 'Unknown',
                'subject_id': subject.id if subject else None,
                'marks': marks,
                'attendance': attendance,
                'grade': grade,
                'semester': student.current_semester
            }
            
            # Categorize based on risk_status
            risk_status = latest.risk_status
            
            # Update counters
            if risk_status == 'Critical':
                critical.append(student_data)
                total_critical += 1
            elif risk_status == 'High Risk':
                high_risk.append(student_data)
                total_high_risk += 1
            elif risk_status == 'Average':
                average.append(student_data)
                total_average += 1
            elif risk_status == 'Best':
                best.append(student_data)
                total_best += 1
            else:  # Safe
                safe.append(student_data)
                total_safe += 1
            
            # Update semester data
            sem = student.current_semester
            if sem in semester_data:
                semester_data[sem]['total'] += 1
                semester_data[sem][risk_status.lower().replace(' ', '_')] += 1
                semester_data[sem]['marks_total'] += marks
                semester_data[sem]['attendance_total'] += attendance
            
            # Update subject data
            if subject and subject.id in subject_risk_data:
                subject_risk_data[subject.id]['total'] += 1
                subject_risk_data[subject.id][risk_status.lower().replace(' ', '_')] += 1
                subject_risk_data[subject.id]['marks_total'] += marks
                subject_risk_data[subject.id]['attendance_total'] += attendance
    
    # Calculate averages for semester data
    for sem, data in semester_data.items():
        if data['total'] > 0:
            data['avg_marks'] = data['marks_total'] / data['total']
            data['avg_attendance'] = data['attendance_total'] / data['total']
    
    # Calculate averages for subject data
    for subject_id, data in subject_risk_data.items():
        if data['total'] > 0:
            data['avg_marks'] = data['marks_total'] / data['total']
            data['avg_attendance'] = data['attendance_total'] / data['total']
    
    # Get unique semesters for filter dropdown
    all_students_in_dept = Student.query.filter_by(department_id=department.id).all()
    semester_set = set()
    for s in all_students_in_dept:
        semester_set.add(s.current_semester)
    semesters = sorted(list(semester_set))
    
    return render_template('hod/risk_levels.html',
                         department=department,
                         critical=critical,
                         high_risk=high_risk,
                         average=average,
                         safe=safe,
                         best=best,
                         total_critical=total_critical,
                         total_high_risk=total_high_risk,
                         total_average=total_average,
                         total_safe=total_safe,
                         total_best=total_best,
                         total_students=total_students,
                         semesters=semesters,
                         all_subjects=all_subjects,
                         subject_risk_data=subject_risk_data,
                         semester_data=semester_data,
                         selected_semester=selected_semester,
                         selected_subject=selected_subject)

# =====================================================
# PROFILE
# =====================================================

@hod_bp.route('/profile')
@login_required
@hod_required
def profile():
    """HOD Profile Page"""
    department = Department.query.filter_by(name=current_user.department).first()
    
    if not department:
        flash('Department not found', 'danger')
        return redirect(url_for('hod.dashboard'))
    
    # Get counts for department statistics
    teacher_count = User.query.filter_by(role='teacher', department=department.name).count()
    student_count = Student.query.filter_by(department_id=department.id).count()
    subject_count = Subject.query.filter_by(department_id=department.id).count()
    
    # Get performance statistics
    performances = StudentPerformance.query.join(Student).filter(
        Student.department_id == department.id
    ).all()
    
    if performances:
        total_marks = sum(p.final_internal for p in performances)
        avg_marks = total_marks / len(performances)
        pass_count = sum(1 for p in performances if p.final_internal >= 10)
        pass_rate = (pass_count / len(performances)) * 100 if performances else 0
        
        # Calculate attendance average
        total_attendance = sum(p.attendance for p in performances)
        avg_attendance = total_attendance / len(performances) if performances else 0
    else:
        avg_marks = 0
        pass_rate = 0
        avg_attendance = 0
    
    return render_template('hod/profile.html',
                         department=department,
                         teacher_count=teacher_count,
                         student_count=student_count,
                         subject_count=subject_count,
                         avg_marks=round(avg_marks, 1),
                         pass_rate=round(pass_rate, 1),
                         avg_attendance=round(avg_attendance, 1))

# =====================================================
# API ENDPOINTS FOR CHARTS
# =====================================================

@hod_bp.route('/api/chart-data')
@login_required
@hod_required
def chart_data():
    """API endpoint to provide chart data"""
    department = Department.query.filter_by(name=current_user.department).first()
    
    if not department:
        return jsonify({'error': 'Department not found'}), 404
    
    department_id = department.id
    
    # Subject-wise average marks
    subjects = Subject.query.filter_by(department_id=department_id).all()
    subject_names = []
    subject_avg = []
    
    for subject in subjects[:10]:  # Limit to 10 subjects
        performances = StudentPerformance.query.filter_by(subject_id=subject.id).all()
        if performances:
            avg = sum(p.final_internal for p in performances) / len(performances)
            subject_names.append(subject.name[:15] + '...' if len(subject.name) > 15 else subject.name)
            subject_avg.append(round(avg, 2))
    
    # Risk distribution
    students = Student.query.filter_by(department_id=department_id).all()
    risk_counts = {'Critical': 0, 'High Risk': 0, 'Average': 0, 'Safe': 0}
    
    for student in students:
        performances = StudentPerformance.query.filter_by(student_id=student.id).all()
        if performances:
            latest = performances[-1]
            if latest.risk_status in risk_counts:
                risk_counts[latest.risk_status] += 1
    
    return jsonify({
        'subject_names': subject_names,
        'subject_avg': subject_avg,
        'risk_labels': list(risk_counts.keys()),
        'risk_data': list(risk_counts.values())
    })

# =====================================================
# DEBUG ROUTES
# =====================================================

@hod_bp.route('/debug-assignments')
@login_required
@hod_required
def debug_assignments():
    """Debug route to check assignments in database"""
    department = Department.query.filter_by(name=current_user.department).first()
    
    if not department:
        return "Department not found"
    
    academic_year = AcademicYear.query.filter_by(is_current=True).first()
    
    if not academic_year:
        return "No academic year found"
    
    # Get all assignments
    assignments = TeacherSubject.query.filter_by(
        academic_year_id=academic_year.id,
        is_active=True
    ).all()
    
    html = f"""
    <h2>Assignments in Database</h2>
    <p>Department: {department.name}</p>
    <p>Academic Year: {academic_year.year}</p>
    <p>Total Assignments: {len(assignments)}</p>
    <table border='1' cellpadding='5'>
        <tr>
            <th>ID</th>
            <th>Teacher</th>
            <th>Subject</th>
            <th>Semester</th>
            <th>Active</th>
        </tr>
    """
    
    for a in assignments:
        teacher = User.query.get(a.teacher_id)
        subject = Subject.query.get(a.subject_id)
        html += f"""
        <tr>
            <td>{a.id}</td>
            <td>{teacher.full_name if teacher else a.teacher_id}</td>
            <td>{subject.name if subject else a.subject_id}</td>
            <td>{a.semester_id}</td>
            <td>{a.is_active}</td>
        </tr>
        """
    
    html += "</table>"
    html += '<br><a href="/hod/assign-teachers">Back to Assign Teachers</a>'
    
    return html

@hod_bp.route('/debug-hod-endpoints')
@login_required
@hod_required
def debug_hod_endpoints():
    """List all HOD endpoints"""
    from flask import current_app
    endpoints = []
    for rule in current_app.url_map.iter_rules():
        if 'hod.' in rule.endpoint:
            endpoints.append(f"{rule.endpoint} -> {rule}")
    return "<br>".join(sorted(endpoints))

# =====================================================
# STUDENT PERFORMANCE - COMPLETE FIXED VERSION
# =====================================================

@hod_bp.route('/student-performance')
@login_required
@hod_required
def student_performance():
    """View student performances - Shows ALL batches and ALL semesters"""
    department = Department.query.filter_by(name=current_user.department).first()
    
    if not department:
        flash('Department not found', 'danger')
        return redirect(url_for('hod.dashboard'))
    
    # Get filter parameters - default to 'all'
    teacher_id = request.args.get('teacher_id', 'all')
    semester = request.args.get('semester', 'all')
    risk_level = request.args.get('risk', 'all')
    search = request.args.get('search', '')
    batch_year = request.args.get('batch', 'all')  # Default to 'all' (show all batches)
    
    print(f"DEBUG: Filter params - batch={batch_year}, semester={semester}, risk={risk_level}")
    
    # Get all teachers in department
    teachers = User.query.filter_by(role='teacher', department=department.name).all()
    
    # Format teacher names
    for teacher in teachers:
        if not teacher.full_name:
            if teacher.username:
                name_parts = teacher.username.replace('.', ' ').split()
                teacher.display_name = ' '.join([part.capitalize() for part in name_parts])
            elif teacher.email:
                name_parts = teacher.email.split('@')[0].replace('.', ' ').split()
                teacher.display_name = ' '.join([part.capitalize() for part in name_parts])
            else:
                teacher.display_name = f"Teacher {teacher.id}"
        else:
            teacher.display_name = teacher.full_name
    
    # Get ALL students in department (base query)
    all_students_query = Student.query.filter_by(department_id=department.id)
    
    # Apply batch filter ONLY if not 'all'
    if batch_year != 'all':
        try:
            all_students_query = all_students_query.filter_by(admission_year=int(batch_year))
            print(f"DEBUG: Filtering to batch {batch_year}")
        except:
            pass
    
    # Get all students (after batch filter)
    all_students = all_students_query.all()
    print(f"DEBUG: Total students after batch filter: {len(all_students)}")
    
    # Apply semester filter in Python (since current_semester is a property)
    if semester != 'all' and semester:
        try:
            semester_int = int(semester)
            students = [s for s in all_students if s.current_semester == semester_int]
            print(f"DEBUG: Filtered to semester {semester_int}: {len(students)} students")
        except:
            students = all_students
    else:
        students = all_students
        print(f"DEBUG: No semester filter, showing all {len(students)} students")
    
    # Apply search filter
    if search:
        search_lower = search.lower()
        filtered = []
        for s in students:
            if (search_lower in s.name.lower() or 
                search_lower in s.registration_number.lower()):
                filtered.append(s)
        students = filtered
        print(f"DEBUG: After search filter: {len(students)} students")
    
    # Get teacher-subject assignments
    teacher_assignments = db.session.query(
        TeacherSubject, User, Subject
    ).join(
        User, TeacherSubject.teacher_id == User.id
    ).join(
        Subject, TeacherSubject.subject_id == Subject.id
    ).filter(
        User.department == department.name,
        TeacherSubject.is_active == True
    ).all()
    
    # Create subject-teacher mapping
    subject_teacher_map = {}
    teacher_info_cache = {}
    
    for assignment, teacher, subject in teacher_assignments:
        if teacher.id not in teacher_info_cache:
            teacher_info_cache[teacher.id] = {
                'id': teacher.id,
                'name': teacher.display_name,
                'username': teacher.username,
                'email': teacher.email
            }
        subject_teacher_map[subject.id] = teacher_info_cache[teacher.id]
    
    # Prepare student data with performances
    performance_data = []
    teacher_stats = {}
    
    # Initialize teacher stats
    for teacher in teachers:
        teacher_stats[teacher.id] = {
            'name': teacher.display_name,
            'critical': 0,
            'total': 0,
            'high_risk': 0,
            'average': 0,
            'safe': 0
        }
    
    teacher_stats['unassigned'] = {
        'name': 'Unassigned Students',
        'critical': 0,
        'total': 0,
        'high_risk': 0,
        'average': 0,
        'safe': 0
    }
    
    students_with_data = 0
    
    # Initialize semester counts
    semester_counts = {sem: 0 for sem in range(1, 9)}
    
    for student in students:
        # Update semester count
        semester_counts[student.current_semester] = semester_counts.get(student.current_semester, 0) + 1
        
        # Get performances for this student
        performances = db.session.query(
            StudentPerformance, Subject
        ).join(
            Subject, StudentPerformance.subject_id == Subject.id
        ).filter(
            StudentPerformance.student_id == student.id
        ).all()
        
        # Track teachers
        student_teachers = set()
        teacher_names = []
        
        if performances:
            students_with_data += 1
            
            # Calculate averages
            marks_list = [p.final_internal for p, _ in performances]
            avg_marks = sum(marks_list) / len(marks_list)
            
            # Get latest risk
            latest_perf = max(performances, key=lambda x: x[0].created_at)[0]
            risk_status = latest_perf.risk_status
            
            # Process subjects
            subjects_data = []
            semester_data = {}
            
            for perf, subject in performances:
                teacher_info = subject_teacher_map.get(subject.id, {})
                if teacher_info:
                    student_teachers.add(teacher_info['id'])
                    teacher_names.append({
                        'id': teacher_info['id'],
                        'name': teacher_info['name']
                    })
                
                subjects_data.append({
                    'subject_name': subject.name,
                    'subject_code': subject.code,
                    'marks': perf.final_internal,
                    'attendance': perf.attendance,
                    'risk': perf.risk_status,
                    'teacher_name': teacher_info.get('name', 'Not Assigned'),
                    'internal1': perf.internal1,
                    'internal2': perf.internal2,
                    'seminar': perf.seminar,
                    'assessment': perf.assessment
                })
                
                # Group by semester
                if perf.semester not in semester_data:
                    semester_data[perf.semester] = []
                semester_data[perf.semester].append({
                    'subject_name': subject.name,
                    'subject_code': subject.code,
                    'marks': perf.final_internal,
                    'attendance': perf.attendance,
                    'risk': perf.risk_status,
                    'teacher_name': teacher_info.get('name', 'Not Assigned'),
                    'internal1': perf.internal1,
                    'internal2': perf.internal2,
                    'seminar': perf.seminar,
                    'assessment': perf.assessment
                })
        else:
            avg_marks = 0
            risk_status = 'No Data'
            subjects_data = []
            semester_data = {}
        
        # Process teachers
        unique_teachers = {}
        for t in teacher_names:
            if t['id'] not in unique_teachers:
                unique_teachers[t['id']] = t['name']
        
        teacher_list = [{'id': tid, 'name': name} for tid, name in unique_teachers.items()]
        
        # Update teacher stats
        if teacher_list:
            for t in teacher_list:
                if t['id'] in teacher_stats:
                    teacher_stats[t['id']]['total'] += 1
                    if risk_status == 'Critical':
                        teacher_stats[t['id']]['critical'] += 1
                    elif risk_status == 'High Risk':
                        teacher_stats[t['id']]['high_risk'] += 1
                    elif risk_status == 'Average':
                        teacher_stats[t['id']]['average'] += 1
                    elif risk_status == 'Safe':
                        teacher_stats[t['id']]['safe'] += 1
        else:
            teacher_stats['unassigned']['total'] += 1
            if risk_status == 'Critical':
                teacher_stats['unassigned']['critical'] += 1
            elif risk_status == 'High Risk':
                teacher_stats['unassigned']['high_risk'] += 1
            elif risk_status == 'Average':
                teacher_stats['unassigned']['average'] += 1
            elif risk_status == 'Safe':
                teacher_stats['unassigned']['safe'] += 1
        
        # Apply teacher filter
        if teacher_id != 'all':
            if teacher_id == 'unassigned':
                if teacher_list:
                    continue
            else:
                teacher_id_int = int(teacher_id) if teacher_id.isdigit() else None
                teacher_ids = [t['id'] for t in teacher_list]
                if teacher_id_int not in teacher_ids:
                    continue
        
        # Apply risk filter
        if risk_level != 'all' and risk_status != risk_level:
            continue
        
        # Calculate current semester data
        current_semester = student.current_semester
        current_sem_marks = []
        current_sem_attendance = []
        if current_semester in semester_data:
            for subject in semester_data[current_semester]:
                current_sem_marks.append(subject['marks'])
                current_sem_attendance.append(subject['attendance'])
        
        current_sem_avg_marks = sum(current_sem_marks) / len(current_sem_marks) if current_sem_marks else 0
        current_sem_avg_attendance = sum(current_sem_attendance) / len(current_sem_attendance) if current_sem_attendance else 0
        
        # Overall averages
        overall_avg_marks = sum(p.final_internal for p, _ in performances) / len(performances) if performances else 0
        overall_avg_attendance = sum(p.attendance for p, _ in performances) / len(performances) if performances else 0
        
        # Year display
        if student.current_semester <= 2:
            year_display = "1st Year"
        elif student.current_semester <= 4:
            year_display = "2nd Year"
        elif student.current_semester <= 6:
            year_display = "3rd Year"
        else:
            year_display = "4th Year"
        
        performance_data.append({
            'student': student,
            'avg_marks': round(avg_marks, 2),
            'risk_status': risk_status,
            'subject_count': len(performances),
            'subjects': subjects_data,
            'has_data': len(performances) > 0,
            'teachers': teacher_list,
            'teacher_count': len(teacher_list),
            'semester_data': semester_data,
            'current_sem_count': len(semester_data.get(current_semester, [])),
            'current_sem_avg_marks': round(current_sem_avg_marks, 1),
            'current_sem_avg_attendance': round(current_sem_avg_attendance, 1),
            'overall_avg_marks': round(overall_avg_marks, 1),
            'overall_avg_attendance': round(overall_avg_attendance, 1),
            'year_display': year_display
        })
    
    # Calculate teacher stats percentages
    for t_id, stats in teacher_stats.items():
        if stats['total'] > 0:
            stats['critical_percent'] = round((stats['critical'] / stats['total']) * 100, 1)
        else:
            stats['critical_percent'] = 0
    
    # Get ALL possible semesters (1-8) for filter dropdown
    all_semesters = list(range(1, 9))
    
    # Get available batches for filter from ALL students (not filtered)
    all_students_in_dept = Student.query.filter_by(department_id=department.id).all()
    available_batches = sorted(set(s.admission_year for s in all_students_in_dept))
    
    # Batch display names
    batch_display = {
        2022: "4th Year (2022 Batch)",
        2023: "3rd Year (2023 Batch)",
        2024: "2nd Year (2024 Batch)",
        2025: "1st Year (2025 Batch)"
    }
    
    # Calculate summary stats
    total_critical = sum(1 for item in performance_data if item['risk_status'] == 'Critical')
    total_students = len(performance_data)
    
    print(f"\n{'='*60}")
    print(f"FINAL SUMMARY:")
    print(f"Total students in performance_data: {total_students}")
    print(f"Students with data: {students_with_data}")
    print(f"Semester counts: { {k: v for k, v in semester_counts.items() if v > 0} }")
    print(f"Available batches: {available_batches}")
    print(f"{'='*60}")
    
    return render_template('hod/student_performance.html',
                         department=department,
                         teachers=teachers,
                         teacher_stats=teacher_stats,
                         performance_data=performance_data,
                         available_semesters=all_semesters,  # All 8 semesters
                         semester_counts=semester_counts,  # Counts per semester
                         available_batches=available_batches,
                         batch_display=batch_display,
                         total_critical=total_critical,
                         total_students=total_students,
                         students_with_data=students_with_data,
                         current_filters={
                             'batch': batch_year,
                             'teacher_id': teacher_id,
                             'semester': semester,
                             'risk': risk_level,
                             'search': search
                         })

# =====================================================
# STUDENT DETAIL
# =====================================================

@hod_bp.route('/student-detail/<int:student_id>')
@login_required
@hod_required
def student_detail(student_id):
    """View individual student performance"""
    student = Student.query.get_or_404(student_id)
    
    # Get department from current user
    department = Department.query.filter_by(name=current_user.department).first()
    
    # Verify student belongs to HOD's department
    if student.department_id != department.id:
        flash('Access denied', 'danger')
        return redirect(url_for('hod.student_performance'))
    
    # Get all performances for this student
    performances = db.session.query(
        StudentPerformance, Subject
    ).join(
        Subject, StudentPerformance.subject_id == Subject.id
    ).filter(
        StudentPerformance.student_id == student.id
    ).all()
    
    return render_template('hod/student_detail.html',
                         student=student,
                         performances=performances)

# =====================================================
# IMPORT STUDENTS
# =====================================================

@hod_bp.route('/import-students', methods=['GET', 'POST'])
@login_required
@hod_required
def import_students():
    """Import students from text data"""
    department = Department.query.filter_by(name=current_user.department).first()
    
    if not department:
        flash('Department not found', 'danger')
        return redirect(url_for('hod.dashboard'))
    
    if request.method == 'POST':
        student_data = request.form.get('student_data', '')
        
        if not student_data:
            flash('Please paste some student data', 'warning')
            return render_template('hod/import_students.html', department=department)
        
        lines = student_data.strip().split('\n')
        imported = 0
        errors = []
        
        for line in lines:
            if not line.strip():
                continue
            
            parts = line.strip().split('\t')
            if len(parts) < 7:
                errors.append(f"Invalid line: {line[:50]}...")
                continue
            
            reg_no = parts[0].strip()
            name = parts[1].strip()
            course_name = parts[2].strip()
            semester_str = parts[3].strip()
            attendance = parts[4].strip()
            marks_str = parts[5].strip()
            risk = parts[6].strip()
            
            # Parse semester number
            try:
                semester = int(''.join(filter(str.isdigit, semester_str)))
            except:
                semester = 1
            
            # Parse marks
            try:
                marks = float(marks_str.split('/')[0])
            except:
                marks = 0.0
            
            # Get or create student (simplified)
            imported += 1
        
        flash(f'Imported {imported} students with {len(errors)} errors', 'success' if imported > 0 else 'warning')
        return redirect(url_for('hod.student_performance'))
    
    return render_template('hod/import_students.html', department=department)

@hod_bp.route('/notifications')
@login_required
@hod_required
def notifications_page():
    """HOD notifications page"""
    department = Department.query.filter_by(name=current_user.department).first()
    total_teachers = User.query.filter_by(role='teacher', department=department.name).count() if department else 0
    total_students = Student.query.filter_by(department_id=department.id).count() if department else 0
    
    return render_template('hod/notifications.html',
                         department=department,
                         total_teachers=total_teachers,
                         total_students=total_students)