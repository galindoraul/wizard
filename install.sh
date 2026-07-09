#!/bin/bash
# install.sh — Wizard
# Downloads and installs all available skills for your Claude environment.
# Run this script once to install, or again anytime to update.

WIZARD_DIR="$HOME/.wizard"
REPO_DIR="$WIZARD_DIR/wizard"
CLAUDE_DIR="$WIZARD_DIR/.claude"

echo ""
echo "🧙 Wizard"
echo "───────────────────────────────────"
echo ""

# Clone or update (bypass corporate SSL interception and cached credentials)
mkdir -p "$WIZARD_DIR"
if [ -d "$REPO_DIR/.git" ]; then
    echo "📥 Updating..."
    git -c http.https://github.com.sslVerify=false -c credential.helper= -C "$REPO_DIR" pull
else
    echo "📦 First-time setup..."
    git -c http.https://github.com.sslVerify=false -c credential.helper= clone https://github.com/galindoraul/wizard.git "$REPO_DIR"
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
