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
	@tmux attach -t hive-swarm

clean:
	@tmux kill-session -t hive-swarm 2>/dev/null || true
	@echo "🛸 Fleet stood down"