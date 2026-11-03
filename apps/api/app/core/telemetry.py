from contextlib import contextmanager
from time import perf_counter
@contextmanager
def measure_operation():
    state={"duration_seconds":0.0}
    start=perf_counter()
    try: yield state
    finally: state["duration_seconds"]=perf_counter()-start
