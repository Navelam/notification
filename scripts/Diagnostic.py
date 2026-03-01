#!/usr/bin/env python
"""
System Diagnostic Script - Run this from project root
This will show you all risk levels in your database
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import create_app
from extensions import db
from model import StudentPerformance, Student, Subject

def run_diagnostic():
    """Check what risk levels are actually stored in the database"""
    
    app = create_app('development')
    
    with app.app_context():
        print("\n" + "="*60)
        print("SYSTEM DIAGNOSTIC")
        print("="*60)
        
        # Check all performances
        performances = StudentPerformance.query.all()
        print(f"\n📊 Total Performance Records: {len(performances)}")
        
        # Count by risk status
        risk_counts = {}
        for p in performances:
            risk_counts[p.risk_status] = risk_counts.get(p.risk_status, 0) + 1
        
        print("\n⚠️ RISK LEVELS IN DATABASE:")
        print("-" * 40)
        for risk, count in risk_counts.items():
            print(f"  {risk}: {count} students")
        
        # Show sample students for each risk level
        print("\n👨‍🎓 SAMPLE STUDENTS BY RISK LEVEL:")
        print("-" * 40)
        
        for risk in risk_counts.keys():
            sample = StudentPerformance.query.filter_by(risk_status=risk).first()
            if sample:
                student = Student.query.get(sample.student_id)
                subject = Subject.query.get(sample.subject_id)
                print(f"\n{risk}:")
                print(f"  • {student.name if student else 'Unknown'} - Marks: {sample.final_internal}/20, Attendance: {sample.attendance}%")
                print(f"    Subject: {subject.name if subject else 'Unknown'}")
        
        print("\n" + "="*60)
        print("DIAGNOSTIC COMPLETE")
        print("="*60)

if __name__ == "__main__":
    run_diagnostic()