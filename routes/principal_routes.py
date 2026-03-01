# routes/principal_routes.py
from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify, make_response
from flask_login import login_required, current_user
from functools import wraps
from extensions import db
from model import (
    User, Student, TeacherSubject, Subject, Department, 
    StudentPerformance, AcademicYear, Semester, Attendance,
    ExamTimetable, Course
)
from datetime import datetime, date
from model import Notification, UserNotification
import csv
from io import StringIO
import json
from sqlalchemy import func

notification_bp = Blueprint('notification', __name__, url_prefix='/api/notifications')
principal_bp = Blueprint('principal', __name__, url_prefix='/principal')

# =====================================================
# DECORATOR - Principal access only
# =====================================================

def principal_required(f):
    """Decorator to restrict access to principal only"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'principal':
            flash('Access denied. Principal privileges required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# =====================================================
# CONTEXT PROCESSOR
# =====================================================

@principal_bp.context_processor
def utility_processor():
    """Add utility functions to template context"""
    return {
        'now': datetime.now(),
        'today': date.today()
    }

# =====================================================
# DASHBOARD
# =====================================================

@principal_bp.route('/dashboard')
@login_required
@principal_required
def dashboard():
    """Principal Dashboard with summary statistics"""
    
    # Basic counts
    total_students = Student.query.count()
    total_teachers = User.query.filter_by(role='teacher', is_active=True).count()
    total_departments = Department.query.count()
    total_subjects = Subject.query.count()
    
    # Risk statistics
    critical_risk_count = StudentPerformance.query.filter(
        StudentPerformance.risk_status.in_(['Critical', 'High Risk'])
    ).count()
    
    # Attendance statistics
    attendance_records = Attendance.query.all()
    if attendance_records:
        overall_attendance = sum(a.attendance_percentage for a in attendance_records) / len(attendance_records)
    else:
        overall_attendance = 0
    
    # Department statistics with teacher counts
    dept_stats = []
    departments = Department.query.all()
    for dept in departments:
        dept_students = Student.query.filter_by(department_id=dept.id).count()
        # Fix: Get teachers by department name string
        dept_teachers = User.query.filter_by(role='teacher', department=dept.name).count()
        dept_stats.append({
            'name': dept.name,
            'code': dept.code,
            'students': dept_students,
            'teachers': dept_teachers
        })
    
    # Performance summary
    performances = StudentPerformance.query.all()
    avg_marks = 0
    if performances:
        avg_marks = sum(p.final_internal for p in performances) / len(performances)
    
    # Risk distribution
    risk_counts = {
        'Critical': StudentPerformance.query.filter_by(risk_status='Critical').count(),
        'High Risk': StudentPerformance.query.filter_by(risk_status='High Risk').count(),
        'Average': StudentPerformance.query.filter_by(risk_status='Average').count(),
        'Safe': StudentPerformance.query.filter_by(risk_status='Safe').count(),
        'Best': StudentPerformance.query.filter_by(risk_status='Best').count()
    }
    
    return render_template('principal/dashboard.html',
                         total_students=total_students,
                         total_teachers=total_teachers,
                         total_departments=total_departments,
                         total_subjects=total_subjects,
                         critical_risk_count=critical_risk_count,
                         overall_attendance=round(overall_attendance, 1),
                         dept_stats=dept_stats,
                         avg_marks=round(avg_marks, 1),
                         risk_counts=risk_counts,
                         now=datetime.now())

# =====================================================
# COMPLETE STUDENT PERFORMANCE WITH TEACHER DETAILS
# =====================================================

@principal_bp.route('/student-performance')
@login_required
@principal_required
def student_performance():
    """Complete student performance with teacher details and subject codes"""
    
    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 50  # Show 50 students per page
    
    # Get filter parameters
    dept_filter = request.args.get('department', 'all')
    sem_filter = request.args.get('semester', 'all')
    risk_filter = request.args.get('risk', 'all')
    search_query = request.args.get('search', '')
    
    # Base query
    query = Student.query
    
    # Apply department filter
    if dept_filter != 'all':
        query = query.filter_by(department_id=int(dept_filter))
    
    # Apply search
    if search_query:
        query = query.filter(
            db.or_(
                Student.name.ilike(f'%{search_query}%'),
                Student.registration_number.ilike(f'%{search_query}%'),
                Student.student_id.ilike(f'%{search_query}%')
            )
        )
    
    # Get total count for pagination
    total_students = query.count()
    
    # Apply pagination
    students = query.order_by(Student.current_semester, Student.name).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get all teacher-subject assignments
    teacher_assignments = db.session.query(
        TeacherSubject, User, Subject
    ).join(
        User, TeacherSubject.teacher_id == User.id
    ).join(
        Subject, TeacherSubject.subject_id == Subject.id
    ).filter(
        TeacherSubject.is_active == True
    ).all()
    
    # Create subject-teacher mapping
    subject_teacher_map = {}
    for assignment, teacher, subject in teacher_assignments:
        subject_teacher_map[subject.id] = {
            'teacher_id': teacher.id,
            'teacher_name': teacher.full_name,
            'teacher_email': teacher.email,
            'subject_code': subject.code,
            'subject_name': subject.name
        }
    
    # Prepare student data with performances
    student_data = []
    all_performances = []
    
    for student in students.items:
        # Get all performances for this student
        performances = StudentPerformance.query.filter_by(
            student_id=student.id
        ).order_by(StudentPerformance.semester).all()
        
        # Get department name
        dept = Department.query.get(student.department_id)
        
        # Prepare subject-wise data with teacher details
        subject_data = []
        total_marks = 0
        total_attendance = 0
        
        for perf in performances:
            subject = Subject.query.get(perf.subject_id)
            teacher_info = subject_teacher_map.get(perf.subject_id, {})
            
            # Get attendance from marks entry
            attendance = perf.attendance
            
            # Calculate grade
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
            
            subject_data.append({
                'subject_id': subject.id if subject else None,
                'subject_name': subject.name if subject else 'N/A',
                'subject_code': subject.code if subject else 'N/A',
                'internal1': perf.internal1,
                'internal2': perf.internal2,
                'seminar': perf.seminar,
                'assessment': perf.assessment,
                'total_marks': perf.total_marks,
                'final_marks': perf.final_internal,
                'attendance': attendance,
                'grade': grade,
                'risk': perf.risk_status,
                'semester': perf.semester,
                'teacher_name': teacher_info.get('teacher_name', 'Not Assigned'),
                'teacher_id': teacher_info.get('teacher_id'),
                'teacher_email': teacher_info.get('teacher_email', '')
            })
            
            total_marks += perf.final_internal
            total_attendance += attendance
        
        # Calculate averages
        subject_count = len(subject_data)
        avg_marks = total_marks / subject_count if subject_count > 0 else 0
        avg_attendance = total_attendance / subject_count if subject_count > 0 else 0
        
        # Determine overall risk
        if avg_attendance < 70 or avg_marks < 10:
            overall_risk = 'Critical'
        elif avg_marks < 12:
            overall_risk = 'Average'
        elif avg_marks >= 18:
            overall_risk = 'Best'
        else:
            overall_risk = 'Safe'
        
        # Year display
        if student.current_semester <= 2:
            year_display = "1st Year"
        elif student.current_semester <= 4:
            year_display = "2nd Year"
        elif student.current_semester <= 6:
            year_display = "3rd Year"
        else:
            year_display = "4th Year"
        
        student_data.append({
            'id': student.id,
            'student_id': student.student_id,
            'registration_number': student.registration_number,
            'name': student.name,
            'email': student.email,
            'phone': student.phone,
            'department': dept.name if dept else 'N/A',
            'department_id': student.department_id,
            'semester': student.current_semester,
            'year_display': year_display,
            'batch_year': student.admission_year,
            'subjects': subject_data,
            'subject_count': subject_count,
            'avg_marks': round(avg_marks, 1),
            'avg_attendance': round(avg_attendance, 1),
            'overall_risk': overall_risk,
            'has_data': subject_count > 0
        })
        
        all_performances.extend(performances)
    
    # Get all departments for filter
    departments = Department.query.all()
    
    # Get unique semesters for filter
    all_students = Student.query.all()
    semesters = sorted(set(str(s.current_semester) for s in all_students if s.current_semester))
    
    # Calculate summary stats
    total_with_data = sum(1 for s in student_data if s['has_data'])
    critical_count = sum(1 for s in student_data if s['overall_risk'] == 'Critical')
    
    return render_template('principal/student_performance.html',
                         students=students,
                         student_data=student_data,
                         departments=departments,
                         semesters=semesters,
                         total_students=total_students,
                         total_with_data=total_with_data,
                         critical_count=critical_count,
                         current_page=page,
                         total_pages=students.pages,
                         per_page=per_page,
                         filters={
                             'department': dept_filter,
                             'semester': sem_filter,
                             'risk': risk_filter,
                             'search': search_query
                         })

# =====================================================
# ACADEMIC OVERVIEW WITH TEACHER DETAILS
# =====================================================

@principal_bp.route('/academic-overview')
@login_required
@principal_required
def academic_overview():
    """Academic overview with teacher details and subject codes"""
    
    # Get current academic year
    current_academic_year = AcademicYear.query.filter_by(is_current=True).first()
    
    # Determine active semester based on month
    today = date.today()
    if 6 <= today.month <= 11:  # June to November
        active_semester = "Odd Semester (1,3,5,7)"
    else:  # December to April
        active_semester = "Even Semester (2,4,6,8)"
    
    # Get upcoming exams (next 30 days)
    from datetime import timedelta
    next_month = today + timedelta(days=30)
    upcoming_exams = ExamTimetable.query.filter(
        ExamTimetable.exam_date >= today,
        ExamTimetable.exam_date <= next_month
    ).order_by(ExamTimetable.exam_date).limit(10).all()
    
    # Get all teacher-subject assignments
    teacher_assignments = db.session.query(
        TeacherSubject, User, Subject
    ).join(
        User, TeacherSubject.teacher_id == User.id
    ).join(
        Subject, TeacherSubject.subject_id == Subject.id
    ).filter(
        TeacherSubject.is_active == True
    ).all()
    
    # Create subject-teacher mapping with subject codes
    subject_teacher_map = {}
    subject_codes = {}
    
    for assignment, teacher, subject in teacher_assignments:
        subject_teacher_map[subject.id] = {
            'teacher_id': teacher.id,
            'teacher_name': teacher.full_name,
            'teacher_email': teacher.email
        }
        subject_codes[subject.id] = subject.code
    
    # Semester-wise statistics with subjects
    all_students = Student.query.all()
    semester_stats = []
    
    for sem in range(1, 9):
        # Count students with this semester
        student_count = len([s for s in all_students if s.current_semester == sem])
        
        # Get all subjects for this semester
        subjects = Subject.query.filter_by(semester_id=sem).all()
        subject_list = []
        
        for subject in subjects:
            teacher_info = subject_teacher_map.get(subject.id, {})
            subject_list.append({
                'id': subject.id,
                'name': subject.name,
                'code': subject.code,
                'teacher': teacher_info.get('teacher_name', 'Not Assigned'),
                'teacher_id': teacher_info.get('teacher_id'),
                'credits': subject.credits
            })
        
        semester_stats.append({
            'semester': sem,
            'students': student_count,
            'subjects': len(subjects),
            'subject_list': subject_list
        })
    
    # Department-wise statistics with teachers
    dept_stats = []
    departments = Department.query.all()
    
    for dept in departments:
        student_count = Student.query.filter_by(department_id=dept.id).count()
        teacher_count = User.query.filter_by(role='teacher', department=dept.name).count()
        subject_count = Subject.query.filter_by(department_id=dept.id).count()
        
        # Get teachers in this department
        teachers = User.query.filter_by(role='teacher', department=dept.name).all()
        teacher_list = [{'id': t.id, 'name': t.full_name, 'email': t.email} for t in teachers]
        
        dept_stats.append({
            'name': dept.name,
            'code': dept.code,
            'students': student_count,
            'teachers': teacher_count,
            'teacher_list': teacher_list,
            'subjects': subject_count
        })
    
    # Get upcoming events (from notifications)
    upcoming_events = Notification.query.filter(
        Notification.is_active == True,
        Notification.start_date <= today,
        Notification.end_date >= today,
        db.or_(
            Notification.target_role == 'all',
            Notification.target_role == 'public'
        )
    ).order_by(Notification.start_date).limit(5).all()
    
    return render_template('principal/academic_overview.html',
                         current_academic_year=current_academic_year.year if current_academic_year else '2025-2026',
                         active_semester=active_semester,
                         upcoming_exams=upcoming_exams,
                         upcoming_events=upcoming_events,
                         semester_stats=semester_stats,
                         dept_stats=dept_stats,
                         subject_teacher_map=subject_teacher_map,
                         subject_codes=subject_codes,
                         now=datetime.now())

# =====================================================
# PERFORMANCE ANALYTICS
# =====================================================
@principal_bp.route('/analytics')
@login_required
@principal_required
def analytics():
    """Performance analytics with charts"""
    
    # Get department filter from URL
    selected_dept = request.args.get('dept', 'all')
    
    # Get all departments
    departments = Department.query.all()
    
    # Department-wise performance
    dept_performance = []
    for dept in departments:
        students = Student.query.filter_by(department_id=dept.id).all()
        student_ids = [s.id for s in students]
        
        performances = StudentPerformance.query.filter(
            StudentPerformance.student_id.in_(student_ids)
        ).all()
        
        if performances:
            avg_marks = sum(p.final_internal for p in performances) / len(performances)
            avg_attendance = sum(p.attendance for p in performances) / len(performances)
        else:
            avg_marks = 0
            avg_attendance = 0
        
        dept_performance.append({
            'name': dept.name,
            'code': dept.code,
            'avg_marks': round(avg_marks, 1),
            'avg_attendance': round(avg_attendance, 1),
            'student_count': len(students)
        })
    
    # Semester-wise performance
    semester_performance = []
    for sem in range(1, 9):
        performances = StudentPerformance.query.filter_by(semester=sem).all()
        if performances:
            avg_marks = sum(p.final_internal for p in performances) / len(performances)
            avg_attendance = sum(p.attendance for p in performances) / len(performances)
            student_count = len(set(p.student_id for p in performances))
        else:
            avg_marks = 0
            avg_attendance = 0
            student_count = 0
        
        semester_performance.append({
            'semester': sem,
            'avg_marks': round(avg_marks, 1),
            'avg_attendance': round(avg_attendance, 1),
            'student_count': student_count
        })
    
    # Risk distribution
    risk_counts = {
        'Critical': StudentPerformance.query.filter_by(risk_status='Critical').count(),
        'High Risk': StudentPerformance.query.filter_by(risk_status='High Risk').count(),
        'Average': StudentPerformance.query.filter_by(risk_status='Average').count(),
        'Safe': StudentPerformance.query.filter_by(risk_status='Safe').count(),
        'Best': StudentPerformance.query.filter_by(risk_status='Best').count()
    }
    
    # Get subjects from ALL departments with department codes
    subject_performance = []
    
    # Get all departments
    all_departments = Department.query.all()
    
    for dept in all_departments:
        # Get all subjects for this department
        subjects = Subject.query.filter_by(department_id=dept.id).order_by(Subject.semester_id, Subject.name).all()
        
        for subject in subjects:
            performances = StudentPerformance.query.filter_by(subject_id=subject.id).all()
            
            if performances:
                avg_marks = sum(p.final_internal for p in performances) / len(performances)
            else:
                avg_marks = 0
            
            subject_performance.append({
                'name': subject.name,
                'code': subject.code,
                'avg_marks': round(avg_marks, 1),
                'department': dept.name,
                'department_code': dept.code,
                'semester': subject.semester_id
            })
    
    # Sort subjects by department and semester
    subject_performance.sort(key=lambda x: (x['department'], x['semester']))
    
    # Print debug info
    print(f"\n{'='*60}")
    print(f"ANALYTICS PAGE - Selected Dept: {selected_dept}")
    print(f"Total subjects found: {len(subject_performance)}")
    for s in subject_performance[:10]:  # First 10 only
        print(f"  {s['department_code']} - {s['code']}: {s['name']}")
    print(f"{'='*60}\n")
    
    return render_template('principal/analytics.html',
                         dept_performance=dept_performance,
                         semester_performance=semester_performance,
                         risk_counts=risk_counts,
                         subject_performance=subject_performance,
                         selected_dept=selected_dept,
                         now=datetime.now())

# =====================================================
# RISK MONITORING WITH PAGINATION
# =====================================================

@principal_bp.route('/risk')
@login_required
@principal_required
def risk_monitoring():
    """Monitor students by risk level with pagination"""
    
    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 50  # Show 50 students per page
    
    # Get filter parameters
    risk_filter = request.args.get('risk', 'all')
    dept_filter = request.args.get('department', 'all')
    sem_filter = request.args.get('semester', 'all')
    search_query = request.args.get('search', '')
    
    # Base query for students
    students_query = Student.query
    
    # Apply department filter
    if dept_filter != 'all':
        students_query = students_query.filter_by(department_id=int(dept_filter))
    
    # Apply search filter
    if search_query:
        students_query = students_query.filter(
            db.or_(
                Student.name.ilike(f'%{search_query}%'),
                Student.registration_number.ilike(f'%{search_query}%'),
                Student.student_id.ilike(f'%{search_query}%')
            )
        )
    
    # Get all students (we'll filter by semester and risk in Python)
    all_students = students_query.all()
    
    # Apply semester filter in Python
    if sem_filter != 'all':
        all_students = [s for s in all_students if str(s.current_semester) == sem_filter]
    
    # Build student data with performances
    student_data = []
    risk_counts = {
        'Critical': 0,
        'High Risk': 0,
        'Average': 0,
        'Safe': 0,
        'Best': 0,
        'No Data': 0
    }
    
    for student in all_students:
        # Get latest performance for this student
        latest_perf = StudentPerformance.query.filter_by(
            student_id=student.id
        ).order_by(StudentPerformance.created_at.desc()).first()
        
        dept = Department.query.get(student.department_id)
        
        if latest_perf:
            subject = Subject.query.get(latest_perf.subject_id)
            
            # Calculate grade
            if latest_perf.final_internal >= 18:
                grade = 'A+'
            elif latest_perf.final_internal >= 15:
                grade = 'A'
            elif latest_perf.final_internal >= 12:
                grade = 'B'
            elif latest_perf.final_internal >= 10:
                grade = 'C'
            else:
                grade = 'D'
            
            # Apply risk filter
            if risk_filter != 'all' and latest_perf.risk_status != risk_filter:
                continue
            
            # Update risk counts
            if latest_perf.risk_status in risk_counts:
                risk_counts[latest_perf.risk_status] += 1
            
            student_data.append({
                'id': student.id,
                'student_id': student.student_id,
                'reg_number': student.registration_number,
                'name': student.name,
                'department': dept.name if dept else 'N/A',
                'department_id': student.department_id,
                'semester': student.current_semester,
                'subject': subject.name if subject else 'N/A',
                'subject_code': subject.code if subject else 'N/A',
                'attendance': latest_perf.attendance,
                'marks': latest_perf.final_internal,
                'grade': grade,
                'risk': latest_perf.risk_status
            })
        else:
            # Student has no performance data
            if risk_filter != 'all' and risk_filter != 'No Data':
                continue
            
            risk_counts['No Data'] += 1
            
            student_data.append({
                'id': student.id,
                'student_id': student.student_id,
                'reg_number': student.registration_number,
                'name': student.name,
                'department': dept.name if dept else 'N/A',
                'department_id': student.department_id,
                'semester': student.current_semester,
                'subject': 'No Data',
                'subject_code': 'N/A',
                'attendance': 0,
                'marks': 0,
                'grade': 'N/A',
                'risk': 'No Data'
            })
    
    # Apply pagination
    total_filtered = len(student_data)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_students = student_data[start:end]
    
    # Calculate total pages
    total_pages = (total_filtered + per_page - 1) // per_page
    
    # Get departments for filter dropdown
    departments = Department.query.all()
    
    # Get unique semesters
    all_students_db = Student.query.all()
    semesters = sorted(set(str(s.current_semester) for s in all_students_db if s.current_semester))
    
    return render_template('principal/risk.html',
                         student_data=paginated_students,
                         departments=departments,
                         semesters=semesters,
                         risk_counts=risk_counts,
                         selected_risk=risk_filter,
                         selected_dept=dept_filter,
                         selected_sem=sem_filter,
                         search_query=search_query,
                         current_page=page,
                         total_pages=total_pages,
                         total_records=total_filtered,
                         per_page=per_page,
                         now=datetime.now())

# =====================================================
# REPORTS PAGE
# =====================================================

@principal_bp.route('/reports')
@login_required
@principal_required
def reports_page():
    """Reports page - Shows export options"""
    
    total_students = Student.query.count()
    total_teachers = User.query.filter_by(role='teacher', is_active=True).count()
    total_departments = Department.query.count()
    total_subjects = Subject.query.count()
    
    return render_template('principal/reports.html', 
                         total_students=total_students,
                         total_teachers=total_teachers,
                         total_departments=total_departments,
                         total_subjects=total_subjects,
                         now=datetime.now())

# =====================================================
# EXPORT REPORTS (CSV)
# =====================================================

@principal_bp.route('/export/student-performance')
@login_required
@principal_required
def export_student_performance():
    """Export student performance as CSV"""
    
    si = StringIO()
    cw = csv.writer(si)
    
    # Headers
    cw.writerow([
        'Registration No', 'Student Name', 'Department', 'Semester',
        'Subject', 'Subject Code', 'Internal 1', 'Internal 2', 'Seminar', 'Assessment',
        'Total Marks', 'Final Marks (/20)', 'Attendance %', 'Grade', 'Risk Status',
        'Teacher Name'
    ])
    
    # Get all teacher-subject assignments
    teacher_assignments = db.session.query(
        TeacherSubject, User
    ).join(
        User, TeacherSubject.teacher_id == User.id
    ).filter(
        TeacherSubject.is_active == True
    ).all()
    
    teacher_map = {}
    for assignment, teacher in teacher_assignments:
        teacher_map[assignment.subject_id] = teacher.full_name
    
    # Get all performances
    performances = StudentPerformance.query.all()
    
    for perf in performances:
        student = Student.query.get(perf.student_id)
        subject = Subject.query.get(perf.subject_id)
        
        if not student or not subject:
            continue
        
        # Calculate grade
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
        
        teacher_name = teacher_map.get(subject.id, 'Not Assigned')
        dept = Department.query.get(student.department_id)
        
        cw.writerow([
            student.registration_number,
            student.name,
            dept.name if dept else 'N/A',
            perf.semester,
            subject.name,
            subject.code,
            perf.internal1,
            perf.internal2,
            perf.seminar,
            perf.assessment,
            perf.total_marks,
            perf.final_internal,
            perf.attendance,
            grade,
            perf.risk_status,
            teacher_name
        ])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=student_performance_{date.today()}.csv"
    output.headers["Content-type"] = "text/csv"
    
    return output

@principal_bp.route('/export/risk-report')
@login_required
@principal_required
def export_risk_report():
    """Export risk report as CSV"""
    
    si = StringIO()
    cw = csv.writer(si)
    
    # Headers
    cw.writerow([
        'Registration No', 'Student Name', 'Department', 'Semester',
        'Subject', 'Subject Code', 'Final Marks', 'Attendance %', 'Grade', 'Risk Status'
    ])
    
    # Get all performances
    performances = StudentPerformance.query.all()
    
    for perf in performances:
        student = Student.query.get(perf.student_id)
        subject = Subject.query.get(perf.subject_id)
        
        if not student or not subject:
            continue
        
        # Calculate grade
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
        
        dept = Department.query.get(student.department_id)
        
        cw.writerow([
            student.registration_number,
            student.name,
            dept.name if dept else 'N/A',
            perf.semester,
            subject.name,
            subject.code,
            perf.final_internal,
            perf.attendance,
            grade,
            perf.risk_status
        ])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=risk_report_{date.today()}.csv"
    output.headers["Content-type"] = "text/csv"
    
    return output

@principal_bp.route('/export/attendance-summary')
@login_required
@principal_required
def export_attendance_summary():
    """Export attendance summary as CSV"""
    
    si = StringIO()
    cw = csv.writer(si)
    
    # Headers
    cw.writerow([
        'Registration No', 'Student Name', 'Department', 'Semester',
        'Subject', 'Subject Code', 'Month', 'Year', 'Total Classes', 'Attended',
        'Attendance %', 'Penalty Amount', 'Penalty Status'
    ])
    
    # Get all attendance records
    attendance_records = Attendance.query.all()
    
    for att in attendance_records:
        student = Student.query.get(att.student_id)
        subject = Subject.query.get(att.subject_id)
        
        if not student or not subject:
            continue
        
        dept = Department.query.get(student.department_id)
        
        cw.writerow([
            student.registration_number,
            student.name,
            dept.name if dept else 'N/A',
            att.semester,
            subject.name,
            subject.code,
            att.month,
            att.year,
            att.total_classes,
            att.attended_classes,
            att.attendance_percentage,
            att.penalty_amount,
            att.penalty_status
        ])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=attendance_summary_{date.today()}.csv"
    output.headers["Content-type"] = "text/csv"
    
    return output

# =====================================================
# STUDENT DETAILS WITH TEACHER INFO
# =====================================================

@principal_bp.route('/student-details/<int:student_id>')
@login_required
@principal_required
def student_details(student_id):
    """View complete student details with teacher information"""
    student = Student.query.get_or_404(student_id)
    
    # Get teacher-subject assignments
    teacher_assignments = db.session.query(
        TeacherSubject, User, Subject
    ).join(
        User, TeacherSubject.teacher_id == User.id
    ).join(
        Subject, TeacherSubject.subject_id == Subject.id
    ).filter(
        TeacherSubject.is_active == True
    ).all()
    
    teacher_map = {}
    for assignment, teacher, subject in teacher_assignments:
        teacher_map[subject.id] = {
            'teacher_id': teacher.id,
            'teacher_name': teacher.full_name,
            'teacher_email': teacher.email
        }
    
    # Get all performances for this student
    performances = student.performances.order_by(
        StudentPerformance.semester,
        StudentPerformance.subject_id
    ).all()
    
    # Group performances by semester
    performances_by_semester = {}
    for perf in performances:
        subject = Subject.query.get(perf.subject_id)
        if perf.semester not in performances_by_semester:
            performances_by_semester[perf.semester] = []
        
        # Calculate grade
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
        
        teacher_info = teacher_map.get(perf.subject_id, {})
        
        performances_by_semester[perf.semester].append({
            'subject': subject,
            'subject_code': subject.code if subject else 'N/A',
            'internal1': perf.internal1,
            'internal2': perf.internal2,
            'seminar': perf.seminar,
            'assessment': perf.assessment,
            'final_marks': perf.final_internal,
            'attendance': perf.attendance,
            'grade': grade,
            'risk': perf.risk_status,
            'teacher_name': teacher_info.get('teacher_name', 'Not Assigned'),
            'teacher_id': teacher_info.get('teacher_id')
        })
    
    # Calculate semester summaries
    semester_summaries = []
    for sem in range(1, student.current_semester + 1):
        if sem in performances_by_semester:
            sem_perfs = performances_by_semester[sem]
            avg_marks = sum(p['final_marks'] for p in sem_perfs) / len(sem_perfs)
            avg_attendance = sum(p['attendance'] for p in sem_perfs) / len(sem_perfs)
            sgpa = (avg_marks / 20) * 10
            
            semester_summaries.append({
                'semester': sem,
                'subjects': len(sem_perfs),
                'avg_marks': round(avg_marks, 2),
                'avg_attendance': round(avg_attendance, 2),
                'sgpa': round(sgpa, 2)
            })
    
    # Calculate CGPA
    if semester_summaries:
        cgpa = sum(s['sgpa'] for s in semester_summaries) / len(semester_summaries)
    else:
        cgpa = 0
    
    # Get department
    department = Department.query.get(student.department_id)
    
    return render_template('principal/student_details.html',
                         student=student,
                         department=department,
                         performances_by_semester=performances_by_semester,
                         semester_summaries=semester_summaries,
                         cgpa=round(cgpa, 2),
                         now=datetime.now())

# =====================================================
# NOTIFICATION API ENDPOINTS
# =====================================================

@notification_bp.route('/unread-count')
@login_required
def unread_count():
    """Get unread notification count for current user"""
    try:
        count = Notification.query.filter(
            Notification.target_role.in_(['all', current_user.role]),
            Notification.is_active == True,
            Notification.is_read == False
        ).count()
        
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        print(f"Error getting unread count: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@notification_bp.route('/list')
@login_required
def list_notifications():
    """Get notifications for current user"""
    try:
        notifications = Notification.query.filter(
            Notification.target_role.in_(['all', current_user.role]),
            Notification.is_active == True,
            Notification.start_date <= datetime.now().date(),
            Notification.end_date >= datetime.now().date()
        ).order_by(Notification.created_at.desc()).limit(20).all()
        
        notif_list = []
        for n in notifications:
            notif_list.append({
                'id': n.id,
                'title': n.get_prefixed_title(),
                'message': n.get_prefixed_message(),
                'notification_type': n.notification_type,
                'is_read': n.is_read,
                'time_ago': n.get_time_ago(),
                'icon': n.get_icon().replace('fa-', ''),
                'icon_class': n.notification_type,
                'link': n.link or '#'
            })
        
        return jsonify({'success': True, 'notifications': notif_list})
    except Exception as e:
        print(f"Error listing notifications: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@notification_bp.route('/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_read(notification_id):
    """Mark a notification as read"""
    try:
        notification = Notification.query.get_or_404(notification_id)
        notification.is_read = True
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error marking read: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@notification_bp.route('/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    """Mark all notifications as read for current user"""
    try:
        Notification.query.filter(
            Notification.target_role.in_(['all', current_user.role]),
            Notification.is_read == False
        ).update({'is_read': True})
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error marking all read: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    
@principal_bp.route('/notifications')
@login_required
@principal_required
def notifications_page():
    """Principal notifications page"""
    return render_template('principal/notifications.html')