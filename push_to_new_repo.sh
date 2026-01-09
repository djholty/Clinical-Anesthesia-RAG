#!/bin/bash

# Script to push david_work branch to a new GitHub repository
# Usage: ./push_to_new_repo.sh <your-github-username> <repo-name>

if [ $# -lt 2 ]; then
    echo "Usage: $0 <github-username> <repo-name>"
    echo ""
    echo "Example:"
    echo "  $0 djholty Clinical-Anesthesia-RAG"
    echo ""
    echo "First, create the repository on GitHub at https://github.com/new"
    echo "Then run this script with your username and repo name."
    exit 1
fi

GITHUB_USER=$1
REPO_NAME=$2
REPO_URL="https://github.com/${GITHUB_USER}/${REPO_NAME}.git"

echo "=========================================="
echo "Pushing to new GitHub repository"
echo "=========================================="
echo "Repository: ${REPO_URL}"
echo "Branch: david_work -> main"
echo ""

# Check if we're on david_work branch
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "david_work" ]; then
    echo "⚠️  Warning: You're on branch '$CURRENT_BRANCH', not 'david_work'"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Add the new remote
echo "Adding remote 'newrepo'..."
git remote add newrepo "${REPO_URL}" 2>/dev/null

if [ $? -ne 0 ]; then
    echo "⚠️  Remote 'newrepo' already exists. Removing and re-adding..."
    git remote remove newrepo
    git remote add newrepo "${REPO_URL}"
fi

# Push to the new repo
echo ""
echo "Pushing david_work branch to ${REPO_URL}..."
echo ""

# Try HTTPS first
git push newrepo david_work:main

if [ $? -ne 0 ]; then
    echo ""
    echo "⚠️  HTTPS push failed. Trying SSH..."
    SSH_URL="git@github.com:${GITHUB_USER}/${REPO_NAME}.git"
    git remote set-url newrepo "${SSH_URL}"
    git push newrepo david_work:main
fi

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Successfully pushed to ${REPO_URL}"
    echo ""
    echo "To set this as your default remote:"
    echo "  git remote remove mygithub  # optional: remove old remote"
    echo "  git remote rename newrepo mygithub"
else
    echo ""
    echo "❌ Push failed. Please check:"
    echo "  1. Repository exists on GitHub"
    echo "  2. You have push access"
    echo "  3. Your GitHub credentials are configured"
    exit 1
fi

