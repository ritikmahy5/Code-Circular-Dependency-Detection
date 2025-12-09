# GCP Deployment Guide - Using GCP Console

This guide walks you through deploying the Circular Dependency Detective application using the GCP web console.

**🚀 GPU-Optimized:** This project is fully GPU-accelerated for maximum performance. See `GPU_OPTIMIZATION.md` for details.

## Prerequisites

- Google Cloud Platform account with an active project
- Docker image built and ready (or we'll build it using Cloud Build)
- **For GPU features:** GPU quota enabled (request if needed)

## Deployment Option 1: Cloud Run (Recommended - Easiest)

### Step 1: Build Docker Image Using Cloud Build

1. **Open Cloud Build:**
   - In the GCP Console, go to **Navigation Menu** (☰) → **Cloud Build** → **History**
   - Or search for "Cloud Build" in the search bar

2. **Create a Build:**
   - Click **"Create Build"** or **"Trigger"** → **"Create Trigger"**
   - **Name:** `circular-dependency-detective`
   - **Source:** Connect your repository (GitHub, GitLab, etc.) or upload your code
   - **Configuration:** Select **"Dockerfile"** and point to your `Dockerfile`
   - **Location:** Choose a region (e.g., `us-central1`)
   - Click **"Create"** or **"Run"**

3. **Wait for Build:**
   - The build will create a Docker image and push it to **Artifact Registry** or **Container Registry**
   - Note the image location (e.g., `gcr.io/YOUR_PROJECT_ID/circular-dependency-detective`)

### Step 2: Deploy to Cloud Run

1. **Open Cloud Run:**
   - Go to **Navigation Menu** (☰) → **Cloud Run**
   - Click **"CREATE SERVICE"**

2. **Configure Service:**
   - **Service name:** `circular-dependency-detective`
   - **Region:** Choose a region (e.g., `us-central1`)
   - **Deploy one revision from an existing container image:** Click **"SELECT"**
   - Choose the image you built in Step 1
   - Click **"SELECT"**

3. **Configure Container:**
   - **Container port:** `8501`
   - **CPU:** `2`
   - **Memory:** `4 GiB`
   - **Timeout:** `3600 seconds`
   - **Maximum number of requests per container:** `80`

4. **Environment Variables:**
   - Click **"Container, Variables & Secrets, Connections, Security"**
   - Under **"Variables & Secrets"**, click **"ADD VARIABLE"**
   - Add: `ENVIRONMENT` = `production`
   - Click **"DONE"**

5. **Authentication:**
   - Under **"Authentication"**, select **"Allow unauthenticated invocations"** (so your class can access it)

6. **Deploy:**
   - Click **"CREATE"** at the bottom
   - Wait for deployment to complete (1-2 minutes)

7. **Access Your Application:**
   - Once deployed, you'll see a **Service URL** (e.g., `https://circular-dependency-detective-xxxxx.run.app`)
   - Click the URL or copy it to share with your class!

---

## Deployment Option 2: Compute Engine VM (Full Features with Ollama)

### Step 1: Create a VM Instance (GPU-Enabled)

1. **Open Compute Engine:**
   - Go to **Navigation Menu** (☰) → **Compute Engine** → **VM instances**
   - Click **"CREATE INSTANCE"**

2. **Configure VM:**
   - **Name:** `cdd-vm`
   - **Region:** `us-central1`
   - **Zone:** `us-central1-a` (or any zone with GPU availability)
   - **Machine type:** 
     - Click **"SELECT"**
     - For **GPU support:** Choose `n1-standard-4` or higher
     - For **CPU-only:** Any standard machine type works
   - **GPU:**
     - Click **"ADD GPU"** (for GPU acceleration)
     - **GPU type:** `NVIDIA T4` (recommended) or `NVIDIA V100`
     - **Number of GPUs:** `1`
     - **Note:** GPU instances cost more but provide 5-10x performance boost
   - **Boot disk:** 
     - Click **"CHANGE"**
     - **OS:** `Ubuntu 22.04 LTS` (required for GPU drivers)
     - **Size:** `50 GB`
     - Click **"SELECT"**

3. **Firewall:**
   - Under **"Firewall"**, check **"Allow HTTP traffic"** and **"Allow HTTPS traffic"**
   - We'll add port 8501 separately

4. **Advanced Options:**
   - Click **"Networking, Disks, Security, Management, Sole-tenancy"**
   - Go to **"Networking"** tab
   - Under **"Network tags"**, add: `http-server`
   - Go to **"Management"** tab
   - Under **"Startup script"**, paste the contents of `deploy/gcp-startup.sh` (or upload the file)

5. **Create:**
   - Click **"CREATE"**
   - Wait for VM to start (1-2 minutes)

### Step 2: Create Firewall Rule for Port 8501

1. **Open Firewall Rules:**
   - Go to **Navigation Menu** (☰) → **VPC network** → **Firewall**
   - Click **"CREATE FIREWALL RULE"**

2. **Configure Rule:**
   - **Name:** `allow-streamlit`
   - **Direction:** `Ingress`
   - **Targets:** `Specified target tags`
   - **Target tags:** `http-server`
   - **Source IP ranges:** `0.0.0.0/0`
   - **Protocols and ports:** Select **"Specified protocols and ports"**
   - Check **"tcp"** and enter `8501`
   - Click **"CREATE"**

### Step 3: Set Up Application on VM

1. **SSH into VM:**
   - Go back to **Compute Engine** → **VM instances**
   - Find your `cdd-vm` instance
   - Click **"SSH"** button (opens browser-based SSH)

2. **Install Docker:**
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   ```

3. **Install NVIDIA Container Toolkit (for GPU support):**
   ```bash
   # Only needed if you added a GPU
   distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
   curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
   curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
     sudo tee /etc/apt/sources.list.d/nvidia-docker.list
   
   sudo apt-get update
   sudo apt-get install -y nvidia-container-toolkit
   sudo systemctl restart docker
   
   # Verify GPU access
   docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
   ```

4. **Install Docker Compose:**
   ```bash
   sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   ```

4. **Clone Your Repository:**
   ```bash
   git clone YOUR_REPO_URL
   cd Code-Circular-Dependency-Detection
   ```

5. **Start Services:**
   ```bash
   docker-compose up -d
   ```

6. **Check Status:**
   ```bash
   docker-compose ps
   docker-compose logs -f cdd
   ```

### Step 4: Access Your Application

1. **Get External IP:**
   - Go to **Compute Engine** → **VM instances**
   - Find your `cdd-vm` instance
   - Copy the **External IP** address

2. **Access:**
   - Open browser and go to: `http://YOUR_EXTERNAL_IP:8501`
   - Share this URL with your class!

---

## GPU Setup Verification

After deployment, verify GPU is working:

1. **SSH into VM** and run:
   ```bash
   # Check GPU in container
   docker-compose exec cdd python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
   
   # Check GPU info
   nvidia-smi
   ```

2. **Expected output:**
   - `CUDA: True` (if GPU is available)
   - GPU utilization should show when running embeddings

3. **If GPU not detected:**
   - Check NVIDIA drivers: `nvidia-smi`
   - Verify Docker GPU support: `docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi`
   - Restart Docker: `sudo systemctl restart docker`

## Troubleshooting

### Application Not Accessible (Cloud Run)

1. Check service status in **Cloud Run** → your service
2. Check **Logs** tab for errors
3. Verify container port is set to `8501`

### Application Not Accessible (Compute Engine)

1. **Check Firewall:**
   - Go to **VPC network** → **Firewall**
   - Verify `allow-streamlit` rule exists and allows port 8501

2. **Check VM Status:**
   - Go to **Compute Engine** → **VM instances**
   - Verify VM is running (green checkmark)

3. **Check Application Logs:**
   - SSH into VM
   - Run: `docker-compose logs cdd`

4. **Verify Port:**
   - SSH into VM
   - Run: `curl http://localhost:8501/_stcore/health`

### View Logs

- **Cloud Run:** Go to your service → **Logs** tab
- **Compute Engine:** SSH into VM → `docker-compose logs -f cdd`

---

## Quick Reference

- **Cloud Run URL:** Found in Cloud Run service page after deployment
- **VM External IP:** Found in Compute Engine → VM instances
- **Application Port:** `8501`
- **Health Check:** `http://YOUR_URL/_stcore/health`

