## ADDED Requirements

### Requirement: Weekly sector rotation rankings
The system SHALL compute weekly sector performance rankings for 11 GICS-mapped Taiwan market sectors using 4-week, 8-week, and 13-week momentum scores. Rankings SHALL be updated every Saturday.

#### Scenario: Rankings computed on Saturday
- **WHEN** APScheduler fires the Saturday sector rotation cron
- **THEN** system computes momentum scores for each sector and stores results (or updates in memory cache)

#### Scenario: Insufficient history
- **WHEN** a sector has fewer than 13 weeks of data available
- **THEN** system computes scores only for the available lookback periods and marks missing periods as null

### Requirement: Sector rotation REST endpoint
The system SHALL expose `GET /api/market/sector-rotation` returning current sector rankings sorted by composite momentum score descending.

#### Scenario: Rankings available
- **WHEN** client calls `GET /api/market/sector-rotation`
- **THEN** response is a JSON array of `{sector, momentum_4w, momentum_8w, momentum_13w, composite_score, rank}` with HTTP 200

#### Scenario: Rankings not yet computed
- **WHEN** client calls `GET /api/market/sector-rotation` before first Saturday run
- **THEN** response is HTTP 503 with `{"detail": "Sector rotation data not available yet"}`
