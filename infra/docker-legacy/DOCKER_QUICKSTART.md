# CBIS Docker Stack - Quick Reference

## 🚀 Quick Start

```powershell
# 1. Build all images
.\docker-build-all.ps1

# 2. Start the stack
.\docker-start.ps1
# or use the stack manager
.\docker-stack.ps1 up

# 3. Check health
.\docker-health-check.ps1
# or
.\docker-stack.ps1 status

# 4. Stop the stack
.\docker-stop.ps1
# or
.\docker-stack.ps1 down
```

## 📚 Stack Information

**Stack Name:** `cbis-stack`  
**Network:** `cbis-stack_cbis-network`  
**Volumes:** `cbis-stack_clip-cache`, `cbis-stack_type-router-v2-cache`, `cbis-stack_insightface-models`

## 📦 Services Overview

| Service | Port | Container Name | Description |
|---------|------|----------------|-------------|
| CLIP | 8000 | cbis-clip | Image embeddings + captions |
| Type Router V2 | 8001 | cbis-type-router-v2 | Multi-label classification |
| NIMA | 8002 | cbis-nima | Image quality scoring |
| Query Optimizer | 8003 | cbis-query-optimizer | Query enhancement |
| Search Router | 8004 | cbis-search-router | Search strategy routing |
| Face Detection | 8005 | cbis-face-detection | Face detection & recognition |

## 🔧 Common Commands

### Using the Stack Manager (Recommended)

```powershell
# Start stack
.\docker-stack.ps1 up

# Start and rebuild
.\docker-stack.ps1 up -Build

# Stop stack
.\docker-stack.ps1 down

# Stop and remove volumes
.\docker-stack.ps1 down -Volumes

# Check status
.\docker-stack.ps1 status

# View logs
.\docker-stack.ps1 logs
.\docker-stack.ps1 logs face-detection -Follow

# Restart service
.\docker-stack.ps1 restart face-detection

# Show resource usage
.\docker-stack.ps1 stats
```

### Using Docker Compose Directly

```bash
# Build all services
docker-compose build

# Start in detached mode
docker-compose up -d

# View logs (all services)
docker-compose logs -f

# View logs (specific service)
docker-compose logs -f clip

# Check status
docker-compose ps

# Restart specific service
docker-compose restart clip

# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Rebuild and restart specific service
docker-compose up -d --build clip
```

### Using Scripts (Windows)

```powershell
# Build all images
.\docker-build-all.ps1

# Start stack
.\docker-start.ps1

# Check health
.\docker-health-check.ps1

# Stop stack
.\docker-stop.ps1

# Or use the unified stack manager
.\docker-stack.ps1 [action] [service] [options]
```

## 🌐 API Endpoints

Once services are running:

- **CLIP**: http://localhost:8000/docs
- **Type Router V2**: http://localhost:8001/docs
- **NIMA**: http://localhost:8002/docs
- **Query Optimizer**: http://localhost:8003/docs
- **Search Router**: http://localhost:8004/docs
- **Face Detection**: http://localhost:8005/docs

## 🔍 Health Checks

Manual health check:

```bash
curl http://localhost:8000/health  # CLIP
curl http://localhost:8001/health  # Type Router V2
curl http://localhost:8002/health  # NIMA
curl http://localhost:8003/health  # Query Optimizer
curl http://localhost:8004/health  # Search Router
curl http://localhost:8005/health  # Face Detection
```

Or use the health check script:

```powershell
.\docker-health-check.ps1
```

## 📁 Directory Structure

```
CBIS_Project/
├── docker-compose.yml           # Main orchestration file
├── DOCKER_SETUP.md             # Detailed documentation
├── docker-build-all.ps1        # Build script
├── docker-start.ps1            # Start script
├── docker-stop.ps1             # Stop script
├── docker-health-check.ps1     # Health check script
│
├── CLIP/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .dockerignore
│   └── app.py
│
├── TYPE_ROUTER_V2/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .dockerignore
│   ├── type_router_service_v2.py
│   └── outputs/
│       └── ovr_rf_clip_model.joblib
│
├── NIMA/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .dockerignore
│   ├── app.py
│   └── mobilenet_nima.h5
│
├── query_optimizer/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .dockerignore
│   └── app.py
│
├── search_router/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .dockerignore
│   └── app.py
│
└── FACE_DETECTION/
    ├── Dockerfile
    ├── requirements.txt
    ├── .dockerignore
    ├── app.py
    └── face_crops/
```

## 🐛 Troubleshooting

### Service won't start

```bash
# Check logs
docker-compose logs <service-name>

# Common issues:
# - Model file missing
# - Port already in use
# - Insufficient memory
```

### Port conflicts

Edit `docker-compose.yml` to change port mappings:

```yaml
services:
  clip:
    ports:
      - "8000:8000"  # Change first number (host port)
```

### Out of memory

Increase Docker memory in Docker Desktop:
Settings → Resources → Memory → Increase limit

Or set limits in docker-compose.yml:

```yaml
services:
  clip:
    mem_limit: 4g
```

### Rebuild after changes

```bash
# Rebuild specific service
docker-compose build --no-cache clip
docker-compose up -d clip

# Or rebuild all
docker-compose build --no-cache
docker-compose up -d
```

## 🔄 Development Workflow

1. **Make code changes** in service directory
2. **Rebuild service**: `docker-compose build <service>`
3. **Restart service**: `docker-compose up -d <service>`
4. **Check logs**: `docker-compose logs -f <service>`
5. **Test endpoint**: `curl http://localhost:<port>/health`

## 📊 Monitoring

View resource usage:

```bash
# All containers
docker stats

# Specific container
docker stats cbis-clip
```

## 🧹 Cleanup

```bash
# Remove stopped containers
docker-compose rm

# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune

# Complete cleanup (BE CAREFUL!)
docker-compose down -v
docker system prune -a --volumes
```

## 🔐 Production Considerations

- [ ] Use environment files for secrets
- [ ] Set resource limits (CPU, memory)
- [ ] Configure log rotation
- [ ] Use specific image tags (not `latest`)
- [ ] Enable HTTPS/TLS
- [ ] Set up monitoring (Prometheus/Grafana)
- [ ] Configure backups for volumes
- [ ] Use Docker secrets for sensitive data

## 📚 Additional Resources

- [DOCKER_SETUP.md](DOCKER_SETUP.md) - Complete setup guide
- [docker-compose.yml](docker-compose.yml) - Service definitions
- Individual service README files in each directory

## 🆘 Getting Help

1. Check service logs: `docker-compose logs <service>`
2. Run health check: `.\docker-health-check.ps1`
3. Test individual endpoints: `curl http://localhost:<port>/health`
4. Check Docker status: `docker ps -a`
5. Review documentation: `http://localhost:<port>/docs`
