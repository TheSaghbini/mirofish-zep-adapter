#!/bin/bash
# Push Zep Adapter to GitHub for Railway deployment

REPO_NAME="mirofish-zep-adapter"
GITHUB_USER="your-username"  # Change this

echo "Setting up GitHub repo for Zep Adapter..."

# Initialize git
git init
git add .
git commit -m "Initial commit: Zep-OpenClaw Adapter"

# Create repo on GitHub (you need to do this manually first)
echo ""
echo "1. Create a new repo on GitHub: https://github.com/new"
echo "   Name: $REPO_NAME"
echo "   Make it public or private"
echo ""
echo "2. Then run:"
echo "   git remote add origin https://github.com/$GITHUB_USER/$REPO_NAME.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "3. In Railway:"
echo "   - New Project → Deploy from GitHub repo"
echo "   - Select $REPO_NAME"
echo "   - Add environment variable:"
echo "     DATABASE_URL=postgresql://postgres:8hx2nuo8kfovxwnxwp3lx7slxapfcd99@postgres.railway.internal:5432/postgres"
echo ""
echo "4. Deploy!"
