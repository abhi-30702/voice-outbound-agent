# ==============================================================================
# setup-voice-outbound-agent.ps1
# Project bootstrap for voice-outbound-agent.
# Reads PRD.md and scaffolds the full folder + config structure.
# Owner: Srinivas / Fidelitus Corp + SherpaVector
# ==============================================================================

# -- PROJECT VARIABLES ---------------------------------------------------------
$PROJECT_NAME  = "voice-outbound-agent"
$PROJECT_ROOT  = "D:\Projects\voice-outbound-agent"
$STACK         = "Python 3.13, FastAPI, PostgreSQL 16, Redis, Docker, Next.js 14, Retell AI, Telnyx SIP, ElevenLabs TTS, Silero VAD, Anthropic Claude Sonnet"
$MODULES       = @(
    "db-schema",
    "dialing-worker",
    "retell-integration",
    "webhook-receiver",
    "post-call-analysis",
    "vad-pipeline",
    "conversation-prompts",
    "dashboard",
    "n8n-flows"
)
$PHASE_CURRENT = 0
# -----------------------------------------------------------------------------

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "   voice-outbound-agent - PROJECT BOOTSTRAP                     " -ForegroundColor Cyan
Write-Host "   Jai Jagannath                                                " -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# -- 0. Create root -------------------------------------------------------------
if (-not (Test-Path $PROJECT_ROOT)) {
    New-Item -ItemType Directory -Path $PROJECT_ROOT -Force | Out-Null
    Write-Host "  [OK] Created: $PROJECT_ROOT" -ForegroundColor Green
} else {
    Write-Host "  [INFO] Root exists: $PROJECT_ROOT" -ForegroundColor DarkGray
}
Set-Location $PROJECT_ROOT

# -- 1. Copy PRD.md if not present ----------------------------------------------
Write-Host ""
Write-Host "[ 1/8 ] Checking for PRD.md..." -ForegroundColor Yellow
$prdSource = "D:\Projects\voice-outbound-agent\PRD.md"
if (-not (Test-Path "$PROJECT_ROOT\PRD.md")) {
    if (Test-Path $prdSource) {
        Copy-Item $prdSource "$PROJECT_ROOT\PRD.md"
        Write-Host "  [OK] PRD.md copied from claude-setup." -ForegroundColor Green
    } else {
        Write-Host "  [WARN] PRD.md not found at $prdSource" -ForegroundColor Yellow
        Write-Host "    Place PRD.md in $PROJECT_ROOT manually before first session." -ForegroundColor DarkGray
    }
} else {
    Write-Host "  [INFO] PRD.md already present." -ForegroundColor DarkGray
}

# -- 2. Folder structure --------------------------------------------------------
Write-Host ""
Write-Host "[ 2/8 ] Creating folder structure..." -ForegroundColor Yellow
$folders = @(
    "tasks",
    "docs",
    "docs\plans",
    "docs\prompts",
    "tests",
    ".claude\skills",
    "n8n-flows",
    "scripts"
) + ($MODULES | ForEach-Object { "app\$_" })

foreach ($f in $folders) {
    $path = Join-Path $PROJECT_ROOT $f
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
        Write-Host "  [OK] $f" -ForegroundColor Green
    } else {
        Write-Host "  [INFO] $f (exists)" -ForegroundColor DarkGray
    }
}

# -- 3. CLAUDE.md ---------------------------------------------------------------
Write-Host ""
Write-Host "[ 3/8 ] Writing CLAUDE.md..." -ForegroundColor Yellow
@"
# CLAUDE.md - voice-outbound-agent
# Extends ~/.claude/CLAUDE.md. Never contradicts it.
# Read PRD.md FIRST before any session. It is the source of truth.

## Stack
$STACK

## Current Phase: $PHASE_CURRENT

## PRD Reference
  Location: PRD.md (project root)
  Read sections: Tech Stack, Module Breakdown, DB Schema, Dialing Worker Logic

