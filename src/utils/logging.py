import logging
import sys
import contextvars
from colorlog import ColoredFormatter

# -------------------------------------------------
# Async-safe correlation ID (ECID)
# -------------------------------------------------
ecid_var = contextvars.ContextVar("ecid", default="-")


class ECIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.ecid = ecid_var.get()
        return True


def setup_logging(
    level: int = logging.DEBUG,
    silence_third_party: bool = True,
) -> logging.Logger:
    """
    Configure colored terminal logging with ECID support.
    Safe to call multiple times (Streamlit reruns).
    """

    root = logging.getLogger()
    root.setLevel(level)

    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(level)

        handler.addFilter(ECIDFilter())

        handler.setFormatter(
            ColoredFormatter(
                "%(asctime)s %(log_color)s%(levelname)-8s%(reset)s "
                "%(light_black)secid=%(ecid)s%(reset)s %(name)s:%(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                log_colors={
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "bold_red",
                },
            )
        )

        root.addHandler(handler)

    if silence_third_party:
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("openai").setLevel(logging.WARNING)
        logging.getLogger("asyncio").setLevel(logging.WARNING)
        logging.getLogger("langchain").setLevel(logging.INFO)
        logging.getLogger("langgraph").setLevel(logging.INFO)

    logger = logging.getLogger("EmailAssist")
    logger.setLevel(level)
    logger.propagate = True

    return logger
