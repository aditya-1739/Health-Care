import contextlib
import threading
from typing import Dict
from sqlalchemy import text
from sqlalchemy.orm import Session

# In-process lock registry for test environments / fallback
_thread_locks_guard = threading.Lock()
_slot_locks: Dict[str, threading.Lock] = {}


def _get_thread_lock(key: str) -> threading.Lock:
    with _thread_locks_guard:
        if key not in _slot_locks:
            _slot_locks[key] = threading.Lock()
        return _slot_locks[key]


@contextlib.contextmanager
def acquire_slot_lock(db: Session, doctor_id: int, start_time_str: str):
    """
    Acquires a resource-level lock for the combination of doctor and slot start time.
    
    1. In PostgreSQL: Uses transaction-level advisory lock `pg_advisory_xact_lock(hashtext(key))`
       which guarantees database-level transactional concurrency protection across processes,
       even when no appointment row exists yet.
    2. In SQLite/in-memory test runners: Uses a synchronized in-process slot lock to ensure
       atomic serialization in multi-threaded test runners.
    """
    lock_key = f"slot:{doctor_id}:{start_time_str}"
    thread_lock = _get_thread_lock(lock_key)

    # Acquire in-process mutex (ensures thread-safety during test concurrency)
    thread_lock.acquire()
    try:
        # If running on PostgreSQL, execute database-level transaction advisory lock
        dialect_name = db.bind.dialect.name if db.bind else ""
        if dialect_name == "postgresql":
            db.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                {"key": lock_key},
            )
        yield
    finally:
        thread_lock.release()
