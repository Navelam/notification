# create_room_tables.py
from app import create_app
from extensions import db
from model import ExamRoomAllocation, SeatingArrangement

print("=" * 60)
print("CREATING ROOM ALLOCATION TABLES")
print("=" * 60)

app = create_app('development')

with app.app_context():
    # Create the new tables
    db.create_all()
    print(" Tables created successfully!")
    
    # Verify tables exist
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    print("\n📊 Tables in database:")
    for table in sorted(tables):
        status = "" if table in ['exam_room_allocations', 'seating_arrangements'] else "  "
        print(f"   {status} {table}")
    
    # Count existing data
    room_count = ExamRoomAllocation.query.count()
    seating_count = SeatingArrangement.query.count()
    print(f"\n Existing data:")
    print(f"   - Room allocations: {room_count}")
    print(f"   - Seating arrangements: {seating_count}")

print("\n" + "=" * 60)
print(" READY TO USE ROOM ALLOCATION SYSTEM")
print("=" * 60)