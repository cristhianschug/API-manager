#!/bin/bash
# Setup script - Configure local development + server SSH

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}🛠️  Setting up API development environment...${NC}"

# Step 1: Python venv
echo -e "${YELLOW}1️⃣  Creating Python virtual environment...${NC}"
if [ ! -d "venv" ]; then
  python3 -m venv venv
  source venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
  echo -e "${GREEN}  ✅ Virtual environment ready${NC}"
else
  echo -e "${GREEN}  ✅ Virtual environment exists${NC}"
fi

# Step 2: Environment files
echo -e "${YELLOW}2️⃣  Setting up environment files...${NC}"
if [ ! -f ".env.local" ]; then
  cp .env.local .env.local
  echo -e "${YELLOW}  ⚠️  Edit .env.local with your Firebird credentials${NC}"
else
  echo -e "${GREEN}  ✅ .env.local exists${NC}"
fi

# Step 3: Git setup
echo -e "${YELLOW}3️⃣  Configuring Git...${NC}"
if ! git config user.name > /dev/null; then
  read -p "  Enter your Git name: " GIT_NAME
  read -p "  Enter your Git email: " GIT_EMAIL
  git config user.name "$GIT_NAME"
  git config user.email "$GIT_EMAIL"
fi
echo -e "${GREEN}  ✅ Git configured${NC}"

# Step 4: SSH key for deployment
echo -e "${YELLOW}4️⃣  Setting up SSH for deployment...${NC}"
if [ ! -f ~/.ssh/id_anexar_deploy ]; then
  read -p "  Generate SSH key for deployment? (y/n) " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    ssh-keygen -t ed25519 -f ~/.ssh/id_anexar_deploy -N ""
    echo -e "${GREEN}  ✅ SSH key generated${NC}"
    echo ""
    echo "  Add this to your server's ~/.ssh/authorized_keys:"
    cat ~/.ssh/id_anexar_deploy.pub
    echo ""
    read -p "  Ready to continue? (y/n) " -n 1 -r
    echo
  fi
else
  echo -e "${GREEN}  ✅ SSH key exists${NC}"
fi

# Step 5: Docker (optional)
echo -e "${YELLOW}5️⃣  Checking Docker...${NC}"
if command -v docker &> /dev/null; then
  echo -e "${GREEN}  ✅ Docker installed${NC}"
  if command -v docker-compose &> /dev/null; then
    echo -e "${GREEN}  ✅ Docker Compose installed${NC}"
  else
    echo -e "${YELLOW}  ⚠️  Docker Compose not found. Install with: pip install docker-compose${NC}"
  fi
else
  echo -e "${YELLOW}  ⚠️  Docker not found. Install from: https://docs.docker.com/install${NC}"
fi

# Step 6: Pre-commit hooks
echo -e "${YELLOW}6️⃣  Setting up Git hooks...${NC}"
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
# Run tests before commit
pytest --quiet || exit 1
EOF
chmod +x .git/hooks/pre-commit
echo -e "${GREEN}  ✅ Pre-commit hook installed${NC}"

echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Edit .env.local with your Firebird credentials"
echo "  2. Run: pytest (to test locally)"
echo "  3. Run: python main.py (to start dev server)"
echo "  4. Setup GitHub: git remote add origin <your-repo>"
echo ""
