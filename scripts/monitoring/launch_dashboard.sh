#!/bin/bash
# Launch Hive AI Apps Monitoring Stack
# Quick setup: Prometheus + Grafana + Dashboard in <2 minutes

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MONITORING_DIR="$PROJECT_ROOT/monitoring"

echo "🚀 Hive AI Apps Dashboard - Quick Launch"
echo "========================================"
echo ""

# Create monitoring directory structure
echo "📁 Setting up monitoring directory..."
mkdir -p "$MONITORING_DIR/dashboards"
mkdir -p "$MONITORING_DIR/datasources"

# Create Prometheus config
echo "📊 Creating Prometheus configuration..."
cat > "$MONITORING_DIR/prometheus.yml" <<'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  # AI Reviewer
  - job_name: 'ai-reviewer'
    static_configs:
      - targets: ['host.docker.internal:8001']
        labels:
          app: 'ai-reviewer'
          component: 'ai'

  # AI Planner
  - job_name: 'ai-planner'
    static_configs:
      - targets: ['host.docker.internal:8002']
        labels:
          app: 'ai-planner'
          component: 'ai'

  # AI Deployer
  - job_name: 'ai-deployer'
    static_configs:
      - targets: ['host.docker.internal:8003']
        labels:
          app: 'ai-deployer'
          component: 'ai'
EOF

# Create Grafana datasource
echo "🔌 Creating Grafana datasource..."
cat > "$MONITORING_DIR/datasources/prometheus.yml" <<'EOF'
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
EOF

# Create Grafana dashboard provider
echo "📈 Creating Grafana dashboard provider..."
cat > "$MONITORING_DIR/dashboards/dashboard-provider.yml" <<'EOF'
apiVersion: 1

providers:
  - name: 'Hive AI Apps'
    orgId: 1
    folder: 'AI Performance'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
EOF

# Copy dashboard JSON
echo "📋 Copying dashboard JSON..."
cp "$PROJECT_ROOT/claudedocs/PROJECT_SIGNAL_PHASE_4_4_UNIFIED_AI_DASHBOARD.json" \
   "$MONITORING_DIR/dashboards/"

# Create Docker Compose file
echo "🐳 Creating Docker Compose configuration..."
cat > "$MONITORING_DIR/docker-compose.yml" <<'EOF'
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: hive-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/usr/share/prometheus/console_libraries'
      - '--web.console.templates=/usr/share/prometheus/consoles'
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: hive-grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
      - ./dashboards:/etc/grafana/provisioning/dashboards
      - ./datasources:/etc/grafana/provisioning/datasources
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_SERVER_ROOT_URL=http://localhost:3000
    depends_on:
      - prometheus
    restart: unless-stopped

volumes:
  prometheus-data:
  grafana-data:
EOF

# Start monitoring stack
echo ""
echo "🚀 Launching monitoring stack..."
cd "$MONITORING_DIR"
docker-compose up -d

# Wait for services to be ready
echo ""
echo "⏳ Waiting for services to start..."
sleep 5

# Check if services are running
echo ""
echo "✅ Service Status:"
docker-compose ps

echo ""
echo "================================================"
echo "✨ Monitoring Stack is Running!"
echo "================================================"
echo ""
echo "📊 Prometheus:  http://localhost:9090"
echo "📈 Grafana:     http://localhost:3000"
echo "   Username:    admin"
echo "   Password:    admin"
echo ""
echo "📂 Dashboard Location:"
echo "   Dashboards → AI Performance → Hive AI Apps"
echo ""
echo "🔍 Next Steps:"
echo "1. Start your AI apps with metrics exposed:"
echo "   - ai-reviewer on port 8001"
echo "   - ai-planner on port 8002"
echo "   - ai-deployer on port 8003"
echo ""
echo "2. Check Prometheus targets:"
echo "   http://localhost:9090/targets"
echo ""
echo "3. View dashboard in Grafana:"
echo "   http://localhost:3000"
echo ""
echo "💡 Tip: See DASHBOARD_QUICKSTART.md for detailed usage"
echo ""
echo "🛑 To stop: cd $MONITORING_DIR && docker-compose down"
echo "================================================"
