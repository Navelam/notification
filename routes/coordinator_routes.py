"""
COMPLETE COORDINATOR EXAM TIMETABLE SYSTEM
All academic logic integrated directly - No external config files
"""

import random
import math
from datetime import datetime, timedelta, date
from flask import Blueprint, render_template, flash, redirect, url_for, request, session, jsonify
from flask_login import login_required, current_user
from flask_wtf.csrf import generate_csrf
from functools import wraps
from extensions import db, csrf
from model import (
    User, Department, Subject, ExamTimetable, 
    ExamRoomAllocation, SeatingArrangement, Student,
    InvigilatorAssignment, Notification, Semester, Course, AcademicYear, UserNotification
)

coordinator_bp = Blueprint('coordinator', __name__, url_prefix='/coordinator')

def coordinator_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'coordinator':
            flash('Access denied. Coordinator privileges required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@coordinator_bp.context_processor
def utility_processor():
    """Make CSRF token available to all templates"""
    return {
        'now': datetime.now(),
        'csrf_token': generate_csrf
    }

# =====================================================
# PART 1 — ACADEMIC STRUCTURE (Integrated)
# =====================================================

# Academic Structure: 4 Years, 8 Semesters
ACADEMIC_STRUCTURE = {
    1: {"year": 1, "semester_type": "Odd", "display": "Year 1 - Odd (Sem 1)"},
    2: {"year": 1, "semester_type": "Even", "display": "Year 1 - Even (Sem 2)"},
    3: {"year": 2, "semester_type": "Odd", "display": "Year 2 - Odd (Sem 3)"},
    4: {"year": 2, "semester_type": "Even", "display": "Year 2 - Even (Sem 4)"},
    5: {"year": 3, "semester_type": "Odd", "display": "Year 3 - Odd (Sem 5)"},
    6: {"year": 3, "semester_type": "Even", "display": "Year 3 - Even (Sem 6)"},
    7: {"year": 4, "semester_type": "Odd", "display": "Year 4 - Odd (Sem 7)"},
    8: {"year": 4, "semester_type": "Even", "display": "Year 4 - Even (Sem 8)"}
}

# All 7 Departments with their codes
ALL_DEPARTMENTS = [
    {"name": "Computer Science", "code": "CS"},
    {"name": "Computer Applications", "code": "CA"},
    {"name": "Commerce Finance", "code": "CF"},
    {"name": "Commerce Co-op", "code": "CC"},
    {"name": "English", "code": "EN"},
    {"name": "Economics", "code": "EC"},
    {"name": "History", "code": "HY"}
]

# Department codes mapping
DEPT_CODE_MAP = {
    "Computer Science": "CS",
    "Computer Applications": "CA",
    "Commerce Finance": "CF",
    "Commerce Co-op": "CC",
    "English": "EN",
    "Economics": "EC",
    "History": "HY"
}

# Complete subject data for all departments (Semesters 1-8)
DEPARTMENT_SUBJECTS = {
    "Computer Science": {
        1: ["Mathematics I", "Physics", "Chemistry", "C Programming", "English"],
        2: ["Mathematics II", "Digital Logic", "Data Structures", "Object Oriented Programming", "Environmental Science"],
        3: ["Discrete Mathematics", "Database Management Systems", "Computer Organization", "Operating Systems", "Soft Skills"],
        4: ["Computer Networks", "Design and Analysis of Algorithms", "Software Engineering", "Web Technologies", "Python Programming"],
        5: ["Compiler Design", "Distributed Systems", "Machine Learning", "Cloud Computing", "Elective I"],
        6: ["Big Data Analytics", "Internet of Things", "Cyber Security", "Elective II", "Project Work"],
        7: ["Artificial Intelligence", "Natural Language Processing", "Computer Vision", "Elective III", "Major Project I"],
        8: ["Deep Learning", "Blockchain", "Quantum Computing", "Elective IV", "Major Project II"]
    },
    "Computer Applications": {
        1: ["Mathematics I", "Digital Computer Fundamentals", "C Programming", "Financial Accounting", "English"],
        2: ["Mathematics II", "Data Structures", "Database Systems", "Object Oriented Programming with C++", "Organizational Behavior"],
        3: ["Operating Systems", "Computer Networks", "Java Programming", "Web Design", "Python Programming"],
        4: ["Software Engineering", "PHP Programming", "Data Mining", "Cloud Computing", "Mobile Application Development"],
        5: ["Machine Learning", "Big Data", "Cyber Security", "Elective I", "Mini Project"],
        6: ["Deep Learning", "Blockchain", "Elective II", "Major Project", "Internship"],
        7: ["Advanced Java", "Python for Data Science", "React Programming", "Elective III", "Industry Project"],
        8: ["DevOps", "Microservices", "Cloud Architecture", "Elective IV", "Research Project"]
    },
    "Commerce Finance": {
        1: ["Financial Accounting I", "Business Economics", "Business Mathematics", "Business Communication", "Computer Applications"],
        2: ["Financial Accounting II", "Corporate Accounting", "Business Statistics", "Banking Theory", "Marketing Management"],
        3: ["Advanced Accounting", "Cost Accounting", "Income Tax I", "Company Law", "Financial Management"],
        4: ["Management Accounting", "Income Tax II", "Auditing", "International Finance", "Investment Management"],
        5: ["Financial Services", "Derivatives Markets", "Risk Management", "Strategic Management", "Elective I"],
        6: ["Portfolio Management", "Mergers and Acquisitions", "Financial Modeling", "Elective II", "Project"],
        7: ["International Finance", "Corporate Governance", "Financial Derivatives", "Elective III", "Research Project"],
        8: ["Wealth Management", "Behavioral Finance", "Financial Analytics", "Elective IV", "Industry Project"]
    },
    "Commerce Co-op": {
        1: ["Co-operative Theory", "Principles of Economics", "Business Organization", "Financial Accounting", "English"],
        2: ["Co-operative Law", "Banking Theory", "Business Mathematics", "Corporate Accounting", "Hindi"],
        3: ["Co-operative Management", "Rural Economics", "Cost Accounting", "Marketing Management", "Human Resource Management"],
        4: ["Co-operative Credit", "Agricultural Economics", "Income Tax", "Auditing", "Entrepreneurship Development"],
        5: ["Co-operative Marketing", "International Trade", "Financial Services", "Research Methodology", "Elective I"],
        6: ["Co-operative Accounting", "Project Planning", "Co-operative Development", "Elective II", "Project Work"],
        7: ["Co-operative Banking", "Micro Finance", "Rural Development", "Elective III", "Field Study"],
        8: ["Co-operative Management", "Co-operative Legislation", "Co-operative Audit", "Elective IV", "Internship"]
    },
    "English": {
        1: ["British Poetry", "Prose", "English Grammar", "History of English Literature I", "Indian Writing in English"],
        2: ["British Drama", "Fiction", "Linguistics", "History of English Literature II", "American Literature"],
        3: ["Shakespeare", "Literary Criticism", "Phonetics", "Postcolonial Literature", "Women's Writing"],
        4: ["Modern Poetry", "Modern Drama", "Modern Fiction", "English Language Teaching", "Translation Studies"],
        5: ["European Literature", "Canadian Literature", "Film Studies", "Cultural Studies", "Elective I"],
        6: ["Comparative Literature", "Diasporic Literature", "New Literatures", "Elective II", "Project"],
        7: ["World Literature", "Literary Theory", "Creative Writing", "Elective III", "Research Paper"],
        8: ["Postmodern Literature", "Eco Criticism", "Digital Humanities", "Elective IV", "Dissertation"]
    },
    "Economics": {
        1: ["Microeconomics I", "Macroeconomics I", "Mathematics for Economics", "Indian Economy", "English"],
        2: ["Microeconomics II", "Macroeconomics II", "Statistics for Economics", "Monetary Economics", "Environmental Studies"],
        3: ["Development Economics", "International Economics", "Public Economics", "Econometrics I", "Agricultural Economics"],
        4: ["Labour Economics", "Industrial Economics", "Health Economics", "Econometrics II", "Research Methodology"],
        5: ["Financial Economics", "Behavioral Economics", "Urban Economics", "Gender Economics", "Elective I"],
        6: ["Political Economy", "Energy Economics", "Economic Thought", "Elective II", "Project"],
        7: ["Environmental Economics", "Transport Economics", "Welfare Economics", "Elective III", "Policy Analysis"],
        8: ["Game Theory", "Experimental Economics", "Development Policy", "Elective IV", "Thesis"]
    },
    "History": {
        1: ["History of India I", "History of Tamil Nadu I", "World History I", "History of Europe I", "English"],
        2: ["History of India II", "History of Tamil Nadu II", "World History II", "History of Europe II", "Constitutional History"],
        3: ["History of India III", "History of Tamil Nadu III", "History of USA", "History of Russia", "History of East Asia"],
        4: ["History of India IV", "History of Tamil Nadu IV", "History of UK", "History of France", "Historiography"],
        5: ["History of South East Asia", "History of West Asia", "History of Africa", "Archaeology", "Elective I"],
        6: ["History of Science", "History of Art", "Museology", "Elective II", "Project"],
        7: ["Medieval India", "Colonial India", "Freedom Movement", "Elective III", "Research Methods"],
        8: ["Modern India", "Contemporary History", "Historical Tourism", "Elective IV", "Dissertation"]
    }
}

# =====================================================
# ROOM ALLOCATION CONSTANTS
# =====================================================

ROOM_BLOCKS = ['A', 'B', 'C', 'D', 'E', 'F']
ROOMS_PER_BLOCK = 15
ROOM_CAPACITY = 20

def generate_room_list():
    """Generate all room numbers A101-F115"""
    rooms = []
    for block in ROOM_BLOCKS:
        for room_num in range(101, 101 + ROOMS_PER_BLOCK):
            rooms.append(f"{block}{room_num}")
    return rooms

ALL_ROOMS = generate_room_list()

# =====================================================
# NOTIFICATION HELPER FUNCTIONS
# =====================================================

def create_notification_helper(title, message, notification_type, target_role, user_id=None, end_date=None):
    """Create a notification in the database"""
    try:
        if end_date is None:
            end_date = date(date.today().year, 12, 31)
        
        # IMPORTANT: Map UI values to database values
        role_mapping = {
            # If form sends plural, map to singular
            'students': 'student',
            'teachers': 'teacher',
            'hods': 'hod',
            'coordinators': 'coordinator',
            'principals': 'principal',
            # Keep these as is
            'student': 'student',
            'teacher': 'teacher',
            'hod': 'hod',
            'coordinator': 'coordinator',
            'principal': 'principal',
            'all': 'all',
            'public': 'public'
        }
        
        # Get the correct database role value
        db_target_role = role_mapping.get(target_role, target_role)
        
        notification = Notification(
            title=title,
            message=message,
            notification_type=notification_type,
            target_role=db_target_role,
            user_id=user_id,
            start_date=date.today(),
            end_date=end_date,
            created_by=current_user.id if current_user.is_authenticated else 1,
            is_active=True,
            is_read=False,  # This is the global read flag, not per-user
            created_at=datetime.utcnow()
        )
        db.session.add(notification)
        db.session.flush()  # Get notification.id
        
        # If it's for a specific user, create UserNotification record
        if user_id:
            user_notification = UserNotification(
                user_id=user_id,
                notification_id=notification.id,
                is_read=False,
                created_at=datetime.utcnow()
            )
            db.session.add(user_notification)
        else:
            # For role-based notifications, we'll create UserNotification records
            # when users first view them (lazy creation) to avoid creating millions of records
            pass
        
        db.session.commit()
        print(f" Notification created: {title} for role: {db_target_role}")
        return notification
        
    except Exception as e:
        db.session.rollback()
        print(f" Error creating notification: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def notify_exam_timetable_published(academic_year, semester_info):
    """Create notification when exam timetable is published"""
    return create_notification_helper(
    title='📅 Exam Timetable Published',
    message=f'Exam timetable for {academic_year} ({semester_info}) has been published.',
    notification_type='timetable',
    target_role='all'
)

def notify_room_allocation_completed(exam_date):
    """Create notification when room allocation is completed"""
    return create_notification_helper(
    title='🏢 Room Allocation Completed',
    message=f'Room allocation for exams on {exam_date} has been completed.',
    notification_type='room',
    target_role='all'
)

def notify_invigilator_assigned(teacher_id, teacher_name, exam_date, room_number, exam_time):
    """Create notification when invigilator is assigned"""
    return create_notification_helper(
    title='👨‍🏫 Invigilation Duty Assigned',
    message=f'You have been assigned as invigilator for Room {room_number} on {exam_date} at {exam_time}.',
    notification_type='invigilation',
    target_role='teachers',
    user_id=teacher_id,
    end_date=exam_date
)

# =====================================================
# PART 2 — SEMESTER LOGIC
# =====================================================

def get_allowed_semesters():
    """
    Based on current month:
    - June to November: Allow odd semesters (1,3,5,7)
    - December to April: Allow even semesters (2,4,6,8)
    - May: Transition month (both allowed)
    """
    current_month = datetime.now().month
    
    if 6 <= current_month <= 11:  # June to November
        return [1, 3, 5, 7], "ODD", "Odd Semesters (1,3,5,7)"
    elif current_month == 12 or 1 <= current_month <= 4:  # December to April
        return [2, 4, 6, 8], "EVEN", "Even Semesters (2,4,6,8)"
    else:  # May (transition)
        return [1, 2, 3, 4, 5, 6, 7, 8], "FULL", "All Semesters (1-8)"

def get_semesters_from_cycle(cycle):
    """Get semesters based on cycle selection"""
    if cycle == 'ODD':
        return [1, 3, 5, 7]
    elif cycle == 'EVEN':
        return [2, 4, 6, 8]
    else:
        return [1, 2, 3, 4, 5, 6, 7, 8]

def get_semester_display(cycle):
    """Get display text for semester cycle"""
    if cycle == 'ODD':
        return "Odd Semesters (1,3,5,7)"
    elif cycle == 'EVEN':
        return "Even Semesters (2,4,6,8)"
    else:
        return "All Semesters (1-8)"

# =====================================================
# ACADEMIC SETUP FUNCTIONS
# =====================================================

def generate_subject_code(dept_name, semester, index):
    """Generate subject code like CS0101, CA0203, etc."""
    dept_code = DEPT_CODE_MAP.get(dept_name, "XX")
    return f"{dept_code}{semester:02d}{index:02d}"

def get_or_create_academic_year():
    """Get or create current academic year"""
    today = date.today()
    if today.month >= 6:
        start_year = today.year
        end_year = today.year + 1
    else:
        start_year = today.year - 1
        end_year = today.year
    
    year_str = f"{start_year}-{end_year}"
    
    academic_year = AcademicYear.query.filter_by(year=year_str).first()
    if not academic_year:
        academic_year = AcademicYear(
            year=year_str,
            start_date=date(start_year, 6, 1),
            end_date=date(end_year, 4, 30),
            is_current=True
        )
        db.session.add(academic_year)
        db.session.flush()
    return academic_year

def get_or_create_course(dept):
    """Get or create course for department"""
    course_code = f"{dept.code}_PROG"
    course = Course.query.filter_by(code=course_code).first()
    if not course:
        course = Course(
            name=f"{dept.name} Program",
            code=course_code,
            duration_years=4,
            department_id=dept.id
        )
        db.session.add(course)
        db.session.flush()
    return course

def get_or_create_semester(course, semester_num, academic_year):
    """Get or create semester"""
    semester = Semester.query.filter_by(
        semester_number=semester_num,
        course_id=course.id,
        academic_year_id=academic_year.id
    ).first()
    
    if not semester:
        if semester_num % 2 == 1:  # Odd semester (1,3,5,7)
            start_date = date(academic_year.start_date.year, 6, 1)
            end_date = date(academic_year.start_date.year, 11, 30)
        else:  # Even semester (2,4,6,8)
            start_date = date(academic_year.start_date.year + 1, 1, 2)
            end_date = date(academic_year.start_date.year + 1, 4, 30)
        
        semester = Semester(
            semester_number=semester_num,
            course_id=course.id,
            academic_year_id=academic_year.id,
            start_date=start_date,
            end_date=end_date
        )
        db.session.add(semester)
        db.session.flush()
    return semester

def setup_academic_structure():
    """
    Initialize the academic structure:
    - Create all departments
    - Create all subjects for all semesters
    """
    created_depts = 0
    created_subjects = 0
    
    try:
        # Create departments
        for dept_data in ALL_DEPARTMENTS:
            dept = Department.query.filter_by(code=dept_data['code']).first()
            if not dept:
                dept = Department(
                    name=dept_data['name'],
                    code=dept_data['code']
                )
                db.session.add(dept)
                db.session.flush()
                created_depts += 1
        
        db.session.commit()
        
        # Get academic year
        academic_year = get_or_create_academic_year()
        
        # Create subjects for each department
        for dept_name, semesters in DEPARTMENT_SUBJECTS.items():
            dept = Department.query.filter_by(name=dept_name).first()
            if not dept:
                continue
            
            course = get_or_create_course(dept)
            
            for semester_num, subjects in semesters.items():
                semester = get_or_create_semester(course, semester_num, academic_year)
                
                for idx, subject_name in enumerate(subjects, 1):
                    subject_code = generate_subject_code(dept_name, semester_num, idx)
                    
                    existing = Subject.query.filter_by(code=subject_code).first()
                    if not existing:
                        subject = Subject(
                            name=subject_name,
                            code=subject_code,
                            credits=4,
                            department_id=dept.id,
                            semester_id=semester.id
                        )
                        db.session.add(subject)
                        created_subjects += 1
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        raise e
    
    return created_depts, created_subjects

# =====================================================
# HELPER FUNCTIONS
# =====================================================

def get_academic_years():
    """Generate list of academic years (current ± 5 years)"""
    current_year = datetime.now().year
    years = []
    for i in range(-2, 6):
        start = current_year + i
        end = start + 1
        years.append(f"{start}-{end}")
    return years

def get_date_range_dates(start_date, end_date):
    """Get list of dates between start and end (inclusive)"""
    date_list = []
    current = start_date
    while current <= end_date:
        date_list.append(current)
        current += timedelta(days=1)
    return date_list

def get_available_dates(start_date, end_date, exclude_sundays=True):
    """Get list of available dates (excluding Sundays if specified)"""
    date_list = []
    current = start_date
    while current <= end_date:
        if not exclude_sundays or current.weekday() != 6:  # 6 = Sunday
            date_list.append(current)
        current += timedelta(days=1)
    return date_list

def validate_date_range(start_date, end_date):
    """Validate that date range is reasonable"""
    if start_date > end_date:
        return False, "Start date must be before end date"
    
    days_diff = (end_date - start_date).days
    if days_diff > 60:  # Max 60 days
        return False, "Date range too long (max 60 days)"
    
    if days_diff < 7:  # Min 7 days
        return False, "Date range too short (min 7 days)"
    
    return True, "Valid"

def check_conflict(department_id, exam_date, exam_time):
    """
    PART 5 — VALIDATION
    Prevent duplicate department on same date and time
    """
    existing = ExamTimetable.query.filter_by(
        department_id=department_id,
        exam_date=exam_date,
        exam_time=exam_time
    ).first()
    
    return existing is not None

def check_duplicate_subject(subject_id, academic_year):
    """Prevent duplicate subject in same academic year"""
    existing = ExamTimetable.query.filter_by(
        subject_id=subject_id,
        academic_year=academic_year
    ).first()
    return existing is not None

def save_exam(subject, exam_date, exam_time, academic_year, exam_cycle):
    """Save exam to database with validation"""
    # Check for conflicts
    if check_conflict(subject.department_id, exam_date, exam_time):
        return False, f"Department already has exam on {exam_date} at {exam_time}"
    
    if check_duplicate_subject(subject.id, academic_year):
        return False, f"Subject '{subject.name}' already scheduled for {academic_year}"
    
    exam = ExamTimetable(
        department_id=subject.department_id,
        semester=subject.semester_id,
        subject_id=subject.id,
        exam_date=exam_date,
        exam_time=exam_time,
        academic_year=academic_year,
        exam_cycle=exam_cycle,
        created_by=current_user.id,
        status='Generated'
    )
    db.session.add(exam)
    return True, "Success"

def setup_academic_structure():
    """
    Initialize the academic structure:
    - Create all departments
    - Create all subjects for all semesters
    """
    created_depts = 0
    created_subjects = 0
    
    try:
        # Create departments
        for dept_data in ALL_DEPARTMENTS:
            dept = Department.query.filter_by(code=dept_data['code']).first()
            if not dept:
                dept = Department(
                    name=dept_data['name'],
                    code=dept_data['code']
                )
                db.session.add(dept)
                db.session.flush()
                created_depts += 1
        
        db.session.commit()
        
        # Get academic year
        academic_year = get_or_create_academic_year()
        
        # Create subjects for each department
        for dept_name, semesters in DEPARTMENT_SUBJECTS.items():
            dept = Department.query.filter_by(name=dept_name).first()
            if not dept:
                continue
            
            course = get_or_create_course(dept)
            
            for semester_num, subjects in semesters.items():
                semester = get_or_create_semester(course, semester_num, academic_year)
                
                for idx, subject_name in enumerate(subjects, 1):
                    subject_code = generate_subject_code(dept_name, semester_num, idx)
                    
                    existing = Subject.query.filter_by(code=subject_code).first()
                    if not existing:
                        subject = Subject(
                            name=subject_name,
                            code=subject_code,
                            credits=4,
                            department_id=dept.id,
                            semester_id=semester.id
                        )
                        db.session.add(subject)
                        created_subjects += 1
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        raise e
    
    return created_depts, created_subjects

# =====================================================
# HELPER FUNCTIONS
# =====================================================

def get_academic_years():
    """Generate list of academic years (current ± 5 years)"""
    current_year = datetime.now().year
    years = []
    for i in range(-2, 6):
        start = current_year + i
        end = start + 1
        years.append(f"{start}-{end}")
    return years

def get_date_range_dates(start_date, end_date):
    """Get list of dates between start and end (inclusive)"""
    date_list = []
    current = start_date
    while current <= end_date:
        date_list.append(current)
        current += timedelta(days=1)
    return date_list

def get_available_dates(start_date, end_date, exclude_sundays=True):
    """Get list of available dates (excluding Sundays if specified)"""
    date_list = []
    current = start_date
    while current <= end_date:
        if not exclude_sundays or current.weekday() != 6:  # 6 = Sunday
            date_list.append(current)
        current += timedelta(days=1)
    return date_list

def validate_date_range(start_date, end_date):
    """Validate that date range is reasonable"""
    if start_date > end_date:
        return False, "Start date must be before end date"
    
    days_diff = (end_date - start_date).days
    if days_diff > 60:  # Max 60 days
        return False, "Date range too long (max 60 days)"
    
    if days_diff < 7:  # Min 7 days
        return False, "Date range too short (min 7 days)"
    
    return True, "Valid"

def check_conflict(department_id, exam_date, exam_time):
    """
    PART 5 — VALIDATION
    Prevent duplicate department on same date and time
    """
    existing = ExamTimetable.query.filter_by(
        department_id=department_id,
        exam_date=exam_date,
        exam_time=exam_time
    ).first()
    
    return existing is not None

def check_duplicate_subject(subject_id, academic_year):
    """Prevent duplicate subject in same academic year"""
    existing = ExamTimetable.query.filter_by(
        subject_id=subject_id,
        academic_year=academic_year
    ).first()
    return existing is not None

def save_exam(subject, exam_date, exam_time, academic_year, exam_cycle):
    """Save exam to database with validation"""
    # Check for conflicts
    if check_conflict(subject.department_id, exam_date, exam_time):
        return False, f"Department already has exam on {exam_date} at {exam_time}"
    
    if check_duplicate_subject(subject.id, academic_year):
        return False, f"Subject '{subject.name}' already scheduled for {academic_year}"
    
    exam = ExamTimetable(
        department_id=subject.department_id,
        semester=subject.semester_id,
        subject_id=subject.id,
        exam_date=exam_date,
        exam_time=exam_time,
        academic_year=academic_year,
        exam_cycle=exam_cycle,
        created_by=current_user.id,
        status='Generated'
    )
    db.session.add(exam)
    return True, "Success"

def allocate_session(date_obj, exam_time, students):
    """Helper function to allocate rooms for a specific session"""
    total_students = len(students)
    rooms_needed = (total_students + ROOM_CAPACITY - 1) // ROOM_CAPACITY
    
    if rooms_needed > len(ALL_ROOMS):
        rooms_needed = len(ALL_ROOMS)
        students = students[:rooms_needed * ROOM_CAPACITY]
    
    student_idx = 0
    rooms_created = 0
    
    for room_idx in range(rooms_needed):
        room_number = ALL_ROOMS[room_idx]
        block = room_number[0]
        
        students_in_room = []
        for seat in range(1, ROOM_CAPACITY + 1):
            if student_idx < len(students):
                students_in_room.append({
                    'student': students[student_idx],
                    'seat': seat
                })
                student_idx += 1
        
        if not students_in_room:
            continue
        
        room = ExamRoomAllocation(
            exam_date=date_obj,
            exam_time=exam_time,
            block=block,
            room_number=room_number,
            capacity=ROOM_CAPACITY,
            total_students=len(students_in_room),
            created_by=current_user.id
        )
        db.session.add(room)
        db.session.flush()
        rooms_created += 1
        
        for item in students_in_room:
            seating = SeatingArrangement(
                room_allocation_id=room.id,
                exam_date=date_obj,
                exam_time=exam_time,
                block=block,
                room_number=room_number,
                seat_number=item['seat'],
                student_id=item['student'].id,
                reg_number=item['student'].registration_number,
                student_name=item['student'].name,
                department=item['student'].department.name
            )
            db.session.add(seating)
        
        db.session.commit()
    
    return rooms_created

def get_all_departments_from_helpers():
    """
    Get all 7 departments in the exact order
    """
    departments_list = []
    
    for dept_data in ALL_DEPARTMENTS:
        dept = Department.query.filter_by(name=dept_data['name']).first()
        if dept:
            exam_count = ExamTimetable.query.filter_by(department_id=dept.id).count()
            subject_count = Subject.query.filter_by(department_id=dept.id).count()
            
            departments_list.append({
                'id': dept.id,
                'name': dept.name,
                'code': dept.code,
                'exam_count': exam_count,
                'subject_count': subject_count
            })
    
    return departments_list

# =====================================================
# ACADEMIC SETUP ROUTES
# =====================================================

@coordinator_bp.route('/academic-setup')
@login_required
@coordinator_required
def academic_setup():
    """Academic setup page"""
    try:
        # Check current status
        dept_count = Department.query.count()
        subject_count = Subject.query.count()
        semester_count = Semester.query.count()
        course_count = Course.query.count()
        
        status = {
            'departments': dept_count,
            'subjects': subject_count,
            'semesters': semester_count,
            'courses': course_count,
            'has_data': dept_count > 0 and subject_count > 0,
            'expected_departments': len(ALL_DEPARTMENTS),
            'expected_subjects': sum(len(sem_subjects) for dept in DEPARTMENT_SUBJECTS.values() for sem_subjects in dept.values())
        }
        
        return render_template('coordinator/academic_setup.html', status=status)
    except Exception as e:
        flash(f'Error loading academic setup: {str(e)}', 'danger')
        return redirect(url_for('coordinator.dashboard'))

@coordinator_bp.route('/run-academic-setup', methods=['POST'])
@login_required
@coordinator_required
@csrf.exempt
def run_academic_setup():
    """Run complete academic setup"""
    try:
        dept_count, subject_count = setup_academic_structure()
        
        flash(f'✅ Academic setup complete! Created/verified {dept_count} departments and {subject_count} subjects.', 'success')
        
        # Create notification
        create_notification_helper(
    title='🎓 Academic Structure Initialized',
    message='All departments and subjects have been set up successfully.',
    notification_type='general',
    target_role='all'
)
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error during academic setup: {str(e)}', 'danger')
    
    return redirect(url_for('coordinator.academic_setup'))

# =====================================================
# ONE-CLICK INITIAL SETUP ROUTE (CRITICAL FIX!)
# =====================================================

@coordinator_bp.route('/run-initial-setup')
@login_required
@coordinator_required
def run_initial_setup():
    """One-click initial setup to create all academic data"""
    try:
        from datetime import date
        
        # Create all 7 departments
        dept_count = 0
        for dept_data in ALL_DEPARTMENTS:
            dept = Department.query.filter_by(code=dept_data['code']).first()
            if not dept:
                dept = Department(name=dept_data['name'], code=dept_data['code'])
                db.session.add(dept)
                dept_count += 1
        db.session.commit()
        
        # Create academic year
        today = date.today()
        if today.month >= 6:
            start_year = today.year
            end_year = today.year + 1
        else:
            start_year = today.year - 1
            end_year = today.year
        
        year_str = f"{start_year}-{end_year}"
        academic_year = AcademicYear.query.filter_by(year=year_str).first()
        if not academic_year:
            academic_year = AcademicYear(
                year=year_str,
                start_date=date(start_year, 6, 1),
                end_date=date(end_year, 4, 30),
                is_current=True
            )
            db.session.add(academic_year)
            db.session.commit()
        
        # Create courses and semesters for each department
        departments = Department.query.all()
        course_count = 0
        semester_count = 0
        
        for dept in departments:
            course_code = f"{dept.code}_PROG"
            course = Course.query.filter_by(code=course_code).first()
            if not course:
                course = Course(
                    name=f"{dept.name} Program",
                    code=course_code,
                    duration_years=4,
                    department_id=dept.id
                )
                db.session.add(course)
                course_count += 1
                db.session.flush()
            
            # Create semesters 1-8
            for sem_num in range(1, 9):
                semester = Semester.query.filter_by(
                    semester_number=sem_num,
                    course_id=course.id,
                    academic_year_id=academic_year.id
                ).first()
                
                if not semester:
                    if sem_num % 2 == 1:  # Odd semester
                        start_date = date(academic_year.start_date.year, 6, 1)
                        end_date = date(academic_year.start_date.year, 11, 30)
                    else:  # Even semester
                        start_date = date(academic_year.start_date.year + 1, 1, 2)
                        end_date = date(academic_year.start_date.year + 1, 4, 30)
                    
                    semester = Semester(
                        semester_number=sem_num,
                        course_id=course.id,
                        academic_year_id=academic_year.id,
                        start_date=start_date,
                        end_date=end_date
                    )
                    db.session.add(semester)
                    semester_count += 1
            db.session.commit()
        
        # Create subjects
        subject_count = 0
        for dept_name, semesters_data in DEPARTMENT_SUBJECTS.items():
            dept = Department.query.filter_by(name=dept_name).first()
            if dept:
                course = Course.query.filter_by(department_id=dept.id).first()
                if course:
                    for sem_num, subjects in semesters_data.items():
                        semester = Semester.query.filter_by(
                            semester_number=sem_num,
                            course_id=course.id,
                            academic_year_id=academic_year.id
                        ).first()
                        
                        if semester:
                            for idx, subject_name in enumerate(subjects, 1):
                                subject_code = f"{dept.code}{sem_num:02d}{idx:02d}"
                                existing = Subject.query.filter_by(code=subject_code).first()
                                if not existing:
                                    subject = Subject(
                                        name=subject_name,
                                        code=subject_code,
                                        credits=4,
                                        department_id=dept.id,
                                        semester_id=semester.id
                                    )
                                    db.session.add(subject)
                                    subject_count += 1
                    db.session.commit()
        
        # Verify even semesters exist
        even_semesters = Semester.query.filter(Semester.semester_number.in_([2,4,6,8])).count()
        
        return f"""
        <html>
        <head>
            <title>Setup Complete</title>
            <style>
                body {{ font-family: Arial; margin: 40px; background: #f5f5f5; }}
                .container {{ max-width: 800px; margin: auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                h1 {{ color: #6f42c1; }}
                .success {{ color: green; font-weight: bold; }}
                ul {{ line-height: 2; }}
                .button {{ display: inline-block; margin-top: 20px; padding: 10px 20px; background: #6f42c1; color: white; text-decoration: none; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>✅ Initial Academic Setup Complete!</h1>
                <p class="success">All academic data has been created successfully.</p>
                
                <h3>Created:</h3>
                <ul>
                    <li><strong>Departments:</strong> {Department.query.count()}/7</li>
                    <li><strong>Courses:</strong> {Course.query.count()}</li>
                    <li><strong>Semesters:</strong> {Semester.query.count()} (including {even_semesters} even semesters)</li>
                    <li><strong>Subjects:</strong> {Subject.query.count()}</li>
                </ul>
                
                <h3>Even Semesters (2,4,6,8) are now available!</h3>
                <p>You can now generate exam timetables.</p>
                
                <a href="/coordinator/generate-timetable" class="button">Go to Generate Timetable</a>
                <a href="/coordinator/timetable-view" class="button" style="background: #28a745;">View Timetable</a>
            </div>
        </body>
        </html>
        """
        
    except Exception as e:
        db.session.rollback()
        return f"<h1>Error</h1><p>{str(e)}</p>"

# =====================================================
# DATABASE STATUS CHECK ROUTE
# =====================================================

@coordinator_bp.route('/db-status')
@login_required
@coordinator_required
def db_status():
    """Check database status"""
    html = """
    <html>
    <head>
        <title>Database Status</title>
        <style>
            body { font-family: Arial; margin: 20px; background: #f5f5f5; }
            .container { max-width: 1000px; margin: auto; background: white; padding: 20px; border-radius: 10px; }
            h1 { color: #6f42c1; }
            table { border-collapse: collapse; width: 100%; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
            th { background: #6f42c1; color: white; }
            .ok { color: green; font-weight: bold; }
            .missing { color: red; font-weight: bold; }
            .button { display: inline-block; padding: 10px 20px; background: #6f42c1; color: white; text-decoration: none; border-radius: 5px; margin-right: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 Database Status</h1>
    """
    
    # Count tables
    dept_count = Department.query.count()
    course_count = Course.query.count()
    sem_count = Semester.query.count()
    subject_count = Subject.query.count()
    exam_count = ExamTimetable.query.count()
    
    html += f"""
        <h2>Record Counts</h2>
        <table>
            <tr><th>Table</th><th>Count</th><th>Status</th></tr>
            <tr><td>Departments</td><td>{dept_count}</td><td class="{'ok' if dept_count == 7 else 'missing'}">{'✅ OK' if dept_count == 7 else '❌ Missing'}</td></tr>
            <tr><td>Courses</td><td>{course_count}</td><td class="{'ok' if course_count > 0 else 'missing'}">{'✅ OK' if course_count > 0 else '❌ Missing'}</td></tr>
            <tr><td>Semesters</td><td>{sem_count}</td><td class="{'ok' if sem_count >= 8 else 'missing'}">{'✅ OK' if sem_count >= 8 else '❌ Missing'}</td></tr>
            <tr><td>Subjects</td><td>{subject_count}</td><td class="{'ok' if subject_count > 0 else 'missing'}">{'✅ OK' if subject_count > 0 else '❌ Missing'}</td></tr>
            <tr><td>Exams</td><td>{exam_count}</td><td>{'📅 Scheduled' if exam_count > 0 else '⏳ None'}</td></tr>
        </table>
    """
    
    # List all semesters
    semesters = Semester.query.all()
    html += "<h2>Semesters in Database</h2><table><tr><th>ID</th><th>Semester #</th><th>Course</th><th>Department</th><th>Subjects</th></tr>"
    
    for sem in semesters:
        course = Course.query.get(sem.course_id)
        dept = Department.query.get(course.department_id) if course else None
        subject_cnt = Subject.query.filter_by(semester_id=sem.id).count()
        html += f"<tr><td>{sem.id}</td><td><strong>{sem.semester_number}</strong></td><td>{course.name if course else 'N/A'}</td><td>{dept.name if dept else 'N/A'}</td><td>{subject_cnt}</td></tr>"
    
    html += "</table>"
    
    # Check even semesters specifically
    even_sems = Semester.query.filter(Semester.semester_number.in_([2,4,6,8])).all()
    html += f"<h3>Even Semesters (2,4,6,8): {len(even_sems)} found</h3>"
    
    html += """
            <div style="margin-top: 30px;">
                <a href="/coordinator/run-initial-setup" class="button">Run Initial Setup</a>
                <a href="/coordinator/generate-timetable" class="button" style="background: #28a745;">Generate Timetable</a>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html

# =====================================================
# QUICK FIX ROUTE
# =====================================================

@coordinator_bp.route('/quick-fix')
@login_required
@coordinator_required
def quick_fix():
    """Quick fix - redirect to setup"""
    return """
    <html>
    <head>
        <title>Quick Fix</title>
        <style>
            body { font-family: Arial; margin: 40px; background: #f5f5f5; }
            .container { max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #6f42c1; }
            .button { display: block; padding: 15px; margin: 10px 0; background: #6f42c1; color: white; text-decoration: none; border-radius: 5px; text-align: center; font-size: 1.2rem; }
            .button:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(111,66,193,0.3); }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔧 Quick Fix</h1>
            <p>The error "No semesters found" means your database is empty. Click the button below to create all academic data:</p>
            <a href="/coordinator/run-initial-setup" class="button">🚀 RUN INITIAL SETUP NOW</a>
            <a href="/coordinator/db-status" class="button" style="background: #28a745;">📊 CHECK DATABASE STATUS</a>
            <a href="/coordinator/generate-timetable" class="button" style="background: #17a2b8;">📅 GENERATE TIMETABLE</a>
        </div>
    </body>
    </html>
    """

# =====================================================
# CREATE TIMETABLE ROUTE
# =====================================================

@coordinator_bp.route('/create-timetable', methods=['GET', 'POST'])
@login_required
@coordinator_required
def create_timetable():
    """Create exam timetable"""
    if request.method == 'POST':
        try:
            academic_year = request.form.get('academic_year')
            exam_cycle = request.form.get('exam_cycle')
            start_date = request.form.get('start_date')
            end_date = request.form.get('end_date')
            exam_time = request.form.get('exam_time')
            mode = request.form.get('mode', 'auto')
            
            if not all([academic_year, exam_cycle, start_date, end_date, exam_time, mode]):
                flash('Please fill in all required fields', 'danger')
                return redirect(url_for('coordinator.create_timetable'))
            
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date format. Use YYYY-MM-DD', 'danger')
                return redirect(url_for('coordinator.create_timetable'))
            
            # Validate date range
            valid, message = validate_date_range(start_date_obj, end_date_obj)
            if not valid:
                flash(message, 'danger')
                return redirect(url_for('coordinator.create_timetable'))
            
            # Get semesters based on cycle
            semesters = get_semesters_from_cycle(exam_cycle)
            
            if mode == 'auto':
                return process_auto_timetable(
                    academic_year, exam_cycle, semesters,
                    start_date_obj, end_date_obj, exam_time
                )
            else:
                return prepare_manual_allocation(
                    academic_year, exam_cycle, semesters,
                    start_date_obj, end_date_obj
                )
                
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating timetable: {str(e)}', 'danger')
            return redirect(url_for('coordinator.create_timetable'))
    
    # GET request
    allowed_semesters, cycle, display = get_allowed_semesters()
    
    return render_template('coordinator/create_timetable.html',
                         academic_years=get_academic_years(),
                         allowed_semesters=display,
                         default_cycle=cycle)

def process_auto_timetable(academic_year, exam_cycle, semester_numbers, start_date, end_date, exam_time):
    """Process auto timetable generation"""
    departments = Department.query.all()

    if not departments:
        flash('No departments found. Please run academic setup first.', 'danger')
        return redirect(url_for('coordinator.run_initial_setup'))

    date_list = get_available_dates(start_date, end_date, exclude_sundays=True)

    if not date_list:
        flash('No available dates in the selected range (Sundays excluded)', 'danger')
        return redirect(url_for('coordinator.create_timetable'))

    total_saved = 0

    try:
        # Delete old timetable first
        ExamTimetable.query.filter_by(
            academic_year=academic_year,
            exam_cycle=exam_cycle
        ).delete()
        db.session.commit()

        # Get semester objects and IDs
        semester_objects = Semester.query.filter(
            Semester.semester_number.in_(semester_numbers)
        ).all()
        
        if not semester_objects:
            flash(f'No semesters found for numbers: {semester_numbers}. Please run academic setup first.', 'danger')
            return redirect(url_for('coordinator.run_initial_setup'))
        
        semester_ids = [s.id for s in semester_objects]

        # Get subjects for each department
        dept_subjects = {}
        for dept in departments:
            subjects = Subject.query.filter(
                Subject.department_id == dept.id,
                Subject.semester_id.in_(semester_ids)
            ).all()

            if subjects:
                random.shuffle(subjects)
                dept_subjects[dept.id] = subjects

        # Track subject index per department
        subject_index = {dept.id: 0 for dept in departments}

        for exam_date in date_list:
            date_saved = 0

            # Morning session (10AM)
            if exam_time in ['10AM', 'BOTH']:
                for dept in departments:
                    if (dept.id in dept_subjects and 
                        subject_index[dept.id] < len(dept_subjects[dept.id])):
                        
                        subject = dept_subjects[dept.id][subject_index[dept.id]]
                        subject_index[dept.id] += 1
                        
                        success, _ = save_exam(
                            subject, exam_date, '10AM', 
                            academic_year, exam_cycle
                        )
                        if success:
                            date_saved += 1
                            total_saved += 1

            # Afternoon session (2PM)
            if exam_time in ['2PM', 'BOTH']:
                for dept in departments:
                    if (dept.id in dept_subjects and 
                        subject_index[dept.id] < len(dept_subjects[dept.id])):
                        
                        subject = dept_subjects[dept.id][subject_index[dept.id]]
                        subject_index[dept.id] += 1
                        
                        success, _ = save_exam(
                            subject, exam_date, '2PM', 
                            academic_year, exam_cycle
                        )
                        if success:
                            date_saved += 1
                            total_saved += 1

            # Commit after each date
            if date_saved > 0:
                db.session.commit()

        if total_saved > 0:
            flash(f'✅ Timetable generated successfully ({total_saved} exams)', 'success')
        else:
            flash('No subjects found for selected semesters', 'warning')

    except Exception as e:
        db.session.rollback()
        flash(f'Error saving timetable: {str(e)}', 'danger')
        return redirect(url_for('coordinator.create_timetable'))

    return redirect(url_for('coordinator.timetable_view'))

def prepare_manual_allocation(academic_year, exam_cycle, semester_numbers, start_date, end_date):
    """Prepare manual allocation page"""
    all_subjects = []
    subjects_by_dept = {}

    # Get semester objects and IDs
    semester_objects = Semester.query.filter(
        Semester.semester_number.in_(semester_numbers)
    ).all()
    
    if not semester_objects:
        flash(f'No semesters found for numbers: {semester_numbers}', 'danger')
        return redirect(url_for('coordinator.create_timetable'))
    
    semester_ids = [s.id for s in semester_objects]

    for dept_data in ALL_DEPARTMENTS:
        dept = Department.query.filter_by(name=dept_data['name']).first()
        if dept:
            subjects = Subject.query.filter(
                Subject.department_id == dept.id,
                Subject.semester_id.in_(semester_ids)
            ).all()

            if subjects:
                subjects_by_dept[dept_data['name']] = subjects
                all_subjects.extend(subjects)

    if not all_subjects:
        flash('No subjects found for selected semesters', 'warning')
        return redirect(url_for('coordinator.create_timetable'))

    session['manual_exam_cycle'] = exam_cycle

    return render_template('coordinator/manual_allocate.html',
                         subjects_by_dept=subjects_by_dept,
                         subjects=all_subjects,
                         total_subjects=len(all_subjects),
                         start_date=start_date.strftime('%Y-%m-%d'),
                         end_date=end_date.strftime('%Y-%m-%d'),
                         academic_year=academic_year,
                         exam_cycle=exam_cycle)

@coordinator_bp.route('/manual-allocate', methods=['POST'])
@login_required
@coordinator_required
@csrf.exempt
def manual_allocate():
    """Save manual allocations"""
    academic_year = request.form.get('academic_year')
    exam_cycle = session.get('manual_exam_cycle', 'FULL')
    start_date = request.form.get('start_date')

    saved_count = 0

    try:
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()

        for key, value in request.form.items():
            if key.startswith('subject_') and key.endswith('_time'):
                subject_id = int(key.split('_')[1])
                selected_time = value

                if selected_time:
                    subject = Subject.query.get(subject_id)

                    if subject:
                        # Delete old entry
                        ExamTimetable.query.filter_by(
                            subject_id=subject_id,
                            academic_year=academic_year
                        ).delete()

                        save_exam(
                            subject,
                            start_date_obj,
                            selected_time,
                            academic_year,
                            exam_cycle
                        )
                        saved_count += 1

        db.session.commit()

        if saved_count > 0:
            flash(f'✅ Timetable updated successfully ({saved_count} subjects)', 'success')
        else:
            flash('No subjects selected', 'warning')

    except Exception as e:
        db.session.rollback()
        flash(f'Error saving timetable: {str(e)}', 'danger')

    return redirect(url_for('coordinator.timetable_view'))

# =====================================================
# TIMETABLE VIEW ROUTES
# =====================================================

@coordinator_bp.route('/timetable-view')
@login_required
@coordinator_required
def timetable_view():
    """View all scheduled exams"""
    try:
        academic_year = request.args.get('year', 'all')
        
        query = ExamTimetable.query
        
        if academic_year != 'all':
            query = query.filter_by(academic_year=academic_year)
        
        timetables = query.order_by(
            ExamTimetable.exam_date,
            ExamTimetable.exam_time,
            ExamTimetable.department_id
        ).all()
        
        # Get all departments for display
        all_depts = get_all_departments_from_helpers()
        
        # Get available years for filter
        available_years = db.session.query(ExamTimetable.academic_year).distinct().order_by(
            ExamTimetable.academic_year.desc()
        ).all()
        available_years = [y[0] for y in available_years if y[0]]
        
        # Group by date for display
        grouped_timetables = {}
        for exam in timetables:
            date_str = exam.exam_date.strftime('%Y-%m-%d')
            if date_str not in grouped_timetables:
                grouped_timetables[date_str] = {
                    'date': exam.exam_date,
                    'exams': []
                }
            
            # Add exam with related data
            grouped_timetables[date_str]['exams'].append({
                'id': exam.id,
                'exam_time': exam.exam_time,
                'academic_year': exam.academic_year,
                'semester': exam.semester,
                'status': exam.status,
                'department': Department.query.get(exam.department_id),
                'subject': Subject.query.get(exam.subject_id)
            })
        
        total_exams = len(timetables)
        published_count = sum(1 for e in timetables if e.status == 'Published')
        
        return render_template('coordinator/timetable_view.html',
                             grouped_timetables=grouped_timetables,
                             total_exams=total_exams,
                             published_count=published_count,
                             all_depts=all_depts,
                             available_years=available_years,
                             selected_year=academic_year)
    except Exception as e:
        flash(f'Error loading timetable: {str(e)}', 'danger')
        return redirect(url_for('coordinator.dashboard'))

@coordinator_bp.route('/clear-timetable/<string:academic_year>', methods=['POST'])
@login_required
@coordinator_required
@csrf.exempt
def clear_timetable(academic_year):
    """Clear all exams for a specific academic year"""
    try:
        count = ExamTimetable.query.filter_by(academic_year=academic_year).count()
        
        if count == 0:
            flash(f'No exams found for academic year {academic_year}', 'warning')
            return redirect(url_for('coordinator.timetable_view'))
        
        ExamTimetable.query.filter_by(academic_year=academic_year).delete()
        db.session.commit()
        
        flash(f'✅ Successfully cleared {count} exams for academic year {academic_year}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error clearing timetable: {str(e)}', 'danger')
    
    return redirect(url_for('coordinator.timetable_view'))

@coordinator_bp.route('/clear-all-exams', methods=['POST'])
@login_required
@coordinator_required
@csrf.exempt
def clear_all_exams():
    """Delete ALL exam records"""
    try:
        count = ExamTimetable.query.count()
        
        if count == 0:
            flash('No exams found in the database', 'warning')
            return redirect(url_for('coordinator.timetable_view'))
        
        ExamTimetable.query.delete()
        db.session.commit()
        
        flash(f'✅ Successfully cleared ALL {count} exams from the database', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error clearing exams: {str(e)}', 'danger')
    
    return redirect(url_for('coordinator.timetable_view'))

@coordinator_bp.route('/delete-exam/<int:exam_id>', methods=['POST'])
@login_required
@coordinator_required
@csrf.exempt
def delete_exam(exam_id):
    """Delete a single exam entry"""
    try:
        exam = ExamTimetable.query.get_or_404(exam_id)
        db.session.delete(exam)
        db.session.commit()
        flash('Exam entry deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting exam: {str(e)}', 'danger')
    
    return redirect(url_for('coordinator.timetable_view'))

@coordinator_bp.route('/publish-timetable', methods=['POST'])
@login_required
@coordinator_required
@csrf.exempt
def publish_timetable():
    """Publish timetable to public"""
    academic_year = request.form.get('academic_year')
    
    if not academic_year:
        flash('Please select an academic year', 'danger')
        return redirect(url_for('coordinator.timetable_view'))
    
    try:
        count = ExamTimetable.query.filter_by(
            academic_year=academic_year,
            status='Generated'
        ).update({'status': 'Published'})
        
        db.session.commit()
        
        if count > 0:
            semester_info = get_semester_display('FULL')
            notify_exam_timetable_published(academic_year, semester_info)
            flash(f'✅ Published {count} exams for {academic_year}', 'success')
        else:
            flash('No exams found to publish', 'warning')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error publishing timetable: {str(e)}', 'danger')
    
    return redirect(url_for('coordinator.timetable_view'))

# =====================================================
# ROOM ALLOCATION ROUTES
# =====================================================

@coordinator_bp.route('/room-allocation-dashboard')
@login_required
@coordinator_required
def room_allocation_dashboard():
    """Room allocation dashboard"""
    try:
        exam_dates = db.session.query(ExamTimetable.exam_date).distinct().order_by(
            ExamTimetable.exam_date.desc()
        ).all()
        exam_dates = [d[0] for d in exam_dates]
        
        allocations = db.session.query(
            ExamRoomAllocation.exam_date,
            ExamRoomAllocation.exam_time,
            db.func.count(ExamRoomAllocation.id).label('room_count'),
            db.func.sum(ExamRoomAllocation.total_students).label('student_count')
        ).group_by(
            ExamRoomAllocation.exam_date,
            ExamRoomAllocation.exam_time
        ).order_by(
            ExamRoomAllocation.exam_date.desc(),
            ExamRoomAllocation.exam_time
        ).all()
        
        return render_template('coordinator/room_allocation_dashboard.html',
                             exam_dates=exam_dates,
                             allocations=allocations)
    except Exception as e:
        flash(f'Error loading room allocation dashboard: {str(e)}', 'danger')
        return redirect(url_for('coordinator.dashboard'))

@coordinator_bp.route('/allocate-rooms')
@login_required
@coordinator_required
def allocate_rooms():
    """Room allocation page"""
    try:
        exam_dates = db.session.query(ExamTimetable.exam_date).distinct().order_by(
            ExamTimetable.exam_date
        ).all()
        exam_dates = [d[0] for d in exam_dates]
        
        total_students = Student.query.count()
        
        return render_template('coordinator/allocate_rooms.html',
                             exam_dates=exam_dates,
                             total_students=total_students)
    except Exception as e:
        flash(f'Error loading room allocation page: {str(e)}', 'danger')
        return redirect(url_for('coordinator.dashboard'))

@coordinator_bp.route('/allocate-all-dates', methods=['POST'])
@login_required
@coordinator_required
@csrf.exempt
def allocate_all_dates():
    """Allocate rooms for ALL exam dates"""
    try:
        # Get all exam dates
        exam_dates = db.session.query(ExamTimetable.exam_date).distinct().order_by(ExamTimetable.exam_date).all()
        
        if not exam_dates:
            flash('No exam dates found. Create timetable first.', 'warning')
            return redirect(url_for('coordinator.allocate_rooms'))
        
        # Get all students
        all_students = Student.query.all()
        if not all_students:
            flash('No students found in database', 'warning')
            return redirect(url_for('coordinator.allocate_rooms'))
        
        total_dates = len(exam_dates)
        students_per_date = len(all_students) // total_dates if total_dates > 0 else 0
        
        if students_per_date == 0:
            students_per_date = len(all_students)
        
        student_index = 0
        processed_dates = []
        total_rooms_created = 0
        
        # Process each date
        for date_row in exam_dates:
            current_date = date_row[0]
            processed_dates.append(current_date)
            
            # Clear existing allocations for this date
            SeatingArrangement.query.filter_by(exam_date=current_date).delete()
            ExamRoomAllocation.query.filter_by(exam_date=current_date).delete()
            db.session.flush()
            
            # Get students for this date
            date_students = all_students[student_index:student_index + students_per_date]
            random.shuffle(date_students)
            student_index += students_per_date
            
            # Allocate rooms
            rooms_created = allocate_session(current_date, '10AM', date_students)
            total_rooms_created += rooms_created
            
            # Also allocate for 2PM if needed
            afternoon_exams = ExamTimetable.query.filter_by(
                exam_date=current_date,
                exam_time='2PM'
            ).count()
            
            if afternoon_exams > 0:
                afternoon_students = all_students.copy()
                random.shuffle(afternoon_students)
                rooms_created = allocate_session(current_date, '2PM', afternoon_students[:students_per_date])
                total_rooms_created += rooms_created
        
        if processed_dates:
            notify_room_allocation_completed(processed_dates[0].strftime('%Y-%m-%d'))
        
        flash(f'✅ Successfully allocated {total_rooms_created} rooms across {total_dates} dates', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error allocating rooms: {str(e)}', 'danger')
    
    return redirect(url_for('coordinator.room_allocation_dashboard'))

@coordinator_bp.route('/allocate-single-date', methods=['POST'])
@login_required
@coordinator_required
@csrf.exempt
def allocate_single_date():
    """Allocate rooms for a single selected date"""
    exam_date = request.form.get('exam_date')
    
    if not exam_date:
        flash('Please select a date', 'danger')
        return redirect(url_for('coordinator.allocate_rooms'))
    
    try:
        date_obj = datetime.strptime(exam_date, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format', 'danger')
        return redirect(url_for('coordinator.allocate_rooms'))
    
    try:
        # Check if exams exist
        morning_exams = ExamTimetable.query.filter_by(
            exam_date=date_obj, 
            exam_time='10AM'
        ).count()
        
        afternoon_exams = ExamTimetable.query.filter_by(
            exam_date=date_obj, 
            exam_time='2PM'
        ).count()
        
        if morning_exams == 0 and afternoon_exams == 0:
            flash(f'No exams found for {exam_date}', 'warning')
            return redirect(url_for('coordinator.allocate_rooms'))
        
        # Clear existing allocations for this date
        SeatingArrangement.query.filter_by(exam_date=date_obj).delete()
        ExamRoomAllocation.query.filter_by(exam_date=date_obj).delete()
        db.session.commit()
        
        # Get all students
        all_students = Student.query.all()
        if not all_students:
            flash('No students found in database', 'warning')
            return redirect(url_for('coordinator.allocate_rooms'))
        
        random.shuffle(all_students)
        rooms_created_total = 0
        
        # Allocate for morning session if needed
        if morning_exams > 0:
            rooms_created = allocate_session(date_obj, '10AM', all_students)
            rooms_created_total += rooms_created
        
        # Allocate for afternoon session if needed
        if afternoon_exams > 0:
            afternoon_students = all_students.copy()
            random.shuffle(afternoon_students)
            rooms_created = allocate_session(date_obj, '2PM', afternoon_students)
            rooms_created_total += rooms_created
        
        notify_room_allocation_completed(exam_date)
        flash(f'✅ Successfully allocated {rooms_created_total} rooms for {exam_date}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error allocating rooms: {str(e)}', 'danger')
    
    return redirect(url_for('coordinator.view_room_allocation', date=exam_date))

@coordinator_bp.route('/view-room-allocation/<date>')
@login_required
@coordinator_required
def view_room_allocation(date):
    """View room allocation for a specific date"""
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format', 'danger')
        return redirect(url_for('coordinator.room_allocation_dashboard'))
    
    try:
        morning_rooms = ExamRoomAllocation.query.filter_by(
            exam_date=date_obj,
            exam_time='10AM'
        ).order_by(ExamRoomAllocation.room_number).all()
        
        afternoon_rooms = ExamRoomAllocation.query.filter_by(
            exam_date=date_obj,
            exam_time='2PM'
        ).order_by(ExamRoomAllocation.room_number).all()
        
        morning_count = sum(r.total_students for r in morning_rooms)
        afternoon_count = sum(r.total_students for r in afternoon_rooms)
        morning_rooms_count = len(morning_rooms)
        afternoon_rooms_count = len(afternoon_rooms)
        
        return render_template('coordinator/room_allocation.html',
                             date=date,
                             date_obj=date_obj,
                             morning_rooms=morning_rooms,
                             afternoon_rooms=afternoon_rooms,
                             morning_count=morning_count,
                             afternoon_count=afternoon_count,
                             morning_rooms_count=morning_rooms_count,
                             afternoon_rooms_count=afternoon_rooms_count)
    except Exception as e:
        flash(f'Error viewing room allocation: {str(e)}', 'danger')
        return redirect(url_for('coordinator.room_allocation_dashboard'))

@coordinator_bp.route('/clear-room-allocation/<date>', methods=['POST'])
@login_required
@coordinator_required
@csrf.exempt
def clear_room_allocation(date):
    """Clear room allocations for a specific date"""
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format', 'danger')
        return redirect(url_for('coordinator.room_allocation_dashboard'))
    
    try:
        room_count = ExamRoomAllocation.query.filter_by(exam_date=date_obj).count()
        
        if room_count == 0:
            flash(f'No allocations found for {date}', 'warning')
            return redirect(url_for('coordinator.room_allocation_dashboard'))
        
        SeatingArrangement.query.filter_by(exam_date=date_obj).delete()
        ExamRoomAllocation.query.filter_by(exam_date=date_obj).delete()
        db.session.commit()
        
        flash(f'✅ Successfully cleared {room_count} room allocations for {date}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error clearing allocations: {str(e)}', 'danger')
    
    return redirect(url_for('coordinator.room_allocation_dashboard'))

@coordinator_bp.route('/clear-all-room-allocations', methods=['POST'])
@login_required
@coordinator_required
@csrf.exempt
def clear_all_room_allocations():
    """Clear ALL room allocations for ALL dates"""
    try:
        room_count = ExamRoomAllocation.query.count()
        seating_count = SeatingArrangement.query.count()
        
        if room_count == 0:
            flash('No room allocations found in database', 'warning')
            return redirect(url_for('coordinator.room_allocation_dashboard'))
        
        SeatingArrangement.query.delete()
        ExamRoomAllocation.query.delete()
        db.session.commit()
        
        flash(f'✅ Successfully cleared ALL {room_count} rooms and {seating_count} seating arrangements from ALL dates', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error clearing allocations: {str(e)}', 'danger')
    
    return redirect(url_for('coordinator.room_allocation_dashboard'))

@coordinator_bp.route('/view-seating/<date>/<time>/<room>')
@login_required
@coordinator_required
def view_seating(date, time, room):
    """View seating arrangement for a specific room"""
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format', 'danger')
        return redirect(url_for('coordinator.room_allocation_dashboard'))
    
    try:
        seating = SeatingArrangement.query.filter_by(
            exam_date=date_obj,
            exam_time=time,
            room_number=room
        ).order_by(SeatingArrangement.seat_number).all()
        
        room_alloc = ExamRoomAllocation.query.filter_by(
            exam_date=date_obj,
            exam_time=time,
            room_number=room
        ).first()
        
        if not seating:
            flash('No seating found for this room', 'warning')
            return redirect(url_for('coordinator.view_room_allocation', date=date))
        
        return render_template('coordinator/seating.html',
                             date=date,
                             time=time,
                             room=room,
                             seating=seating,
                             room_alloc=room_alloc,
                             date_obj=date_obj,
                             total_seats=20)
    except Exception as e:
        flash(f'Error viewing seating: {str(e)}', 'danger')
        return redirect(url_for('coordinator.view_room_allocation', date=date))

# =====================================================
# INVIGILATOR ALLOCATION ROUTES
# =====================================================

@coordinator_bp.route('/invigilator-allocation')
@login_required
@coordinator_required
def invigilator_allocation():
    """Invigilator allocation page"""
    try:
        exam_dates = db.session.query(ExamRoomAllocation.exam_date).distinct().order_by(
            ExamRoomAllocation.exam_date
        ).all()
        exam_dates = [d[0] for d in exam_dates]
        
        teachers = User.query.filter_by(role='teacher', is_active=True).all()
        
        # Get summary of existing assignments
        assignments_summary = db.session.query(
            InvigilatorAssignment.exam_date,
            db.func.count(InvigilatorAssignment.id).label('room_count')
        ).group_by(
            InvigilatorAssignment.exam_date
        ).order_by(
            InvigilatorAssignment.exam_date
        ).all()
        
        return render_template('coordinator/invigilator_allocation.html',
                             exam_dates=exam_dates,
                             teachers=teachers,
                             assignments_summary=assignments_summary)
    except Exception as e:
        flash(f'Error loading invigilator allocation: {str(e)}', 'danger')
        return redirect(url_for('coordinator.dashboard'))

@coordinator_bp.route('/allocate-invigilators-all', methods=['POST'])
@login_required
@coordinator_required
@csrf.exempt
def allocate_invigilators_all():
    """Auto-allocate invigilators for ALL exam dates"""
    new_assignments = []
    
    try:
        # Get all exam dates with room allocations
        exam_dates = db.session.query(ExamRoomAllocation.exam_date).distinct().order_by(
            ExamRoomAllocation.exam_date
        ).all()
        
        if not exam_dates:
            flash('No room allocations found. Please allocate rooms first.', 'warning')
            return redirect(url_for('coordinator.invigilator_allocation'))
        
        # Get all teachers
        teachers = User.query.filter_by(role='teacher', is_active=True).all()
        
        if not teachers:
            flash('No teachers found in database', 'danger')
            return redirect(url_for('coordinator.invigilator_allocation'))
        
        # Clear existing assignments
        InvigilatorAssignment.query.delete()
        db.session.commit()
        
        total_assignments = 0
        teacher_index = 0
        num_teachers = len(teachers)
        
        # Process each date
        for date_row in exam_dates:
            current_date = date_row[0]
            
            # Get all rooms for this date
            rooms = ExamRoomAllocation.query.filter_by(exam_date=current_date).all()
            
            # Assign invigilators to each room
            for room in rooms:
                teacher = teachers[teacher_index % num_teachers]
                teacher_index += 1
                
                # Get department as string (since User.department is a string)
                dept_name = teacher.department if teacher.department else 'General'
                
                assignment = InvigilatorAssignment(
                    exam_date=current_date,
                    exam_time=room.exam_time,
                    block=room.block,
                    room_number=room.room_number,
                    teacher_id=teacher.id,
                    teacher_name=teacher.full_name,
                    teacher_department=dept_name,  # ← FIXED
                    status='Assigned'
                )
                db.session.add(assignment)
                new_assignments.append(assignment)
                total_assignments += 1
            
            db.session.commit()
        
        # Send notifications
        for assignment in new_assignments:
            notify_invigilator_assigned(
                teacher_id=assignment.teacher_id,
                teacher_name=assignment.teacher_name,
                exam_date=assignment.exam_date,
                room_number=assignment.room_number,
                exam_time=assignment.exam_time
            )
        
        flash(f'✅ Successfully allocated {total_assignments} invigilators across {len(exam_dates)} dates', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error allocating invigilators: {str(e)}', 'danger')
        print(f"Detailed error: {str(e)}")
    
    return redirect(url_for('coordinator.view_all_invigilators'))

@coordinator_bp.route('/allocate-invigilators-date', methods=['POST'])
@login_required
@coordinator_required
def allocate_invigilators_date():
    """Auto-allocate invigilators for a specific date"""
    exam_date = request.form.get('exam_date')
    
    if not exam_date:
        flash('Please select a date', 'danger')
        return redirect(url_for('coordinator.invigilator_allocation'))
    
    try:
        date_obj = datetime.strptime(exam_date, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format', 'danger')
        return redirect(url_for('coordinator.invigilator_allocation'))
    
    try:
        # Get rooms for this date
        rooms = ExamRoomAllocation.query.filter_by(exam_date=date_obj).all()
        
        if not rooms:
            flash(f'No room allocations found for {exam_date}', 'warning')
            return redirect(url_for('coordinator.invigilator_allocation'))
        
        # Get teachers
        teachers = User.query.filter_by(role='teacher', is_active=True).all()
        
        if not teachers:
            flash('No teachers found in database', 'danger')
            return redirect(url_for('coordinator.invigilator_allocation'))
        
        # Clear existing assignments for this date
        InvigilatorAssignment.query.filter_by(exam_date=date_obj).delete()
        db.session.commit()
        
        # Assign invigilators
        teacher_index = 0
        num_teachers = len(teachers)
        assignments = []
        
        for room in rooms:
            teacher = teachers[teacher_index % num_teachers]
            teacher_index += 1
            
            assignment = InvigilatorAssignment(
                exam_date=date_obj,
                exam_time=room.exam_time,
                block=room.block,
                room_number=room.room_number,
                teacher_id=teacher.id,
                teacher_name=teacher.full_name,
                teacher_department=teacher.department if teacher.department else 'General',
                status='Assigned'
            )
            db.session.add(assignment)
            assignments.append(assignment)
            
            # Send notification
            notify_invigilator_assigned(
                teacher_id=teacher.id,
                teacher_name=teacher.full_name,
                exam_date=date_obj,
                room_number=room.room_number,
                exam_time=room.exam_time
            )
        
        db.session.commit()
        
        flash(f'✅ Successfully allocated {len(assignments)} invigilators for {exam_date}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error allocating invigilators: {str(e)}', 'danger')
    
    return redirect(url_for('coordinator.view_invigilators', date=exam_date))

@coordinator_bp.route('/view-invigilators')
@login_required
@coordinator_required
def view_invigilators():
    """View invigilator assignments"""
    date_filter = request.args.get('date', 'all')
    
    query = InvigilatorAssignment.query
    
    if date_filter != 'all':
        try:
            date_obj = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter_by(exam_date=date_obj)
        except ValueError:
            flash('Invalid date format', 'danger')
    
    assignments = query.order_by(
        InvigilatorAssignment.exam_date,
        InvigilatorAssignment.exam_time,
        InvigilatorAssignment.room_number
    ).all()
    
    # Group by date
    grouped = {}
    for assignment in assignments:
        date_str = assignment.exam_date.strftime('%Y-%m-%d')
        if date_str not in grouped:
            grouped[date_str] = {
                'date': assignment.exam_date,
                'assignments': []
            }
        grouped[date_str]['assignments'].append(assignment)
    
    # Get all dates for filter
    all_dates = db.session.query(InvigilatorAssignment.exam_date).distinct().order_by(
        InvigilatorAssignment.exam_date
    ).all()
    all_dates = [d[0] for d in all_dates]
    
    # FIX: Add teachers for the edit modal
    teachers = User.query.filter_by(role='teacher', is_active=True).all()
    
    # Get teacher workload stats
    teacher_workload = db.session.query(
        InvigilatorAssignment.teacher_id,
        InvigilatorAssignment.teacher_name,
        db.func.count(InvigilatorAssignment.id).label('duty_count')
    ).group_by(
        InvigilatorAssignment.teacher_id,
        InvigilatorAssignment.teacher_name
    ).order_by(
        db.func.count(InvigilatorAssignment.id).desc()
    ).all()
    
    return render_template('coordinator/view_invigilators.html',
                         grouped=grouped,
                         all_dates=all_dates,
                         teachers=teachers,
                         teacher_workload=teacher_workload,
                         selected_date=date_filter)

@coordinator_bp.route('/view-all-invigilators')
@login_required
@coordinator_required
def view_all_invigilators():
    """View all invigilator assignments with filters"""
    
    # Get filter parameters
    date_filter = request.args.get('date', 'all')
    teacher_filter = request.args.get('teacher', 'all')
    
    # Base query
    query = InvigilatorAssignment.query
    
    # Apply date filter
    if date_filter != 'all':
        try:
            date_obj = datetime.strptime(date_filter, '%Y-%m-%d').date()
            query = query.filter_by(exam_date=date_obj)
        except ValueError:
            flash('Invalid date format', 'danger')
    
    # Apply teacher filter
    if teacher_filter != 'all':
        try:
            teacher_id = int(teacher_filter)
            query = query.filter_by(teacher_id=teacher_id)
        except ValueError:
            pass
    
    # Get assignments
    assignments = query.order_by(
        InvigilatorAssignment.exam_date,
        InvigilatorAssignment.exam_time,
        InvigilatorAssignment.room_number
    ).all()
    
    # Get all unique dates for filter
    all_dates = db.session.query(InvigilatorAssignment.exam_date).distinct().order_by(
        InvigilatorAssignment.exam_date
    ).all()
    all_dates = [d[0] for d in all_dates]
    
    # Get all teachers for filter
    all_teachers = User.query.filter_by(role='teacher', is_active=True).all()
    
    # Group by date for summary
    grouped_by_date = {}
    for assignment in assignments:
        date_key = assignment.exam_date.strftime('%Y-%m-%d')
        if date_key not in grouped_by_date:
            grouped_by_date[date_key] = {
                'date': assignment.exam_date,
                'count': 0
            }
        grouped_by_date[date_key]['count'] += 1
    
    # Calculate statistics
    total_dates = len(all_dates)
    total_assignments = len(assignments)
    total_teachers = len(all_teachers)
    
    # Calculate average assignments per teacher
    teacher_counts = db.session.query(
        InvigilatorAssignment.teacher_id,
        db.func.count(InvigilatorAssignment.id).label('count')
    ).group_by(InvigilatorAssignment.teacher_id).all()
    
    if teacher_counts:
        avg_per_teacher = round(sum(c[1] for c in teacher_counts) / len(teacher_counts), 1)
    else:
        avg_per_teacher = 0
    
    return render_template('coordinator/view_all_invigilators.html',
                         assignments=assignments,
                         all_dates=all_dates,
                         all_teachers=all_teachers,
                         grouped_by_date=grouped_by_date,
                         selected_date=date_filter,
                         selected_teacher=teacher_filter,
                         total_dates=total_dates,
                         total_assignments=total_assignments,
                         total_teachers=total_teachers,
                         avg_per_teacher=avg_per_teacher)

@coordinator_bp.route('/update-invigilator', methods=['POST'])
@login_required
@coordinator_required
@csrf.exempt
def update_invigilator():
    """Manually update invigilator for a room"""
    assignment_id = request.form.get('assignment_id')
    new_teacher_id = request.form.get('teacher_id')
    
    if not assignment_id or not new_teacher_id:
        flash('Missing required fields', 'danger')
        return redirect(url_for('coordinator.view_all_invigilators'))
    
    try:
        assignment = InvigilatorAssignment.query.get_or_404(assignment_id)
        teacher = User.query.get_or_404(new_teacher_id)
        
        assignment.teacher_id = teacher.id
        assignment.teacher_name = teacher.full_name
        assignment.teacher_department = teacher.department.name if teacher.department else 'General'
        assignment.status = 'Updated'
        
        db.session.commit()
        
        flash(f'Invigilator updated to {teacher.full_name}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating invigilator: {str(e)}', 'danger')
    
    return redirect(url_for('coordinator.view_all_invigilators'))

@coordinator_bp.route('/clear-invigilators/<date>', methods=['POST'])
@login_required
@coordinator_required
@csrf.exempt
def clear_invigilators(date):
    """Clear invigilator assignments for a specific date"""
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format', 'danger')
        return redirect(url_for('coordinator.view_invigilators'))
    
    try:
        count = InvigilatorAssignment.query.filter_by(exam_date=date_obj).count()
        
        if count == 0:
            flash(f'No invigilator assignments found for {date}', 'warning')
            return redirect(url_for('coordinator.view_invigilators'))
        
        InvigilatorAssignment.query.filter_by(exam_date=date_obj).delete()
        db.session.commit()
        
        flash(f'✅ Successfully cleared {count} invigilator assignments for {date}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error clearing invigilators: {str(e)}', 'danger')
    
    return redirect(url_for('coordinator.view_invigilators'))

@coordinator_bp.route('/clear-all-invigilators', methods=['POST'])
@login_required
@coordinator_required
@csrf.exempt
def clear_all_invigilators():
    """Clear ALL invigilator assignments"""
    try:
        count = InvigilatorAssignment.query.count()
        
        if count == 0:
            flash('No invigilator assignments found', 'warning')
            return redirect(url_for('coordinator.view_invigilators'))
        
        InvigilatorAssignment.query.delete()
        db.session.commit()
        
        flash(f'✅ Successfully cleared ALL {count} invigilator assignments', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error clearing invigilators: {str(e)}', 'danger')
    
    return redirect(url_for('coordinator.view_invigilators'))

@coordinator_bp.route('/invigilator-workload')
@login_required
@coordinator_required
def invigilator_workload():
    """View teacher workload statistics"""
    try:
        # Get all teachers
        teachers = User.query.filter_by(role='teacher', is_active=True).all()
        
        workload_data = []
        for teacher in teachers:
            assignments = InvigilatorAssignment.query.filter_by(teacher_id=teacher.id).count()
            workload_data.append({
                'teacher': teacher,
                'assignments': assignments
            })
        
        # Sort by assignments (highest first)
        workload_data.sort(key=lambda x: x['assignments'], reverse=True)
        
        return render_template('coordinator/invigilator_workload.html',
                             workload_data=workload_data)
    except Exception as e:
        flash(f'Error loading workload: {str(e)}', 'danger')
        return redirect(url_for('coordinator.dashboard'))

@coordinator_bp.route('/delete-invigilator/<int:assignment_id>', methods=['POST'])
@login_required
@coordinator_required
@csrf.exempt
def delete_invigilator(assignment_id):
    """Delete a single invigilator assignment"""
    try:
        assignment = InvigilatorAssignment.query.get_or_404(assignment_id)
        db.session.delete(assignment)
        db.session.commit()
        flash('Invigilator assignment deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting assignment: {str(e)}', 'danger')
    
    return redirect(url_for('coordinator.view_all_invigilators'))

# =====================================================
# NOTIFICATION ROUTES
# =====================================================

@coordinator_bp.route('/notifications-dashboard')
@login_required
@coordinator_required
def notifications_dashboard():
    """Notifications dashboard"""
    try:
        notifications = Notification.query.order_by(Notification.created_at.desc()).all()
        
        # Count statistics
        total = len(notifications)
        active = sum(1 for n in notifications if n.is_active)
        
        today_date = datetime.now().date()
        expired = sum(1 for n in notifications if n.end_date and n.end_date < today_date and n.is_active)
        inactive = len(notifications) - active
        
        return render_template('coordinator/notifications_dashboard.html',
                             notifications=notifications,
                             total=total,
                             active=active,
                             inactive=inactive,
                             expired=expired,
                             now=datetime.now())
    except Exception as e:
        flash(f'Error loading notifications: {str(e)}', 'danger')
        return redirect(url_for('coordinator.dashboard'))

@coordinator_bp.route('/create-notification', methods=['GET', 'POST'])
@login_required
@coordinator_required
@csrf.exempt
def create_notification():
    """Create a new notification"""
    if request.method == 'POST':
        try:
            title = request.form.get('title')
            message = request.form.get('message')
            notification_type = request.form.get('notification_type')
            target_role = request.form.get('target_role')
            start_date_str = request.form.get('start_date')
            end_date_str = request.form.get('end_date')
            
            if not all([title, message, notification_type, target_role, start_date_str, end_date_str]):
                flash('Please fill in all required fields', 'danger')
                return redirect(url_for('coordinator.create_notification'))
            
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date format. Use YYYY-MM-DD', 'danger')
                return redirect(url_for('coordinator.create_notification'))
            
            if end_date < start_date:
                flash('End date must be after start date', 'danger')
                return redirect(url_for('coordinator.create_notification'))
            
            notification = Notification(
                title=title,
                message=message,
                notification_type=notification_type,
                target_role=target_role,
                start_date=start_date,
                end_date=end_date,
                created_by=current_user.id,
                is_active=True,
                is_read=False
            )
            
            db.session.add(notification)
            db.session.commit()
            
            flash(f'✅ Notification created successfully', 'success')
            return redirect(url_for('coordinator.notifications_dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating notification: {str(e)}', 'danger')
            return redirect(url_for('coordinator.create_notification'))
    
    # GET request
    return render_template('coordinator/create_notification.html',
                         today=date.today().strftime('%Y-%m-%d'))

@coordinator_bp.route('/edit-notification/<int:notification_id>', methods=['GET', 'POST'])
@login_required
@coordinator_required
@csrf.exempt
def edit_notification(notification_id):
    """Edit an existing notification"""
    notification = Notification.query.get_or_404(notification_id)
    
    if request.method == 'POST':
        try:
            notification.title = request.form.get('title')
            notification.message = request.form.get('message')
            notification.notification_type = request.form.get('notification_type')
            notification.target_role = request.form.get('target_role')
            
            try:
                start_date_str = request.form.get('start_date')
                end_date_str = request.form.get('end_date')
                notification.start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                notification.end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date format', 'danger')
                return redirect(url_for('coordinator.edit_notification', notification_id=notification_id))
            
            if notification.end_date < notification.start_date:
                flash('End date must be after start date', 'danger')
                return redirect(url_for('coordinator.edit_notification', notification_id=notification_id))
            
            db.session.commit()
            flash('Notification updated successfully!', 'success')
            return redirect(url_for('coordinator.notifications_dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating notification: {str(e)}', 'danger')
            return redirect(url_for('coordinator.edit_notification', notification_id=notification_id))
    
    # GET request
    return render_template('coordinator/edit_notification.html',
                         notification=notification,
                         today=date.today().strftime('%Y-%m-%d'))

@coordinator_bp.route('/toggle-notification/<int:notification_id>', methods=['POST'])
@login_required
@coordinator_required
@csrf.exempt
def toggle_notification(notification_id):
    """Toggle notification active status"""
    try:
        notification = Notification.query.get_or_404(notification_id)
        notification.is_active = not notification.is_active
        db.session.commit()
        status = "activated" if notification.is_active else "deactivated"
        flash(f'Notification {status} successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error toggling notification: {str(e)}', 'danger')
    
    return redirect(url_for('coordinator.notifications_dashboard'))

@coordinator_bp.route('/delete-notification/<int:notification_id>', methods=['POST'])
@login_required
@coordinator_required
@csrf.exempt
def delete_notification(notification_id):
    """Delete a notification and all related UserNotification records"""
    try:
        # Get the notification
        notification = Notification.query.get_or_404(notification_id)
        
        # FIRST: Delete all related UserNotification records
        UserNotification.query.filter_by(notification_id=notification_id).delete()
        
        # THEN: Delete the notification itself
        db.session.delete(notification)
        
        # Commit all changes
        db.session.commit()
        
        flash('Notification deleted successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting notification: {str(e)}', 'danger')
    
    return redirect(url_for('coordinator.notifications_dashboard'))

# =====================================================
# DASHBOARD
# =====================================================

@coordinator_bp.route('/dashboard')
@login_required
@coordinator_required
def dashboard():
    """Coordinator Dashboard"""
    try:
        total_exams = ExamTimetable.query.count()
        total_departments = Department.query.count()
        total_subjects = Subject.query.count()
        
        room_count = ExamRoomAllocation.query.count()
        student_seated_count = db.session.query(db.func.sum(ExamRoomAllocation.total_students)).scalar() or 0
        
        recent_allocations = db.session.query(
            ExamRoomAllocation.exam_date,
            ExamRoomAllocation.exam_time,
            db.func.count(ExamRoomAllocation.id).label('room_count'),
            db.func.sum(ExamRoomAllocation.total_students).label('student_count')
        ).group_by(
            ExamRoomAllocation.exam_date,
            ExamRoomAllocation.exam_time
        ).order_by(
            ExamRoomAllocation.exam_date.desc()
        ).limit(5).all()
        
        # Get department statistics
        dept_stats = []
        for dept_data in ALL_DEPARTMENTS:
            dept = Department.query.filter_by(name=dept_data['name']).first()
            if dept:
                subject_count = Subject.query.filter_by(department_id=dept.id).count()
                exam_count = ExamTimetable.query.filter_by(department_id=dept.id).count()
                dept_stats.append({
                    'name': dept.name,
                    'code': dept.code,
                    'subjects': subject_count,
                    'exams': exam_count
                })
        
        today = datetime.now().date()
        next_month = today + timedelta(days=30)
        
        upcoming_exams = ExamTimetable.query.filter(
            ExamTimetable.exam_date >= today,
            ExamTimetable.exam_date <= next_month
        ).order_by(ExamTimetable.exam_date, ExamTimetable.exam_time).limit(10).all()
        
        # Get recent notifications
        recent_notifications = Notification.query.order_by(
            Notification.created_at.desc()
        ).limit(5).all()
        
        return render_template('coordinator/dashboard.html',
                             total_exams=total_exams,
                             total_departments=total_departments,
                             total_subjects=total_subjects,
                             room_count=room_count,
                             student_seated_count=student_seated_count,
                             dept_stats=dept_stats,
                             upcoming_exams=upcoming_exams,
                             recent_allocations=recent_allocations,
                             recent_notifications=recent_notifications)
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'danger')
        return render_template('coordinator/dashboard.html', error=str(e))
    
@coordinator_bp.route('/create-coordinator-user')
def create_coordinator_user():
    """Create a coordinator user (no login required - temporary)"""
    from werkzeug.security import generate_password_hash
    
    # Check if coordinator already exists
    existing = User.query.filter_by(role='coordinator').first()
    if existing:
        return f"""
        <html>
        <body>
            <h1>Coordinator Already Exists</h1>
            <p>Username: {existing.username}</p>
            <p>Password: coord123</p>
            <p><a href="/auth/login">Go to Login</a></p>
        </body>
        </html>
        """
    
    # Create coordinator
    coordinator = User(
        username='coordinator',
        email='coordinator@college.edu',
        full_name='Exam Coordinator',
        role='coordinator',
        department=None,
        password_hash=generate_password_hash('coord123'),
        is_active=True
    )
    
    db.session.add(coordinator)
    db.session.commit()
    
    return """
    <html>
    <body>
        <h1>✅ Coordinator Created!</h1>
        <p>Username: coordinator</p>
        <p>Password: coord123</p>
        <p><a href="/auth/login">Go to Login</a></p>
    </body>
    </html>
    """
@coordinator_bp.route('/fix-all-notifications')
@login_required
@coordinator_required
def fix_all_notifications():
    """Fix all notifications to have correct dates"""
    from datetime import datetime, timedelta
    
    today = datetime.now().date()
    notifications = Notification.query.all()
    
    for n in notifications:
        n.start_date = today - timedelta(days=1)
        n.end_date = today + timedelta(days=30)
        n.is_active = True
    
    db.session.commit()
    
    return f"""
    <html>
    <head><title>Fixed</title></head>
    <body style="font-family: Arial; margin: 40px;">
        <h1 style="color: #6f42c1;">✅ Fixed {len(notifications)} Notifications</h1>
        <p>All notifications have been updated with current dates.</p>
        <p><a href="/teacher/dashboard">Go to Teacher Dashboard</a></p>
    </body>
    </html>
    """
@coordinator_bp.route('/fix-notification-system', methods=['GET'])
@login_required
@coordinator_required
def fix_notification_system():
    """Fix all notifications and create UserNotification records"""
    from datetime import datetime, timedelta
    from model import User
    
    fixed_count = 0
    created_records = 0
    
    # Fix existing notifications
    notifications = Notification.query.all()
    today = datetime.now().date()
    
    # Role mapping for fixing
    role_mapping = {
        'students': 'student',
        'teachers': 'teacher',
        'hods': 'hod',
        'coordinators': 'coordinator',
        'principals': 'principal',
        'all': 'all',
        'public': 'public'
    }
    
    html = "<h1>🔧 Fixing Notification System</h1>"
    html += "<pre>"
    
    for n in notifications:
        # Fix target_role
        if n.target_role in role_mapping:
            old_role = n.target_role
            n.target_role = role_mapping[old_role]
            fixed_count += 1
            html += f"Fixed: {old_role} -> {n.target_role}\n"
        
        # Fix dates if missing
        if not n.start_date:
            n.start_date = today - timedelta(days=1)
            html += f"Added start_date for notification {n.id}\n"
        if not n.end_date:
            n.end_date = today + timedelta(days=30)
            html += f"Added end_date for notification {n.id}\n"
        if n.is_active is None:
            n.is_active = True
    
    db.session.commit()
    html += f"\n✅ Fixed {fixed_count} notifications\n"
    
    # Create UserNotification records for all users and notifications
    users = User.query.all()
    notifications = Notification.query.filter_by(is_active=True).all()
    
    html += f"\nCreating UserNotification records for {len(users)} users and {len(notifications)} notifications...\n"
    
    for user in users:
        for notif in notifications:
            # Check if notification is for this user's role
            if notif.target_role in ['all', user.role] or (notif.user_id and notif.user_id == user.id):
                # Check if record already exists
                existing = UserNotification.query.filter_by(
                    user_id=user.id,
                    notification_id=notif.id
                ).first()
                
                if not existing:
                    un = UserNotification(
                        user_id=user.id,
                        notification_id=notif.id,
                        is_read=False,
                        created_at=datetime.utcnow()
                    )
                    db.session.add(un)
                    created_records += 1
    
    db.session.commit()
    html += f"✅ Created {created_records} UserNotification records\n"
    
    # Create test notifications if none exist
    if Notification.query.count() == 0:
        html += "\nCreating test notifications...\n"
        test_notifications = [
            {'title': 'Welcome to SPAS', 'message': 'Welcome to Student Performance Analysis System', 'type': 'general', 'target': 'all'},
            {'title': 'Exam Schedule Published', 'message': 'The exam timetable for March 2026 has been published.', 'type': 'timetable', 'target': 'all'},
            {'title': 'Fee Reminder', 'message': 'Last date for fee payment is March 31, 2026.', 'type': 'fee', 'target': 'student'},
            {'title': 'Staff Meeting', 'message': 'Department meeting scheduled for tomorrow at 3 PM.', 'type': 'meeting', 'target': 'teacher'},
            {'title': 'HOD Meeting', 'message': 'All HODs please attend the meeting on Friday.', 'type': 'meeting', 'target': 'hod'},
            {'title': 'Principal Announcement', 'message': 'College will remain closed on March 15.', 'type': 'general', 'target': 'principal'},
            {'title': 'Exam Results', 'message': 'Semester exam results have been published.', 'type': 'result', 'target': 'all'}
        ]
        
        for t in test_notifications:
            notif = Notification(
                title=t['title'],
                message=t['message'],
                notification_type=t['type'],
                target_role=t['target'],
                start_date=today,
                end_date=today + timedelta(days=60),
                created_by=current_user.id,
                is_active=True,
                is_read=False,
                created_at=datetime.utcnow()
            )
            db.session.add(notif)
        
        db.session.commit()
        html += f"✅ Created {len(test_notifications)} test notifications\n"
    
    html += "</pre>"
    html += f"""
    <h2>Summary</h2>
    <ul>
        <li>Fixed notifications: {fixed_count}</li>
        <li>Created UserNotification records: {created_records}</li>
        <li>Total notifications: {Notification.query.count()}</li>
        <li>Total UserNotification records: {UserNotification.query.count()}</li>
    </ul>
    <p><a href="/coordinator/notifications-dashboard">Go to Notifications Dashboard</a></p>
    """
    
    return html
