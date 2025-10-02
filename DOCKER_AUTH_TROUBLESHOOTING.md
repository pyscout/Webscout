# Webscout Docker Auth Mode Troubleshooting Guide

## Quick Start

### For Windows:
```bash
# Run the batch file
run-auth-mode.bat
```

### For Linux/Mac:
```bash
# Make the script executable and run it
chmod +x run-auth-mode.sh
./run-auth-mode.sh
```

### Manual Docker Commands:
```bash
# Build the image with local code (includes AttributeError fix)
docker build -f Dockerfile.local -t webscout-api:local .

# Run with auth mode
docker-compose -f docker-compose.auth.yml up -d

# Check status
docker-compose -f docker-compose.auth.yml ps

# View logs
docker-compose -f docker-compose.auth.yml logs -f webscout-api
```

## Common Issues and Solutions

### 1. Container Keeps Restarting

**Symptoms:**
- Container status shows "Restarting" or "Exited"
- Logs show AttributeError: 'tuple' object has no attribute 'get'

**Solution:**
The issue was in the original code where `get_auth_components()` returns a tuple but the code tried to use `.get()` on it. This has been fixed in the local build.

```bash
# Check logs to confirm the fix
docker-compose -f docker-compose.auth.yml logs webscout-api

# If you still see the AttributeError, rebuild the image
docker build -f Dockerfile.local -t webscout-api:local . --no-cache
```

### 2. Docker Build Fails

**Symptoms:**
- Build process fails during pip install
- Network timeout errors

**Solutions:**
```bash
# Try building with no cache
docker build -f Dockerfile.local -t webscout-api:local . --no-cache

# If network issues, try with different DNS
docker build -f Dockerfile.local -t webscout-api:local . --build-arg BUILDKIT_INLINE_CACHE=1
```

### 3. Port Already in Use

**Symptoms:**
- Error: "Port 8000 is already in use"

**Solutions:**
```bash
# Check what's using port 8000
netstat -tulpn | grep 8000  # Linux/Mac
netstat -ano | findstr 8000  # Windows

# Use a different port
WEBSCOUT_PORT=8001 docker-compose -f docker-compose.auth.yml up -d

# Or stop the conflicting service
docker stop $(docker ps -q --filter "publish=8000")
```

### 4. Authentication Issues

**Symptoms:**
- API returns 401 Unauthorized
- Cannot generate API keys

**Solutions:**
```bash
# Check if auth is properly enabled
docker exec -it webscout-api-auth env | grep WEBSCOUT_NO_AUTH

# Generate an API key
curl -X POST http://localhost:8000/v1/auth/generate-key \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "name": "Test Key"}'

# Test with the generated API key
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "Hello"}]}'
```

### 5. Health Check Failures

**Symptoms:**
- Health check endpoint returns 500 error
- Container marked as unhealthy

**Solutions:**
```bash
# Check health endpoint manually
curl -v http://localhost:8000/health

# Check container logs for errors
docker-compose -f docker-compose.auth.yml logs webscout-api

# Restart the container
docker-compose -f docker-compose.auth.yml restart webscout-api
```

### 6. Database Connection Issues

**Symptoms:**
- Logs show database connection errors
- API key generation fails

**Solutions:**
```bash
# Check if using MongoDB (optional)
docker-compose -f docker-compose.auth.yml logs mongodb

# The system falls back to JSON file storage by default
# Check if data directory is writable
docker exec -it webscout-api-auth ls -la /app/data

# If using MongoDB, ensure it's running
docker-compose -f docker-compose.auth.yml up -d mongodb
```

## Debugging Commands

### View Container Logs:
```bash
# All logs
docker-compose -f docker-compose.auth.yml logs

# Follow logs in real-time
docker-compose -f docker-compose.auth.yml logs -f webscout-api

# Last 50 lines
docker-compose -f docker-compose.auth.yml logs --tail=50 webscout-api
```

### Shell into Container:
```bash
# As webscout user
docker exec -it webscout-api-auth bash

# As root (for debugging)
docker exec -it --user root webscout-api-auth bash
```

### Check Container Status:
```bash
# Container status
docker-compose -f docker-compose.auth.yml ps

# Detailed container info
docker inspect webscout-api-auth

# Resource usage
docker stats webscout-api-auth
```

### Test API Endpoints:
```bash
# Health check
curl http://localhost:8000/health

# Generate API key
curl -X POST http://localhost:8000/v1/auth/generate-key \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "name": "Test Key"}'

# List models
curl http://localhost:8000/v1/models

# Test chat completion (requires API key)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "Hello"}]}'
```

## Clean Up

### Stop Services:
```bash
docker-compose -f docker-compose.auth.yml down
```

### Remove Everything:
```bash
# Stop and remove containers, networks, volumes
docker-compose -f docker-compose.auth.yml down -v

# Remove the built image
docker rmi webscout-api:local

# Remove all unused Docker resources
docker system prune -a
```

## Environment Variables

Key environment variables for auth mode:

- `WEBSCOUT_NO_AUTH=false` - Enables authentication
- `WEBSCOUT_NO_RATE_LIMIT=false` - Enables rate limiting
- `WEBSCOUT_LOG_LEVEL=info` - Set log level
- `WEBSCOUT_DEBUG=false` - Enable debug mode
- `WEBSCOUT_DATA_DIR=/app/data` - Data directory for JSON storage
- `MONGODB_URL` - MongoDB connection string (optional)

## Support

If you continue to have issues:

1. Check the logs first: `docker-compose -f docker-compose.auth.yml logs webscout-api`
2. Verify the fix is applied by looking for the corrected line in the logs
3. Try rebuilding with `--no-cache` flag
4. Test the API endpoints manually with curl
5. Check Docker and system resources
