"""
Database module for ATS Resume Analyzer
Uses SQLite for simplicity, can be easily switched to PostgreSQL
"""

import sqlite3
import json
from datetime import datetime
import os

DATABASE_PATH = 'ats.db'

def init_db():
    """Initialize database with required tables"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Resumes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resumes (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            analysis TEXT,
            job_profile_id TEXT
        )
    ''')
    
    # Job profiles table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_profiles (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            required_skills TEXT,
            preferred_skills TEXT,
            minimum_experience INTEGER,
            description TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Analysis jobs table (for tracking batch processing)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analysis_jobs (
            id TEXT PRIMARY KEY,
            status TEXT DEFAULT 'pending',
            total_resumes INTEGER,
            completed_resumes INTEGER DEFAULT 0,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_date TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def add_resume(resume_id, filename, file_path, status='pending', job_profile_id=None):
    """Add a new resume to the database"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO resumes (id, filename, file_path, status, job_profile_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (resume_id, filename, file_path, status, job_profile_id))
    
    conn.commit()
    conn.close()

def get_resume(resume_id):
    """Get resume by ID"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, filename, file_path, upload_date, status, analysis, job_profile_id
        FROM resumes WHERE id = ?
    ''', (resume_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'id': row[0],
            'filename': row[1],
            'file_path': row[2],
            'upload_date': row[3],
            'status': row[4],
            'analysis': row[5],
            'job_profile_id': row[6]
        }
    return None

def update_resume_analysis(resume_id, analysis_result):
    """Update resume with analysis results"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE resumes 
        SET analysis = ?, status = 'completed'
        WHERE id = ?
    ''', (json.dumps(analysis_result), resume_id))
    
    conn.commit()
    conn.close()

def get_all_resumes(limit=100, offset=0):
    """Get all resumes with pagination"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, filename, file_path, upload_date, status, job_profile_id
        FROM resumes 
        ORDER BY upload_date DESC
        LIMIT ? OFFSET ?
    ''', (limit, offset))
    
    rows = cursor.fetchall()
    conn.close()
    
    resumes = []
    for row in rows:
        resumes.append({
            'id': row[0],
            'filename': row[1],
            'file_path': row[2],
            'upload_date': row[3],
            'status': row[4],
            'job_profile_id': row[5]
        })
    
    return resumes

def add_job_profile(profile_id, title, required_skills, preferred_skills, minimum_experience, description):
    """Add a new job profile"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO job_profiles (id, title, required_skills, preferred_skills, minimum_experience, description)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (profile_id, title, json.dumps(required_skills), json.dumps(preferred_skills), minimum_experience, description))
    
    conn.commit()
    conn.close()

def get_job_profiles():
    """Get all job profiles"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, title, required_skills, preferred_skills, minimum_experience, description
        FROM job_profiles
        ORDER BY created_date DESC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    profiles = []
    for row in rows:
        profiles.append({
            'id': row[0],
            'title': row[1],
            'requiredSkills': json.loads(row[2]) if row[2] else [],
            'preferredSkills': json.loads(row[3]) if row[3] else [],
            'minimumExperience': row[4],
            'description': row[5]
        })
    
    return profiles

def create_analysis_job(job_id, total_resumes):
    """Create a new analysis job for batch processing"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO analysis_jobs (id, total_resumes)
        VALUES (?, ?)
    ''', (job_id, total_resumes))
    
    conn.commit()
    conn.close()

def update_job_progress(job_id, completed_resumes):
    """Update job progress"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE analysis_jobs 
        SET completed_resumes = ?
        WHERE id = ?
    ''', (completed_resumes, job_id))
    
    conn.commit()
    conn.close()

def get_analysis_stats():
    """Get overall analysis statistics"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Total resumes
    cursor.execute('SELECT COUNT(*) FROM resumes')
    total_resumes = cursor.fetchone()[0]
    
    # Completed analyses
    cursor.execute('SELECT COUNT(*) FROM resumes WHERE status = "completed"')
    completed_analyses = cursor.fetchone()[0]
    
    # Average score (if analysis exists)
    cursor.execute('''
        SELECT analysis FROM resumes 
        WHERE status = "completed" AND analysis IS NOT NULL
    ''')
    
    analyses = cursor.fetchall()
    scores = []
    
    for (analysis_json,) in analyses:
        try:
            analysis = json.loads(analysis_json)
            scores.append(analysis.get('overallScore', 0))
        except:
            continue
    
    avg_score = sum(scores) / len(scores) if scores else 0
    
    conn.close()
    
    return {
        'totalResumes': total_resumes,
        'completedAnalyses': completed_analyses,
        'averageScore': round(avg_score, 1),
        'processingRate': (completed_analyses / total_resumes * 100) if total_resumes > 0 else 0
    }