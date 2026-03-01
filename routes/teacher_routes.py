# routes/teacher_routes.py
from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from model import QuestionPaper, Notification
from utils.helpers import get_current_academic_year
from extensions import db
from model import (
    User, Student, Subject, TeacherSubject, 
    StudentPerformance, AcademicYear, Department, Attendance,
    Course, Semester
)
from datetime import datetime
import calendar

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')

def teacher_required(f):
    """Decorator to restrict access to teachers only"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'teacher':
            flash('Access denied. Teacher privileges required.', 'danger')
            return redirect(url_for('auth.login'))
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
    """Calculate percentage from final marks (out of 20)"""
    return int((final_marks / 20) * 100)

def calculate_risk_status(attendance_percent, final_marks):
    """Calculate risk status based on attendance and marks"""
    if attendance_percent < 70:
        return 'Critical'
    elif final_marks < 10:
        return 'Critical'
    elif final_marks < 15:
        return 'Average'
    elif final_marks >= 18:
        return 'Best'
    else:
        return 'Safe'

def get_student_attendance(student_id, subject_id, semester):
    """Get attendance percentage for a student from Attendance table"""
    attendance_records = Attendance.query.filter_by(
        student_id=student_id,
        subject_id=subject_id,
        semester=semester
    ).all()
    
    if not attendance_records:
        return 0, 0, 0
    
    avg_percentage = sum(record.attendance_percentage for record in attendance_records) / len(attendance_records)
    total_classes = sum(record.total_classes for record in attendance_records)
    attended_classes = sum(record.attended_classes for record in attendance_records)
    
    return round(avg_percentage, 1), total_classes, attended_classes

def get_students_for_subject(subject_id):
    """Get all students for a subject based on semester"""
    subject = Subject.query.get(subject_id)
    if not subject:
        return []
    
    # Get the correct semester number
    semester = Semester.query.get(subject.semester_id)
    semester_number = semester.semester_number if semester else subject.semester_id
    
    # Get all students in department
    all_students = Student.query.filter_by(
        department_id=subject.department_id
    ).all()
    
    # Filter by current semester
    students = [s for s in all_students if s.current_semester == semester_number]
    students.sort(key=lambda s: s.name)
    
    return students

def get_next_student(current_student_id, subject_id):
    """Get next student in the list for this subject"""
    students = get_students_for_subject(subject_id)
    
    for i, student in enumerate(students):
        if student.id == current_student_id:
            if i + 1 < len(students):
                return students[i + 1]
            break
    return None

def get_previous_student(current_student_id, subject_id):
    """Get previous student in the list for this subject"""
    students = get_students_for_subject(subject_id)
    
    for i, student in enumerate(students):
        if student.id == current_student_id:
            if i - 1 >= 0:
                return students[i - 1]
            break
    return None

def get_student_index(current_student_id, subject_id):
    """Get current student index for display"""
    students = get_students_for_subject(subject_id)
    
    for i, student in enumerate(students):
        if student.id == current_student_id:
            return i + 1
    return 0

def get_marks_entry_stats(subject_id):
    """Get statistics about marks entry progress"""
    subject = Subject.query.get(subject_id)
    if not subject:
        return {'total': 0, 'entered': 0, 'pending': 0}
    
    students = get_students_for_subject(subject_id)
    total_students = len(students)
    
    academic_year = AcademicYear.query.filter_by(is_current=True).first()
    if academic_year:
        entered = StudentPerformance.query.filter_by(
            subject_id=subject_id,
            academic_year_id=academic_year.id
        ).count()
    else:
        entered = 0
    
    return {
        'total': total_students,
        'entered': entered,
        'pending': total_students - entered
    }

def get_teacher_department():
    """Helper function to get teacher's department object"""
    if current_user.department:
        return Department.query.filter_by(name=current_user.department).first()
    return None

@teacher_bp.context_processor
def utility_processor():
    """Add utility functions to template context"""
    assignments = TeacherSubject.query.filter_by(
        teacher_id=current_user.id,
        is_active=True
    ).all()
    
    teacher_subjects = []
    for assignment in assignments:
        subject = Subject.query.get(assignment.subject_id)
        if subject:
            teacher_subjects.append(subject)
    
    department = get_teacher_department()
    
    return {
        'now': datetime.now(),
        'teacher_subjects': teacher_subjects,
        'department': department,
        'calculate_grade': calculate_grade,
        'calculate_risk_status': calculate_risk_status,
        'calculate_percentage': calculate_percentage,
        'get_student_attendance': get_student_attendance
    }

# =====================================================
# DASHBOARD
# =====================================================

