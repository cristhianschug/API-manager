#!/bin/bash
# Deploy script - Manual deployment to production server

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SSH_USER="${SSH_USER:-anexo_tecnologia}"
SSH_HOST="${SSH_HOST:-45.177.152.60}"
DEPLOY_PATH="/home/anexar_deploy/api-anexar"
CONTAINER_NAME="anexar-api-prod"
IMAGE_NAME="api-anexar:1.0"

echo -e "${YELLOW}🚀 Starting deployment...${NC}"

# Step 1: Pre-deployment checks
echo -e "${YELLOW}📋 Running pre-deployment checks...${NC}"
ssh -i ~/.ssh/id_anexar_deploy ${SSH_USER}@${SSH_HOST} << 'EOF'
  echo "  Checking disk space..."
  df -h /home | awk 'NR==2 {print "  Disk usage: " $5}'

  echo "  Checking Docker..."
  docker ps > /dev/null && echo "  ✅ Docker OK" || exit 1

  echo "  Checking port 9000..."
  ! lsof -i :9000 > /dev/null && echo "  ✅ Port 9000 free" || exit 1
EOF

# Step 2: Pull latest code
echo -e "${YELLOW}📥 Pulling latest code...${NC}"
ssh -i ~/.ssh/id_anexar_deploy ${SSH_USER}@${SSH_HOST} << EOF
  cd ${DEPLOY_PATH}
  git pull origin main || exit 1
  echo "  ✅ Code updated"
EOF

# Step 3: Build image
echo -e "${YELLOW}🔨 Building Docker image...${NC}"
ssh -i ~/.ssh/id_anexar_deploy ${SSH_USER}@${SSH_HOST} << EOF
  cd ${DEPLOY_PATH}
  docker build -t ${IMAGE_NAME} . || exit 1
  echo "  ✅ Image built"
EOF

# Step 4: Backup current container
echo -e "${YELLOW}💾 Backing up current container...${NC}"
ssh -i ~/.ssh/id_anexar_deploy ${SSH_USER}@${SSH_HOST} << EOF
  docker-compose -f ${DEPLOY_PATH}/docker-compose.prod.yml ps
  echo "  ✅ Backup ready"
EOF

# Step 5: Stop and remove old container
echo -e "${YELLOW}⛔ Stopping old container...${NC}"
ssh -i ~/.ssh/id_anexar_deploy ${SSH_USER}@${SSH_HOST} << EOF
  cd ${DEPLOY_PATH}
  docker-compose -f docker-compose.prod.yml down || true
  echo "  ✅ Old container stopped"
EOF

# Step 6: Start new container
echo -e "${YELLOW}🚀 Starting new container...${NC}"
ssh -i ~/.ssh/id_anexar_deploy ${SSH_USER}@${SSH_HOST} << EOF
  cd ${DEPLOY_PATH}
  docker-compose -f docker-compose.prod.yml up -d || exit 1
  sleep 5
  echo "  ✅ New container started"
EOF

# Step 7: Health check
echo -e "${YELLOW}🏥 Performing health check...${NC}"
ssh -i ~/.ssh/id_anexar_deploy ${SSH_USER}@${SSH_HOST} << EOF
  for i in {1..30}; do
    if curl -s http://localhost:9000/api/v1/health | grep -q '"status":"ok"'; then
      echo "  ✅ Health check passed"
      exit 0
    fi
    echo "  Attempt \$i/30..."
    sleep 1
  done
  echo "  ❌ Health check failed"
  exit 1
EOF

if [ $? -eq 0 ]; then
  echo -e "${GREEN}✅ Deployment successful!${NC}"
  echo ""
  echo "API is live at:"
  echo "  http://${SSH_HOST}:9000/api/v1/health"
  echo ""
else
  echo -e "${RED}❌ Deployment failed!${NC}"
  echo "Rolling back..."
  ssh -i ~/.ssh/id_anexar_deploy ${SSH_USER}@${SSH_HOST} << EOF
    cd ${DEPLOY_PATH}
    docker-compose -f docker-compose.prod.yml down || true
    docker-compose -f docker-compose.prod.yml up -d || true
EOF
  exit 1
fi
