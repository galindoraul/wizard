#!/bin/bash
# install.sh — Wizard
# Downloads and installs all available skills for your Claude environment.
# Run this script once to install, or again anytime to update.
# Usage: cd ~/.wizard && claude

WIZARD_DIR="$HOME/.wizard"
REPO_DIR="$WIZARD_DIR/wizard"
CLAUDE_DIR="$WIZARD_DIR/.claude"

echo ""
echo "🧙 Wizard"
echo "───────────────────────────────────"
echo ""

# Clone or update
mkdir -p "$WIZARD_DIR"
if [ -d "$REPO_DIR/.git" ]; then
    echo "📥 Updating..."
    cd "$REPO_DIR" && git pull
else
    echo "📦 First-time setup..."
    git clone https://github.com/galindoraul/wizard.git "$REPO_DIR"
fi

# Clean old symlinks
rm -rf "$CLAUDE_DIR"
mkdir -p "$CLAUDE_DIR"

# Process all .claude/ contents from repo
process_repo() {
    local repo_dir="$1"
    local label="$2"
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

echo ""
echo "🔗 Installed:"
process_repo "$REPO_DIR" "wizard"

echo ""
echo "───────────────────────────────────"
echo "✅ Done! Use: cd ~/.wizard && claude"
echo ""
