import os
import threading

import psutil


class MemoryMonitor:
    def __init__(self):
        self.stop_event = threading.Event()
        self.controller = 0
        self.model = 0
        self.model_samples = 0
        self.errors = set()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _sample(self):
        try:
            self.controller = max(
                self.controller, psutil.Process(os.getpid()).memory_info().rss
            )
        except (psutil.Error, OSError) as exc:
            self.errors.add(f"Controller RSS unavailable: {exc}")
        try:
            model_rss = 0
            complete = True
            for process in psutil.process_iter(["name", "memory_info"]):
                try:
                    name = (process.info["name"] or "").lower()
                    if name in {"ollama", "llama-server"}:
                        model_rss += process.info["memory_info"].rss
                except (psutil.Error, TypeError, AttributeError) as exc:
                    complete = False
                    self.errors.add(f"Process RSS sample incomplete: {exc}")
            if complete:
                self.model = max(self.model, model_rss)
                self.model_samples += 1
        except (psutil.Error, OSError) as exc:
            self.errors.add(f"Model process RSS unavailable: {exc}")

    def _run(self):
        while not self.stop_event.is_set():
            self._sample()
            self.stop_event.wait(0.2)

    def start(self):
        self.thread.start()

    def finish(self):
        self.stop_event.set()
        self.thread.join(timeout=1)
        return {
            "controller_peak_rss_mb": self.controller / 2**20,
            "ollama_processes_peak_sum_rss_mb": self.model / 2**20 if self.model_samples else None,
            "model_rss_samples": self.model_samples,
            "measurement_errors": sorted(self.errors),
            "sampling_seconds": 0.2,
            "scope": "Host RSS of visible processes named ollama/llama-server; may include other sessions. Excludes Metal allocations and Docker daemon/VM. Worker peak RSS is recorded separately.",
        }
