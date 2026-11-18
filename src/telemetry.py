"""Low-volume asynchronous custom metrics; telemetry never breaks API traffic."""
import logging
import os
import queue
import threading
from datetime import datetime, timezone

import boto3
from botocore.config import Config

log = logging.getLogger(__name__)


class CloudWatchMetrics:
    def __init__(self):
        self.pending = queue.Queue(maxsize=1000)
        self.stop_event = threading.Event()
        self.worker = None

    def start(self):
        self.worker = threading.Thread(target=self._run, daemon=True)
        self.worker.start()

    def stop(self):
        self.stop_event.set()
        if self.worker:
            self.worker.join(timeout=8)

    def emit(self, name, value, unit="Count"):
        datum = {
            "MetricName": name, "Timestamp": datetime.now(timezone.utc),
            "Value": value, "Unit": unit,
            "Dimensions": [{"Name": "Application", "Value": os.getenv("APP_NAME", "practica4-todo")}],
        }
        try:
            self.pending.put_nowait(datum)
        except queue.Full:
            log.warning("Metric buffer full; dropped %s", name)

    def _run(self):
        client = boto3.client("cloudwatch", config=Config(
            connect_timeout=2, read_timeout=3, retries={"max_attempts": 1}))
        while not self.stop_event.wait(10):
            self._flush(client)
        self._flush(client)

    def _flush(self, client):
        batch = []
        while len(batch) < 1000:
            try:
                batch.append(self.pending.get_nowait())
            except queue.Empty:
                break
        if batch:
            try:
                client.put_metric_data(Namespace="TodoList", MetricData=batch)
            except Exception:
                log.exception("CloudWatch PutMetricData failed")
