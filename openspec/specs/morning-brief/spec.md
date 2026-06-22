# Morning Brief

## Purpose

Daily AI-generated market summary delivered via Telegram at 08:30 Taiwan time on weekdays.

## Requirements

### Requirement: Daily morning brief generation
The system SHALL generate a daily AI market brief at 08:30 Taiwan time (UTC+8) on weekdays (Mon–Fri). The brief SHALL be persisted in the `daily_ai_report` table with a `date` UNIQUE constraint to prevent duplicates.

#### Scenario: Brief generated on weekday
- **WHEN** APScheduler fires the 08:30 cron on a weekday
- **THEN** system fetches market sentiment, top movers, alert counts, and AI screener picks, calls Claude API to produce a prose summary, stores the result in `daily_ai_report`, and pushes the summary via Telegram

#### Scenario: Duplicate prevention
- **WHEN** the cron fires and a record for today's date already exists in `daily_ai_report`
- **THEN** system skips generation and does not push a duplicate Telegram message

#### Scenario: Claude API timeout
- **WHEN** the Claude API call takes longer than 30 seconds
- **THEN** system logs an error, does not store a partial record, and skips Telegram push for that day

### Requirement: Morning brief REST endpoint
The system SHALL expose `GET /api/reports/morning-brief` returning the most recent daily brief. If today's brief has not yet been generated, return the most recent available.

#### Scenario: Brief available
- **WHEN** client calls `GET /api/reports/morning-brief`
- **THEN** response is `{date, report_json, sent_at}` with HTTP 200

#### Scenario: No brief ever generated
- **WHEN** client calls `GET /api/reports/morning-brief` and `daily_ai_report` is empty
- **THEN** response is HTTP 404 with `{"detail": "No morning brief available"}`
