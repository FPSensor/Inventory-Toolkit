import time
from contextlib import contextmanager
from core.logger import log, log_debug_event

@contextmanager
def execution_timer(stage_name: str):
    start = time.perf_counter()
    log_debug_event("stage_start", stage=stage_name)
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        log.info(f"⏱️ Stage '{stage_name}' completed in {elapsed:.4f}s")
        log_debug_event("stage_finish", stage=stage_name, elapsed_seconds=round(elapsed, 6))
