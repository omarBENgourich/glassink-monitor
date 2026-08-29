.DEFAULT_GOAL := help
SHELL := /bin/bash

# Load .env if present, so local helper targets can use its values.
ifneq (,$(wildcard .env))
include .env
export
endif

COMPOSE := docker compose

.PHONY: help init up demo down restart logs ps influx mqtt-sub mqtt-pub \
        reset-influx reset-db nuke check test verify phase2 phase3 phase4 screenshots

help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

init: ## Create .env from the template (does not overwrite)
	@if [ -f .env ]; then \
		echo ".env already exists — leaving it alone."; \
	else \
		cp .env.example .env; \
		echo ".env created. Fill in the required InfluxDB, Grafana, and Node-RED secrets."; \
		echo "Generate one with:  openssl rand -base64 24"; \
	fi

check: ## Validate the compose file without starting anything
	@$(COMPOSE) config --quiet && echo "compose file OK"
	@python3 -m compileall -q simulator/src notifier/src
	@node --check ingestion/settings.js
	@node ingestion/line_protocol.js
	@python3 -m json.tool ingestion/flows.json >/dev/null
	@node -e 'const f=require("./ingestion/flows.json"); for(const n of f.filter(n=>n.type==="function")) new Function("msg","node","global","env",n.func)'
	@for f in dashboards/definitions/*.json; do python3 -m json.tool "$$f" >/dev/null; done
	@echo "source, Node-RED flow, and dashboard syntax OK"

test: ## Run deterministic simulator and notifier unit tests
	PYTHONPATH=simulator python3 -m unittest discover -s simulator/tests -v
	PYTHONPATH=notifier python3 -m unittest discover -s notifier/tests -v

verify: check test ## Verify the live stack, Grafana assets, and InfluxDB flow
	@python3 dashboards/verify.py
	@curl -fsS http://localhost:$${NODE_RED_PORT:-1880}/health | grep -q '"status":"ok"'
	@curl -fsS http://localhost:$${NOTIFIER_PORT:-8080}/health >/dev/null
	@curl -fsS -H "Authorization: Token $${INFLUXDB_TOKEN}" \
		-H 'Content-Type: application/vnd.flux' \
		--data "from(bucket: \"$${INFLUXDB_BUCKET:-printer_monitoring}\") |> range(start: -15m) |> filter(fn: (r) => r._measurement == \"printer_telemetry\") |> limit(n: 1)" \
		"http://localhost:$${INFLUXDB_PORT:-8086}/api/v2/query?org=$${INFLUXDB_ORG:-saint-gobain}" \
		| grep -q printer_telemetry
	@echo "Node-RED live ingestion OK"

up: ## Start phase 1 (broker + InfluxDB + Grafana)
	$(COMPOSE) up -d
	@echo ""
	@echo "  Grafana   http://localhost:$${GRAFANA_PORT:-3000}"
	@echo "  InfluxDB  http://localhost:$${INFLUXDB_PORT:-8086}"
	@echo "  MQTT      localhost:$${MQTT_PORT:-1883}"

demo: ## Build and start the complete local prototype
	$(COMPOSE) --profile phase2 --profile phase3 --profile phase4 up -d --build
	@echo ""
	@echo "  Grafana   http://localhost:$${GRAFANA_PORT:-3000}"
	@echo "  Node-RED  http://localhost:$${NODE_RED_PORT:-1880}"
	@echo "  Notifier  http://localhost:$${NOTIFIER_PORT:-8080}/health"

down: ## Stop everything, keep data
	$(COMPOSE) --profile phase2 --profile phase3 --profile phase4 down

restart: down up ## Restart phase 1

phase2: ## Start the printer simulator
	$(COMPOSE) --profile phase2 up -d simulator

phase3: ## Start Node-RED ingestion and editor
	$(COMPOSE) --profile phase3 up -d node-red

phase4: ## Start the alert notifier
	$(COMPOSE) --profile phase4 up -d notifier

screenshots: ## Refresh the Grafana and Node-RED interface captures
	@cd rapport/scripts && npm ci --no-audit --no-fund
	@cd rapport/scripts && \
		GRAFANA_USER="$(GRAFANA_ADMIN_USER)" \
		GRAFANA_PASSWORD="$(GRAFANA_ADMIN_PASSWORD)" \
		npm run capture:grafana
	@cd rapport/scripts && \
		NODE_RED_USER="$(NODE_RED_ADMIN_USER)" \
		NODE_RED_PASSWORD="$(NODE_RED_ADMIN_PASSWORD)" \
		npm run capture:node-red

logs: ## Tail logs of all running services
	$(COMPOSE) logs -f --tail=100

ps: ## Show container status
	$(COMPOSE) ps

influx: ## Open an InfluxDB CLI shell context
	$(COMPOSE) exec influxdb influx bucket list \
		--host http://localhost:8086 \
		--org "$${INFLUXDB_ORG:-saint-gobain}" \
		--token "$${INFLUXDB_TOKEN}"

mqtt-sub: ## Subscribe to every topic on the broker
	$(COMPOSE) exec broker mosquitto_sub -h localhost -t '#' -v

mqtt-pub: ## Publish a test message  (make mqtt-pub T=sgx/test M=hello)
	$(COMPOSE) exec broker mosquitto_pub -h localhost -t '$(T)' -m '$(M)'

reset-influx: ## DESTROY the InfluxDB volumes and initialize an empty bucket
	@echo "This deletes all stored telemetry, events and traceability data."
	@read -p "Type 'yes' to continue: " ans; [ "$$ans" = "yes" ] || exit 1
	$(COMPOSE) rm -sf influxdb
	docker volume rm sg-printer-monitoring_influxdb_data sg-printer-monitoring_influxdb_config
	$(COMPOSE) up -d influxdb
	$(COMPOSE) restart grafana

reset-db: reset-influx ## Backward-compatible alias

nuke: ## DESTROY all volumes (database, grafana, broker) and start over
	@echo "This deletes ALL data including Grafana dashboards not exported to git."
	@read -p "Type 'yes' to continue: " ans; [ "$$ans" = "yes" ] || exit 1
	$(COMPOSE) --profile phase2 --profile phase3 --profile phase4 down -v
