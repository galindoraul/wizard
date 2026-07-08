# install.ps1 — Wizard
# Downloads and installs all available skills for your Claude environment.
# Run this script once to install, or again anytime to update.
# Usage in PowerShell: irm https://raw.githubusercontent.com/galindoraul/wizard/main/install.ps1 | iex

Write-Host ""
Write-Host "🧙 Wizard" -ForegroundColor Cyan
Write-Host "───────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""

$WizardDir = "$env:USERPROFILE\.wizard"
$RepoDir = "$WizardDir\wizard"
$ClaudeDir = "$WizardDir\.claude"

# Check git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Git not found. Install it from https://git-scm.com/download/win" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Git found" -ForegroundColor Green

# Clone or update
if (-not (Test-Path "$RepoDir\.git")) {
    Write-Host "📦 First-time setup..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $WizardDir -Force | Out-Null
    git clone https://github.com/galindoraul/wizard.git $RepoDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Git clone failed. Check your internet connection." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "📥 Updating..." -ForegroundColor Yellow
    Push-Location $RepoDir
    git pull -q
    Pop-Location
}

# Clean old symlinks/junctions
if (Test-Path $ClaudeDir) {
    Remove-Item $ClaudeDir -Recurse -Force
}
New-Item -ItemType Directory -Path $ClaudeDir -Force | Out-Null

# Process .claude/ contents from repo
$SkillsSrc = "$RepoDir\.claude\skills"
$count = 0

if (Test-Path $SkillsSrc) {
    $SkillsTarget = "$ClaudeDir\skills"
    New-Item -ItemType Directory -Path $SkillsTarget -Force | Out-Null

    Get-ChildItem -Path $SkillsSrc -Directory | ForEach-Object {
        $skillDir = $_.FullName
        $skillName = $_.Name
        if (Test-Path "$skillDir\SKILL.md") {
            # Create directory junction (like symlink but works without admin)
            cmd /c mklink /J "$SkillsTarget\$skillName" "$skillDir" | Out-Null
            Write-Host "   ✅ skills/$skillName" -ForegroundColor Green
            $count++
        }
    }
}

# Process other .claude/ subdirs
Get-ChildItem -Path "$RepoDir\.claude" -Directory | Where-Object { $_.Name -ne "skills" } | ForEach-Object {
    $subdir = $_.FullName
    $subdirName = $_.Name
    $target = "$ClaudeDir\$subdirName"
    New-Item -ItemType Directory -Path $target -Force | Out-Null

    Get-ChildItem -Path $subdir -Directory | ForEach-Object {
        $item = $_.FullName
        $itemName = $_.Name
        cmd /c mklink /J "$target\$itemName" "$item" | Out-Null
        Write-Host "   ✅ $subdirName/$itemName" -ForegroundColor Green
        $count++
    }
}

# Process root files in .claude/
Get-ChildItem -Path "$RepoDir\.claude" -File | ForEach-Object {
    $file = $_.FullName
    $fileName = $_.Name
    cmd /c mklink "$ClaudeDir\$fileName" "$file" | Out-Null
    Write-Host "   ✅ $fileName" -ForegroundColor Green
}

# Add wizard function to PowerShell profile
$profilePath = $PROFILE
$aliasLine = 'function wizard { Push-Location $env:USERPROFILE\.wizard; Start-Job { Set-Location $env:USERPROFILE\.wizard\wizard; git pull -q } | Out-Null; claude; Pop-Location }'

if (-not (Test-Path $profilePath)) {
    New-Item -ItemType File -Path $profilePath -Force | Out-Null
}

if (-not (Select-String -Path $profilePath -Pattern "function wizard" -Quiet -ErrorAction SilentlyContinue)) {
    Add-Content -Path $profilePath -Value "`n$aliasLine"
    Write-Host ""
    Write-Host "   ⚡ Command 'wizard' added (auto-updates on launch)" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "───────────────────────────────────" -ForegroundColor DarkGray
Write-Host "✅ Done! $count skill(s) ready." -ForegroundColor Green
Write-Host ""
Write-Host "   Close this window, open a new PowerShell, and type: wizard" -ForegroundColor White
Write-Host ""
