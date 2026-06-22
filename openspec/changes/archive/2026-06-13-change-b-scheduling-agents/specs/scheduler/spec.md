## MODIFIED Requirements

### Requirement: APScheduler cron consolidation
The system SHALL manage all scheduled jobs in `backend/main.py` under a single APScheduler instance with the following schedule (all times Taiwan UTC+8, weekdays unless noted):

| Time | Job | Frequency |
|------|-----|-----------|
| 08:30 | Morning Brief generation + Telegram push | Mon–Fri |
| 09:05 | Open: chip data fetch + anomaly agent first scan | Mon–Fri |
| 10:00–13:20 | Anomaly agent scan (every 10 min) | Mon–Fri |
| 13:35 | Close: factor scan + AI batch scoring + account snapshot | Mon–Fri |
| 15:15 | Correlation service update | Mon–Fri (existing) |
| Saturday | TDCC chip fetch | Weekly (existing) |

#### Scenario: All jobs registered at startup
- **WHEN** FastAPI app starts (lifespan)
- **THEN** APScheduler starts with all 6 job types registered; log shows each job's next fire time

#### Scenario: Job failure isolation
- **WHEN** one scheduled job raises an exception
- **THEN** APScheduler logs the error and continues scheduling remaining jobs; other jobs are not affected

#### Scenario: Duplicate job prevention
- **WHEN** app restarts while a job is mid-execution
- **THEN** APScheduler does not enqueue a second instance of the same job (misfire_grace_time enforced)