## Module Boundaries (one session = one module)
  Session -> db-schema          : app/db-schema/ ONLY
  Session -> dialing-worker     : app/dialing-worker/ ONLY
  Session -> retell-integration : app/retell-integration/ ONLY
  Session -> webhook-receiver   : app/webhook-receiver/ ONLY
  Session -> post-call-analysis : app/post-call-analysis/ ONLY
  Session -> vad-pipeline       : app/vad-pipeline/ ONLY
  Session -> conversation-prompts : app/conversation-prompts/ ONLY
  Session -> dashboard          : app/dashboard/ ONLY
  Session -> n8n-flows          : n8n-flows/ ONLY
  Session -> docker-compose     : docker-compose.yml + Dockerfile per service
  Session -> evals              : tests/ ONLY
  Session -> debug              : one error + one file per session

## Key Architecture Rules
  - DNC check MUST be in SQL (NOT EXISTS), never application-level filtering
  - Dialing worker MUST enforce 1 CPS hard limit via asyncio.sleep(1.0)
  - Timezone gate MUST use lead.timezone; never assume IST
  - All webhook handlers MUST verify x-retell-signature HMAC
  - LLM DB access via memories_role ONLY (scoped schema: agent_operations)
  - Parameterised queries only - no string interpolation in SQL
  - No bare sockets; all telephony via Retell AI + Telnyx SDK

## Conversation Prompts Rule
  - Max sentence: 12 words
  - No bullets, no lists, no special chars in TTS text
  - Spell acronyms phonetically
  - Every step must WAIT for user acknowledgement before advancing

## Environment
  Windows + PowerShell
  Python 3.13 with venv at .venv/
  Node 20+ for Next.js dashboard
  Docker Desktop for containers

## Git
  main / dev / feature/TASK-XXX
  Format: [TASK-XXX] verb: what changed
  Never commit .env files
"@ | Set-Content "$PROJECT_ROOT\CLAUDE.md" -Encoding UTF8
Write-Host "  [OK] CLAUDE.md written." -ForegroundColor Green

# -- 4. .env.example -----------------------------------------------------------
Write-Host ""
Write-Host "[ 4/8 ] Writing .env.example..." -ForegroundColor Yellow
@'
# -- Retell AI ------------------------------------------------------------------
RETELL_API_KEY=
RETELL_AGENT_ID=
RETELL_WEBHOOK_SECRET=

# -- Telnyx SIP -----------------------------------------------------------------
TELNYX_API_KEY=
TELNYX_SIP_USERNAME=
TELNYX_SIP_PASSWORD=
TELNYX_FROM_NUMBER=+91XXXXXXXXXX

# -- ElevenLabs TTS -------------------------------------------------------------
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=

# -- OpenAI (GPT-4o Realtime via Retell) ---------------------------------------
OPENAI_API_KEY=

# -- Anthropic (post-call analysis) --------------------------------------------
ANTHROPIC_API_KEY=

# -- PostgreSQL -----------------------------------------------------------------
DATABASE_URL=postgresql://voice_user:changeme@localhost:5432/voice_agent
POSTGRES_USER=voice_user
POSTGRES_PASSWORD=changeme
POSTGRES_DB=voice_agent

# -- Redis ----------------------------------------------------------------------
REDIS_URL=redis://localhost:6379

# -- App ------------------------------------------------------------------------
WEBHOOK_BASE_URL=https://your-domain.com
PORT=8000
DASHBOARD_PORT=3000
ENV=development
'@ | Set-Content "$PROJECT_ROOT\.env.example" -Encoding UTF8
Write-Host "  [OK] .env.example written. Copy to .env and fill values." -ForegroundColor Green

# -- 5. TOOLS.md ---------------------------------------------------------------
Write-Host ""
Write-Host "[ 5/8 ] Writing TOOLS.md..." -ForegroundColor Yellow
@"
# TOOLS.md - voice-outbound-agent

