#!/bin/bash
# =============================================================================
# NicheIQ Server Setup Script
# =============================================================================
# Run this script on a fresh Ubuntu 24.04 DigitalOcean Droplet
# Usage: curl -sSL <raw-github-url> | bash
#    or: bash server-setup.sh
# =============================================================================

set -e  # Exit on error

echo "=============================================="
echo "NicheIQ Server Setup"
echo "=============================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo bash server-setup.sh)"
    exit 1
fi

# =============================================================================
# 1. System Updates
# =============================================================================
echo ""
echo "[1/6] Updating system packages..."
apt-get update
apt-get upgrade -y

# =============================================================================
# 2. Install Docker
# =============================================================================
echo ""
echo "[2/6] Installing Docker..."

# Remove old versions if any
apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

# Install prerequisites
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Add Docker's official GPG key
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Enable and start Docker
systemctl enable docker
systemctl start docker

echo "Docker version: $(docker --version)"
echo "Docker Compose version: $(docker compose version)"

# =============================================================================
# 3. Install useful tools
# =============================================================================
echo ""
echo "[3/6] Installing additional tools..."
apt-get install -y \
    git \
    htop \
    vim \
    unzip \
    fail2ban

# Enable fail2ban
systemctl enable fail2ban
systemctl start fail2ban

# =============================================================================
# 4. Create application directory
# =============================================================================
echo ""
echo "[4/6] Creating application directory..."
mkdir -p /opt/nicheiq
chown -R root:root /opt/nicheiq

# =============================================================================
# 5. Configure system limits for production
# =============================================================================
echo ""
echo "[5/6] Configuring system limits..."

# Increase file descriptors
cat >> /etc/security/limits.conf << 'EOF'
* soft nofile 65535
* hard nofile 65535
root soft nofile 65535
root hard nofile 65535
EOF

# Optimize kernel parameters for production
cat >> /etc/sysctl.conf << 'EOF'

# NicheIQ Production Settings
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
vm.overcommit_memory = 1
net.ipv4.ip_local_port_range = 1024 65535
EOF

sysctl -p

# =============================================================================
# 6. Configure Docker logging
# =============================================================================
echo ""
echo "[6/6] Configuring Docker logging..."

mkdir -p /etc/docker
cat > /etc/docker/daemon.json << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF

# Restart Docker to apply logging config
systemctl restart docker

# =============================================================================
# Setup Complete
# =============================================================================
echo ""
echo "=============================================="
echo "Server setup complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo "1. Clone your repository:"
echo "   cd /opt/nicheiq"
echo "   git clone https://github.com/YOUR_REPO/nicheiq.git ."
echo ""
echo "2. Configure environment:"
echo "   cp .env.production.example .env"
echo "   vim .env  # Add your API keys"
echo ""
echo "3. Deploy:"
echo "   ./scripts/deploy.sh"
echo ""
echo "=============================================="
