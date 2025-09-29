#!/bin/bash

echo "🐝 Hive Initial Setup Script"
echo "============================"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v git &> /dev/null; then
    echo "❌ Git is not installed"
    exit 1
fi

if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) is not installed"
    echo "   Install from: https://cli.github.com/"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed"
    exit 1
fi

if ! command -v tmux &> /dev/null; then
    echo "❌ tmux is not installed"
    echo "   Install with: apt-get install tmux (or brew install tmux)"
    exit 1
fi

echo "✅ All prerequisites found"
echo ""

# Check GitHub authentication
echo "Checking GitHub authentication..."
if ! gh auth status &> /dev/null; then
    echo "❌ GitHub CLI not authenticated"
    echo "   Run: gh auth login"
    exit 1
fi
echo "✅ GitHub authenticated"
echo ""

# Get repository info
REMOTE_URL=$(git remote get-url origin 2>/dev/null)
if [ -z "$REMOTE_URL" ]; then
    echo "⚠️  No remote origin found"
    echo "Please enter your GitHub username:"
    read GITHUB_USER
    echo "Creating remote repository..."
    gh repo create hive --public --source=. --remote=origin
else
    echo "✅ Remote origin found: $REMOTE_URL"
fi

# Extract owner/repo from remote URL
OWNER_REPO=$(git remote get-url origin | sed 's/.*github.com[:/]\(.*\)\.git/\1/')
echo "Repository: $OWNER_REPO"
echo ""

# Push initial commit if needed
echo "Pushing initial commit..."
git add .
git commit -m "chore: initial hive setup" || true
git push -u origin main || true
echo ""

# Set up branch protection
echo "Setting up branch protection for main..."
gh api -X PUT "repos/$OWNER_REPO/branches/main/protection" \
  -f required_status_checks[strict]=true \
  -f required_status_checks.contexts[]="backend" \
  -f required_status_checks.contexts[]="frontend" \
  -f enforce_admins=false \
  -f required_pull_request_reviews.required_approving_review_count=0 \
  -f allow_force_pushes=false \
  -f allow_deletions=false \
  2>/dev/null && echo "✅ Branch protection enabled" || echo "⚠️  Branch protection may already be set"
echo ""

# Create worker branches
echo "Creating worker branches..."
git branch worker/backend main 2>/dev/null || echo "  worker/backend already exists"
git branch worker/frontend main 2>/dev/null || echo "  worker/frontend already exists"
git branch worker/infra main 2>/dev/null || echo "  worker/infra already exists"
echo ""

# Create worktrees
echo "Creating worktrees..."
if [ ! -d "workspaces/backend" ]; then
    git worktree add workspaces/backend worker/backend
    echo "✅ Created backend worktree"
else
    echo "  Backend worktree already exists"
fi

if [ ! -d "workspaces/frontend" ]; then
    git worktree add workspaces/frontend worker/frontend
    echo "✅ Created frontend worktree"
else
    echo "  Frontend worktree already exists"
fi

if [ ! -d "workspaces/infra" ]; then
    git worktree add workspaces/infra worker/infra
    echo "✅ Created infra worktree"
else
    echo "  Infra worktree already exists"
fi
echo ""

# Push worker branches
echo "Pushing worker branches to remote..."
git push origin worker/backend 2>/dev/null || echo "  worker/backend already pushed"
git push origin worker/frontend 2>/dev/null || echo "  worker/frontend already pushed"
git push origin worker/infra 2>/dev/null || echo "  worker/infra already pushed"
echo ""

# Python environment reminder
echo "📝 Next steps:"
echo "1. Create Python virtual environment:"
echo "   python3 -m venv .venv"
echo "   source .venv/bin/activate"
echo "   pip install -r requirements.txt"
echo ""
echo "2. Start the hive:"
echo "   Terminal 1: ./setup.sh"
echo "   Terminal 2: python run.py --dry-run"
echo ""
echo "✅ Initial setup complete!"
