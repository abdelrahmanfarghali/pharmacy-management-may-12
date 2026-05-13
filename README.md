## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Branch Strategy](#branch-strategy)
- [Daily Git Workflow](#daily-git-workflow)
- [Commit Message Guide](#commit-message-guide)
- [Push & Pull Guide](#push--pull-guide)
- [Merge & Rebase Guide](#merge--rebase-guide)
- [Pull Request Checklist](#pull-request-checklist)
- [Hotfix Workflow](#hotfix-workflow)
- [Useful Git Commands](#useful-git-commands)
- [Git Configuration](#git-configuration)

---

## Overview

This repository contains the source code and custom modules for the Odoo 18.0 implementation. All contributors must follow the branching model, commit conventions, and review process described in this document to maintain a clean, traceable project history.

## Getting Started

```bash
# 1. Clone the repository
git clone [repository-url] --branch [branch-name] --depth 1
cd [repository-folder]

# 2. Set up Python virtual environment
python3.10 -m venv .venv
source .venv/bin/activate          # Linux / macOS
.venv\Scripts\Activate.ps1         # Windows PowerShell

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Configure your local database (see docs/setup.md for full config)
cp odoo.conf.example odoo.conf

# 5. Run the server
python odoo-bin -c odoo.conf -i base --dev xml,qweb
```

---

## Branch Strategy

This project follows **Git Flow** adapted for Odoo versioning. All branches are prefixed with the Odoo version to avoid ambiguity across releases.

```
main
 └── 18.0                        ← stable production branch
      ├── feat/18.0-<topic>       ← new features
      ├── fix/18.0-<topic>        ← bug fixes
      ├── hotfix/18.0-<topic>     ← urgent production patches
      ├── refactor/18.0-<topic>   ← code restructuring (no behaviour change)
      ├── chore/<topic>           ← tooling, deps, CI — no version prefix needed
      └── docs/<topic>            ← documentation only
```

### Branch naming rules

- Use **lowercase kebab-case** only — no spaces, no underscores
- Keep names **short and descriptive** (3–5 words max)
- Always include the version prefix (`18.0-`) for feature/fix/hotfix/refactor branches
- Reference the issue or UC ID where applicable

**Examples**

```
feat/18.0-sale-pricelist-v2
fix/18.0-stock-negative-quant
hotfix/18.0-invoice-vat-crash
refactor/18.0-mrp-bom-service
chore/bump-psycopg2-3.1
docs/install-guide-windows
```

---

## Daily Git Workflow

### Start a new task

```bash
# Always branch from the latest 18.0
git checkout 18.0
git pull origin 18.0

# Create and switch to your feature branch
git checkout -b feat/18.0-your-feature-name

# Verify you are on the right branch
git branch --show-current
```

### Work and stage changes

```bash
# Check what changed
git status
git diff

# Stage specific files (preferred — avoid blanket `git add .`)
git add addons/sale/models/sale_order.py
git add addons/sale/views/sale_order_views.xml

# Stage all changes in a specific module directory
git add addons/sale/

# Review staged diff before committing
git diff --staged

# Commit (see Commit Message Guide below)
git commit -m "feat(sale): add automatic tax recalculation on currency change"
```

### Keep your branch up to date

```bash
# Fetch latest changes from remote
git fetch origin

# Rebase your branch on top of 18.0 (preferred over merge for feature branches)
git rebase origin/18.0

# If conflicts arise during rebase:
git status                          # identify conflicting files
# ... resolve conflicts in editor ...
git add <resolved-file>
git rebase --continue

# Abort rebase if needed
git rebase --abort
```

---

## Commit Message Guide

Follow **Conventional Commits v1.0.0**. Every commit must be atomic — one logical change per commit.

### Format

```
<type>(<scope>): <short imperative summary>

[optional body — explain WHY, not WHAT. Wrap at 72 chars.]

[optional footer — issue refs, breaking change notice]
```

### Rules

- **Subject line ≤ 50 characters**
- **Use imperative mood** — "add", "fix", "remove" — never "added" or "fixes"
- **Body and footer are optional** but required for breaking changes
- **Scope = Odoo technical module name** (`sale`, `stock`, `account`, `mrp`, `hr`)

### Type reference

| Type       | When to use                                          |
|------------|------------------------------------------------------|
| `feat`     | New user-facing feature                              |
| `fix`      | Bug fix visible to end users                         |
| `docs`     | Documentation only                                   |
| `style`    | Formatting, whitespace — zero logic change           |
| `refactor` | Code restructure without behaviour change            |
| `perf`     | Performance improvement                              |
| `test`     | Add or update tests — no production code             |
| `chore`    | Build tools, dependency bumps, CI configuration      |
| `ci`       | CI/CD pipeline files only                            |
| `revert`   | Reverts a previous commit                            |

### Breaking changes

Append `!` after type and add a `BREAKING CHANGE:` footer:

```
feat!(account)!: rename journal entry fields for IFRS compliance

Migrates `debit_account_id` → `account_debit_id` and
`credit_account_id` → `account_credit_id` across all journal models.

BREAKING CHANGE: Any custom module referencing the old field names
will break. Run the provided migration script: scripts/migrate_v18_journals.py
Closes #204
```

### Examples

```bash
# Feature
git commit -m "feat(sale): add multi-currency discount lines"

# Bug fix with issue reference
git commit -m "fix(stock): correct negative quant on return transfer

Stock quants were going negative when a return was validated without
first confirming the original picking. Added a guard in _action_done.

Closes #117"

# Chore (no scope needed)
git commit -m "chore: bump psycopg2-binary to 2.9.9"

# Docs
git commit -m "docs(readme): add Apple Silicon compiler flags note"

# Revert
git commit -m "revert: feat(sale): add multi-currency discount lines

Reverts commit a1b2c3d — caused regression in SO confirmation flow.
Tracked in #135"
```

---

## Push & Pull Guide

### Push your branch

```bash
# First push — set upstream tracking
git push --set-upstream origin feat/18.0-your-feature-name

# Subsequent pushes
git push

# Force push after a rebase (your feature branch only — NEVER on 18.0 or main)
git push --force-with-lease
```

> `--force-with-lease` is safer than `--force`. It aborts if someone else pushed to the same branch since your last fetch.

### Pull latest changes

```bash
# Pull with rebase (keeps linear history — recommended)
git pull --rebase origin 18.0

# Pull with merge (creates a merge commit — use only if rebase is not appropriate)
git pull origin 18.0
```

### Fetch without merging

```bash
# Download all remote changes without applying them
git fetch origin

# Inspect what changed on 18.0 before applying
git log HEAD..origin/18.0 --oneline

# Then apply when ready
git rebase origin/18.0
```

---

## Merge & Rebase Guide

### Merge feature branch into 18.0 (via Pull Request)

All merges into `18.0` must go through a Pull Request on GitHub. Direct pushes to `18.0` are protected.

```bash
# On your feature branch — ensure it is rebased and clean
git checkout feat/18.0-your-feature-name
git rebase origin/18.0

# Push final state
git push --force-with-lease

# Open Pull Request on GitHub targeting 18.0
# Assign at least one reviewer before merging
```

### Squash merge (keep 18.0 history clean)

Use **Squash and Merge** on GitHub for feature branches with multiple WIP commits. Use **Merge Commit** only for hotfixes or branches where full commit history is important.

### Local merge (for integrating into a long-running feature branch)

```bash
# Merge 18.0 updates into your branch (to resolve conflicts early)
git checkout feat/18.0-your-feature-name
git merge origin/18.0

# Resolve any conflicts, then
git add <resolved-files>
git commit
```

### Delete branch after merge

```bash
# Delete remote branch (GitHub does this automatically if enabled)
git push origin --delete feat/18.0-your-feature-name

# Delete local branch
git branch -d feat/18.0-your-feature-name

# Force-delete unmerged local branch (use with caution)
git branch -D feat/18.0-your-feature-name
```

---

## Pull Request Checklist

Before opening a PR, verify all of the following:

- [ ] Branch is rebased on the latest `18.0`
- [ ] All commits follow the Conventional Commit format
- [ ] No secrets, passwords, or `odoo.conf` credentials committed
- [ ] No `.venv/`, `__pycache__/`, or `.pyc` files staged
- [ ] New functionality is covered by at least one test (`/tests/`)
- [ ] Odoo module version bumped in `__manifest__.py` if applicable
- [ ] `README.md` or module docstring updated if behaviour changed
- [ ] PR title follows the same `type(scope): summary` format
- [ ] PR is linked to the relevant issue or UC ID

---

## Hotfix Workflow

Use when a critical bug must go to production immediately, bypassing the normal feature cycle.

```bash
# 1. Branch from 18.0 (production branch)
git checkout 18.0
git pull origin 18.0
git checkout -b hotfix/18.0-invoice-vat-crash

# 2. Apply the minimal fix
# ... edit files ...
git add <file(s)>
git commit -m "fix(<module>): <summary>

<description>

Closes #302"

# 3. Push and open PR targeting 18.0
git push --set-upstream origin hotfix/18.0-invoice-vat-crash

# 4. After merge, tag the release
git checkout 18.0
git pull origin 18.0
git tag -a v18.0.1 -m "hotfix: prevent VAT crash on zero-amount invoice lines"
git push origin v18.0.1

# 5. Clean up
git branch -d hotfix/18.0-invoice-vat-crash
git push origin --delete hotfix/18.0-invoice-vat-crash
```

---

## Useful Git Commands

### Inspect & navigate

```bash
# Compact, visual branch log
git log --oneline --graph --all --decorate

# Log for a specific file
git log --oneline -- addons/sale/models/sale_order.py

# Show what changed in a specific commit
git show <commit-hash>

# Find which commit introduced a string
git log -S "def _compute_tax_totals" --oneline

# See all local branches with last commit date
git branch -v

# List all remote branches
git branch -r
```

### Undo & recover

```bash
# Unstage a file (keep changes in working tree)
git restore --staged addons/sale/models/sale_order.py

# Discard local changes to a file
git restore addons/sale/models/sale_order.py

# Undo last commit — keep changes staged
git reset --soft HEAD~1

# Undo last commit — keep changes unstaged
git reset --mixed HEAD~1

# Undo last commit — discard all changes (DESTRUCTIVE)
git reset --hard HEAD~1

# Recover a deleted branch using reflog
git reflog
git checkout -b feat/18.0-recovered-branch <commit-hash>
```

### Stash

```bash
# Save uncommitted work temporarily
git stash push -m "wip: sale pricelist discount"

# List all stashes
git stash list

# Apply most recent stash (keeps it in stash list)
git stash apply

# Apply and remove from stash list
git stash pop

# Apply a specific stash
git stash apply stash@{2}

# Drop a stash
git stash drop stash@{0}
```

### Tags

```bash
# Create an annotated tag
git tag -a v18.0.0 -m "Initial 18.0 stable release"

# Push a tag
git push origin v18.0.0

# Push all tags
git push origin --tags

# List all tags
git tag -l

# Delete a tag locally and remotely
git tag -d v18.0.0
git push origin --delete v18.0.0
```

---

## Git Configuration Cheatsheet

Run these once per machine before contributing:

```bash
# Identity (required — shows in commit history)
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"

# Default branch name
git config --global init.defaultBranch main

# Rebase on pull (keeps history linear)
git config --global pull.rebase true

# Sign commits with GPG (recommended)
git config --global commit.gpgsign true
git config --global user.signingkey <YOUR_GPG_KEY_ID>

# Useful aliases
git config --global alias.lg  "log --oneline --graph --all --decorate"
git config --global alias.st  "status -sb"
git config --global alias.undo "reset --soft HEAD~1"
git config --global alias.wip  "commit -am 'chore: wip'"
```

---

## Contributing

1. Fork or clone the repository
2. Create your branch following the [Branch Strategy](#branch-strategy)
3. Commit following the [Commit Message Guide](#commit-message-guide)
4. Open a Pull Request and complete the [PR Checklist](#pull-request-checklist)
5. Await review — at least one approval is required before merging

For questions, open an issue or contact the project maintainer.