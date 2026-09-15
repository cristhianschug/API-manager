# Git + Deploy Guide

**Complete workflow para desenvolvimento e produção**

---

## 🚀 Quick Start (5 minutos)

### 1. Setup Local Environment

```bash
# Clone your repo
git clone https://github.com/seu-user/api-anexar.git
cd api-anexar

# Run setup script
chmod +x scripts/setup.sh
./scripts/setup.sh

# Activate venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Test locally
pytest -v
python main.py  # http://localhost:8000/api/v1/health
```

### 2. Deploy to Production

```bash
# Make sure SSH key is set up
ls ~/.ssh/id_anexar_deploy

# Deploy
chmod +x scripts/deploy.sh
./scripts/deploy.sh

# Verify
curl http://45.177.152.60:9000/api/v1/health
```

---

## 📦 Complete Git Workflow

### Step 1: Initial Setup (First Time Only)

```bash
# 1. Create GitHub repository
#    - Go to github.com/new
#    - Name: api-anexar
#    - Description: "FastAPI + Firebird ERP API"
#    - Public or Private (your choice)
#    - Create repository

# 2. Clone and configure
git clone https://github.com/seu-user/api-anexar.git
cd api-anexar

git config user.name "Your Name"
git config user.email "seu@email.com"

# 3. Add all project files
git add .
git commit -m "Initial commit: FastAPI + Firebird API

- FastAPI framework with SQLAlchemy ORM
- Firebird database integration
- 5 read-only endpoints (clientes, produtos, pedidos, parcelas, fornecedores)
- 19 integration tests
- Docker deployment ready
- CI/CD workflow included"

git push -u origin main

# 4. Verify
git log --oneline  # Should show your commit
```

### Step 2: Daily Development

```bash
# Start feature branch
git checkout -b feature/new-endpoint

# Make changes
nano main.py  # Edit

# Test changes
pytest -v

# Commit (runs pre-commit tests)
git add main.py
git commit -m "Add new endpoint: GET /api/v1/exemplo"

# Push
git push origin feature/new-endpoint

# Create Pull Request on GitHub
#    - Open github.com/seu-user/api-anexar/pull/new/feature/new-endpoint
#    - Add description
#    - Request review
#    - GitHub Actions runs tests automatically ✅

# Merge (after approval)
git checkout main
git merge feature/new-endpoint
git push origin main

# CI/CD automatically deploys to production! 🚀
```

### Step 3: Version Management

```bash
# Tag releases
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0

# List versions
git tag -l
git log --oneline | head -5
```

---

## 🔐 GitHub Secrets (For CI/CD)

### Setup SSH Key for GitHub Actions

```bash
# 1. GitHub Settings → Secrets and variables → Actions

# Add these secrets:

SSH_HOST=45.177.152.60
SSH_USER=anexo_tecnologia
SSH_PRIVATE_KEY=
  (paste contents of ~/.ssh/id_anexar_deploy)

DOCKER_USERNAME=seu-docker-user
DOCKER_PASSWORD=seu-docker-token
  (optional, only if using Docker Hub)
```

---

## 🚀 Deployment Workflows

### Option A: Manual Deploy (Recommended for v1)

```bash
# Test locally
pytest -v

# Commit and push
git add .
git commit -m "Update: ..."
git push origin main

# SSH deploy
./scripts/deploy.sh

# Verify
curl http://45.177.152.60:9000/api/v1/health
```

### Option B: Automatic Deploy (GitHub Actions)

```bash
# Just push to main, CI/CD does everything:
# 1. Runs tests ✅
# 2. Builds image ✅
# 3. Deploys to server ✅
# 4. Health check ✅

git push origin main
# Watch: github.com/seu-user/api-anexar/actions
```

### Option C: Staged Rollout

```bash
# Develop on develop branch
git checkout -b develop origin/develop
git checkout -b feature/something
# ... develop ...
git push origin feature/something

# PR to develop (staging)
# ... review, test in staging ...

# PR to main (production)
# ... auto-deploys ...
```

---

## 🔄 Git Branches Strategy

```
main
  ↑
  └─ stable, always deployable
  
develop
  ↑
  ├─ feature/new-endpoint
  ├─ feature/bug-fix
  └─ hotfix/urgent
  
hotfix/urgent
  ↑
  └─ main (urgent fix)
```

### Branch Naming Convention

