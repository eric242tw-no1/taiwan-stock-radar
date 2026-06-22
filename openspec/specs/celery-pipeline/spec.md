# Celery Pipeline

## Purpose

Async task queue infrastructure using Celery and Redis for long-running backend tasks.

## Requirements

### Requirement: Celery async task queue
The system SHALL use Celery with Redis broker to execute long-running tasks asynchronously. The following tasks SHALL be moved to Celery: AI factor scoring, screener batch scan, and backtest runs.

#### Scenario: AI scoring task enqueued
- **WHEN** an API handler or APScheduler job needs AI scoring for a symbol
- **THEN** handler calls `score_symbol.delay(symbol)` and returns immediately; result is stored in DB when the worker completes

#### Scenario: Worker unavailable
- **WHEN** Celery worker is not running and a task is enqueued
- **THEN** task remains in Redis queue; API handler still returns HTTP 202; task executes when worker restarts

### Requirement: Celery worker deployment
The system SHALL include a `celery-worker` Docker service in `docker-compose.yml`. A Flower monitoring dashboard SHALL be available at port 5555.

#### Scenario: Worker starts with compose
- **WHEN** `docker-compose up` is run
- **THEN** celery-worker container starts, connects to Redis, and shows as READY in Flower at localhost:5555

#### Scenario: Flower dashboard accessible
- **WHEN** user navigates to localhost:5555
- **THEN** Flower UI shows active workers, task queue length, and recent task results
