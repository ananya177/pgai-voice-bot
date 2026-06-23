"""Command-line client for triggering and checking voice-bot calls."""

from __future__ import annotations

import argparse
import json
import sys

import requests

from config import get_settings
from scenarios import SCENARIOS


def print_json(data: object) -> None:
    print(json.dumps(data, indent=2))


def list_scenarios() -> None:
    print("\nAvailable scenarios\n" + "=" * 72)
    for scenario in SCENARIOS:
        print(f"{scenario['id']}  {scenario['name']}")
        print(f"  Persona: {scenario['persona']}")
        print(f"  Goal:    {scenario['goal']}\n")


def request_json(method: str, url: str, **kwargs: object) -> dict:
    response = requests.request(method, url, timeout=30, **kwargs)
    try:
        data = response.json()
    except ValueError:
        data = {"raw": response.text}
    if not response.ok:
        raise RuntimeError(f"HTTP {response.status_code}: {json.dumps(data)}")
    return data


def trigger_call(server: str, scenario_id: str | None, index: int | None) -> None:
    payload: dict[str, object] = {}
    if scenario_id:
        payload["scenario_id"] = scenario_id
    elif index is not None:
        payload["scenario_index"] = index
    data = request_json("POST", f"{server}/make-call", json=payload)
    print("\nCall started")
    print_json(data)
    call_id = data.get("call_id")
    if call_id:
        print(f"\nCheck status with:\n  python run_calls.py --status {call_id}")


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="PGAI voice-bot call runner")
    parser.add_argument("--server", default=settings.server_url)
    parser.add_argument("--list", action="store_true", help="List scenarios")
    parser.add_argument("--scenario", help="Scenario ID, such as SCN-01")
    parser.add_argument("--index", type=int, help="Scenario index, 0 through 11")
    parser.add_argument("--all", action="store_true", help="Queue all scenarios")
    parser.add_argument("--delay", type=int, default=120, help="Seconds between calls")
    parser.add_argument("--status", help="Show one call's status")
    parser.add_argument("--health", action="store_true", help="Run a deep health check")
    args = parser.parse_args()
    server = args.server.rstrip("/")

    try:
        if args.list:
            list_scenarios()
        elif args.health:
            print_json(request_json("GET", f"{server}/health?deep=1"))
        elif args.status:
            print_json(request_json("GET", f"{server}/call-status/{args.status}"))
        elif args.all:
            print_json(
                request_json(
                    "POST",
                    f"{server}/run-all",
                    json={"delay_seconds": args.delay},
                )
            )
        elif args.scenario or args.index is not None:
            trigger_call(server, args.scenario, args.index)
        else:
            list_scenarios()
            parser.print_help()
        return 0
    except (requests.RequestException, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print("Confirm that start.py is running and the configuration passes preflight.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
