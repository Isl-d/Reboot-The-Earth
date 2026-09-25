# ColdGuard - one command per thing you do on stage.
.DEFAULT_GOAL := help
COMPOSE := docker compose

help:   ## show this help
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  \033[1m%-12s\033[0m %s\n", $$1, $$2}'

demo:   ## start everything (except the NodeMCU) and open the dashboard
	$(COMPOSE) up -d --build
	@echo "dashboard  http://localhost:5173"
	@echo "API        http://localhost:8000/api/fleet"
	@echo "QR page    http://localhost:8000/track/TRK-07"

stop:   ## stop everything, keep the data
	$(COMPOSE) down

reset:  ## put the demo back to its starting state (no restart needed)
	curl -fsS -X POST http://localhost:8000/api/demo/reset && echo " reset"

logs:   ## follow the backend log
	$(COMPOSE) logs -f backend

model:  ## pull the local LLM once, before the event (about 5 GB)
	$(COMPOSE) exec ollama ollama pull qwen2.5:7b

data:   ## refetch the open data (needs internet; run the day before)
	python scripts/build_data.py

qr:     ## make the QR code for the cooler box
	python scripts/make_qr.py

test:   ## run the test suite
	python -m pytest tests/ -q

watch:  ## watch raw telemetry, to check the NodeMCU is publishing
	mosquitto_sub -h localhost -t 'coldguard/#' -v

dev-backend:  ## run the backend on the host, with reload
	uvicorn backend.main:app --reload --port 8000

dev-sim:      ## run the simulator on the host
	python simulator/sim.py --broker localhost --demo-speed 10

dev-web:      ## run the dashboard on the host
	cd web && npm install && npm run dev

.PHONY: help demo stop reset logs model data qr test watch dev-backend dev-sim dev-web