@teacher_bp.route('/dashboard')
@login_required
@teacher_required
def dashboard():
    """Teacher Dashboard with performance table"""
    # Get teacher's assigned subjects
    assignments = TeacherSubject.query.filter_by(
        teacher_id=current_user.id,
        is_active=True
    ).all()
    
    subjects = []
    subject_ids = []
    
    # Get all students in the department once for efficiency
    department = get_teacher_department()
    all_students_in_dept = []
    if department:
        all_students_in_dept = Student.query.filter_by(department_id=department.id).all()
    
    for assignment in assignments:
        subject = Subject.query.get(assignment.subject_id)
        if subject:
            subject_ids.append(subject.id)
            
            # Get the correct semester number
            semester = Semester.query.get(subject.semester_id)
            semester_number = semester.semester_number if semester else subject.semester_id
            
            # Count students by their current semester
            student_count = 0
            for student in all_students_in_dept:
                if student.current_semester == semester_number:
                    student_count += 1
            
            # Get marks entry progress
            stats = get_marks_entry_stats(subject.id)
            
            subjects.append({
                'id': subject.id,
                'name': subject.name,
                'code': subject.code,
                'semester': semester_number,
                'student_count': student_count,
                'entered': stats['entered'],
                'pending': stats['pending'],
                'progress': stats['entered'] / stats['total'] * 100 if stats['total'] > 0 else 0
            })
    
    # Get all performances for teacher's subjects
    performances = []
    if subject_ids:
        performances = StudentPerformance.query.filter(
            StudentPerformance.subject_id.in_(subject_ids)
        ).order_by(
            StudentPerformance.created_at.desc()
        ).limit(50).all()
    
    # Calculate statistics
    total_students = len(set(p.student_id for p in performances))
    critical_count = 0
    best_count = 0
    total_marks_sum = 0
    marks_count = 0
    
    for perf in performances:
        total_marks_sum += perf.final_internal
        marks_count += 1
        
        attendance, _, _ = get_student_attendance(perf.student_id, perf.subject_id, perf.semester)
        risk = calculate_risk_status(attendance, perf.final_internal)
        
        if risk == 'Critical':
            critical_count += 1
        elif risk == 'Best':
            best_count += 1
    
    avg_marks = total_marks_sum / marks_count if marks_count > 0 else 0
    
    # Prepare performance data
    performance_data = []
    for perf in performances:
        student = Student.query.get(perf.student_id)
        if student:
            attendance, _, _ = get_student_attendance(perf.student_id, perf.subject_id, perf.semester)
            grade = calculate_grade(perf.final_internal)
            risk = calculate_risk_status(attendance, perf.final_internal)
            
            performance_data.append({
                'id': perf.id,
                'student': student,
                'student_id': student.id,
                'subject_id': perf.subject_id,
                'attendance_percentage': attendance,
                'final_marks': perf.final_internal,
                'grade': grade,
                'risk_status': risk,
                'percentage': calculate_percentage(perf.final_internal),
                'created_at': perf.created_at
            })
    
    # Get notifications
    today = datetime.now().date()
    notifications = Notification.query.filter(
        Notification.is_active == True,
        Notification.start_date <= today,
        Notification.end_date >= today,
        db.or_(
            Notification.target_role == 'all',
            Notification.target_role == 'teacher'
        )
    ).order_by(Notification.created_at.desc()).limit(10).all()
    
    recent_papers = []
    if subject_ids:
        recent_papers = QuestionPaper.query.filter(
            QuestionPaper.subject_id.in_(subject_ids),
            QuestionPaper.is_active == True
        ).order_by(QuestionPaper.uploaded_at.desc()).limit(6).all()

    return render_template('teacher/dashboard.html',
                         subjects=subjects,
                         performances=performance_data,
                         total_students=total_students,
                         critical_count=critical_count,
                         best_count=best_count,
                         avg_marks=round(avg_marks, 1),
                         recent_papers=recent_papers,
                         notifications=notifications)

# =====================================================
# ENTER MARKS - DIRECT ENTRY (NEW)
# =====================================================

@teacher_bp.route('/marks/enter/<int:subject_id>')
@login_required
@teacher_required
def enter_marks(subject_id):
    """Direct marks entry page - opens immediately with first student"""
    # Verify teacher is assigned to this subject
    assignment = TeacherSubject.query.filter_by(
        teacher_id=current_user.id,
        subject_id=subject_id,
        is_active=True
    ).first()
    
    if not assignment:
        flash('You are not authorized to access this subject', 'danger')
        return redirect(url_for('teacher.dashboard'))
    
    subject = Subject.query.get_or_404(subject_id)
    
    # Get student_id from query parameter (if navigating)
    student_id = request.args.get('student_id', type=int)
    
    # Get all students for this subject
    students = get_students_for_subject(subject_id)
    
    if not students:
        flash('No students enrolled in this subject', 'warning')
        return redirect(url_for('teacher.dashboard'))
    
    # Determine which student to show
    selected_student = None
    if student_id:
        selected_student = Student.query.get(student_id)
    else:
        # Default to first student
        selected_student = students[0]
        student_id = selected_student.id
    
    # Get navigation students
    next_student = get_next_student(student_id, subject_id)
    prev_student = get_previous_student(student_id, subject_id)
    current_index = get_student_index(student_id, subject_id)
    total_students = len(students)
    
    # Get marks entry stats
    stats = get_marks_entry_stats(subject_id)
    
    # Get existing marks if any
    existing_marks = None
    if selected_student:
        academic_year = AcademicYear.query.filter_by(is_current=True).first()
        if academic_year:
            existing_marks = StudentPerformance.query.filter_by(
                student_id=selected_student.id,
                subject_id=subject_id,
                academic_year_id=academic_year.id
            ).first()
    
    return render_template('teacher/enter_marks.html',
                         subject=subject,
                         students=students,
                         selected_student=selected_student,
                         next_student=next_student,
                         prev_student=prev_student,
                         current_index=current_index,
                         total_students=total_students,
                         stats=stats,
                         existing_marks=existing_marks)

