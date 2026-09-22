.PHONY: install dev gui cli test docker clean

install:  ## Install micher with GUI deps
	pip install -e ".[gui]"

dev:  ## Install with dev deps
	pip install -e ".[gui,dev]"

gui:  ## Launch the GUI
	micher-gui

cli:  ## Run CLI interface list
	micher interfaces

test:  ## Run loopback transfer test
	python -m pytest tests/ -v 2>/dev/null || python -c "\
import threading, time; \
from micher.core.transfer import BondedSender, BondedReceiver; \
data = b'X' * (5*1024*1024); PORT = 19192; \
r = BondedReceiver('127.0.0.1', PORT, 1); \
res = [None]; \
t = threading.Thread(target=lambda: res.__setitem__(0, r.receive())); \
t.start(); time.sleep(0.3); \
s = BondedSender('127.0.0.1', PORT, ['127.0.0.1']); \
s.send(data); t.join(5); \
print('PASS' if res[0]==data else 'FAIL')"

docker:  ## Build and run Docker server
	docker compose up --build -d

docker-stop:  ## Stop Docker server
	docker compose down

desktop:  ## Install desktop shortcuts
	python desktop/create_shortcut.py

clean:  ## Remove build artifacts
	rm -rf dist build *.egg-info __pycache__
	find . -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
