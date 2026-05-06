# ==============================================================================
# setup-machine.ps1
# ONE-TIME machine bootstrap for voice-outbound-agent project.
# Safe to re-run.
# ==============================================================================

Clear-Host

Write-Host ""
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "VOICE OUTBOUND AGENT - MACHINE BOOTSTRAP" -ForegroundColor Cyan
Write-Host "Run ONCE per machine. Safe to re-run." -ForegroundColor Cyan
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host ""

Read-Host "Press ENTER to begin"

# STEP 1 - Check prerequisites
Write-Host ""
Write-Host "[1/9] Checking prerequisites..." -ForegroundColor Yellow

$missing = @()

# Node.js
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    $missing += "Node.js 20+ -> https://nodejs.org"
}
else {
    $nodeVer = node --version
    Write-Host "[OK] Node.js $nodeVer" -ForegroundColor Green
}

# npm
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    $missing += "npm -> comes with Node.js"
}
else {
    $npmVer = npm --version
    Write-Host "[OK] npm $npmVer" -ForegroundColor Green
}

# Git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    $missing += "Git -> https://git-scm.com/download/win"
}
else {
    $gitVer = git --version
    Write-Host "[OK] $gitVer" -ForegroundColor Green
}

# Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    $missing += "Python 3.13 -> https://www.python.org/downloads"
}
else {
    $pyVer = python --version 2>&1
    Write-Host "[OK] $pyVer" -ForegroundColor Green
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "[ERROR] Missing prerequisites:" -ForegroundColor Red

    foreach ($item in $missing) {
        Write-Host " - $item" -ForegroundColor Red
    }

    Write-Host ""
    Write-Host "Install missing software and re-run this script." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "[OK] All prerequisites installed." -ForegroundColor Green

# STEP 2 - Claude Code CLI
Write-Host ""
Write-Host "[2/9] Installing Claude Code CLI..." -ForegroundColor Yellow

npm install -g @anthropic-ai/claude-code

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Claude Code installed." -ForegroundColor Green
}
else {
    Write-Host "[ERROR] Failed installing Claude Code." -ForegroundColor Red
    exit 1
}

# STEP 3 - MCP servers
Write-Host ""
Write-Host "[3/9] Installing MCP servers..." -ForegroundColor Yellow

$mcpPackages = @(
    "@modelcontextprotocol/server-filesystem",
    "@modelcontextprotocol/server-memory",
    "@modelcontextprotocol/server-sequential-thinking"
)

foreach ($pkg in $mcpPackages) {

    Write-Host "Installing $pkg ..." -ForegroundColor DarkGray

    npm install -g $pkg

    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Installed $pkg" -ForegroundColor Green
    }
    else {
        Write-Host "[WARN] Failed installing $pkg" -ForegroundColor Yellow
    }
}

# STEP 4 - cc-status-line
Write-Host ""
Write-Host "[4/9] Installing cc-status-line..." -ForegroundColor Yellow

npx cc-status-line@latest --install

# STEP 5 - Claude folder
Write-Host ""
Write-Host "[5/9] Creating Claude config..." -ForegroundColor Yellow

$claudeDir = "$env:USERPROFILE\.claude"

if (-not (Test-Path $claudeDir)) {
    New-Item -ItemType Directory -Path $claudeDir | Out-Null
}

# settings.json
@'
{
  "defaultModel": "claude-sonnet-4-6",
  "autoApprove": false,
  "theme": "dark"
}
'@ | Set-Content "$claudeDir\settings.json" -Encoding UTF8

Write-Host "[OK] settings.json written." -ForegroundColor Green

# CLAUDE.md
@'
# Global Claude Rules

- Watch context usage
- Use Sonnet for coding
- Never commit directly to main
- Use /clear at 50 percent context
'@ | Set-Content "$claudeDir\CLAUDE.md" -Encoding UTF8

Write-Host "[OK] CLAUDE.md written." -ForegroundColor Green

# STEP 6 - Install Python packages
Write-Host ""
Write-Host "[6/9] Installing Python packages..." -ForegroundColor Yellow

$pipTools = @(
    "alembic",
    "httpx",
    "fastapi",
    "uvicorn",
    "rq",
    "redis",
    "psycopg2-binary",
    "python-dotenv",
    "pytest",
    "pytest-asyncio"
)

foreach ($tool in $pipTools) {

    Write-Host "Installing $tool ..." -ForegroundColor DarkGray

    pip install $tool --quiet

    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] $tool" -ForegroundColor Green
    }
    else {
        Write-Host "[WARN] Failed: $tool" -ForegroundColor Yellow
    }
}

# STEP 7 - Create staging folders
Write-Host ""
Write-Host "[7/9] Creating folders..." -ForegroundColor Yellow

$staging = "D:\staging"

if (-not (Test-Path $staging)) {
    New-Item -ItemType Directory -Path $staging | Out-Null
}

$setupDir = "D:\staging\_claude-setup\projects\voice-outbound-agent"

if (-not (Test-Path $setupDir)) {
    New-Item -ItemType Directory -Path $setupDir -Force | Out-Null
}

Write-Host "[OK] Folder structure created." -ForegroundColor Green

# STEP 8 - Plugin instructions
Write-Host ""
Write-Host "[8/9] Manual Claude plugin setup:" -ForegroundColor Yellow
Write-Host ""
Write-Host "Open Claude Code and install:" -ForegroundColor White
Write-Host " - superpowers" -ForegroundColor Cyan
Write-Host " - code-simplifier" -ForegroundColor Cyan
Write-Host " - context7" -ForegroundColor Cyan
Write-Host " - context-mode" -ForegroundColor Cyan

# STEP 9 - Final
Write-Host ""
Write-Host "==============================================================" -ForegroundColor Green
Write-Host "[OK] MACHINE BOOTSTRAP COMPLETE" -ForegroundColor Green
Write-Host "==============================================================" -ForegroundColor Green
Write-Host ""

Write-Host "NEXT:" -ForegroundColor Cyan
Write-Host "1. Copy PRD.md into:" -ForegroundColor White
Write-Host "   D:\staging\_claude-setup\projects\voice-outbound-agent" -ForegroundColor Yellow
Write-Host ""
Write-Host "2. Run:" -ForegroundColor White
Write-Host "   .\setup-voice-outbound-agent.ps1" -ForegroundColor Yellow
Write-Host ""