@teacher_bp.route('/marks/save/<int:subject_id>', methods=['POST'])
@login_required
@teacher_required
def save_marks(subject_id):
    """Save marks from manual entry form with navigation options"""
    # Verify teacher is assigned to this subject
    assignment = TeacherSubject.query.filter_by(
        teacher_id=current_user.id,
        subject_id=subject_id,
        is_active=True
    ).first()
    
    if not assignment:
        flash('You are not authorized to access this subject', 'danger')
        return redirect(url_for('teacher.dashboard'))
    
    subject = Subject.query.get_or_404(subject_id)
    student_id = request.form.get('student_id', type=int)
    action = request.form.get('action', 'save')  # 'save', 'save_next', 'save_previous'
    
    if not student_id:
        flash('Please select a student', 'danger')
        return redirect(url_for('teacher.enter_marks', subject_id=subject_id))
    
    student = Student.query.get_or_404(student_id)
    academic_year = AcademicYear.query.filter_by(is_current=True).first()
    
    if not academic_year:
        from datetime import date
        current_year = datetime.now().year
        academic_year = AcademicYear(
            year=f"{current_year}-{current_year+1}",
            start_date=date(current_year, 6, 1),
            end_date=date(current_year+1, 4, 30),
            is_current=True
        )
        db.session.add(academic_year)
        db.session.commit()
    
    try:
        # Get form data
        total_classes = int(request.form.get('total_classes', 0))
        attended = int(request.form.get('attended', 0))
        internal1 = int(request.form.get('internal1', 0))
        internal2 = int(request.form.get('internal2', 0))
        seminar = int(request.form.get('seminar', 0))
        assessment = int(request.form.get('assessment', 0))
        
        # Validate
        if total_classes <= 0:
            flash('Total classes must be greater than 0', 'warning')
            return redirect(url_for('teacher.enter_marks', subject_id=subject_id, student_id=student_id))
        
        if attended > total_classes:
            flash('Attended classes cannot exceed total classes', 'warning')
            return redirect(url_for('teacher.enter_marks', subject_id=subject_id, student_id=student_id))
        
        if not (0 <= internal1 <= 70 and 0 <= internal2 <= 70):
            flash('Internal marks must be between 0 and 70', 'warning')
            return redirect(url_for('teacher.enter_marks', subject_id=subject_id, student_id=student_id))
        
        if not (0 <= seminar <= 10 and 0 <= assessment <= 10):
            flash('Seminar and Assessment marks must be between 0 and 10', 'warning')
            return redirect(url_for('teacher.enter_marks', subject_id=subject_id, student_id=student_id))
        
        # Calculate values
        attendance_percent = int((attended / total_classes) * 100) if total_classes > 0 else 0
        total_marks = internal1 + internal2 + seminar + assessment
        final_internal = round((total_marks / 160) * 20, 1)
        
        # Calculate risk
        from utils.risk_analysis import RiskAnalyzer
        risk = RiskAnalyzer.calculate_risk_status(final_internal, attendance_percent)
        
        # Get semester number
        semester = Semester.query.get(subject.semester_id)
        semester_number = semester.semester_number if semester else subject.semester_id
        
        # Check if performance exists
        performance = StudentPerformance.query.filter_by(
            student_id=student_id,
            subject_id=subject_id,
            academic_year_id=academic_year.id
        ).first()
        
        if performance:
            # Update existing
            performance.attendance = attendance_percent
            performance.internal1 = internal1
            performance.internal2 = internal2
            performance.seminar = seminar
            performance.assessment = assessment
            performance.total_marks = total_marks
            performance.final_internal = final_internal
            performance.risk_status = risk
            performance.updated_at = datetime.utcnow()
            action_msg = "updated"
        else:
            # Create new
            performance = StudentPerformance(
                student_id=student_id,
                subject_id=subject_id,
                attendance=attendance_percent,
                internal1=internal1,
                internal2=internal2,
                seminar=seminar,
                assessment=assessment,
                total_marks=total_marks,
                final_internal=final_internal,
                risk_status=risk,
                semester=semester_number,
                academic_year_id=academic_year.id
            )
            db.session.add(performance)
            action_msg = "added"
        
        # Update or create attendance record
        attendance_record = Attendance.query.filter_by(
            student_id=student_id,
            subject_id=subject_id,
            semester=semester_number
        ).first()
        
        penalty_amount = 0
        penalty_status = 'No Penalty'
        if attendance_percent < 60:
            penalty_amount = 1000
            penalty_status = 'High Penalty'
        elif attendance_percent < 70:
            penalty_amount = 500
            penalty_status = 'Medium Penalty'
        elif attendance_percent < 75:
            penalty_amount = 200
            penalty_status = 'Low Penalty'
        
        if attendance_record:
            attendance_record.total_classes = total_classes
            attendance_record.attended_classes = attended
            attendance_record.attendance_percentage = attendance_percent
            attendance_record.penalty_amount = penalty_amount
            attendance_record.penalty_status = penalty_status
            attendance_record.updated_at = datetime.utcnow()
        else:
            attendance_record = Attendance(
                student_id=student_id,
                subject_id=subject_id,
                teacher_id=current_user.id,
                total_classes=total_classes,
                attended_classes=attended,
                attendance_percentage=attendance_percent,
                penalty_amount=penalty_amount,
                penalty_status=penalty_status,
                month=datetime.now().month,
                year=datetime.now().year,
                semester=semester_number
            )
            db.session.add(attendance_record)
        
        db.session.commit()
        flash(f'✅ Marks {action_msg} for {student.name}', 'success')
        
        # Handle navigation based on action
        if action == 'save_next':
            next_student = get_next_student(student_id, subject_id)
            if next_student:
                return redirect(url_for('teacher.enter_marks', 
                                      subject_id=subject_id, 
                                      student_id=next_student.id))
            else:
                flash('🎉 All students completed!', 'success')
                return redirect(url_for('teacher.student_results', subject_id=subject_id))
        
        elif action == 'save_previous':
            prev_student = get_previous_student(student_id, subject_id)
            if prev_student:
                return redirect(url_for('teacher.enter_marks', 
                                      subject_id=subject_id, 
                                      student_id=prev_student.id))
        
        # Default: stay on same student
        return redirect(url_for('teacher.enter_marks', 
                              subject_id=subject_id, 
                              student_id=student_id))
        
    except ValueError as e:
        flash(f'Please enter valid numbers: {str(e)}', 'warning')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        db.session.rollback()
    
    return redirect(url_for('teacher.enter_marks', subject_id=subject_id, student_id=student_id))

# =====================================================
# STUDENT RESULTS (VIEW ONLY)
# =====================================================

@teacher_bp.route('/results/<int:subject_id>')
@login_required
@teacher_required
def student_results(subject_id):
    """View results for a specific subject - RESULTS PAGE ONLY"""
    # Verify teacher is assigned to this subject
    assignment = TeacherSubject.query.filter_by(
        teacher_id=current_user.id,
        subject_id=subject_id,
        is_active=True
    ).first()
    
    if not assignment:
        flash('You are not authorized to access this subject', 'danger')
        return redirect(url_for('teacher.dashboard'))
    
    subject = Subject.query.get_or_404(subject_id)
    
    # Get semester number
    semester = Semester.query.get(subject.semester_id)
    semester_number = semester.semester_number if semester else subject.semester_id
    
    academic_year = AcademicYear.query.filter_by(is_current=True).first()
    
    # Get students for this subject
    students = get_students_for_subject(subject_id)
    
    # Get all performances for this subject
    performances = StudentPerformance.query.filter_by(
        subject_id=subject_id,
        academic_year_id=academic_year.id if academic_year else None
    ).all()
    
    # Create dictionary for quick lookup
    performance_dict = {p.student_id: p for p in performances}
    
    # Prepare display data with attendance
    for perf in performances:
        attendance, total, attended = get_student_attendance(
            perf.student_id, subject_id, semester_number
        )
        perf.attendance = attendance
        perf.total_classes = total
        perf.attended_classes = attended
    
    # Calculate statistics
    total_students = len(students)
    marks_entered = len(performances)
    pending = total_students - marks_entered
    avg_marks = sum(p.final_internal for p in performances) / marks_entered if marks_entered > 0 else 0
    
    department = get_teacher_department()
    
    return render_template('teacher/student_results.html',
                         subject=subject,
                         students=students,
                         performances=performance_dict,
                         department=department,
                         total_students=total_students,
                         marks_entered=marks_entered,
                         pending=pending,
                         avg_marks=round(avg_marks, 1))

