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
