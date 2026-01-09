# Quick Push Commands

Replace `YOUR_REPO_NAME` with your actual repository name.

## Option 1: Add as new remote and push

```bash
# Add your new repo as a remote
git remote add mynewrepo https://github.com/djholty/YOUR_REPO_NAME.git

# Push david_work branch to main branch
git push mynewrepo david_work:main

# Or if you want to push to a branch called david_work
git push mynewrepo david_work
```

## Option 2: Use SSH (recommended if you have SSH keys set up)

```bash
# Add your new repo as a remote (SSH)
git remote add mynewrepo git@github.com:djholty/YOUR_REPO_NAME.git

# Push david_work branch to main branch
git push mynewrepo david_work:main
```

## Option 3: Use the helper script

```bash
./push_to_new_repo.sh djholty YOUR_REPO_NAME
```

## After pushing, you can set it as your default remote:

```bash
# Remove old mygithub remote (optional)
git remote remove mygithub

# Rename newrepo to mygithub
git remote rename mynewrepo mygithub
```

