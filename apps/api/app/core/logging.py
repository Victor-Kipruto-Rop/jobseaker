import logging
import structlog

def configure_logging():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    structlog.configure(processors=[structlog.processors.TimeStamper(fmt="iso"), structlog.processors.JSONRenderer()])
