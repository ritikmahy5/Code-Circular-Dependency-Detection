#!/bin/bash
# Quick deployment script for GCP

set -e

echo "🚀 Deploying Circular Dependency Detective to GCP..."

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI is not installed"
    echo "Install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Get project ID
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: No GCP project configured"
    echo "Run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo "📦 Project ID: $PROJECT_ID"

# Ask for deployment method
echo ""
echo "Select deployment method:"
echo "1) Cloud Run (Serverless, recommended for quick demo)"
echo "2) Compute Engine VM (Full features with Ollama)"
echo "3) Build and push image only"
read -p "Enter choice [1-3]: " choice

case $choice in
    1)
        echo "🏗️  Building and deploying to Cloud Run..."
        gcloud builds submit --tag gcr.io/$PROJECT_ID/circular-dependency-detective
        
        gcloud run deploy circular-dependency-detective \
            --image gcr.io/$PROJECT_ID/circular-dependency-detective \
            --platform managed \
            --region us-central1 \
            --allow-unauthenticated \
            --port 8501 \
            --memory 4Gi \
            --cpu 2 \
            --timeout 3600 \
            --set-env-vars ENVIRONMENT=production
        
        SERVICE_URL=$(gcloud run services describe circular-dependency-detective \
            --platform managed \
            --region us-central1 \
            --format 'value(status.url)')
        
        echo ""
        echo "✅ Deployment complete!"
        echo "🌐 Access your app at: $SERVICE_URL"
        ;;
    2)
        echo "🏗️  Creating Compute Engine VM..."
        
        # Create VM
        gcloud compute instances create cdd-vm \
            --zone=us-central1-a \
            --machine-type=n1-standard-4 \
            --image-family=cos-stable \
            --image-project=cos-cloud \
            --boot-disk-size=50GB \
            --tags=http-server \
            --metadata-from-file startup-script=deploy/gcp-startup.sh
        
        # Create firewall rule
        echo "🔥 Creating firewall rule..."
        gcloud compute firewall-rules create allow-streamlit \
            --allow tcp:8501 \
            --source-ranges 0.0.0.0/0 \
            --target-tags http-server \
            --description "Allow Streamlit" 2>/dev/null || echo "Firewall rule already exists"
        
        # Get external IP
        EXTERNAL_IP=$(gcloud compute instances describe cdd-vm \
            --zone=us-central1-a \
            --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
        
        echo ""
        echo "✅ VM created!"
        echo "📝 Next steps:"
        echo "1. SSH into the VM: gcloud compute ssh cdd-vm --zone=us-central1-a"
        echo "2. Clone your repository"
        echo "3. Run: docker-compose up -d"
        echo "4. Access at: http://$EXTERNAL_IP:8501"
        ;;
    3)
        echo "🏗️  Building and pushing Docker image..."
        gcloud builds submit --tag gcr.io/$PROJECT_ID/circular-dependency-detective
        
        echo ""
        echo "✅ Image pushed to: gcr.io/$PROJECT_ID/circular-dependency-detective"
        echo "📝 You can now use this image in GKE, Cloud Run, or Compute Engine"
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "📚 For more details, see GCP_DEPLOYMENT.md"

