.PHONY: up ingest transform test charts refresh

up:            ## start local Postgres
	docker compose up -d

ingest:        ## pull latest data from the Oura API
	.venv/bin/python -m ingestion.ingest --start 2022-01-01

transform:     ## build + test dbt staging layer
	.venv/bin/dbt build --project-dir dbt_project --profiles-dir dbt_project

test:          ## run Python tests
	.venv/bin/pytest -q

charts:        ## regenerate README charts
	.venv/bin/python -m analysis.charts

refresh: ingest transform charts   ## full daily refresh