@teacher_bp.route('/results/<int:subject_id>/download')
@login_required
@teacher_required
def download_results(subject_id):
    """Download results as CSV"""
    # Verify teacher is assigned to this subject
    assignment = TeacherSubject.query.filter_by(
        teacher_id=current_user.id,
        subject_id=subject_id,
        is_active=True
    ).first()
    
    if not assignment:
        flash('You are not authorized to access this subject', 'danger')
        return redirect(url_for('teacher.dashboard'))
    
    subject = Subject.query.get_or_404(subject_id)
    academic_year = AcademicYear.query.filter_by(is_current=True).first()
    
    # Get all performances for this subject
    performances = StudentPerformance.query.filter_by(
        subject_id=subject_id,
        academic_year_id=academic_year.id if academic_year else None
    ).all()
    
    # Create CSV
    import csv
    from io import StringIO
    from flask import make_response
    
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Reg No', 'Name', 'Semester', 'Internal 1', 'Internal 2', 
                 'Seminar', 'Assessment', 'Total', 'Final Marks', 'Grade', 'Risk'])
    
    for perf in performances:
        student = Student.query.get(perf.student_id)
        if student:
            grade = calculate_grade(perf.final_internal)
            attendance, _, _ = get_student_attendance(perf.student_id, subject_id, perf.semester)
            risk = calculate_risk_status(attendance, perf.final_internal)
            
            cw.writerow([
                student.registration_number,
                student.name,
                perf.semester,
                perf.internal1,
                perf.internal2,
                perf.seminar,
                perf.assessment,
                perf.total_marks,
                perf.final_internal,
                grade,
                risk
            ])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename={subject.code}_results.csv"
    output.headers["Content-type"] = "text/csv"
    return output

# =====================================================
# STUDENT MANAGEMENT
# =====================================================

@teacher_bp.route('/students-list')
@login_required
@teacher_required
def students_list():
    """Redirect to all students page"""
    return redirect(url_for('teacher.all_students'))

@teacher_bp.route('/all-students')
@login_required
@teacher_required
def all_students():
    """Show all students in teacher's department grouped by year"""
    department = get_teacher_department()
    
    if not department:
        flash('Department not found', 'danger')
        return redirect(url_for('teacher.dashboard'))
    
    # Get all students in teacher's department
    students = Student.query.filter_by(
        department_id=department.id
    ).all()
    
    # Sort by current_semester and name
    students.sort(key=lambda s: (s.current_semester, s.name))
    
    # Group by year
    year1 = [s for s in students if s.current_semester <= 2]
    year2 = [s for s in students if 3 <= s.current_semester <= 4]
    year3 = [s for s in students if 5 <= s.current_semester <= 6]
    year4 = [s for s in students if s.current_semester >= 7]
    
    return render_template('teacher/all_students.html',
                         year1=year1,
                         year2=year2,
                         year3=year3,
                         year4=year4,
                         total=len(students))

@teacher_bp.route('/students/year/<int:year>')
@login_required
@teacher_required
def students_by_year(year):
    """Show students for a specific year"""
    # Define semester ranges for each year
    if year == 1:
        semester_range = [1, 2]
    elif year == 2:
        semester_range = [3, 4]
    elif year == 3:
        semester_range = [5, 6]
    elif year == 4:
        semester_range = [7, 8]
    else:
        flash('Invalid year', 'danger')
        return redirect(url_for('teacher.dashboard'))
    
    department = get_teacher_department()
    
    if not department:
        flash('Department not found', 'danger')
        return redirect(url_for('teacher.dashboard'))
    
    # Get all students in the department
    all_students = Student.query.filter_by(
        department_id=department.id
    ).all()
    
    # Filter by semester range
    students = [s for s in all_students if s.current_semester in semester_range]
    students.sort(key=lambda s: (s.current_semester, s.name))
    
    # Get performance data for each student
    student_data = []
    for student in students:
        perf = StudentPerformance.query.filter_by(
            student_id=student.id
        ).order_by(StudentPerformance.created_at.desc()).first()
        
        if perf:
            attendance, total, attended = get_student_attendance(
                student.id, 
                perf.subject_id, 
                student.current_semester
            )
            grade = calculate_grade(perf.final_internal)
            risk = calculate_risk_status(attendance, perf.final_internal)
            
            student_data.append({
                'id': student.id,
                'student_id': student.student_id,
                'reg_no': student.registration_number,
                'name': student.name,
                'semester': student.current_semester,
                'attendance': attendance,
                'marks': perf.final_internal,
                'grade': grade,
                'risk': risk
            })
        else:
            student_data.append({
                'id': student.id,
                'student_id': student.student_id,
                'reg_no': student.registration_number,
                'name': student.name,
                'semester': student.current_semester,
                'attendance': 0,
                'marks': 0,
                'grade': 'N/A',
                'risk': 'Unknown'
            })
    
    return render_template('teacher/students_by_year.html',
                         year=year,
                         students=student_data,
                         total=len(student_data))

