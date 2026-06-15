.PHONY: up ps

up:
	docker compose up -d

ps:
	docker compose ps
