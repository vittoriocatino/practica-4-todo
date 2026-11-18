"""Controlled outage of only the Terraform-managed lab RDS, with real requests."""
import json
import time
from pathlib import Path
import urllib.error

import boto3

from smoke import request


def main():
    rds = boto3.client("rds")
    ec2 = boto3.client("ec2")
    cw = boto3.client("cloudwatch")
    db = rds.describe_db_instances(DBInstanceIdentifier="practica4-todo")["DBInstances"][0]
    tags = rds.list_tags_for_resource(ResourceName=db["DBInstanceArn"])["TagList"]
    assert {"Key": "Project", "Value": "practica4-todo"} in tags, "Refuse to touch unrelated database"
    instances = [i for r in ec2.describe_instances(Filters=[
        {"Name": "tag:Project", "Values": ["practica4-todo"]},
        {"Name": "instance-state-name", "Values": ["running"]},
    ])["Reservations"] for i in r["Instances"]]
    assert len(instances) == 1
    base = f"http://{instances[0]['PublicIpAddress']}:8000"
    assert request(base + "/health")["database"] == "OK"
    rds.stop_db_instance(DBInstanceIdentifier="practica4-todo")
    evidence = Path("evidence")
    evidence.mkdir(exist_ok=True)
    samples = []
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        try:
            health = request(base + "/health")
            samples.append({"time": time.time(), "http": 200, "health": health})
        except urllib.error.HTTPError as exc:
            samples.append({"time": time.time(), "http": exc.code, "body": exc.read().decode()})
        except OSError as exc:
            samples.append({"time": time.time(), "error": type(exc).__name__})
        alarm = cw.describe_alarms(AlarmNames=["practica4-todo-database-errors"])["MetricAlarms"][0]
        status = rds.describe_db_instances(DBInstanceIdentifier="practica4-todo")["DBInstances"][0]["DBInstanceStatus"]
        print("RDS:", status, "Alarm:", alarm["StateValue"], "HTTP:", samples[-1].get("http"), flush=True)
        (evidence / "outage-requests.json").write_text(json.dumps(samples, indent=2))
        if alarm["StateValue"] == "ALARM" and status == "stopped":
            (evidence / "alarm-real-outage.json").write_text(json.dumps(alarm, default=str, indent=2))
            print("Real outage alarm verified; restoring database in next workflow step.")
            return
        time.sleep(15)
    raise TimeoutError("RDS outage alarm did not reach ALARM with stopped database")


if __name__ == "__main__":
    main()
