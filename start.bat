@echo off
REM PrepPath — start backend (port 8000) and frontend (port 3000), then open the browser.
cd /d "%~dp0"

if not exist backend\.venv (
  echo Setting up backend...
  python -m venv backend\.venv
  backend\.venv\Scripts\python -m pip install -r backend\requirements.txt
)
if not exist backend\.env copy backend\.env.example backend\.env
if not exist backend\dev.db (
  pushd backend
  .venv\Scripts\alembic upgrade head
  .venv\Scripts\python -m app.seed
  popd
)
if not exist frontend\node_modules (
  pushd frontend
  call npm install
  popd
)

start "PrepPath backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\python -m uvicorn app.main:app --port 8000"
start "PrepPath frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
timeout /t 8 >nul
start http://localhost:3000
