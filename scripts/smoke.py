"""Real HTTP validation of all four endpoints; no extra dependencies."""
import argparse
import json
import time
import urllib.error
import urllib.request


def request(url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)


def smoke(base, wait=0, expected_version=None):
    deadline = time.monotonic() + wait
    while True:
        try:
            health = request(f"{base}/health")
            assert health["database"] == "OK"
            break
        except (OSError, AssertionError, ValueError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(10)
    version = request(f"{base}/version")["version"]
    if expected_version:
        assert version == expected_version, (version, expected_version)
    task = request(f"{base}/tasks", {"title": "Validar práctica 4 - Vittorio Catino", "done": False})
    assert task["id"] > 0
    assert any(t["id"] == task["id"] for t in request(f"{base}/tasks"))
    print(json.dumps({"health": health, "version": version, "created_task": task}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("--wait", type=int, default=0)
    parser.add_argument("--version")
    args = parser.parse_args()
    smoke(args.base.rstrip("/"), args.wait, args.version)
