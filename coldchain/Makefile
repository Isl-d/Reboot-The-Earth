# Person 3 data platform. Run from the repository root:  make -C coldchain <target>
.DEFAULT_GOAL := help
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
PG := postgresql+psycopg://coldchain:coldchain@localhost:5432/coldchain

help:            ## Show this help
	@grep -hE '^[a-z-]+:.*?##' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-12s %s\n", $$1, $$2}'

up:              ## Start mosquitto, timescaledb, redis and the API
	docker compose up -d

down:            ## Stop everything
	docker compose down

logs:            ## Follow the API log
	docker compose logs -f api

api:             ## Run the API on this machine (degrades without services)
	cd $(ROOT) && python -m coldchain.api.main

test:            ## Tests on SQLite, skipping the broker ones
	cd $(ROOT) && python -m pytest coldchain/tests -q

test-full:       ## The same tests against Postgres (and the broker, if up)
	cd $(ROOT) && COLDCHAIN_TEST_DATABASE_URL=$(PG) python -m pytest coldchain/tests -q

demo:            ## Drive the refrigeration-failure demo against a running API
	cd $(ROOT) && python coldchain/scripts/demo.py

health:          ## What is actually live right now
	@curl -s localhost:8100/api/health | python3 -m json.tool

.PHONY: help up down logs api test test-full demo health