@teacher_bp.route('/student/<int:student_id>')
@login_required
@teacher_required
def student_detail(student_id):
    """View detailed information for a student"""
    student = Student.query.get_or_404(student_id)
    
    # Verify student belongs to teacher's department
    department = get_teacher_department()
    if not department or student.department_id != department.id:
        flash('Access denied', 'danger')
        return redirect(url_for('teacher.dashboard'))
    
    # Get all performances for this student
    performances = StudentPerformance.query.filter_by(
        student_id=student_id
    ).order_by(StudentPerformance.semester).all()
    
    # Prepare performance data
    performance_data = []
    suggestions = []
    
    for perf in performances:
        subject = Subject.query.get(perf.subject_id)
        if subject:
            attendance, _, _ = get_student_attendance(perf.student_id, perf.subject_id, perf.semester)
            grade = calculate_grade(perf.final_internal)
            risk = calculate_risk_status(attendance, perf.final_internal)
            
            performance_data.append({
                'id': perf.id,
                'subject': subject,
                'internal1': perf.internal1,
                'internal2': perf.internal2,
                'seminar': perf.seminar,
                'assessment': perf.assessment,
                'total_marks': perf.total_marks,
                'final_marks': perf.final_internal,
                'grade': grade,
                'risk_status': risk,
                'attendance_percentage': attendance,
                'semester': perf.semester
            })
            
            # Generate suggestion
            if perf.final_internal >= 18:
                suggestion = "Excellent performance! Keep it up!"
            elif perf.final_internal >= 15:
                needed = 18 - perf.final_internal
                suggestion = f"Need {needed:.1f} more marks to reach A+ grade."
            elif perf.final_internal >= 12:
                needed = 15 - perf.final_internal
                suggestion = f"Need {needed:.1f} more marks to reach A grade."
            elif perf.final_internal >= 10:
                needed = 12 - perf.final_internal
                suggestion = f"Need {needed:.1f} more marks to reach B grade."
            else:
                needed = 10 - perf.final_internal
                suggestion = f"CRITICAL: Need {needed:.1f} more marks to pass!"
            
            if attendance < 70:
                suggestion += f" Attendance is {attendance}% (below 70%) - Penalty applied!"
            
            suggestions.append({
                'subject': subject.name,
                'marks': perf.final_internal,
                'attendance': attendance,
                'suggestion': suggestion
            })
    
    return render_template('teacher/student_detail.html',
                         student=student,
                         performances=performance_data,
                         suggestions=suggestions)

# =====================================================
# ATTENDANCE MANAGEMENT
# =====================================================

@teacher_bp.route('/attendance')
@login_required
@teacher_required
def attendance():
    """Attendance overview page with subject selection"""
    assignments = TeacherSubject.query.filter_by(
        teacher_id=current_user.id,
        is_active=True
    ).all()
    
    # Group by semester/year
    subjects_by_year = {
        '1st Year': [],
        '2nd Year': [],
        '3rd Year': [],
        '4th Year': []
    }
    
    for assignment in assignments:
        subject = Subject.query.get(assignment.subject_id)
        if subject:
            semester = Semester.query.get(subject.semester_id)
            semester_number = semester.semester_number if semester else subject.semester_id
            
            subject_info = {
                'id': subject.id,
                'name': subject.name,
                'code': subject.code,
                'semester': semester_number,
                'assignment_id': assignment.id
            }
            
            if semester_number <= 2:
                subjects_by_year['1st Year'].append(subject_info)
            elif semester_number <= 4:
                subjects_by_year['2nd Year'].append(subject_info)
            elif semester_number <= 6:
                subjects_by_year['3rd Year'].append(subject_info)
            else:
                subjects_by_year['4th Year'].append(subject_info)
    
    return render_template('teacher/attendance_overview.html',
                         subjects_by_year=subjects_by_year)

@teacher_bp.route('/attendance/<int:subject_id>', methods=['GET', 'POST'])
@login_required
@teacher_required
def attendance_entry(subject_id):
    """Enter monthly attendance for students"""
    # Verify teacher is assigned to this subject
    assignment = TeacherSubject.query.filter_by(
        teacher_id=current_user.id,
        subject_id=subject_id,
        is_active=True
    ).first()
    
    if not assignment:
        flash('You are not authorized to access this subject', 'danger')
        return redirect(url_for('teacher.dashboard'))
    
    subject = Subject.query.get_or_404(subject_id)
    
    # Get semester number
    semester = Semester.query.get(subject.semester_id)
    semester_number = semester.semester_number if semester else subject.semester_id
    
    # Get current month and year
    now = datetime.now()
    current_month = now.month
    current_year = now.year
    
    # Get month from request or use current
    selected_month = request.args.get('month', current_month, type=int)
    selected_year = request.args.get('year', current_year, type=int)
    
    # Get students for this subject
    students = get_students_for_subject(subject_id)
    
    # Get existing attendance for selected month
    attendance_dict = {}
    for student in students:
        record = Attendance.query.filter_by(
            student_id=student.id,
            subject_id=subject_id,
            month=selected_month,
            year=selected_year
        ).first()
        attendance_dict[student.id] = record
    
    # Get months for dropdown
    months = []
    for i in range(1, 13):
        months.append({
            'number': i,
            'name': calendar.month_name[i]
        })
    
    years = [current_year, current_year + 1]
    
    if request.method == 'POST':
        return save_attendance(subject_id)
    
    return render_template('teacher/attendance.html',
                         subject=subject,
                         students=students,
                         attendance_dict=attendance_dict,
                         months=months,
                         years=years,
                         current_month=selected_month,
                         current_year=selected_year)

@teacher_bp.route('/attendance/save/<int:subject_id>', methods=['POST'])
@login_required
@teacher_required
def save_attendance(subject_id):
    """Save monthly attendance for students - NO PENALTY"""
    # Verify teacher is assigned to this subject
    assignment = TeacherSubject.query.filter_by(
        teacher_id=current_user.id,
        subject_id=subject_id,
        is_active=True
    ).first()
    
    if not assignment:
        return jsonify({'error': 'Unauthorized'}), 403
    
    subject = Subject.query.get_or_404(subject_id)
    
    # Get semester number
    semester = Semester.query.get(subject.semester_id)
    semester_number = semester.semester_number if semester else subject.semester_id
    
    # Get form data
    student_ids = request.form.getlist('student_id[]')
    total_classes = request.form.getlist('total_classes[]')
    attended_classes = request.form.getlist('attended_classes[]')
    month = int(request.form.get('month', datetime.now().month))
    year = int(request.form.get('year', datetime.now().year))
    
    success_count = 0
    errors = []
    
    for i, student_id in enumerate(student_ids):
        try:
            total = int(total_classes[i]) if total_classes[i] else 0
            attended = int(attended_classes[i]) if attended_classes[i] else 0
            
            # Validate
            if total <= 0:
                errors.append(f"Total classes must be > 0 for student")
                continue
            
            if attended < 0 or attended > total:
                errors.append(f"Attended classes must be between 0 and {total}")
                continue
            
            # Calculate percentage
            attendance_percent = int((attended / total) * 100)
            
            # Determine risk level based on attendance (NO PENALTY)
            if attendance_percent < 70:
                attendance_risk = 'Critical'
            elif attendance_percent < 75:
                attendance_risk = 'Average'
            else:
                attendance_risk = 'Safe'
            
            # Check for existing record
            existing = Attendance.query.filter_by(
                student_id=student_id,
                subject_id=subject_id,
                month=month,
                year=year
            ).first()
            
            if existing:
                existing.total_classes = total
                existing.attended_classes = attended
                existing.attendance_percentage = attendance_percent
                existing.penalty_amount = 0  # NO PENALTY
                existing.penalty_status = 'No Penalty'
                existing.updated_at = datetime.utcnow()
            else:
                attendance_record = Attendance(
                    student_id=student_id,
                    subject_id=subject_id,
                    teacher_id=current_user.id,
                    total_classes=total,
                    attended_classes=attended,
                    attendance_percentage=attendance_percent,
                    penalty_amount=0,  # NO PENALTY
                    penalty_status='No Penalty',
                    month=month,
                    year=year,
                    semester=semester_number
                )
                db.session.add(attendance_record)
            
            success_count += 1
            
        except (ValueError, TypeError) as e:
            errors.append(f"Invalid data: {str(e)}")
        except Exception as e:
            errors.append(f"Error: {str(e)}")
    
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'message': f'Saved attendance for {success_count} students',
            'errors': errors
        })
    
    flash(f'✅ Saved attendance for {success_count} students', 'success')
    if errors:
        for error in errors[:3]:
            flash(f'⚠️ {error}', 'warning')
    
    return redirect(url_for('teacher.attendance_report', subject_id=subject_id, month=month, year=year))

