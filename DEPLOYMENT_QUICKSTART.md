# Quick Deployment Guide

## 🚀 Quick Start (5 minutes)

### For GCP Deployment:

1. **Build and test locally first:**
   ```bash
   docker-compose up -d
   # Access at http://localhost:8501
   ```

2. **Deploy to GCP using the helper script:**
   ```bash
   ./deploy.sh
   ```

3. **Or manually:**
   ```bash
   # Build and push to GCR
   gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/circular-dependency-detective
   
   # Deploy to Cloud Run
   gcloud run deploy circular-dependency-detective \
     --image gcr.io/YOUR_PROJECT_ID/circular-dependency-detective \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --port 8501 \
     --memory 4Gi
   ```

## 📋 What's Included

### Updated Files:
- ✅ **Dockerfile** - Production-ready, runs Streamlit on port 8501
- ✅ **docker-compose.yml** - Exposes port 8501, includes health checks
- ✅ **.dockerignore** - Optimizes Docker build
- ✅ **deploy/gcp-startup.sh** - GCP VM startup script
- ✅ **deploy.sh** - Automated deployment helper
- ✅ **GCP_DEPLOYMENT.md** - Complete deployment guide

### Key Features:
- 🌐 Streamlit web app exposed on port 8501
- 🔍 Health checks for both Streamlit and Ollama
- 🐳 Production-ready Docker configuration
- 📦 All dependencies included (git, curl, Python packages)
- 🔒 Proper environment variables for production

## 🔧 Configuration

### Ports:
- **8501** - Streamlit web application (exposed)
- **11434** - Ollama LLM service (internal, optional)

### Environment Variables:
- `ENVIRONMENT=production` - Production mode
- `OLLAMA_HOST=http://ollama:11434` - Ollama service URL
- `STREAMLIT_SERVER_PORT=8501` - Streamlit port
- `STREAMLIT_SERVER_ADDRESS=0.0.0.0` - Listen on all interfaces

## 🧪 Testing Locally

```bash
# Start services
docker-compose up -d

# Check logs
docker-compose logs -f cdd

# Access application
# Open browser: http://localhost:8501

# Stop services
docker-compose down
```

## 🌐 Accessing on GCP

After deployment, your application will be available at:

- **Cloud Run:** `https://YOUR_SERVICE_URL.run.app`
- **Compute Engine:** `http://YOUR_VM_IP:8501`

## 📚 Next Steps

1. Review `GCP_DEPLOYMENT.md` for detailed instructions
2. Set up firewall rules if using Compute Engine
3. Configure domain name (optional)
4. Set up monitoring and alerts

## ⚠️ Important Notes

1. **Ollama is optional** - The app works without it, but LLM features won't be available
2. **Memory requirements** - For full features, use at least 4GB RAM
3. **GitHub cloning** - Requires git (included in Dockerfile)
4. **Health checks** - Both services have health check endpoints

## 🆘 Troubleshooting

See `GCP_DEPLOYMENT.md` for detailed troubleshooting guide.

Common issues:
- Port 8501 not accessible → Check firewall rules
- Ollama not working → Increase VM resources or use external APIs
- Memory errors → Disable persistent DB loading in UI

