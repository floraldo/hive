# Makefile for Hive Fleet Command Docker Operations
# Usage: make [target]

# Variables
DOCKER_COMPOSE = docker-compose
DOCKER = docker
PROJECT_NAME = hive
VERSION ?= latest
ENVIRONMENT ?= development

# Color output
RED = \033[0;31m
GREEN = \033[0;32m
YELLOW = \033[1;33m
NC = \033[0m # No Color

# Default target
.DEFAULT_GOAL := help

# Phony targets
.PHONY: help build up down restart logs clean validate test deploy

# Help target
help: ## Show this help message
	@echo "$(GREEN)Hive Fleet Command - Docker Operations$(NC)"
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'

# Development targets
dev: ## Start development environment
	@echo "$(GREEN)Starting development environment...$(NC)"
	$(DOCKER_COMPOSE) -f ../docker-compose.yml -f ../docker-compose.dev.yml up -d
	@echo "$(GREEN)Development environment is ready!$(NC)"

dev-logs: ## Show development logs
	$(DOCKER_COMPOSE) -f ../docker-compose.yml -f ../docker-compose.dev.yml logs -f

dev-down: ## Stop development environment
	@echo "$(YELLOW)Stopping development environment...$(NC)"
	$(DOCKER_COMPOSE) -f ../docker-compose.yml -f ../docker-compose.dev.yml down
	@echo "$(GREEN)Development environment stopped.$(NC)"

# Production targets
prod: ## Start production environment
	@echo "$(GREEN)Starting production environment...$(NC)"
	$(DOCKER_COMPOSE) -f ../docker-compose.yml -f ../docker-compose.prod.yml up -d
	@echo "$(GREEN)Production environment is ready!$(NC)"

prod-logs: ## Show production logs
	$(DOCKER_COMPOSE) -f ../docker-compose.yml -f ../docker-compose.prod.yml logs -f

prod-down: ## Stop production environment
	@echo "$(YELLOW)Stopping production environment...$(NC)"
	$(DOCKER_COMPOSE) -f ../docker-compose.yml -f ../docker-compose.prod.yml down
	@echo "$(GREEN)Production environment stopped.$(NC)"

# Build targets
build: ## Build all Docker images
	@echo "$(GREEN)Building Docker images...$(NC)"
	$(DOCKER_COMPOSE) build --no-cache
	@echo "$(GREEN)Build complete!$(NC)"

build-quick: ## Build Docker images (with cache)
	@echo "$(GREEN)Building Docker images with cache...$(NC)"
	$(DOCKER_COMPOSE) build
	@echo "$(GREEN)Build complete!$(NC)"

build-prod: ## Build production images
	@echo "$(GREEN)Building production images...$(NC)"
	$(DOCKER) build -t $(PROJECT_NAME)/queen:$(VERSION) -f ../Dockerfile ..
	$(DOCKER) build -t $(PROJECT_NAME)/frontend-worker:$(VERSION) -f ../Dockerfile ..
	$(DOCKER) build -t $(PROJECT_NAME)/backend-worker:$(VERSION) -f ../Dockerfile ..
	$(DOCKER) build -t $(PROJECT_NAME)/infra-worker:$(VERSION) -f ../Dockerfile ..
	@echo "$(GREEN)Production images built successfully!$(NC)"

# Container management
up: ## Start all containers
	@echo "$(GREEN)Starting containers...$(NC)"
	$(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)All containers are running!$(NC)"

down: ## Stop all containers
	@echo "$(YELLOW)Stopping containers...$(NC)"
	$(DOCKER_COMPOSE) down
	@echo "$(GREEN)All containers stopped.$(NC)"

restart: ## Restart all containers
	@echo "$(YELLOW)Restarting containers...$(NC)"
	$(DOCKER_COMPOSE) restart
	@echo "$(GREEN)All containers restarted!$(NC)"

stop: ## Stop all containers (keep volumes)
	@echo "$(YELLOW)Stopping containers...$(NC)"
	$(DOCKER_COMPOSE) stop
	@echo "$(GREEN)Containers stopped (volumes preserved).$(NC)"

# Individual service targets
queen: ## Start Queen service
	$(DOCKER_COMPOSE) up -d queen

frontend: ## Start Frontend Worker
	$(DOCKER_COMPOSE) up -d frontend-worker

backend: ## Start Backend Worker
	$(DOCKER_COMPOSE) up -d backend-worker

infra: ## Start Infrastructure Worker
	$(DOCKER_COMPOSE) up -d infra-worker

# Logging and monitoring
logs: ## Show logs for all services
	$(DOCKER_COMPOSE) logs -f

logs-queen: ## Show Queen logs
	$(DOCKER_COMPOSE) logs -f queen

logs-frontend: ## Show Frontend Worker logs
	$(DOCKER_COMPOSE) logs -f frontend-worker

logs-backend: ## Show Backend Worker logs
	$(DOCKER_COMPOSE) logs -f backend-worker

logs-infra: ## Show Infrastructure Worker logs
	$(DOCKER_COMPOSE) logs -f infra-worker

# Health and status
status: ## Show container status
	@echo "$(GREEN)Container Status:$(NC)"
	@$(DOCKER_COMPOSE) ps

health: ## Check health of all services
	@echo "$(GREEN)Checking service health...$(NC)"
	@for service in queen frontend-worker backend-worker infra-worker message-bus database; do \
		echo -n "$$service: "; \
		$(DOCKER_COMPOSE) exec -T $$service python /app/docker/healthcheck.py 2>/dev/null && echo "$(GREEN)✓ Healthy$(NC)" || echo "$(RED)✗ Unhealthy$(NC)"; \
	done

# Shell access
shell-queen: ## Open shell in Queen container
	$(DOCKER_COMPOSE) exec queen /bin/bash

shell-frontend: ## Open shell in Frontend Worker
	$(DOCKER_COMPOSE) exec frontend-worker /bin/bash

shell-backend: ## Open shell in Backend Worker
	$(DOCKER_COMPOSE) exec backend-worker /bin/bash

shell-infra: ## Open shell in Infrastructure Worker
	$(DOCKER_COMPOSE) exec infra-worker /bin/bash

# Cleanup
clean: ## Remove all containers and volumes
	@echo "$(RED)WARNING: This will remove all containers and volumes!$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		$(DOCKER_COMPOSE) down -v; \
		echo "$(GREEN)Cleanup complete!$(NC)"; \
	else \
		echo "$(YELLOW)Cleanup cancelled.$(NC)"; \
	fi

clean-images: ## Remove all project Docker images
	@echo "$(RED)Removing all project images...$(NC)"
	$(DOCKER) images | grep $(PROJECT_NAME) | awk '{print $$3}' | xargs -r $(DOCKER) rmi -f
	@echo "$(GREEN)Images removed!$(NC)"

prune: ## Prune Docker system
	@echo "$(YELLOW)Pruning Docker system...$(NC)"
	$(DOCKER) system prune -af --volumes
	@echo "$(GREEN)Docker system pruned!$(NC)"

# Testing
test: ## Run tests in containers
	@echo "$(GREEN)Running tests...$(NC)"
	$(DOCKER_COMPOSE) exec -T backend-worker pytest /app/tests
	@echo "$(GREEN)Tests complete!$(NC)"

validate: ## Validate Docker configuration
	@echo "$(GREEN)Validating Docker configuration...$(NC)"
	@./validate_docker.sh
	@echo "$(GREEN)Validation complete!$(NC)"

# Deployment
deploy: build-prod ## Deploy to production
	@echo "$(GREEN)Deploying to production...$(NC)"
	# Add your deployment commands here
	# Example: docker push $(PROJECT_NAME)/queen:$(VERSION)
	@echo "$(GREEN)Deployment complete!$(NC)"

# Database operations
db-backup: ## Backup database
	@echo "$(GREEN)Backing up database...$(NC)"
	@mkdir -p ../backups
	$(DOCKER_COMPOSE) exec -T database pg_dump -U hive hive_db > ../backups/hive_db_$$(date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)Database backup complete!$(NC)"

db-restore: ## Restore database from backup
	@echo "$(YELLOW)Restoring database...$(NC)"
	@read -p "Enter backup file path: " backup_file; \
	$(DOCKER_COMPOSE) exec -T database psql -U hive hive_db < $$backup_file
	@echo "$(GREEN)Database restored!$(NC)"

# Monitoring
monitor: ## Start monitoring dashboard
	@echo "$(GREEN)Opening monitoring dashboards...$(NC)"
	@echo "Adminer (Database): http://localhost:8082"
	@echo "Redis Commander: http://localhost:8081"
	@echo "Application: http://localhost:3000"
	@echo "API: http://localhost:8000"