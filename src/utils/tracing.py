# src/utils/tracing.py

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
import logging
import time

_INSTRUMENTED = False

# Import your logging setup
from .logging import ColoredFormatter

logger = logging.getLogger(__name__)


class TracingFormatter(ColoredFormatter):
    """Extends ColoredFormatter to include OpenTelemetry trace and span IDs."""
    
    # Additional colors
    DARK_GREEN = '\033[32m'
    DARKER_GREEN = '\033[2;32m'  # ✅ Dimmed/darker green
    BLUE = '\033[34m'
    
    def __init__(self, *args, service_name: str = "unknown", **kwargs):
        super().__init__(*args, **kwargs)
        self.service_name = service_name
    
    def format(self, record):
        span = trace.get_current_span()
        span_context = span.get_span_context()
        
        if span_context.is_valid:
            trace_id = format(span_context.trace_id, '032x')[:8]
            span_id = format(span_context.span_id, '016x')[:8]
            record.trace_id = f"[{trace_id}:{span_id}]"
        else:
            record.trace_id = ""
        
        record.service_name = f"{self.BLUE}{self.service_name}{self.RESET}"
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        
        return super(ColoredFormatter, self).format(record)
    
    def formatTime(self, record, datefmt=None):
        ct = self.converter(record.created)
        s = time.strftime(datefmt, ct) if datefmt else time.strftime(self.default_time_format, ct)
        s = self.default_msec_format % (s, record.msecs)
        return f"{self.DARKER_GREEN}[{s}]{self.RESET}"


def setup_tracing(service_name: str, enable_console_export: bool = False):
    """
    Initialize OpenTelemetry tracing with strict guards for Streamlit reruns.
    """
    global _INSTRUMENTED
    
    # 1. Check if TracerProvider is already set
    # Using ProxyTracerProvider check is standard, but a custom flag is more reliable in Streamlit.
    current_provider = trace.get_tracer_provider()
    
    if hasattr(current_provider, 'get_span_processor') or _INSTRUMENTED:
        # Already initialized, exit silently
        return

    # 2. Configure the Provider
    resource = Resource(attributes={"service.name": service_name})
    provider = TracerProvider(resource=resource)
    
    if enable_console_export:
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console_exporter))
    
    # Set global provider (wrapped in try/except for race conditions)
    try:
        trace.set_tracer_provider(provider)
    except ValueError:
        pass 

    # 3. Apply Instrumentation (THE FIX)
    # This block is what causes the "Attempting to instrument" spam.
    # We only enter if _INSTRUMENTED is False.
    if not _INSTRUMENTED:
        try:
            FastAPIInstrumentor().instrument()
            HTTPXClientInstrumentor().instrument()
            RequestsInstrumentor().instrument()
            _INSTRUMENTED = True
            logging.info(f"✅ OTEL: Instrumentation complete for {service_name}")
        except Exception as e:
            # Catch internal OTEL warnings that trigger even with the guard
            if "already instrumented" not in str(e).lower():
                logging.warning(f"OTEL Instrumentation warning: {e}")


def get_tracer(name: str):
    return trace.get_tracer(name)


def setup_logger_with_tracing(name: str, level: int = logging.INFO, service_name: str = "unknown") -> logging.Logger:
    import sys
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if logger.handlers:
        logger.handlers.clear()
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    
    formatter = TracingFormatter(
        fmt='%(asctime)s [%(service_name)s] %(levelname)s:    %(trace_id)s %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        service_name=service_name
    )
    
    formatter.default_time_format = '%Y-%m-%d %H:%M:%S'
    formatter.default_msec_format = '%s.%03d'
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    
    return logger


def traced(span_name: str = None):
    def decorator(func):
        import functools
        from opentelemetry import trace
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            name = span_name or func.__name__
            
            with tracer.start_as_current_span(name):
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator