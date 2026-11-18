"""RDS credentials are fetched at runtime, using the EC2 instance role."""
import json
import os
import threading
import time

import boto3
from sqlalchemy import create_engine
from sqlalchemy.engine import URL


class RuntimeDatabase:
    def __init__(self):
        self._engine = None
        self._expires = 0.0
        self._lock = threading.Lock()

    def engine(self):
        with self._lock:
            if self._engine is None or time.monotonic() >= self._expires:
                response = boto3.client("secretsmanager").get_secret_value(
                    SecretId=os.environ["DB_SECRET_ARN"]
                )
                secret = json.loads(response["SecretString"])
                url = URL.create(
                    "mysql+pymysql", username=secret["username"],
                    password=secret["password"], host=secret["host"],
                    port=int(secret.get("port", 3306)),
                    database=secret.get("dbname", "todo"),
                )
                engine = create_engine(
                    url, pool_pre_ping=True, pool_recycle=240,
                    connect_args={"connect_timeout": 4, "read_timeout": 4,
                                  "write_timeout": 4, "ssl": {"check_hostname": True}},
                )
                if self._engine is not None:
                    self._engine.dispose()
                self._engine = engine
                self._expires = time.monotonic() + 300
            return self._engine
