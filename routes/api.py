# routes/api.py
from flask import Blueprint, jsonify
from flask_login import current_user
from datetime import datetime
from model import Notification, UserNotification
from extensions import db

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/notifications/unread-count')
def api_unread_count():
    """Get unread notification count for current user"""
    try:
        if not current_user.is_authenticated:
            return jsonify({'success': True, 'count': 0})
        
        today = datetime.now().date()
        
        # Get all notifications that match the user's role
        matching_notifications = Notification.query.filter(
            Notification.is_active == True,
            Notification.start_date <= today,
            Notification.end_date >= today,
            db.or_(
                Notification.target_role == 'all',
                Notification.target_role == current_user.role
            )
        ).all()
        
        # Count how many are unread for this user using UserNotification
        count = 0
        for notification in matching_notifications:
            # Check if user has a record for this notification
            user_notif = UserNotification.query.filter_by(
                user_id=current_user.id,
                notification_id=notification.id
            ).first()
            
            # If no record exists OR record exists but is_read=False, it's unread
            if not user_notif or not user_notif.is_read:
                count += 1
        
        return jsonify({'success': True, 'count': count})
        
    except Exception as e:
        print(f"Error in unread count: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': True, 'count': 0})  # Return 0 on error to avoid breaking UI


@api_bp.route('/notifications/list')
def api_notification_list():
    """Get list of notifications for current user"""
    try:
        if not current_user.is_authenticated:
            return jsonify({'success': True, 'notifications': []})
        
        today = datetime.now().date()
        
        # Get notifications that match user's role
        notifications = Notification.query.filter(
            Notification.is_active == True,
            Notification.start_date <= today,
            Notification.end_date >= today,
            db.or_(
                Notification.target_role == 'all',
                Notification.target_role == current_user.role
            )
        ).order_by(Notification.created_at.desc()).limit(20).all()
        
        result = []
        for notif in notifications:
            # Check if user has a read record for this notification
            user_notif = UserNotification.query.filter_by(
                user_id=current_user.id,
                notification_id=notif.id
            ).first()
            
            # Determine if read based on UserNotification
            is_read = user_notif.is_read if user_notif else False
            
            # If no UserNotification record exists, create one (mark as unread)
            if not user_notif:
                user_notif = UserNotification(
                    user_id=current_user.id,
                    notification_id=notif.id,
                    is_read=False,
                    created_at=datetime.utcnow()
                )
                db.session.add(user_notif)
                db.session.commit()  # Commit immediately to have record for next time
            
            result.append({
                'id': notif.id,
                'title': notif.get_prefixed_title(),
                'message': notif.get_prefixed_message(),
                'type': notif.notification_type,
                'is_read': is_read,
                'time_ago': get_time_ago(notif.created_at),
                'link': notif.link or '#',
                'icon': get_icon_name(notif.notification_type),
                'icon_class': notif.notification_type
            })
        
        return jsonify({'success': True, 'notifications': result})
        
    except Exception as e:
        print(f"Error loading notifications: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': True, 'notifications': []})


@api_bp.route('/notifications/<int:id>/read', methods=['POST'])
def api_mark_read(id):
    """Mark a notification as read for the current user"""
    try:
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        # Check if notification exists
        notification = Notification.query.get(id)
        if not notification:
            return jsonify({'success': False, 'error': 'Notification not found'}), 404
        
        # Check if user has permission to mark this notification
        if notification.target_role not in ['all', current_user.role] and notification.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Not authorized'}), 403
        
        # Find or create UserNotification record
        user_notif = UserNotification.query.filter_by(
            user_id=current_user.id,
            notification_id=id
        ).first()
        
        if user_notif:
            # Update existing
            user_notif.is_read = True
            user_notif.read_at = datetime.utcnow()
        else:
            # Create new
            user_notif = UserNotification(
                user_id=current_user.id,
                notification_id=id,
                is_read=True,
                read_at=datetime.utcnow()
            )
            db.session.add(user_notif)
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error marking read: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/notifications/mark-all-read', methods=['POST'])
def api_mark_all_read():
    """Mark all notifications as read for current user"""
    try:
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        today = datetime.now().date()
        
        # Get all notifications that match user's role
        notifications = Notification.query.filter(
            Notification.is_active == True,
            Notification.start_date <= today,
            Notification.end_date >= today,
            db.or_(
                Notification.target_role == 'all',
                Notification.target_role == current_user.role
            )
        ).all()
        
        # Mark each as read via UserNotification
        for notification in notifications:
            user_notif = UserNotification.query.filter_by(
                user_id=current_user.id,
                notification_id=notification.id
            ).first()
            
            if user_notif:
                user_notif.is_read = True
                user_notif.read_at = datetime.utcnow()
            else:
                user_notif = UserNotification(
                    user_id=current_user.id,
                    notification_id=notification.id,
                    is_read=True,
                    read_at=datetime.utcnow()
                )
                db.session.add(user_notif)
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error marking all read: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


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


def get_icon_name(notification_type):
    """Get icon name for notification type"""
    icons = {
        'fee': 'fa-indian-rupee-sign',
        'meeting': 'fa-people-group',
        'event': 'fa-calendar-check',
        'result': 'fa-chart-simple',
        'timetable': 'fa-calendar-days',
        'holiday': 'fa-umbrella-beach',
        'emergency': 'fa-exclamation-triangle',
        'general': 'fa-bullhorn',
        'room': 'fa-door-open',
        'invigilation': 'fa-user-tie',
        'exam': 'fa-pencil-alt',
        'academic': 'fa-school'
    }
    return icons.get(notification_type, 'fa-bell')

# In api.py, update the public_notifications function:

@api_bp.route('/public/notifications')
def public_notifications():
    """Public endpoint for home page bell - shows 'public' and 'all' notifications"""
    try:
        today = datetime.now().date()
        
        print(f"🔍 Fetching public notifications for date: {today}")
        
        # Get public notifications (target_role = 'public' or 'all')
        notifications = Notification.query.filter(
            Notification.is_active == True,
            Notification.start_date <= today,
            Notification.end_date >= today,
            db.or_(
                Notification.target_role == 'public',
                Notification.target_role == 'all'
            )
        ).order_by(Notification.created_at.desc()).limit(10).all()
        
        print(f"📊 Found {len(notifications)} notifications")
        
        result = []
        for notif in notifications:
            print(f"  - {notif.id}: {notif.title} (target: {notif.target_role})")
            result.append({
                'id': notif.id,
                'title': notif.get_prefixed_title(),
                'message': notif.get_prefixed_message(),
                'type': notif.notification_type,
                'time_ago': get_time_ago(notif.created_at),
                'icon': get_icon_name(notif.notification_type),
                'icon_class': notif.notification_type,
                'link': notif.link or '#'
            })
        
        return jsonify({'success': True, 'notifications': result})
        
    except Exception as e:
        print(f"❌ Error loading public notifications: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': True, 'notifications': []})
    
# Add to api.py or a new debug route

@api_bp.route('/debug/notifications')
def debug_notifications():
    """Debug endpoint to check all notifications"""
    notifications = Notification.query.all()
    
    html = "<h1>📋 All Notifications in Database</h1>"
    html += "<table border='1' cellpadding='10'><tr><th>ID</th><th>Title</th><th>Target Role</th><th>Type</th><th>Active</th><th>Start Date</th><th>End Date</th></tr>"
    
    for n in notifications:
        html += f"<tr>"
        html += f"<td>{n.id}</td>"
        html += f"<td>{n.title}</td>"
        html += f"<td>{n.target_role}</td>"
        html += f"<td>{n.notification_type}</td>"
        html += f"<td>{n.is_active}</td>"
        html += f"<td>{n.start_date}</td>"
        html += f"<td>{n.end_date}</td>"
        html += f"</tr>"
    
    html += "</table>"
    
    # Check if dates are valid
    today = datetime.now().date()
    html += f"<p>Today's date: {today}</p>"
    
    return html