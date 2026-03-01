# routes/public_routes.py
from flask import Blueprint, render_template, jsonify
from model import ExamTimetable, ExamRoomAllocation, InvigilatorAssignment, Notification
from datetime import datetime
from extensions import db

public_bp = Blueprint('public', __name__)

@public_bp.route('/')
def index():
    """Public index page with public announcements"""
    today = datetime.now().date()
    
    # Get public notifications (target_role = 'public' or 'all')
    public_notifications = Notification.query.filter(
        db.or_(
            Notification.target_role == 'public',
            Notification.target_role == 'all'
        ),
        Notification.is_active == True,
        Notification.start_date <= today,
        Notification.end_date >= today
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    return render_template('public/index.html', 
                         public_notifications=public_notifications,
                         now=datetime.now())
@public_bp.route('/exam-timetable')
def exam_timetable():
    """Public view for exam timetable - shows ALL exams"""
    exams = ExamTimetable.query.order_by(
        ExamTimetable.exam_date,
        ExamTimetable.exam_time
    ).all()
    
    grouped = {}
    for exam in exams:
        date_str = exam.exam_date.strftime('%Y-%m-%d')
        if date_str not in grouped:
            grouped[date_str] = {
                'date': exam.exam_date,
                'exams': []
            }
        grouped[date_str]['exams'].append(exam)
    
    return render_template('public/exam_timetable.html', grouped=grouped)

@public_bp.route('/room-allocation')
def room_allocation():
    """Public view for room allocations"""
    allocations = ExamRoomAllocation.query.order_by(
        ExamRoomAllocation.exam_date,
        ExamRoomAllocation.exam_time,
        ExamRoomAllocation.room_number
    ).all()
    
    grouped = {}
    for alloc in allocations:
        date_str = alloc.exam_date.strftime('%Y-%m-%d')
        if date_str not in grouped:
            grouped[date_str] = {
                'date': alloc.exam_date,
                'rooms': []
            }
        grouped[date_str]['rooms'].append(alloc)
    
    return render_template('public/room_allocation.html', grouped=grouped)

@public_bp.route('/invigilator')
def invigilator():
    """Public view for invigilator assignments"""
    assignments = InvigilatorAssignment.query.order_by(
        InvigilatorAssignment.exam_date,
        InvigilatorAssignment.exam_time,
        InvigilatorAssignment.room_number
    ).all()
    
    grouped = {}
    for inv in assignments:
        date_str = inv.exam_date.strftime('%Y-%m-%d')
        if date_str not in grouped:
            grouped[date_str] = {
                'date': inv.exam_date,
                'assignments': []
            }
        grouped[date_str]['assignments'].append(inv)
    
    return render_template('public/invigilator.html', grouped=grouped)
@public_bp.route('/notifications')
def notifications():
    """Public view for notifications - Shows 'public' and 'all'"""
    today = datetime.now().date()
    
    notifications = Notification.query.filter(
        db.or_(
            Notification.target_role == 'public',
            Notification.target_role == 'all'
        ),
        Notification.is_active == True,
        Notification.start_date <= today,
        Notification.end_date >= today
    ).order_by(Notification.created_at.desc()).all()
    
    return render_template('public/notifications.html', 
                         notifications=notifications,
                         now=datetime.now())

# API endpoint for home page bell icon
@public_bp.route('/api/notifications')
def public_notifications_api():
    """API endpoint for public notifications (for home page bell)"""
    today = datetime.now().date()
    
    # Show 'public' and 'all' notifications on home page bell
    notifications = Notification.query.filter(
        db.or_(
            Notification.target_role == 'public',
            Notification.target_role == 'all'
        ),
        Notification.is_active == True,
        Notification.start_date <= today,
        Notification.end_date >= today
    ).order_by(Notification.created_at.desc()).limit(10).all()
    
    result = []
    for n in notifications:
        result.append({
            'id': n.id,
            'title': n.get_prefixed_title(),
            'message': n.get_prefixed_message(),
            'type': n.notification_type,
            'time_ago': get_time_ago(n.created_at),
            'icon': n.get_icon().replace('fa-', ''),
            'icon_class': n.notification_type
        })
    
    return jsonify({'success': True, 'notifications': result})

def get_time_ago(dt):
    """Convert datetime to time ago string"""
    if not dt:
        return "Just now"
    
    now = datetime.utcnow()
    diff = now - dt
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "Just now"
# Add this to public_routes.py or create a new route file

@public_bp.route('/home')
def home():
    """Home page with college information"""
    today = datetime.now().date()
    
    # Get recent public notifications
    recent_notifications = Notification.query.filter(
        db.or_(
            Notification.target_role == 'public',
            Notification.target_role == 'all'
        ),
        Notification.is_active == True,
        Notification.start_date <= today,
        Notification.end_date >= today
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    return render_template('home.html', 
                         recent_notifications=recent_notifications,
                         now=datetime.now())