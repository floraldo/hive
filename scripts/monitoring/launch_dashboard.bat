@echo off
REM Launch Hive AI Apps Monitoring Stack
REM Quick setup: Prometheus + Grafana + Dashboard in <2 minutes

setlocal enabledelayedexpansion

echo.
echo 🚀 Hive AI Apps Dashboard - Quick Launch
echo ========================================
echo.

REM Get script directory and project root
set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..\..
set MONITORING_DIR=%PROJECT_ROOT%\monitoring

REM Create monitoring directory structure
echo 📁 Setting up monitoring directory...
if not exist "%MONITORING_DIR%" mkdir "%MONITORING_DIR%"
if not exist "%MONITORING_DIR%\dashboards" mkdir "%MONITORING_DIR%\dashboards"
if not exist "%MONITORING_DIR%\datasources" mkdir "%MONITORING_DIR%\datasources"

REM Create Prometheus config
echo 📊 Creating Prometheus configuration...
(
echo global:
echo   scrape_interval: 15s
echo   evaluation_interval: 15s
echo.
echo scrape_configs:
echo   # AI Reviewer
echo   - job_name: 'ai-reviewer'
echo     static_configs:
echo       - targets: ['host.docker.internal:8001']
echo         labels:
echo           app: 'ai-reviewer'
echo           component: 'ai'
echo.
echo   # AI Planner
echo   - job_name: 'ai-planner'
echo     static_configs:
echo       - targets: ['host.docker.internal:8002']
echo         labels:
echo           app: 'ai-planner'
echo           component: 'ai'
echo.
echo   # AI Deployer
echo   - job_name: 'ai-deployer'
echo     static_configs:
echo       - targets: ['host.docker.internal:8003']
echo         labels:
echo           app: 'ai-deployer'
echo           component: 'ai'
) > "%MONITORING_DIR%\prometheus.yml"

REM Create Grafana datasource
echo 🔌 Creating Grafana datasource...
(
echo apiVersion: 1
echo.
echo datasources:
echo   - name: Prometheus
echo     type: prometheus
echo     access: proxy
echo     url: http://prometheus:9090
echo     isDefault: true
echo     editable: false
) > "%MONITORING_DIR%\datasources\prometheus.yml"

REM Create Grafana dashboard provider
echo 📈 Creating Grafana dashboard provider...
(
echo apiVersion: 1
echo.
echo providers:
echo   - name: 'Hive AI Apps'
echo     orgId: 1
echo     folder: 'AI Performance'
echo     type: file
echo     disableDeletion: false
echo     updateIntervalSeconds: 10
echo     allowUiUpdates: true
echo     options:
echo       path: /etc/grafana/provisioning/dashboards
) > "%MONITORING_DIR%\dashboards\dashboard-provider.yml"

REM Copy dashboard JSON
echo 📋 Copying dashboard JSON...
copy /Y "%PROJECT_ROOT%\claudedocs\PROJECT_SIGNAL_PHASE_4_4_UNIFIED_AI_DASHBOARD.json" ^
     "%MONITORING_DIR%\dashboards\" >nul

REM Create Docker Compose file
echo 🐳 Creating Docker Compose configuration...
(
echo version: '3.8'
echo.
echo services:
echo   prometheus:
echo     image: prom/prometheus:latest
echo     container_name: hive-prometheus
echo     ports:
echo       - "9090:9090"
echo     volumes:
echo       - ./prometheus.yml:/etc/prometheus/prometheus.yml
echo       - prometheus-data:/prometheus
echo     command:
echo       - '--config.file=/etc/prometheus/prometheus.yml'
echo       - '--storage.tsdb.path=/prometheus'
echo       - '--web.console.libraries=/usr/share/prometheus/console_libraries'
echo       - '--web.console.templates=/usr/share/prometheus/consoles'
echo     restart: unless-stopped
echo.
echo   grafana:
echo     image: grafana/grafana:latest
echo     container_name: hive-grafana
echo     ports:
echo       - "3000:3000"
echo     volumes:
echo       - grafana-data:/var/lib/grafana
echo       - ./dashboards:/etc/grafana/provisioning/dashboards
echo       - ./datasources:/etc/grafana/provisioning/datasources
echo     environment:
echo       - GF_SECURITY_ADMIN_PASSWORD=admin
echo       - GF_USERS_ALLOW_SIGN_UP=false
echo       - GF_SERVER_ROOT_URL=http://localhost:3000
echo     depends_on:
echo       - prometheus
echo     restart: unless-stopped
echo.
echo volumes:
echo   prometheus-data:
echo   grafana-data:
) > "%MONITORING_DIR%\docker-compose.yml"

REM Start monitoring stack
echo.
echo 🚀 Launching monitoring stack...
cd /d "%MONITORING_DIR%"
docker-compose up -d

REM Wait for services to be ready
echo.
echo ⏳ Waiting for services to start...
timeout /t 5 /nobreak >nul

REM Check if services are running
echo.
echo ✅ Service Status:
docker-compose ps

echo.
echo ================================================
echo ✨ Monitoring Stack is Running!
echo ================================================
echo.
echo 📊 Prometheus:  http://localhost:9090
echo 📈 Grafana:     http://localhost:3000
echo    Username:    admin
echo    Password:    admin
echo.
echo 📂 Dashboard Location:
echo    Dashboards → AI Performance → Hive AI Apps
echo.
echo 🔍 Next Steps:
echo 1. Start your AI apps with metrics exposed:
echo    - ai-reviewer on port 8001
echo    - ai-planner on port 8002
echo    - ai-deployer on port 8003
echo.
echo 2. Check Prometheus targets:
echo    http://localhost:9090/targets
echo.
echo 3. View dashboard in Grafana:
echo    http://localhost:3000
echo.
echo 💡 Tip: See DASHBOARD_QUICKSTART.md for detailed usage
echo.
echo 🛑 To stop: cd %MONITORING_DIR% ^&^& docker-compose down
echo ================================================
echo.

pause