## Plugins (install inside Claude Code -> /plugin -> user scope)
  superpowers        sub-agent orchestration
  context7           live API docs (use for: Retell AI, FastAPI, SQLAlchemy, Next.js)
  code-simplifier    refactor helper
  context-mode       98% context savings on large outputs

## MCPs
  filesystem         read files - never paste full files into chat
  memory             persist schema decisions, open questions
  sequential-thinking  architecture and complex debugging

## Session Launcher
  .\voice-outbound-agent-sessions.ps1 -Session list
  .\voice-outbound-agent-sessions.ps1 -Session db-schema

## Python Environment
  python -m venv .venv
  .venv\Scripts\Activate.ps1
  pip install -r requirements.txt

## Test Commands
  pytest tests/ -v                     # all tests
  pytest tests/test_dnc.py -v          # DNC regression
  pytest tests/test_worker.py -v       # dialing worker

## Alembic
  alembic upgrade head                 # apply migrations
  alembic downgrade -1                 # roll back one

## n8n
  docker compose up -d n8n
  # Access: http://localhost:5678
"@ | Set-Content "$PROJECT_ROOT\TOOLS.md" -Encoding UTF8
Write-Host "  [OK] TOOLS.md written." -ForegroundColor Green

# -- 6. SKILLS.md + task-create skill -----------------------------------------
Write-Host ""
Write-Host "[ 6/8 ] Writing SKILLS.md + task-create skill..." -ForegroundColor Yellow
@"
# SKILLS.md - voice-outbound-agent

| Command        | File                            | What it does                        |
|----------------|-------------------------------|-------------------------------------|
| task-create    | .claude/skills/task-create.md | Create a new TASK-XXX.md            |
| audit-module   | .claude/skills/audit-module.md| Read module files; report issues      |
| prompt-review  | .claude/skills/prompt-review.md| Validate voice prompt against rules |
"@ | Set-Content "$PROJECT_ROOT\SKILLS.md" -Encoding UTF8

@'
# Skill: task-create
1. Ask: task title + module + phase
2. Find next TASK number in tasks/
3. Create tasks/TASK-XXX-<slug>.md with PDCA template
4. Create branch: feature/TASK-XXX
5. Report path + branch name
'@ | Set-Content "$PROJECT_ROOT\.claude\skills\task-create.md" -Encoding UTF8

@'
# Skill: audit-module
1. Read PRD.md section for this module
2. Read all files in app/<module>/
3. List: what exists, what is missing, what is broken
4. NO code changes - report only
5. Output a checklist the developer can approve
'@ | Set-Content "$PROJECT_ROOT\.claude\skills\audit-module.md" -Encoding UTF8

