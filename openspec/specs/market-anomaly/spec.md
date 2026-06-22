# Market Anomaly

## Purpose

Intraday anomaly detection scanning for volume spikes, gap opens, and limit moves during Taiwan trading hours.

## Requirements

### Requirement: Intraday anomaly detection
The system SHALL scan for market anomalies every 10 minutes during trading hours (09:00–13:30 Taiwan time, weekdays). The following conditions SHALL trigger an anomaly alert:
- Gap open >3% from previous close
- Current volume >3× the 20-day average volume
- Stock hitting daily limit-up or limit-down

#### Scenario: Volume spike detected
- **WHEN** scanner finds a stock with current volume > 3× 20-day average volume
- **THEN** system sends a Telegram alert with symbol, current volume, ratio, and price

#### Scenario: Gap detected
- **WHEN** scanner finds a stock with opening price differing >3% from previous close
- **THEN** system sends a Telegram alert with symbol, gap percentage, and direction

#### Scenario: Limit move detected
- **WHEN** scanner finds a stock at limit-up or limit-down price
- **THEN** system sends a Telegram alert with symbol, price, and limit direction

#### Scenario: Market hours check
- **WHEN** scanner cron fires outside 09:00–13:30 Taiwan time
- **THEN** system skips the scan and returns immediately without alerts

#### Scenario: No anomalies found
- **WHEN** scanner runs and no stocks meet anomaly thresholds
- **THEN** system logs a debug message and sends no Telegram alert
