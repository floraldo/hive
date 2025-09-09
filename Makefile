.PHONY: help swarm attach clean

help:
	@echo "🚀 Fleet Command System"
	@echo "======================="
	@echo "  make swarm   - Launch the AI fleet in tmux"
	@echo "  make attach  - Attach to running fleet"
	@echo "  make clean   - Destroy the fleet session"

swarm:
	@echo "🚀 Launching Fleet Command..."
	@./setup.sh
	@echo "✅ Fleet ready! Run 'make attach' to enter cockpit"

attach:
	@if [ "$$(id -u)" -eq 0 ] && id -u hiveuser >/dev/null 2>&1; then \
		su hiveuser -c "tmux attach -t hive-swarm"; \
	else \
		tmux attach -t hive-swarm; \
	fi

clean:
	@if [ "$$(id -u)" -eq 0 ] && id -u hiveuser >/dev/null 2>&1; then \
		su hiveuser -c "tmux kill-session -t hive-swarm 2>/dev/null || true"; \
	else \
		tmux kill-session -t hive-swarm 2>/dev/null || true; \
	fi
	@echo "🛸 Fleet stood down"