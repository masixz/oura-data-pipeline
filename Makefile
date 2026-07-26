.PHONY: up deps ingest backfill freshness transform test charts refresh

up:            ## start local Postgres
	docker compose up -d

deps:          ## install dbt packages (dbt_utils)
	.venv/bin/dbt deps --project-dir dbt_project --profiles-dir dbt_project

ingest:        ## pull new and revised data (incremental, resumes per endpoint)
	.venv/bin/python -m ingestion.ingest

backfill:      ## refetch the entire history from scratch
	.venv/bin/python -m ingestion.ingest --full

freshness:     ## warn if no new or revised data has arrived in 36h
	.venv/bin/dbt source freshness --project-dir dbt_project --profiles-dir dbt_project

transform: deps  ## build + test the dbt staging and marts layers
	.venv/bin/dbt build --project-dir dbt_project --profiles-dir dbt_project

test:          ## run Python tests
	.venv/bin/pytest -q

charts:        ## regenerate README charts
	.venv/bin/python -m analysis.charts

refresh: ingest transform charts   ## full daily refresh