```
feature/add-user-endpoint      # New feature
fix/email-masking-bug          # Bug fix
docs/update-readme             # Documentation
chore/update-dependencies      # Maintenance
hotfix/critical-security       # Urgent fix
```

---

## 📝 Commit Message Convention

```
type(scope): subject

Body (optional)

Footer (optional)
```

### Examples

```
feat(clients): add pagination support
  - Added limit and offset params
  - Added next_page link in response
  - Closes #42

fix(security): fix email masking regex
  - Previous regex allowed @ in local part
  - Closes #35

docs(api): update endpoint examples
  - Added curl examples
  - Fixed JSON response samples

perf(database): add connection pooling
  - Reduced query time by 40%
  - Pool size: 5, max overflow: 10
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code formatting
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `test`: Test changes
- `chore`: Build/tooling

---

## 🔍 Git Commands Reference

### Basic

```bash
# Check status
git status

# See changes
git diff

# Commit
git commit -m "message"

# Push
git push origin branch-name

# Pull
git pull origin main
```

### Branching

```bash
# Create branch
git checkout -b feature/name

# Switch branch
git checkout main

# List branches
git branch -a

# Delete branch
git branch -d feature/name
```

### History

```bash
# See log
git log --oneline

# See specific file history
git log -- filename

# See commit details
git show commit-hash
```

### Undo

```bash
# Undo uncommitted changes
git restore filename

# Undo last commit (keep changes)
git reset HEAD~1

# Undo last commit (discard changes)
git reset --hard HEAD~1

# Revert published commit
git revert commit-hash
```

---

## 🚨 Rollback Procedures

### If Deployment Fails

```bash
# Stop server
ssh anexo_tecnologia@45.177.152.60 << EOF
  cd /home/anexar_deploy/api-anexar
  docker-compose -f docker-compose.prod.yml down
  docker-compose -f docker-compose.prod.yml up -d
EOF

# OR: Revert to previous version
git revert HEAD~1  # Revert last commit
git push origin main  # Auto-deploy again
```

### If Git History Is Messed Up

```bash
# See what happened
git reflog

# Go back to specific point
git reset --hard abc123def

# Force push (CAREFUL!)
git push --force origin main
```

---

## 📊 Git Workflow Diagram

```
┌─────────────┐
│   Develop   │ (your local machine)
│   locally   │
└──────┬──────┘
       │ git push
       ↓
┌─────────────────┐
│  GitHub Repo    │ (remote)
│  Pull Request   │
└──────┬──────────┘
       │ Review + Approve
       ↓
┌──────────────────┐
│ GitHub Actions   │ (CI/CD)
│ - Test           │ - Build
│ - Coverage       │ - Push image
└──────┬───────────┘
       │ Deploy
       ↓
┌──────────────────┐
│  Your Server     │ (production)
│  45.177.152.60   │ 
│  Docker running  │ 
└──────────────────┘
```

---

## 🆘 Common Issues

### Issue: "Permission denied (publickey)"

```bash
# Solution: Check SSH key
ls -la ~/.ssh/id_anexar_deploy
chmod 600 ~/.ssh/id_anexar_deploy

# Add to ssh-agent
ssh-add ~/.ssh/id_anexar_deploy

# Test
ssh -i ~/.ssh/id_anexar_deploy anexo_tecnologia@45.177.152.60
```

### Issue: "Conflict in merge"

```bash
# Solution: Resolve conflicts manually
git status  # See conflicted files
nano conflicted-file.py  # Fix manually
git add conflicted-file.py
git commit -m "Resolve merge conflict"
git push origin main
```

### Issue: "Push rejected"

```bash
# Solution: Pull first
git pull origin main
# Fix conflicts if needed
git push origin main
```

---

## 📚 Resources

- [Git Handbook](https://guides.github.com/)
- [GitHub Flow](https://guides.github.com/introduction/flow/)
- [Commit Message Guidelines](https://www.conventionalcommits.org/)
- [SSH Key Setup](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)

---

## ✅ Pre-Deploy Checklist

Before pushing to main/production:

- [ ] All tests pass: `pytest -v`
- [ ] Code is reviewed: `git diff main`
- [ ] No secrets in code: `grep -r "password\|secret" .`
- [ ] `.env.local` not committed: `git status`
- [ ] Commit message is clear
- [ ] Feature branch merged cleanly
- [ ] No merge conflicts
- [ ] Docker builds locally: `docker build -t api-anexar:test .`

---

**Happy coding! 🚀**