@'
# Skill: prompt-review
Rules to check (fail any = rewrite):
1. No sentence > 12 words
2. No bullet points or numbered lists in TTS text
3. No special characters (*, #, /, |)
4. Acronyms spelled out phonetically
5. Every flow step has explicit "wait for response" instruction
6. Objection paths present: busy / not_interested / angry
7. Escape hatch present (email follow-up -> end call)
Report: PASS or FAIL with line numbers
'@ | Set-Content "$PROJECT_ROOT\.claude\skills\prompt-review.md" -Encoding UTF8
Write-Host "  [OK] SKILLS.md + 3 skills written." -ForegroundColor Green

# -- 7. Initial TASK files ------------------------------------------------------
Write-Host ""
Write-Host "[ 7/8 ] Creating initial TASK files..." -ForegroundColor Yellow

@"
# TASK-000: Repo Init

## Status: COMPLETE
## Phase: 0
## Objective
Bootstrap project structure, CLAUDE.md, .env.example, TOOLS.md, SKILLS.md.

## PDCA Log
### Cycle 1
**Plan:** Run setup-voice-outbound-agent.ps1
**Approved:** Yes
**Do:** Script executed
**Check:** All files present
**Act:** Commit [TASK-000] init: project bootstrap

## Checkpoints
| Step | Status | Git Commit | Notes |
|------|--------|------------|-------|
| 1    | [x]    |            | Folders created |
| 2    | [x]    |            | CLAUDE.md written |
| 3    | [x]    |            | .env.example written |
"@ | Set-Content "$PROJECT_ROOT\tasks\TASK-000-repo-init.md" -Encoding UTF8

@"
# TASK-001: Database Schema

## Status: PLANNING
## Phase: 1
## Objective
PostgreSQL schema live with Alembic migrations; scoped agent_operations schema;
memories_role with correct permissions; seed data for one test campaign and
two test leads (one DNC, one clean).

## PDCA Log
### Cycle 1
**Plan:**
**Approved:** Pending
**Do:**
**Check:**
**Act:**

## Checkpoints
| Step | Status | Git Commit | Notes |
|------|--------|------------|-------|
| 1    | [ ]    |            | alembic init |
| 2    | [ ]    |            | migrations for all 5 tables |
| 3    | [ ]    |            | memories_role grant script |
| 4    | [ ]    |            | seed data |
| 5    | [ ]    |            | pytest db connection test passes |
"@ | Set-Content "$PROJECT_ROOT\tasks\TASK-001-db-schema.md" -Encoding UTF8
Write-Host "  [OK] TASK-000 and TASK-001 created." -ForegroundColor Green

# -- 8. .mcp.json --------------------------------------------------------------
Write-Host ""
Write-Host "[ 8/8 ] Writing .mcp.json..." -ForegroundColor Yellow

$npmGlobalRoot = ""
if (Get-Command npm -ErrorAction SilentlyContinue) {
    $npmOutput = (npm root -g 2>$null)
    if ($npmOutput) {
        $npmGlobalRoot = $npmOutput.Trim()
    }
}
if (-not $npmGlobalRoot) { 
    $npmGlobalRoot = "C:\Users\$env:USERNAME\AppData\Roaming\npm\node_modules" 
}
# Escape backslashes for valid JSON
$npmGlobalRootEscaped = $npmGlobalRoot.Replace("\", "\\")

@"
{
  "mcpServers": {
    "filesystem": {
      "command": "node",
      "args": ["$npmGlobalRootEscaped\\@modelcontextprotocol\\server-filesystem\\dist\\index.js", "$PROJECT_ROOT"]
    },
    "memory": {
      "command": "node",
      "args": ["$npmGlobalRootEscaped\\@modelcontextprotocol\\server-memory\\dist\\index.js"]
    },
    "sequential-thinking": {
      "command": "node",
      "args": ["$npmGlobalRootEscaped\\@modelcontextprotocol\\server-sequential-thinking\\dist\\index.js"]
    }
  }
}
"@ | Set-Content "$PROJECT_ROOT\.mcp.json" -Encoding UTF8
Write-Host "  [OK] .mcp.json written." -ForegroundColor Green

# -- Final summary --------------------------------------------------------------
Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "  [OK] voice-outbound-agent bootstrap complete." -ForegroundColor Green
Write-Host ""
Write-Host "  NEXT STEPS:" -ForegroundColor Cyan
Write-Host "    1. Copy .env.example -> .env and fill all API keys" -ForegroundColor White
Write-Host "    2. git init && git add . && git commit -m '[TASK-000] init: bootstrap'" -ForegroundColor White
Write-Host "    3. .\voice-outbound-agent-sessions.ps1 -Session list" -ForegroundColor White
Write-Host "    4. .\voice-outbound-agent-sessions.ps1 -Session db-schema" -ForegroundColor White
Write-Host ""
Write-Host "  FIRST SESSION RULE: Start with db-schema, not code." -ForegroundColor Yellow
Write-Host "  Read PRD.md Section 5 (DB Schema) before doing anything." -ForegroundColor Yellow
Write-Host "================================================================" -ForegroundColor Green
Write-Host ""