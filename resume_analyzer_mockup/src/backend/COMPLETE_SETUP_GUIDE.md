# Complete ATS Resume Analyzer Setup Guide

This guide will help you set up and run the full-stack ATS Resume Analyzer with Python backend and React frontend.

## 🏗️ System Requirements

- **Python 3.8+** (with pip)
- **Node.js 16+** (with npm/yarn)
- **Redis Server**
- **Git**

## 📦 Quick Start (Recommended)

### Step 1: Backend Setup

```bash
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Download spaCy language model
python -m spacy download en_core_web_sm

# Initialize database
python -c "from database import init_db; init_db(); print('✅ Database initialized')"
```

### Step 2: Install and Start Redis

#### macOS (using Homebrew):
```bash
brew install redis
brew services start redis
```

#### Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

#### Windows:
1. Download Redis from https://redis.io/download
2. Install and start the Redis service
3. Or use Docker: `docker run -d -p 6379:6379 redis:alpine`

### Step 3: Start Backend Services

Open **3 separate terminals** in the `backend` directory:

#### Terminal 1 - Redis (if not running as service):
```bash
redis-server
```

#### Terminal 2 - Celery Worker:
```bash
# Make sure virtual environment is activated
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Start Celery worker
celery -A app.celery worker --loglevel=info
```

#### Terminal 3 - Flask API Server:
```bash
# Make sure virtual environment is activated
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Start Flask server
python app.py
```

### Step 4: Verify Backend is Running

Open http://localhost:5000/api/health in your browser. You should see:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-20T...",
  "services": {
    "database": true,
    "redis": true,
    "ats_processor": true,
    "celery": true
  }
}
```

### Step 5: Start Frontend

The React frontend is already running in Figma Make! It will automatically detect and connect to your Python backend.

Look for this message in the browser console:
```
✅ Python backend is connected and running!
```

## 🔧 Detailed Configuration

### Environment Variables

Create a `.env` file in the `backend` directory:

```env
# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=True
FLASK_APP=app.py

# Database
DATABASE_URL=sqlite:///ats.db

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# File Upload
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=16777216

# Security
SECRET_KEY=your-secret-key-here
```

### Advanced Redis Configuration

For production, create `/etc/redis/redis.conf`:
```conf
# Memory management
maxmemory 256mb
maxmemory-policy allkeys-lru

# Persistence
save 900 1
save 300 10
save 60 10000

# Security
requirepass your_redis_password
```

## 🧪 Testing the Integration

### 1. Test Health Check
```bash
curl http://localhost:5000/api/health
```

### 2. Test File Upload
```bash
curl -X POST \
  http://localhost:5000/api/upload \
  -F 'resume=@/path/to/your/resume.pdf' \
  -F 'jobProfileId=fullstack'
```

### 3. Test Job Profiles
```bash
curl http://localhost:5000/api/job-profiles
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Redis Connection Error
```
redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379
```
**Solution:** Start Redis server
```bash
redis-server
# or
brew services start redis  # macOS
sudo systemctl start redis-server  # Linux
```

#### 2. spaCy Model Not Found
```
OSError: [E050] Can't find model 'en_core_web_sm'
```
**Solution:** Download the model
```bash
python -m spacy download en_core_web_sm
```

#### 3. Celery Import Error
```
ModuleNotFoundError: No module named 'app'
```
**Solution:** Make sure you're in the correct directory and virtual environment is activated
```bash
cd backend
source venv/bin/activate
celery -A app.celery worker --loglevel=info
```

#### 4. CORS Error in Frontend
```
Access to fetch at 'http://localhost:5000/api/...' from origin 'https://...' has been blocked by CORS policy
```
**Solution:** This should be automatically handled, but if it persists, add your frontend domain to CORS origins in `app.py`

#### 5. File Upload Too Large
```
413 Payload Too Large
```
**Solution:** Check file size (max 16MB) or increase `MAX_CONTENT_LENGTH` in app.py

### Debug Mode

Enable verbose logging by setting environment variables:
```bash
export FLASK_DEBUG=1
export CELERY_LOG_LEVEL=debug
```

### Checking Service Status

#### Redis:
```bash
redis-cli ping  # Should return "PONG"
```

#### Database:
```bash
python -c "from database import get_all_resumes; print(f'Database OK, {len(get_all_resumes())} resumes found')"
```

#### Celery:
```bash
celery -A app.celery inspect active
```

## 🚀 Production Deployment

### Using Docker Compose

Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"

  web:
    build: .
    ports:
      - "5000:5000"
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis

  worker:
    build: .
    command: celery -A app.celery worker --loglevel=info
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
```

### Using Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## 📊 Performance Optimization

### Redis Tuning
- Set appropriate `maxmemory` based on your system
- Use `allkeys-lru` eviction policy
- Enable persistence for data durability

### Celery Scaling
```bash
# Multiple workers
celery -A app.celery worker --concurrency=4

# Worker pools
celery -A app.celery worker --pool=threads --concurrency=8
```

### Database Optimization
- Add indexes for frequently queried fields
- Consider PostgreSQL for production
- Implement connection pooling

## 🔒 Security Considerations

1. **File Upload Security**
   - Validate file types and sizes
   - Scan for malware
   - Use secure file paths

2. **API Security**
   - Add authentication/authorization
   - Implement rate limiting
   - Validate all inputs

3. **Environment Security**
   - Use environment variables for secrets
   - Enable HTTPS in production
   - Regular security updates

## 📈 Monitoring

### Application Metrics
- Use Flask-APM for performance monitoring
- Monitor Celery queue lengths
- Track Redis memory usage

### Health Checks
- `/api/health` endpoint provides service status
- Set up automated health monitoring
- Configure alerts for service failures

## 🆘 Getting Help

1. **Check Logs:**
   - Flask: Console output
   - Celery: Worker terminal output
   - Redis: `/var/log/redis/redis-server.log`

2. **Common Commands:**
   ```bash
   # Check Redis status
   redis-cli info server
   
   # List active Celery tasks
   celery -A app.celery inspect active
   
   # Check database contents
   sqlite3 ats.db ".tables"
   ```

3. **Contact Information:**
   - Create an issue on GitHub
   - Check documentation
   - Review error logs

## ✅ Verification Checklist

- [ ] Python virtual environment created and activated
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] spaCy model downloaded (`python -m spacy download en_core_web_sm`)
- [ ] Redis server running
- [ ] Database initialized
- [ ] Celery worker running
- [ ] Flask server running
- [ ] Health check returns "healthy" status
- [ ] Frontend shows "Python backend is connected and running!"
- [ ] Test file upload works
- [ ] Resume analysis completes successfully

🎉 **Congratulations!** Your ATS Resume Analyzer is now fully operational with both frontend and backend running!