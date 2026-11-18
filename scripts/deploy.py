"""Deploy an immutable public GitHub Release through SSM; no SSH or scp."""
import argparse
import re
import shlex
import time

import boto3

from smoke import smoke


def deploy(repository, tag):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid repository")
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise ValueError("Invalid semantic tag")
    ec2 = boto3.client("ec2")
    reservations = ec2.describe_instances(Filters=[
        {"Name": "tag:Project", "Values": ["practica4-todo"]},
        {"Name": "instance-state-name", "Values": ["running"]},
    ])["Reservations"]
    instances = [i for r in reservations for i in r["Instances"]]
    if len(instances) != 1:
        raise RuntimeError(f"Expected exactly one running lab instance, got {len(instances)}")
    instance = instances[0]
    base = f"https://github.com/{repository}/releases/download/{tag}"
    script = f"""#!/bin/bash
set -euo pipefail
test -f /etc/systemd/system/todo.service
WORK=$(mktemp -d /opt/todo/releases/{tag}.XXXXXX)
cd "$WORK"
curl --fail --location --retry 5 {shlex.quote(base + '/todo-list.zip')} -o todo-list.zip
curl --fail --location --retry 5 {shlex.quote(base + '/todo-list.zip.sha256')} -o todo-list.zip.sha256
sha256sum -c todo-list.zip.sha256
unzip -q todo-list.zip
python3 -m venv "$WORK/.venv"
"$WORK/.venv/bin/pip" install --no-cache-dir -r src/requirements.txt
OLD=$(readlink -f /opt/todo/current)
OLDENV=$(cat /etc/todo/version.env)
ln -s "$WORK" /opt/todo/current.new
mv -Tf /opt/todo/current.new /opt/todo/current
printf 'APP_VERSION={tag}\\n' > /etc/todo/version.env
chown -R todo:todo "$WORK"
systemctl restart todo
for attempt in $(seq 1 30); do
  if curl --fail --silent http://127.0.0.1:8000/health >/dev/null; then
    curl --fail --silent http://127.0.0.1:8000/version
    exit 0
  fi
  sleep 5
done
ln -s "$OLD" /opt/todo/current.rollback
mv -Tf /opt/todo/current.rollback /opt/todo/current
printf '%s\\n' "$OLDENV" > /etc/todo/version.env
systemctl restart todo
exit 1
"""
    ssm = boto3.client("ssm")
    command = ssm.send_command(
        InstanceIds=[instance["InstanceId"]], DocumentName="AWS-RunShellScript",
        Parameters={"commands": [script], "executionTimeout": ["900"]},
        Comment=f"Deploy practica4-todo {tag}", TimeoutSeconds=900,
    )["Command"]["CommandId"]
    deadline = time.monotonic() + 960
    while time.monotonic() < deadline:
        try:
            invocation = ssm.get_command_invocation(CommandId=command, InstanceId=instance["InstanceId"])
        except ssm.exceptions.InvocationDoesNotExist:
            time.sleep(3)
            continue
        status = invocation["Status"]
        if status == "Success":
            print(invocation.get("StandardOutputContent", ""))
            smoke(f"http://{instance['PublicIpAddress']}:8000", wait=60, expected_version=tag)
            return
        if status not in {"Pending", "InProgress", "Delayed"}:
            raise RuntimeError(invocation.get("StandardErrorContent", status))
        time.sleep(5)
    raise TimeoutError("SSM deployment timed out")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    deploy(args.repository, args.tag)
