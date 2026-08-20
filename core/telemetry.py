import time
from contextlib import contextmanager
from core.logger import log

@contextmanager
def execution_timer(stage_name: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        log.info(f"⏱️ Stage '{stage_name}' completed in {elapsed:.4f}s")
