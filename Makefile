.PHONY: help install up down restart logs psql schema test import import-dry-run import-no-geocode clean

# Default target
help:
	@echo "Travel Recap - Makefile Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install          - Install Python dependencies"
	@echo "  make up               - Start Postgres container"
	@echo "  make down             - Stop and remove Postgres container"
	@echo "  make restart           - Restart Postgres container"
	@echo ""
	@echo "Database:"
	@echo "  make psql             - Connect to Postgres database"
	@echo "  make schema            - View database schema"
	@echo ""
	@echo "Import:"
	@echo "  make import            - Import visits with geocoding (full)"
	@echo "  make import-dry-run    - Preview import without inserting"
	@echo "  make import-no-geocode - Import visits without geocoding (faster)"
	@echo ""
	@echo "Testing:"
	@echo "  make test              - Run tests to verify setup (DB connection, dependencies)"
	@echo ""
	@echo "Utilities:"
	@echo "  make logs              - View Postgres container logs"
	@echo "  make clean             - Remove Python cache files"
	@echo ""

# Install Python dependencies
install:
	@echo "Installing Python dependencies..."
	pip install -r requirements.txt

# Docker Compose commands
up:
	@echo "Starting Postgres container..."
	docker-compose up -d postgres
	@echo "Waiting for database to be ready..."
	@sleep 3
	@echo "✓ Postgres is ready on localhost:5432"

down:
	@echo "Stopping Postgres container..."
	docker-compose down

restart: down up

logs:
	docker-compose logs -f postgres

# Database connection
psql:
	@echo "Connecting to Postgres database..."
	@docker-compose exec postgres psql -U travelrecap -d travelrecap

# View schema
schema:
	@echo "Database schema:"
	@docker-compose exec postgres psql -U travelrecap -d travelrecap -c "\d+ visits"
	@docker-compose exec postgres psql -U travelrecap -d travelrecap -c "\d+ place_locations"

# Import commands
import:
	@echo "Importing visits with geocoding..."
	@python scripts/import_visits.py

import-dry-run:
	@echo "Dry run - previewing import..."
	@python scripts/import_visits.py --dry-run

import-no-geocode:
	@echo "Importing visits without geocoding..."
	@python scripts/import_visits.py --skip-geocode

# Test setup
test:
	@echo "Running tests to verify setup..."
	@echo ""
	@echo "1. Checking Python dependencies..."
	@python3 -c "import psycopg2; from geopy.geocoders import Nominatim; print('   ✓ Dependencies installed')" || (echo "   ✗ Dependencies missing - run 'make install'" && exit 1)
	@echo ""
	@echo "2. Checking Docker container..."
	@docker-compose ps postgres | grep -q "Up" && echo "   ✓ Postgres container is running" || (echo "   ✗ Postgres container not running - run 'make up'" && exit 1)
	@echo ""
	@echo "3. Testing database connection..."
	@python3 -c "import psycopg2, os; conn = psycopg2.connect(host=os.getenv('DB_HOST', 'localhost'), port=os.getenv('DB_PORT', '5432'), user=os.getenv('DB_USER', 'travelrecap'), password=os.getenv('DB_PASSWORD', 'travelrecap_password'), dbname=os.getenv('DB_NAME', 'travelrecap')); conn.close(); print('   ✓ Database connection successful')" || (echo "   ✗ Database connection failed" && exit 1)
	@echo ""
	@echo "4. Checking database tables..."
	@docker-compose exec -T postgres psql -U travelrecap -d travelrecap -c "\dt" | grep -q "visits" && echo "   ✓ 'visits' table exists" || (echo "   ✗ 'visits' table not found - check schema.sql" && exit 1)
	@docker-compose exec -T postgres psql -U travelrecap -d travelrecap -c "\dt" | grep -q "place_locations" && echo "   ✓ 'place_locations' table exists" || (echo "   ✗ 'place_locations' table not found - check schema.sql" && exit 1)
	@echo ""
	@echo "5. Checking JSON file..."
	@test -f data/GoogleTimeline.json && echo "   ✓ GoogleTimeline.json found" || (echo "   ✗ GoogleTimeline.json not found in data/ directory" && exit 1)
	@echo ""
	@echo "6. Testing import script (syntax check)..."
	@python3 -m py_compile scripts/import_visits.py && echo "   ✓ Import script syntax is valid" || (echo "   ✗ Import script has syntax errors" && exit 1)
	@echo ""
	@echo "=========================================="
	@echo "✓ All tests passed! Setup is ready."
	@echo "=========================================="
	@echo ""
	@echo "Next steps:"
	@echo "  - Run 'make import-dry-run' to preview import"
	@echo "  - Run 'make import' to import with geocoding"
	@echo "  - Run 'make import-no-geocode' for faster import"

# Clean Python cache
clean:
	@echo "Cleaning Python cache files..."
	find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@echo "✓ Cleaned"

