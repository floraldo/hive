.PHONY: help setup test-setup run dry-run swarm

help:
	@echo "🐝 Hive Management Commands"
	@echo "=========================="
	@echo "  make setup        - Run the one-time initial setup and verification"
	@echo "  make swarm        - Start the tmux session with the Queen and Workers"
	@echo "  make run          - Run the main orchestrator in your current terminal"
	@echo "  make dry-run      - Run the orchestrator in dry-run mode"
	@echo "  make test-setup   - Verify that the Hive environment is correctly configured"
	@echo "  make docker-up    - Start all services with Docker Compose"
	@echo "  make docker-down  - Stop all Docker services"

setup:
	@echo "🚀 Setting up Hive..."
	@./scripts/initial_setup.sh
	@echo "Creating Python environment..."
	@python3 -m venv .venv || true
	@echo "Installing dependencies..."
	@source .venv/Scripts/activate && pip install -r requirements.txt
	@make test-setup

swarm:
	@echo "🐝 Starting the hive swarm..."
	@./setup.sh

run:
	@echo "👑 Starting the Queen orchestrator..."
	@bash -c "source .venv-wsl/bin/activate && python hive_cli.py run"

dry-run:
	@echo "🧪 Starting orchestrator in dry-run mode..."
	@bash -c "source .venv-wsl/bin/activate && python hive_cli.py run --dry-run"

test-setup:
	@echo "🔍 Verifying Hive setup..."
	@python test_setup_simple.py

docker-up:
	@echo "🐳 Starting Docker services..."
	@docker-compose up -d

docker-down:
	@echo "🐳 Stopping Docker services..."
	@docker-compose down