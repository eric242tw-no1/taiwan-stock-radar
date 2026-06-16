"""DB migration stubs — schema is now managed by schema_sqlite.sql via main.py lifespan."""
import logging

logger = logging.getLogger(__name__)


def ensure_daily_ai_report_table() -> None:
    pass


def ensure_strategy_versions_table() -> None:
    pass


def ensure_trade_journal_table() -> None:
    pass


def ensure_workflow_definitions_table() -> None:
    pass
