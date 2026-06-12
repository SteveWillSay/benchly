"""Shared background-job store for long-running, polled operations.

One running job at a time per store; finished jobs are pruned when a new one
starts. The runner mutates its job dict in place; "done" is managed here.
"""

import threading
import uuid


class JobStore:
    def __init__(self):
        self._jobs = {}
        self._lock = threading.Lock()

    def start(self, runner, **initial):
        """Run `runner(job)` on a daemon thread. Returns the job id, or None
        if a job from this store is still running."""
        with self._lock:
            if any(not j["done"] for j in self._jobs.values()):
                return None
            self._jobs.clear()
            job_id = uuid.uuid4().hex[:12]
            job = {"done": False, **initial}
            self._jobs[job_id] = job

        def wrap():
            try:
                runner(job)
            finally:
                job["done"] = True

        threading.Thread(target=wrap, daemon=True).start()
        return job_id

    def get(self, job_id):
        return self._jobs.get(job_id)
