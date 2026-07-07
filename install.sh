#!/bin/bash
# install.sh — Wizard
# Downloads and installs all available skills for your Claude environment.
# Run this script once to install, or again anytime to update.
# Usage: cd ~/.wizard && claude

REPO_URL="https://github.com/galindoraul/wizard.git"
WIZARD_DIR="$HOME/.wizard"
REPOS_DIR="$WIZARD_DIR/.repos"
REPO_DIR="$REPOS_DIR/wizard"
SKILLS_DIR="$WIZARD_DIR/.claude/skills"

echo ""
echo "🧙 Wizard"
echo "─────────────────────────────"
echo ""

# Clone or update
if [ -d "$REPO_DIR/.git" ]; then
    echo "📥 Updating skills..."
    cd "$REPO_DIR" && git pull
else
    echo "📦 First-time setup..."
    mkdir -p "$REPOS_DIR"
    git clone "$REPO_URL" "$REPO_DIR"
fi

# Auto-detect and symlink all skills
mkdir -p "$SKILLS_DIR"
count=0
echo ""
echo "🔗 Installed skills:"

SKILLS_SRC="$REPO_DIR/.claude/skills"
if [ -d "$SKILLS_SRC" ]; then
    for skill_dir in "$SKILLS_SRC"/*/; do
        if [ -f "$skill_dir/SKILL.md" ]; then
            skill_name=$(basename "$skill_dir")
            ln -sf "$skill_dir" "$SKILLS_DIR/$skill_name"
            echo "   ✅ /$skill_name"
            count=$((count + 1))
        fi
    done
fi

echo ""
echo "─────────────────────────────"
echo "✅ Done! $count skill(s) ready."
echo ""
echo "To use: cd ~/.wizard && claude"
echo ""
