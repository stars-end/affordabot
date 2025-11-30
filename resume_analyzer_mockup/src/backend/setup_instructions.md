# ATS Resume Analyzer Backend Setup

## Prerequisites
- Python 3.8 or higher
- Redis server
- Git

## Installation Steps

### 1. Clone and Setup Python Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm
```

### 2. Install and Start Redis
```bash
# On macOS with Homebrew:
brew install redis
brew services start redis

# On Ubuntu/Debian:
sudo apt-get install redis-server
sudo systemctl start redis-server

# On Windows:
# Download and install Redis from https://redis.io/download
```

### 3. Setup Environment Variables
Create a `.env` file in the backend directory:
```env
FLASK_ENV=development
FLASK_DEBUG=True
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=sqlite:///ats.db
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=16777216
```

### 4. Initialize Database
```bash
python -c "from database import init_db; init_db()"
```

### 5. Start the Services

#### Terminal 1 - Start Redis (if not running as service)
```bash
redis-server
```

#### Terminal 2 - Start Celery Worker
```bash
celery -A app.celery worker --loglevel=info
```

#### Terminal 3 - Start Flask Application
```bash
python app.py
```

## API Endpoints

### Resume Processing
- `POST /api/upload` - Upload single resume
- `POST /api/batch-upload` - Upload multiple resumes
- `GET /api/analysis/{job_id}/status` - Check analysis status
- `GET /api/analysis/{resume_id}` - Get analysis results

### Data Management
- `GET /api/resumes` - List all resumes
- `DELETE /api/resumes/{resume_id}` - Delete resume
- `POST /api/export` - Export analysis results

### Job Profiles
- `GET /api/job-profiles` - List job profiles
- `POST /api/job-profiles` - Create job profile

## Testing the API

### Upload a Resume
```bash
curl -X POST \
  http://localhost:5000/api/upload \
  -F 'resume=@/path/to/resume.pdf' \
  -F 'jobProfileId=fullstack'
```

### Check Status
```bash
curl http://localhost:5000/api/analysis/{job_id}/status
```

### Get Results
```bash
curl http://localhost:5000/api/analysis/{resume_id}
```

## Production Deployment

### Using Gunicorn
```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Using Docker
Create `Dockerfile`:
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN python -m spacy download en_core_web_sm

COPY . .
EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

### Environment Variables for Production
```env
FLASK_ENV=production
FLASK_DEBUG=False
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql://user:password@localhost/ats_db
SECRET_KEY=your-secret-key-here
```

## Monitoring and Logging

### Celery Monitoring
```bash
# Install flower for monitoring
pip install flower

# Start flower
celery -A app.celery flower
# Access at http://localhost:5555
```

### Logs
- Flask logs: Configure logging in `app.py`
- Celery logs: Use `--loglevel=info` flag
- Redis logs: Check Redis configuration

## Performance Optimization

### Redis Configuration
Add to `redis.conf`:
```
maxmemory 256mb
maxmemory-policy allkeys-lru
```

### Database Optimization
- Add indexes for frequently queried fields
- Consider PostgreSQL for production
- Implement connection pooling

### File Storage
- Use cloud storage (AWS S3, etc.) for production
- Implement file cleanup routines
- Add virus scanning for uploaded files

## Security Considerations

1. **File Upload Security**
   - Validate file types and sizes
   - Scan for malware
   - Use secure file paths

2. **API Security**
   - Add authentication/authorization
   - Rate limiting
   - Input validation

3. **Data Privacy**
   - Encrypt sensitive data
   - Implement data retention policies
   - GDPR compliance for EU users

## Troubleshooting

### Common Issues
1. **spaCy model not found**: Run `python -m spacy download en_core_web_sm`
2. **Redis connection error**: Check if Redis server is running
3. **PDF extraction fails**: Install additional dependencies for complex PDFs
4. **Memory issues**: Adjust Celery worker memory limits

### Debug Mode
```bash
export FLASK_DEBUG=1
python app.py
```

### Logs Location
- Application logs: `logs/app.log`
- Celery logs: Console output
- Redis logs: `/var/log/redis/redis-server.log`
```