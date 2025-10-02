# Docker Quick Start Guide

## 🚀 Quick Commands

### Build and Run (Recommended)
```bash
# Build and start the server
docker-compose up --build

# Run in background
docker-compose up -d --build

# View logs
docker-compose logs -f webscout-api

# Stop
docker-compose down
```

### Direct Docker Commands
```bash
# Build image
docker build -t webscout-api:latest .

# Run container
docker run -p 8000:8000 \
  -e WEBSCOUT_NO_AUTH=false \
  -e WEBSCOUT_NO_RATE_LIMIT=false \
  --name webscout-api \
  webscout-api:latest

# Stop container
docker stop webscout-api
docker rm webscout-api
```

---

## 📋 Common Tasks

### Test the API
```bash
# Health check
curl http://localhost:8000/health

# Generate API key
curl -X POST http://localhost:8000/v1/auth/generate-key \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@example.com","telegram_id":"123456"}'

# Test chat completion
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Hello!"}]}'

# View API documentation
open http://localhost:8000/docs
```

### Development Workflow
```bash
# 1. Edit code
vim webscout/auth/server.py

# 2. Rebuild
docker-compose build

# 3. Restart
docker-compose up

# 4. Test changes
curl http://localhost:8000/health
```

### Debugging
```bash
# View logs
docker-compose logs -f webscout-api

# Execute commands in container
docker-compose exec webscout-api bash

# Check running processes
docker-compose exec webscout-api ps aux

# View environment variables
docker-compose exec webscout-api env
```

### Cleanup
```bash
# Stop and remove containers
docker-compose down

# Remove images
docker rmi webscout-api:latest

# Clean everything (careful!)
docker system prune -af --volumes
```

---

## ⚙️ Configuration

### Environment Variables

Edit `docker-compose.yml` or create `.env` file:

```bash
# Server settings
WEBSCOUT_HOST=0.0.0.0
WEBSCOUT_PORT=8000
WEBSCOUT_WORKERS=1
WEBSCOUT_LOG_LEVEL=info

# Authentication
WEBSCOUT_NO_AUTH=false          # Set to true to disable auth
WEBSCOUT_NO_RATE_LIMIT=false    # Set to true to disable rate limiting
WEBSCOUT_DATA_DIR=/app/data

# Database (optional)
MONGODB_URL=mongodb://mongodb:27017/webscout
```

### Port Mapping

Change the port in `docker-compose.yml`:
```yaml
ports:
  - "8080:8000"  # Access on port 8080
```

### Volume Mounting (for development)

Add to `docker-compose.yml`:
```yaml
volumes:
  - ./webscout:/app/webscout  # Live code updates
  - ./data:/app/data          # Persistent data
```

---

## 🔧 Troubleshooting

### Container Won't Start

**Check logs:**
```bash
docker-compose logs webscout-api
```

**Common issues:**
- Port 8000 already in use → Change port in docker-compose.yml
- Permission errors → Check file ownership
- Missing dependencies → Rebuild with `--no-cache`

### Build Fails

**Clear cache and rebuild:**
```bash
docker-compose build --no-cache
```

**Check Docker daemon:**
```bash
docker info
docker system df
```

### Can't Access API

**Check if container is running:**
```bash
docker-compose ps
```

**Check port mapping:**
```bash
docker port webscout-api-auth
```

**Test from inside container:**
```bash
docker-compose exec webscout-api curl http://localhost:8000/health
```

### Changes Not Reflected

**Rebuild without cache:**
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up
```

---

## 📊 Monitoring

### View Resource Usage
```bash
# Container stats
docker stats webscout-api-auth

# Disk usage
docker system df
```

### Health Checks
```bash
# Check health status
docker inspect webscout-api-auth | grep -A 10 Health

# Manual health check
curl http://localhost:8000/health
```

### Request Monitoring
```bash
# View request logs
curl http://localhost:8000/monitor/requests

# View statistics
curl http://localhost:8000/monitor/stats
```

---

## 🎯 Production Deployment

### Build for Production
```bash
# Build with version tag
docker build \
  --build-arg VERSION=1.0.0 \
  --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
  -t webscout-api:1.0.0 \
  -t webscout-api:latest \
  .
```

### Run in Production
```bash
# Use production compose file
docker-compose -f docker-compose.prod.yml up -d

# Or run directly
docker run -d \
  --name webscout-api \
  --restart unless-stopped \
  -p 8000:8000 \
  -e WEBSCOUT_NO_AUTH=false \
  -e WEBSCOUT_NO_RATE_LIMIT=false \
  -v webscout-data:/app/data \
  -v webscout-logs:/app/logs \
  webscout-api:1.0.0
```

### Enable MongoDB (Optional)
```bash
# Uncomment MongoDB section in docker-compose.yml
# Then run:
docker-compose up -d mongodb webscout-api
```

---

## 🔐 Security Best Practices

1. **Never disable authentication in production**
   ```yaml
   WEBSCOUT_NO_AUTH=false  # Keep this!
   ```

2. **Use strong API keys**
   - Generate unique keys for each user
   - Rotate keys regularly

3. **Enable rate limiting**
   ```yaml
   WEBSCOUT_NO_RATE_LIMIT=false  # Keep this!
   ```

4. **Use HTTPS in production**
   - Put behind reverse proxy (nginx, traefik)
   - Use SSL certificates

5. **Limit resource usage**
   ```yaml
   deploy:
     resources:
       limits:
         memory: 1G
         cpus: '1.0'
   ```

---

## 📚 Additional Resources

- **API Documentation**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health
- **Monitoring**: http://localhost:8000/monitor/stats

---

## 🆘 Getting Help

### Check Logs
```bash
docker-compose logs -f webscout-api
```

### Inspect Container
```bash
docker inspect webscout-api-auth
```

### Access Container Shell
```bash
docker-compose exec webscout-api bash
```

### Test API Manually
```bash
# Inside container
docker-compose exec webscout-api python -m webscout.auth.server
```

---

## ✅ Verification Checklist

After deployment, verify:

- [ ] Container is running: `docker-compose ps`
- [ ] Health check passes: `curl http://localhost:8000/health`
- [ ] API docs accessible: http://localhost:8000/docs
- [ ] Can generate API key
- [ ] Can make authenticated requests
- [ ] Rate limiting works
- [ ] Logs are being written
- [ ] Data persists after restart

---

**Happy Coding! 🚀**

