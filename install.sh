#!/bin/bash
# install.sh — Wizard
# Downloads and installs all available skills for your Claude environment.
# Run this script once to install, or again anytime to update.

WIZARD_DIR="$HOME/.wizard"
REPO_DIR="$WIZARD_DIR/wizard"
CLAUDE_DIR="$WIZARD_DIR/.claude"
RAW_BASE="https://raw.githubusercontent.com/galindoraul/wizard/main"

echo ""
echo "🧙 Wizard"
echo "───────────────────────────────────"
echo ""

# Clone or update
mkdir -p "$WIZARD_DIR"

clone_with_git() {
    if [ -d "$REPO_DIR/.git" ]; then
        git -c http.https://github.com.sslVerify=false -c credential.helper= -C "$REPO_DIR" pull 2>/dev/null
    else
        git -c http.https://github.com.sslVerify=false -c credential.helper= clone https://github.com/galindoraul/wizard.git "$REPO_DIR" 2>/dev/null
    fi
}

download_with_curl() {
    rm -rf "$REPO_DIR"
    mkdir -p "$REPO_DIR"

    # Download manifest (auto-generated list of all files)
    local manifest
    manifest=$(curl -sL "$RAW_BASE/manifest.txt")
    if [ -z "$manifest" ]; then
        echo "   ❌ Could not download manifest"
        return 1
    fi

    # Download each file from manifest
    while IFS= read -r file; do
        [ -z "$file" ] && continue
        local dir=$(dirname "$REPO_DIR/$file")
        mkdir -p "$dir"
        curl -sL "$RAW_BASE/$file" -o "$REPO_DIR/$file"
    done <<< "$manifest"
}

# Try git first, fall back to curl
if clone_with_git; then
    echo "📥 Updated via git"
else
    echo "📥 Downloading files..."
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

# Add wizard alias (auto-updates + ensures claude is installed)
SHELL_RC="$HOME/.zshrc"
ALIAS_LINE='alias wizard="(curl -sL https://raw.githubusercontent.com/galindoraul/wizard/main/install.sh | bash > /dev/null 2>&1 &); command -v claude >/dev/null 2>&1 || devfeature install claude_code; cd ~/.wizard && claude"'
grep -v 'alias wizard=' "$SHELL_RC" > "$SHELL_RC.tmp" 2>/dev/null && mv "$SHELL_RC.tmp" "$SHELL_RC"
echo '' >> "$SHELL_RC"
echo "$ALIAS_LINE" >> "$SHELL_RC"

echo ""
echo "   ⚡ Alias 'wizard' ready (auto-updates on launch)"
echo ""
echo "───────────────────────────────────"
echo "✅ Done! Restart terminal, then type: wizard"
echo ""
