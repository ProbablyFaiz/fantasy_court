import logging
import sys

import rl.utils.io
import sentry_sdk
import structlog

SENTRY_DSN = rl.utils.io.getenv("BLANK_SENTRY_DSN")
BLANK_ENV = rl.utils.io.getenv("BLANK_ENV", "dev")


def configure_logging():
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
        )
    )
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)


configure_logging()
LOGGER = structlog.get_logger()


def safe_init_sentry():
    if not SENTRY_DSN:
        LOGGER.warning("SENTRY_DSN is not set, skipping sentry initialization")
        return

    sentry_sdk.init(dsn=SENTRY_DSN, send_default_pii=True, environment=BLANK_ENV)
