from fastapi import Request
from fastapi.responses import JSONResponse
import time
from collections import defaultdict
from typing import Dict
import asyncio

class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, list] = defaultdict(list)
        self.cleanup_task = None
    
    async def cleanup_old_requests(self):
        """Periodically clean up old request timestamps."""
        while True:
            await asyncio.sleep(60)  # Clean up every minute
            current_time = time.time()
            for ip in list(self.requests.keys()):
                self.requests[ip] = [
                    req_time for req_time in self.requests[ip]
                    if current_time - req_time < 60
                ]
                if not self.requests[ip]:
                    del self.requests[ip]
    
    async def __call__(self, request: Request, call_next):
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Start cleanup task if not running
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self.cleanup_old_requests())
        
        # Check rate limit
        current_time = time.time()
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip]
            if current_time - req_time < 60
        ]
        
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Maximum {self.requests_per_minute} requests per minute allowed"
                }
            )
        
        # Add current request
        self.requests[client_ip].append(current_time)
        
        # Process request
        response = await call_next(request)
        return response
