#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

# --- Color Codes for Output ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# --- Helper Functions ---
info() {
    echo -e "${GREEN}[INFO] ${1}${NC}"
}

warn() {
    echo -e "${YELLOW}[WARN] ${1}${NC}"
}

error() {
    echo -e "${RED}[ERROR] ${1}${NC}"
    exit 1
}

# --- Main Setup Logic ---

# 1. Welcome and Initial Checks
info "Starting Live Interpreter Environment Setup..."
info "This script will check for dependencies and guide you through the setup."

# 2. Check for NVIDIA GPU and Drivers
info "Step 1: Checking for NVIDIA GPU and drivers..."
if ! command -v nvidia-smi &> /dev/null; then
    error "NVIDIA drivers are not installed. 'nvidia-smi' command not found. Please install the appropriate drivers for your GPU and rerun this script. See: https://www.nvidia.com/Download/index.aspx"
else
    info "NVIDIA drivers found."
    VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -n 1)
    if [ "$VRAM" -lt "10000" ]; then # Check for at least 10GB VRAM
        warn "GPU found, but it has less than 10GB of VRAM (${VRAM}MB). Performance might be suboptimal or models may fail to load."
    else
        info "GPU has sufficient VRAM (${VRAM}MB)."
    fi
fi

# 3. Check and Install Docker
info "Step 2: Checking for Docker..."
if ! command -v docker &> /dev/null; then
    warn "Docker is not installed. Attempting to install..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh
    # Add user to docker group to avoid using sudo
    sudo usermod -aG docker $USER
    info "Docker installed successfully."
    warn "You must log out and log back in for the Docker group changes to take effect!"
    warn "Please log out, log back in, and then re-run this script to continue."
    exit 0
else
    info "Docker is already installed."
fi

# 4. Check Network and Firewall Settings
info "Step 3: Checking network and firewall settings..."
PORTS_TO_CHECK=("3000" "8000" "9090" "3001")
warn "This script will check for a local 'ufw' firewall. It CANNOT check for external firewalls (e.g., AWS Security Groups, corporate firewalls)."

if command -v ufw &> /dev/null && sudo ufw status | grep -q 'Status: active'; then
    info "UFW firewall is active. Checking rules..."
    for PORT in "${PORTS_TO_CHECK[@]}"; do
        if sudo ufw status | grep -q "${PORT}/tcp"; then
            info "Port ${PORT} is allowed in UFW."
        else
            warn "Port ${PORT} is NOT allowed in UFW. To allow it, run: sudo ufw allow ${PORT}/tcp"
        fi
    done
else
    info "No active UFW firewall detected. Assuming ports are open locally."
fi
warn "Please ensure ports 3000, 8000, 9090, and 3001 are open in any external firewalls."

# 5. Install Python Dependencies and Download Models
info "Step 4: Installing Python dependencies for host scripts..."
if ! command -v pip &> /dev/null; then
    error "pip is not installed. Please install python3-pip and rerun this script."
fi
pip install --user -r requirements-host.txt

info "Step 5: Downloading AI Models..."
if [ -d "models" ] && [ "$(ls -A models)" ]; then
    info "Models directory already exists and is not empty. Skipping download."
else
    warn "Models directory is empty or does not exist. Starting download..."
    warn "This will take a significant amount of time and disk space."
    python3 download_models.py
    info "Model download complete."
fi

# 6. Final Instructions
info "--------------------------------------------------"
info "Environment setup and verification complete!"
info "You can now start the application using the Makefile."
info "To start all services, run:"
echo -e "  ${YELLOW}make up${NC}"
info "To view logs, run:"
echo -e "  ${YELLOW}make logs${NC}"
info "To stop all services, run:"
echo -e "  ${YELLOW}make down${NC}"
info "--------------------------------------------------"