@teacher_bp.route('/attendance-report/<int:subject_id>')
@login_required
@teacher_required
def attendance_report(subject_id):
    """View attendance report based on marks entry data"""
    # Verify teacher is assigned to this subject
    assignment = TeacherSubject.query.filter_by(
        teacher_id=current_user.id,
        subject_id=subject_id,
        is_active=True
    ).first()
    
    if not assignment:
        flash('You are not authorized to access this subject', 'danger')
        return redirect(url_for('teacher.dashboard'))
    
    subject = Subject.query.get_or_404(subject_id)
    
    # Get semester number
    semester = Semester.query.get(subject.semester_id)
    semester_number = semester.semester_number if semester else subject.semester_id
    
    # Get students for this subject
    students = get_students_for_subject(subject_id)
    
    # Get academic year
    academic_year = AcademicYear.query.filter_by(is_current=True).first()
    
    # Get performance data (which contains attendance from marks entry)
    performance_dict = {}
    if academic_year:
        performances = StudentPerformance.query.filter_by(
            subject_id=subject_id,
            academic_year_id=academic_year.id
        ).all()
        
        for perf in performances:
            performance_dict[perf.student_id] = perf
    
    # Prepare display data
    display_data = []
    attendance_list = []
    
    for student in students:
        perf = performance_dict.get(student.id)
        if perf:
            display_data.append({
                'student': student,
                'attendance': perf.attendance,
                'marks': perf.final_internal,
                'has_data': True
            })
            attendance_list.append(perf.attendance)
        else:
            display_data.append({
                'student': student,
                'attendance': 0,
                'marks': 0,
                'has_data': False
            })
    
    # Calculate statistics
    avg_attendance = sum(attendance_list) / len(attendance_list) if attendance_list else 0
    critical_count = sum(1 for a in attendance_list if a < 70) if attendance_list else 0
    average_count = sum(1 for a in attendance_list if 70 <= a < 75) if attendance_list else 0
    safe_count = sum(1 for a in attendance_list if a >= 75) if attendance_list else 0
    
    # Get months for filter (from marks entry dates)
    months = []
    for i in range(1, 13):
        months.append({'number': i, 'name': calendar.month_name[i]})
    
    now = datetime.now()
    
    return render_template('teacher/attendance_report.html',
                         subject=subject,
                         display_data=display_data,
                         avg_attendance=round(avg_attendance, 1),
                         critical_count=critical_count,
                         average_count=average_count,
                         safe_count=safe_count,
                         total_students=len(students),
                         recorded_count=len(performance_dict),
                         months=months,
                         current_month=now.month,
                         current_year=now.year)

# =====================================================
# RISK ALERTS
# =====================================================

@teacher_bp.route('/risk-alerts')
@login_required
@teacher_required
def risk_alerts():
    """View all students with risk alerts"""
    # Get teacher's assigned subjects
    assignments = TeacherSubject.query.filter_by(
        teacher_id=current_user.id,
        is_active=True
    ).all()
    
    subject_ids = [a.subject_id for a in assignments]
    
    # Get all performances
    performances = StudentPerformance.query.filter(
        StudentPerformance.subject_id.in_(subject_ids)
    ).all()
    
    critical_list = []
    high_risk_list = []
    seen_students = set()
    
    for perf in performances:
        student = Student.query.get(perf.student_id)
        subject = Subject.query.get(perf.subject_id)
        
        if not student or not subject:
            continue
        
        # Avoid duplicates
        if student.id in seen_students:
            continue
        
        # Get attendance
        attendance, _, _ = get_student_attendance(student.id, subject.id, perf.semester)
        risk = calculate_risk_status(attendance, perf.final_internal)
        grade = calculate_grade(perf.final_internal)
        
        risk_item = {
            'student': student,
            'subject': subject,
            'marks': perf.final_internal,
            'attendance': attendance,
            'grade': grade,
            'risk': risk,
            'semester': perf.semester,
            'penalty': attendance < 70
        }
        
        if risk == 'Critical' or attendance < 70:
            critical_list.append(risk_item)
            seen_students.add(student.id)
        elif risk == 'Average':
            high_risk_list.append(risk_item)
            seen_students.add(student.id)
    
    # Sort by marks
    critical_list.sort(key=lambda x: x['marks'])
    high_risk_list.sort(key=lambda x: x['marks'])
    
    return render_template('teacher/risk_alerts.html',
                         critical=critical_list,
                         high_risk=high_risk_list,
                         total_critical=len(critical_list),
                         total_high=len(high_risk_list))

# =====================================================
# QUESTION PAPER MANAGEMENT
# =====================================================

