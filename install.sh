#!/bin/bash
# install.sh — Wizard
# Downloads and installs all available skills for your Claude environment.
# Run this script once to install, or again anytime to update.

WIZARD_DIR="$HOME/.wizard"
REPO_DIR="$WIZARD_DIR/wizard"
CLAUDE_DIR="$WIZARD_DIR/.claude"
RAW_BASE="https://raw.githubusercontent.com/galindoraul/wizard/main"

# File manifest
FILES=(
    ".claude/skills/config.json"
    ".claude/skills/tasks-creation/SKILL.md"
    ".claude/skills/tasks-creation/assets/kt.md"
    ".claude/skills/tasks-creation/assets/test_request_after_closure.md"
    ".claude/skills/tasks-creation/assets/metrics_review.md"
    ".claude/skills/tasks-creation/assets/sev_creation.md"
    ".claude/skills/tasks-creation/assets/test_execution.md"
    ".claude/skills/tasks-creation/assets/training.md"
    ".claude/skills/tasks-creation/assets/access_request.md"
    ".claude/skills/tasks-creation/assets/support_activities.md"
    ".claude/skills/tasks-creation/assets/tool.md"
    ".claude/skills/tasks-creation/assets/reporting.md"
    ".claude/skills/tasks-creation/assets/documentation_update.md"
    ".claude/skills/tasks-creation/assets/aip_review.md"
    ".claude/skills/tasks-creation/assets/data_preparation.md"
    ".claude/skills/tasks-creation/assets/sev_followup.md"
    ".claude/skills/tasks-creation/assets/documentation_creation.md"
    ".claude/skills/tasks-creation/assets/peer_review.md"
    ".claude/skills/tasks-creation/assets/roadmap.md"
    ".claude/skills/tasks-creation/assets/bugs_followup.md"
    ".claude/skills/tasks-creation/assets/clarification.md"
    ".claude/skills/tasks-creation/assets/test_creation.md"
    ".claude/skills/tasks-creation/assets/onboarding.md"
    ".claude/skills/tasks-creation/assets/data_request.md"
    ".claude/skills/tasks-to-click2sync/SKILL.md"
    ".claude/skills/tasks-to-click2sync/scripts/pto-reader.py"
    ".claude/skills/tasks-to-click2sync/scripts/validate-tasks.py"
    ".claude/skills/tasks-to-click2sync/scripts/row-builder.py"
    ".claude/skills/tasks-to-click2sync/scripts/json-writer.py"
    ".claude/skills/tasks-to-click2sync/scripts/read-tasks.py"
)

echo ""
echo "🧙 Wizard"
echo "───────────────────────────────────"
echo ""

# Clone or update
mkdir -p "$WIZARD_DIR"

clone_with_git() {
    if [ -d "$REPO_DIR/.git" ]; then
        echo "📥 Updating..."
        git -c http.https://github.com.sslVerify=false -c credential.helper= -C "$REPO_DIR" pull 2>/dev/null
    else
        echo "📦 First-time setup..."
        git -c http.https://github.com.sslVerify=false -c credential.helper= clone https://github.com/galindoraul/wizard.git "$REPO_DIR" 2>/dev/null
    fi
}

download_with_curl() {
    echo "📥 Downloading files..."
    rm -rf "$REPO_DIR"
    mkdir -p "$REPO_DIR"
    local failed=0
    for file in "${FILES[@]}"; do
        local dir=$(dirname "$REPO_DIR/$file")
        mkdir -p "$dir"
        curl -sL "$RAW_BASE/$file" -o "$REPO_DIR/$file"
        if [ $? -ne 0 ]; then
            echo "   ❌ Failed: $file"
            failed=1
        fi
    done
    return $failed
}

# Try git first, fall back to curl
if ! clone_with_git; then
    echo "⚠️  git failed, using direct download..."
    download_with_curl
fi

# Clean old symlinks
rm -rf "$CLAUDE_DIR"
mkdir -p "$CLAUDE_DIR"

# Process all .claude/ contents from repo
process_repo() {
    local repo_dir="$1"
    local src="$repo_dir/.claude"
    [ ! -d "$src" ] && return
    for subdir in "$src"/*/; do
        [ ! -d "$subdir" ] && continue
        subdir_name=$(basename "$subdir")
        target="$CLAUDE_DIR/$subdir_name"
        mkdir -p "$target"
        for item in "$subdir"*/; do
            [ ! -d "$item" ] && continue
            item_name=$(basename "$item")
            ln -sf "$item" "$target/$item_name"
            echo "   ✅ $subdir_name/$item_name"
        done
    done
    for file in "$src"/*; do
        [ -d "$file" ] && continue
        [ ! -f "$file" ] && continue
        file_name=$(basename "$file")
        ln -sf "$file" "$CLAUDE_DIR/$file_name"
        echo "   ✅ $file_name"
    done
}

echo "🔗 Installed:"
process_repo "$REPO_DIR"

# Add wizard alias (safe: remove old + append new, avoids sed & corruption)
SHELL_RC="$HOME/.zshrc"
ALIAS_LINE='alias wizard="cd ~/.wizard && (cd wizard && git pull -q &) 2>/dev/null; claude"'
grep -v 'alias wizard=' "$SHELL_RC" > "$SHELL_RC.tmp" 2>/dev/null && mv "$SHELL_RC.tmp" "$SHELL_RC"
echo '' >> "$SHELL_RC"
echo "$ALIAS_LINE" >> "$SHELL_RC"

echo ""
echo "   ⚡ Alias 'wizard' ready (auto-updates on launch)"
echo ""
echo "───────────────────────────────────"
echo "✅ Done! Restart terminal, then type: wizard"
echo ""
