"""
ATS Resume Analyzer Backend - Flask Application
Requirements: pip install flask flask-cors pdfplumber PyMuPDF docx2txt spacy keybert transformers scikit-learn redis celery sqlalchemy
python -m spacy download en_core_web_sm
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import uuid
import json
from datetime import datetime
import sqlite3
import redis
from celery import Celery
import io
import pandas as pd
from reportlab.pdfgen import canvas

# Import our ATS processing modules
from ats_processor import ATSProcessor
from database import init_db, add_resume, get_resume, update_resume_analysis, get_all_resumes

app = Flask(__name__)

# Enable CORS for all routes and origins
CORS(app, origins=["*"], supports_credentials=True)

# Configuration
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'

# Initialize Celery
def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    celery.conf.update(app.config)
    return celery

celery = make_celery(app)

# Initialize Redis for job tracking
try:
    redis_client = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)
    redis_client.ping()  # Test connection
    print("✅ Redis connected successfully")
except redis.ConnectionError:
    print("❌ Redis connection failed. Please start Redis server.")
    redis_client = None

# Initialize ATS Processor
try:
    ats_processor = ATSProcessor()
    print("✅ ATS Processor initialized successfully")
except Exception as e:
    print(f"❌ ATS Processor initialization failed: {e}")
    ats_processor = None

# Create upload folder
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database
try:
    init_db()
    print("✅ Database initialized successfully")
except Exception as e:
    print(f"❌ Database initialization failed: {e}")

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@celery.task(bind=True)
def process_resume_task(self, resume_id, file_path, job_profile_id=None):
    """Background task to process resume"""
    try:
        # Update progress
        self.update_state(state='PROGRESS', meta={'progress': 10, 'message': 'Starting analysis...'})
        
        if not ats_processor:
            raise Exception("ATS Processor not available")
        
        # Process the resume
        self.update_state(state='PROGRESS', meta={'progress': 30, 'message': 'Extracting text...'})
        
        analysis_result = ats_processor.analyze_resume(file_path, job_profile_id)
        
        self.update_state(state='PROGRESS', meta={'progress': 80, 'message': 'Finalizing analysis...'})
        
        # Save analysis to database
        update_resume_analysis(resume_id, analysis_result)
        
        self.update_state(state='PROGRESS', meta={'progress': 100, 'message': 'Analysis complete!'})
        
        return {'status': 'completed', 'analysis': analysis_result}
    
    except Exception as e:
        self.update_state(state='FAILURE', meta={'error': str(e), 'message': f'Analysis failed: {str(e)}'})
        return {'status': 'failed', 'error': str(e)}

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    status = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'services': {
            'database': True,
            'redis': redis_client is not None,
            'ats_processor': ats_processor is not None,
            'celery': True
        }
    }
    
    # Check if any critical services are down
    if not all(status['services'].values()):
        status['status'] = 'degraded'
    
    return jsonify(status)

@app.route('/api/upload', methods=['POST'])
def upload_resume():
    """Upload and queue single resume for analysis"""
    try:
        if 'resume' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['resume']
        job_profile_id = request.form.get('jobProfileId')
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Please upload PDF, DOC, or DOCX files.'}), 400
        
        # Generate unique IDs
        resume_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{resume_id}_{filename}")
        
        # Save file
        file.save(file_path)
        print(f"📄 File saved: {file_path}")
        
        # Add to database
        add_resume(resume_id, filename, file_path, 'processing', job_profile_id)
        
        # Queue for processing
        task = process_resume_task.delay(resume_id, file_path, job_profile_id)
        job_id = task.id
        
        # Store job mapping in Redis
        if redis_client:
            redis_client.set(f"job:{job_id}:resume", resume_id, ex=3600)  # Expire in 1 hour
            redis_client.set(f"resume:{resume_id}:job", job_id, ex=3600)
        
        print(f"🔄 Processing queued: Job {job_id}, Resume {resume_id}")
        
        return jsonify({
            'jobId': job_id,
            'resumeId': resume_id,
            'status': 'queued',
            'message': 'Resume uploaded successfully and queued for analysis'
        })
    
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/batch-upload', methods=['POST'])
def batch_upload():
    """Upload multiple resumes for batch processing"""
    try:
        files = request.files.getlist('resumes')
        job_profile_id = request.form.get('jobProfileId')
        
        if not files:
            return jsonify({'error': 'No files provided'}), 400
        
        job_id = str(uuid.uuid4())
        resume_ids = []
        task_ids = []
        
        print(f"📦 Batch upload started: {len(files)} files")
        
        for file in files:
            if file and allowed_file(file.filename):
                resume_id = str(uuid.uuid4())
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{resume_id}_{filename}")
                
                file.save(file_path)
                add_resume(resume_id, filename, file_path, 'processing', job_profile_id)
                
                # Queue individual processing task
                task = process_resume_task.delay(resume_id, file_path, job_profile_id)
                task_ids.append(task.id)
                resume_ids.append(resume_id)
                
                print(f"  📄 Queued: {filename}")
        
        # Store batch job mapping in Redis
        if redis_client:
            redis_client.set(f"batch:{job_id}:resumes", json.dumps(resume_ids), ex=3600)
            redis_client.set(f"batch:{job_id}:tasks", json.dumps(task_ids), ex=3600)
        
        print(f"✅ Batch upload complete: {len(resume_ids)} files queued")
        
        return jsonify({
            'jobId': job_id,
            'resumeIds': resume_ids,
            'status': 'queued',
            'message': f'{len(resume_ids)} resumes uploaded and queued for analysis'
        })
    
    except Exception as e:
        print(f"❌ Batch upload error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analysis/<job_id>/status', methods=['GET'])
def get_analysis_status(job_id):
    """Get analysis progress status"""
    try:
        # Check if it's a batch job
        if redis_client:
            batch_resumes = redis_client.get(f"batch:{job_id}:resumes")
            if batch_resumes:
                task_ids = json.loads(redis_client.get(f"batch:{job_id}:tasks") or '[]')
                completed = 0
                total = len(task_ids)
                
                for task_id in task_ids:
                    task = process_resume_task.AsyncResult(task_id)
                    if task.state == 'SUCCESS':
                        completed += 1
                
                progress = (completed / total) * 100 if total > 0 else 0
                status = 'completed' if completed == total else 'processing'
                
                return jsonify({
                    'status': status,
                    'progress': progress,
                    'completed': completed,
                    'total': total,
                    'message': f'Processed {completed} of {total} resumes'
                })
        
        # Single resume job
        task = process_resume_task.AsyncResult(job_id)
        
        if task.state == 'PENDING':
            return jsonify({
                'status': 'queued', 
                'progress': 0,
                'message': 'Analysis queued and waiting to start'
            })
        elif task.state == 'PROGRESS':
            info = task.info or {}
            return jsonify({
                'status': 'processing',
                'progress': info.get('progress', 0),
                'message': info.get('message', 'Processing...')
            })
        elif task.state == 'SUCCESS':
            return jsonify({
                'status': 'completed', 
                'progress': 100,
                'message': 'Analysis completed successfully'
            })
        elif task.state == 'FAILURE':
            info = task.info or {}
            return jsonify({
                'status': 'failed', 
                'error': str(info.get('error', 'Unknown error')),
                'message': info.get('message', 'Analysis failed')
            })
        
        return jsonify({
            'status': 'unknown',
            'message': 'Job status could not be determined'
        })
    
    except Exception as e:
        print(f"❌ Status check error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analysis/<resume_id>', methods=['GET'])
def get_analysis_result(resume_id):
    """Get analysis result for a specific resume"""
    try:
        resume = get_resume(resume_id)
        if not resume:
            return jsonify({'error': 'Resume not found'}), 404
        
        if not resume['analysis']:
            return jsonify({'error': 'Analysis not completed yet'}), 404
        
        analysis = json.loads(resume['analysis'])
        print(f"📊 Analysis retrieved for resume {resume_id}")
        
        return jsonify(analysis)
    
    except Exception as e:
        print(f"❌ Get analysis error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/resumes', methods=['GET'])
def get_resumes():
    """Get all resumes with pagination"""
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        resumes = get_all_resumes(limit, offset)
        
        # Add analysis data if available
        for resume in resumes:
            if resume.get('analysis'):
                try:
                    resume['analysis'] = json.loads(resume['analysis'])
                except:
                    resume['analysis'] = None
        
        print(f"📋 Retrieved {len(resumes)} resumes")
        return jsonify(resumes)
    
    except Exception as e:
        print(f"❌ Get resumes error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/resumes/<resume_id>', methods=['DELETE'])
def delete_resume(resume_id):
    """Delete a resume and its analysis"""
    try:
        resume = get_resume(resume_id)
        if not resume:
            return jsonify({'error': 'Resume not found'}), 404
        
        # Delete file
        if os.path.exists(resume['file_path']):
            os.remove(resume['file_path'])
            print(f"🗑️ File deleted: {resume['file_path']}")
        
        # Delete from database
        conn = sqlite3.connect('ats.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM resumes WHERE id = ?', (resume_id,))
        conn.commit()
        conn.close()
        
        print(f"🗑️ Resume deleted: {resume_id}")
        return jsonify({'message': 'Resume deleted successfully'})
    
    except Exception as e:
        print(f"❌ Delete error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/export', methods=['POST'])
def export_analysis():
    """Export analysis results in various formats"""
    try:
        data = request.json
        resume_ids = data.get('resumeIds', [])
        format_type = data.get('format', 'csv')
        
        print(f"📤 Exporting {len(resume_ids)} analyses as {format_type}")
        
        # Collect analysis data
        analysis_data = []
        for resume_id in resume_ids:
            resume = get_resume(resume_id)
            if resume and resume['analysis']:
                analysis = json.loads(resume['analysis'])
                analysis_data.append({
                    'filename': resume['filename'],
                    'overall_score': analysis['overallScore'],
                    'skills_score': next((s['score'] for s in analysis['sections'] if s['name'] == 'Skills Match'), 0),
                    'experience_score': next((s['score'] for s in analysis['sections'] if s['name'] == 'Experience'), 0),
                    'education_score': next((s['score'] for s in analysis['sections'] if s['name'] == 'Education'), 0),
                    'job_match': analysis['jobMatch']['matchPercentage'],
                    'detected_skills': ', '.join([s['name'] for s in analysis['skills']]),
                    'missing_skills': ', '.join(analysis['jobMatch']['missingSkills']),
                    'upload_date': resume['upload_date']
                })
        
        if format_type == 'csv':
            df = pd.DataFrame(analysis_data)
            output = io.StringIO()
            df.to_csv(output, index=False)
            output.seek(0)
            
            return send_file(
                io.BytesIO(output.getvalue().encode()),
                mimetype='text/csv',
                as_attachment=True,
                download_name='ats_analysis.csv'
            )
        
        elif format_type == 'excel':
            df = pd.DataFrame(analysis_data)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='ATS Analysis')
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='ats_analysis.xlsx'
            )
        
        elif format_type == 'pdf':
            output = io.BytesIO()
            p = canvas.Canvas(output)
            
            # Simple PDF generation
            y = 800
            p.drawString(100, y, "ATS Analysis Report")
            p.drawString(100, y-20, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            y -= 60
            
            for item in analysis_data:
                if y < 100:
                    p.showPage()
                    y = 800
                
                p.drawString(100, y, f"File: {item['filename']}")
                y -= 20
                p.drawString(120, y, f"Overall Score: {item['overall_score']}%")
                y -= 20
                p.drawString(120, y, f"Job Match: {item['job_match']}%")
                y -= 20
                p.drawString(120, y, f"Top Skills: {item['detected_skills'][:60]}...")
                y -= 40
            
            p.save()
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/pdf',
                as_attachment=True,
                download_name='ats_analysis.pdf'
            )
        
        return jsonify({'error': 'Unsupported format'}), 400
    
    except Exception as e:
        print(f"❌ Export error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/job-profiles', methods=['GET', 'POST'])
def job_profiles():
    """Get or create job profiles"""
    try:
        if request.method == 'GET':
            # Return predefined job profiles
            profiles = [
                {
                    'id': 'fullstack',
                    'title': 'Full Stack Developer',
                    'requiredSkills': ['JavaScript', 'React', 'Node.js', 'HTML', 'CSS'],
                    'preferredSkills': ['Python', 'TypeScript', 'PostgreSQL', 'AWS'],
                    'minimumExperience': 3,
                    'description': 'Full stack web developer with modern JavaScript technologies'
                },
                {
                    'id': 'frontend',
                    'title': 'Frontend Developer',
                    'requiredSkills': ['JavaScript', 'React', 'HTML', 'CSS'],
                    'preferredSkills': ['TypeScript', 'Vue.js', 'Sass', 'Webpack'],
                    'minimumExperience': 2,
                    'description': 'Frontend developer focused on user interface development'
                },
                {
                    'id': 'backend',
                    'title': 'Backend Developer',
                    'requiredSkills': ['Python', 'Node.js', 'SQL', 'API Development'],
                    'preferredSkills': ['Django', 'Flask', 'PostgreSQL', 'Redis'],
                    'minimumExperience': 3,
                    'description': 'Backend developer for server-side applications'
                },
                {
                    'id': 'datascientist',
                    'title': 'Data Scientist',
                    'requiredSkills': ['Python', 'Machine Learning', 'SQL', 'Statistics'],
                    'preferredSkills': ['TensorFlow', 'PyTorch', 'R', 'Spark'],
                    'minimumExperience': 2,
                    'description': 'Data scientist with machine learning expertise'
                }
            ]
            print(f"📋 Retrieved {len(profiles)} job profiles")
            return jsonify(profiles)
        
        elif request.method == 'POST':
            # Create new job profile
            data = request.json
            profile_id = str(uuid.uuid4())
            profile = {
                'id': profile_id,
                **data
            }
            print(f"✅ Created job profile: {profile['title']}")
            return jsonify(profile)
    
    except Exception as e:
        print(f"❌ Job profiles error: {e}")
        return jsonify({'error': str(e)}), 500

# Error handlers
@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large. Maximum size is 16MB.'}), 413

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    print("🚀 Starting ATS Resume Analyzer Backend...")
    print("📋 Available endpoints:")
    print("  GET  /api/health - Health check")
    print("  POST /api/upload - Upload single resume")
    print("  POST /api/batch-upload - Upload multiple resumes")
    print("  GET  /api/analysis/<job_id>/status - Check analysis status")
    print("  GET  /api/analysis/<resume_id> - Get analysis result")
    print("  GET  /api/resumes - List all resumes")
    print("  DELETE /api/resumes/<resume_id> - Delete resume")
    print("  POST /api/export - Export analysis results")
    print("  GET  /api/job-profiles - List job profiles")
    print("  POST /api/job-profiles - Create job profile")
    print("\n💡 Make sure to start Redis and Celery worker before uploading files!")
    print("   Redis: redis-server")
    print("   Celery: celery -A app.celery worker --loglevel=info")
    print("\n🌐 Frontend should connect to: http://localhost:5000/api")
    
    # Start Flask development server
    app.run(debug=True, host='0.0.0.0', port=5000)