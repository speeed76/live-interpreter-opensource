.PHONY: all build up down logs clean download-models

# ====================================================================================
#  Development
# ====================================================================================

build:
	@echo "Building Docker images..."
	docker-compose build

up:
	@echo "Starting services..."
	docker-compose up -d

down:
	@echo "Stopping services..."
	docker-compose down

logs:
	@echo "Tailing logs..."
	docker-compose logs -f

test:
	@echo "Running backend tests..."
	docker-compose run --rm backend pytest

# ====================================================================================
#  Management
# ====================================================================================

download-models:
	@echo "Downloading all AI models..."
	@echo "This may take a while and requires significant disk space."
	python download_models.py

clean: down
	@echo "Cleaning up..."
	docker-compose rm -f
	sudo rm -rf models
	@echo "Cleanup complete."

# ====================================================================================
#  Default
# ====================================================================================

all: build up

help:
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  build              Build all docker images"
	@echo "  up                 Start all services in detached mode"
	@echo "  down               Stop all services"
	@echo "  logs               Follow logs from all services"
	@echo "  download-models    Download and cache all AI models"
	@echo "  clean              Stop and remove all containers and volumes"
	@echo ""