@teacher_bp.route('/question-papers')
@login_required
@teacher_required
def question_papers():
    """View all question papers for teacher's subjects"""
    assignments = TeacherSubject.query.filter_by(
        teacher_id=current_user.id,
        is_active=True
    ).all()
    
    subject_ids = [a.subject_id for a in assignments]
    
    papers = QuestionPaper.query.filter(
        QuestionPaper.subject_id.in_(subject_ids),
        QuestionPaper.is_active == True
    ).order_by(QuestionPaper.uploaded_at.desc()).all()
    
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
    
    return render_template('teacher/question_papers.html',
                         papers_by_subject=papers_by_subject,
                         subjects=[Subject.query.get(sid) for sid in subject_ids])

@teacher_bp.route('/upload-question-paper/<int:subject_id>', methods=['GET', 'POST'])
@login_required
@teacher_required
def upload_question_paper(subject_id):
    """Upload a question paper for a subject"""
    assignment = TeacherSubject.query.filter_by(
        teacher_id=current_user.id,
        subject_id=subject_id,
        is_active=True
    ).first()
    
    if not assignment:
        flash('You are not authorized to upload papers for this subject', 'danger')
        return redirect(url_for('teacher.dashboard'))
    
    subject = Subject.query.get_or_404(subject_id)
    
    if request.method == 'POST':
        title = request.form.get('title')
        exam_type = request.form.get('exam_type')
        description = request.form.get('description')
        semester = request.form.get('semester', type=int)
        academic_year = request.form.get('academic_year')
        
        if 'question_paper' not in request.files:
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        file = request.files['question_paper']
        
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(request.url)
        
        # Validate file type
        allowed_extensions = {'pdf', 'doc', 'docx', 'txt'}
        if '.' not in file.filename or file.filename.split('.')[-1].lower() not in allowed_extensions:
            flash('Invalid file type. Allowed: PDF, DOC, DOCX, TXT', 'danger')
            return redirect(request.url)
        
        # Save file
        import os
        from werkzeug.utils import secure_filename
        
        upload_folder = os.path.join('static', 'uploads', 'question_papers')
        os.makedirs(upload_folder, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = secure_filename(f"{subject.code}_{exam_type}_{timestamp}.{file.filename.split('.')[-1]}")
        filepath = os.path.join(upload_folder, filename)
        
        file.save(filepath)
        file_size = os.path.getsize(filepath)
        
        if not academic_year:
            from datetime import date
            today = date.today()
            if today.month >= 6:
                academic_year = f"{today.year}-{today.year + 1}"
            else:
                academic_year = f"{today.year - 1}-{today.year}"
        
        paper = QuestionPaper(
            subject_id=subject_id,
            exam_type=exam_type,
            title=title,
            description=description,
            file_path=filepath.replace('\\', '/'),
            file_name=file.filename,
            file_size=file_size,
            uploaded_by=current_user.id,
            semester=semester or subject.semester_id,
            academic_year=academic_year,
            is_active=True
        )
        
        db.session.add(paper)
        db.session.commit()
        
        flash(f'✅ Question paper "{title}" uploaded successfully!', 'success')
        return redirect(url_for('teacher.question_papers'))
    
    current_year = datetime.now().year
    academic_years = [f"{current_year-1}-{current_year}", f"{current_year}-{current_year+1}"]
    
    return render_template('teacher/upload_question_paper.html',
                         subject=subject,
                         academic_years=academic_years,
                         exam_types=[
                             {'value': 'internal1', 'label': 'Internal Assessment I'},
                             {'value': 'internal2', 'label': 'Internal Assessment II'},
                             {'value': 'semester', 'label': 'Semester Exam'},
                             {'value': 'model', 'label': 'Model Exam'},
                             {'value': 'assignment', 'label': 'Assignment'},
                             {'value': 'quiz', 'label': 'Quiz'}
                         ])

@teacher_bp.route('/delete-question-paper/<int:paper_id>', methods=['POST'])
@login_required
@teacher_required
def delete_question_paper(paper_id):
    """Delete a question paper"""
    paper = QuestionPaper.query.get_or_404(paper_id)
    
    assignment = TeacherSubject.query.filter_by(
        teacher_id=current_user.id,
        subject_id=paper.subject_id,
        is_active=True
    ).first()
    
    if not assignment and paper.uploaded_by != current_user.id:
        flash('You are not authorized to delete this paper', 'danger')
        return redirect(url_for('teacher.question_papers'))
    
    try:
        import os
        if os.path.exists(paper.file_path):
            os.remove(paper.file_path)
        
        paper.is_active = False
        db.session.commit()
        
        flash('Question paper deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting paper: {str(e)}', 'danger')
    
    return redirect(url_for('teacher.question_papers'))

@teacher_bp.route('/download-question-paper/<int:paper_id>')
@login_required
@teacher_required
def download_question_paper(paper_id):
    """Download a question paper"""
    paper = QuestionPaper.query.get_or_404(paper_id)
    
    assignment = TeacherSubject.query.filter_by(
        teacher_id=current_user.id,
        subject_id=paper.subject_id,
        is_active=True
    ).first()
    
    if not assignment:
        flash('You are not authorized to download this paper', 'danger')
        return redirect(url_for('teacher.question_papers'))
    
    from flask import send_file
    import os
    
    if not os.path.exists(paper.file_path):
        flash('File not found', 'danger')
        return redirect(url_for('teacher.question_papers'))
    
    return send_file(
        paper.file_path,
        as_attachment=True,
        download_name=paper.file_name,
        mimetype='application/octet-stream'
    )

# =====================================================
# ADD NEW STUDENT
# =====================================================

@teacher_bp.route('/add-student', methods=['GET', 'POST'])
@login_required
@teacher_required
def add_student():
    """Add a new student to the department"""
    department = get_teacher_department()
    
    if not department:
        flash('Department not found', 'danger')
        return redirect(url_for('teacher.dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        semester = request.form.get('semester', type=int)
        batch_year = request.form.get('batch_year', type=int)
        
        if not all([name, email, semester, batch_year]):
            flash('All fields are required', 'danger')
            return redirect(url_for('teacher.add_student'))
        
        course = Course.query.filter_by(department_id=department.id).first()
        if not course:
            flash('No course found for department', 'danger')
            return redirect(url_for('teacher.add_student'))
        
        from utils.helpers import generate_registration_number, generate_student_id
        
        existing_students = Student.query.filter_by(
            department_id=department.id,
            admission_year=batch_year
        ).count()
        
        sequence = existing_students + 1
        
        reg_number = generate_registration_number(department.name, batch_year, sequence)
        student_id = generate_student_id(department.name, batch_year, sequence)
        username = f"{department.code.lower()}_stu{sequence}"
        password = "1234"
        
        if User.query.filter_by(username=username).first():
            flash(f'Username {username} already exists', 'danger')
            return redirect(url_for('teacher.add_student'))
        
        try:
            user = User(
                username=username,
                email=email,
                full_name=name,
                role='student',
                department=department.name,
                is_active=True,
                created_at=datetime.utcnow()
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            
            student = Student(
                registration_number=reg_number,
                student_id=student_id,
                name=name,
                email=email,
                phone=phone,
                user_id=user.id,
                course_id=course.id,
                department_id=department.id,
                admission_year=batch_year,
                admission_date=datetime(batch_year, 6, 15).date(),
                is_active=True,
                created_at=datetime.utcnow()
            )
            db.session.add(student)
            db.session.commit()
            
            flash(f'✅ Student {name} added successfully! Username: {username}, Password: {password}', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding student: {str(e)}', 'danger')
            print(f"ERROR adding student: {type(e).__name__}: {str(e)}")
        
        return redirect(url_for('teacher.all_students'))
    
    current_year = datetime.now().year
    return render_template('teacher/add_student.html',
                         department=department,
                         current_year=current_year)

# =====================================================
# API ENDPOINTS
# =====================================================

@teacher_bp.route('/api/calculate-marks', methods=['POST'])
@login_required
@teacher_required
def calculate_marks_api():
    """API endpoint for live marks calculation"""
    data = request.get_json()
    
    try:
        internal1 = int(data.get('internal1', 0))
        internal2 = int(data.get('internal2', 0))
        seminar = int(data.get('seminar', 0))
        assessment = int(data.get('assessment', 0))
        attendance = int(data.get('attendance', 0))
        
        if internal1 < 0 or internal1 > 70:
            return jsonify({'error': 'Internal 1 must be 0-70'}), 400
        if internal2 < 0 or internal2 > 70:
            return jsonify({'error': 'Internal 2 must be 0-70'}), 400
        if seminar < 0 or seminar > 10:
            return jsonify({'error': 'Seminar must be 0-10'}), 400
        if assessment < 0 or assessment > 10:
            return jsonify({'error': 'Assessment must be 0-10'}), 400
        
        total = internal1 + internal2 + seminar + assessment
        final = round((total / 160) * 20, 1)
        grade = calculate_grade(final)
        risk = calculate_risk_status(attendance, final)
        
        return jsonify({
            'total': total,
            'final': final,
            'grade': grade,
            'risk': risk
        })
        
    except ValueError:
        return jsonify({'error': 'Invalid integers'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@teacher_bp.route('/api/attendance-stats/<int:subject_id>')
@login_required
@teacher_required
def attendance_stats(subject_id):
    """API endpoint for attendance statistics"""
    subject = Subject.query.get_or_404(subject_id)
    
    records = Attendance.query.filter_by(
        subject_id=subject_id
    ).all()
    
    monthly_data = {}
    for record in records:
        key = f"{record.month}-{record.year}"
        if key not in monthly_data:
            monthly_data[key] = {'total': 0, 'count': 0}
        monthly_data[key]['total'] += record.attendance_percentage
        monthly_data[key]['count'] += 1
    
    labels = []
    data = []
    
    for key, value in monthly_data.items():
        month, year = key.split('-')
        month_name = calendar.month_abbr[int(month)]
        labels.append(f"{month_name} {year}")
        data.append(round(value['total'] / value['count'], 1))
    
    return jsonify({
        'labels': labels,
        'averages': data
    })

@teacher_bp.route('/api/attendance-summary/<int:subject_id>')
@login_required
@teacher_required
def attendance_summary(subject_id):
    """API endpoint for attendance summary chart"""
    subject = Subject.query.get_or_404(subject_id)
    
    records = Attendance.query.filter_by(
        subject_id=subject_id
    ).order_by(Attendance.year, Attendance.month).all()
    
    monthly_data = {}
    for record in records:
        key = f"{record.year}-{record.month:02d}"
        if key not in monthly_data:
            monthly_data[key] = {'total': 0, 'count': 0, 'month': record.month, 'year': record.year}
        monthly_data[key]['total'] += record.attendance_percentage
        monthly_data[key]['count'] += 1
    
    labels = []
    averages = []
    
    sorted_months = sorted(monthly_data.keys())
    for key in sorted_months:
        data = monthly_data[key]
        month_name = calendar.month_abbr[data['month']]
        labels.append(f"{month_name} {data['year']}")
        averages.append(round(data['total'] / data['count'], 1))
    
    return jsonify({
        'labels': labels,
        'averages': averages
    })

@teacher_bp.route('/api/marks-progress/<int:subject_id>')
@login_required
@teacher_required
def marks_progress_api(subject_id):
    """API endpoint for marks entry progress"""
    stats = get_marks_entry_stats(subject_id)
    return jsonify(stats)

# =====================================================
# DEBUG ROUTES
# =====================================================

@teacher_bp.route('/debug/check-subject/<int:subject_id>')
@login_required
@teacher_required
def debug_check_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    
    students = get_students_for_subject(subject_id)
    performances = StudentPerformance.query.filter_by(subject_id=subject_id).all()
    
    html = f"""
    <h2>Subject: {subject.name} (ID: {subject.id})</h2>
    <p>Department ID: {subject.department_id}</p>
    <p>Semester ID: {subject.semester_id}</p>
    
    <h3>Students in this Department/Semester: {len(students)}</h3>
    <ul>
    """
    for s in students:
        html += f"<li>{s.name} (ID: {s.id}, Sem: {s.current_semester})</li>"
    
    html += f"</ul><h3>Performance Records: {len(performances)}</h3><ul>"
    for p in performances:
        student = Student.query.get(p.student_id)
        html += f"<li>Student {student.name if student else p.student_id}: Marks {p.final_internal}/20, Attendance {p.attendance}%</li>"
    
    html += "</ul>"
    return html


@teacher_bp.route('/notifications')
@login_required
@teacher_required
def notifications_page():
    """Teacher notifications page"""
    return render_template('teacher/notifications.html')