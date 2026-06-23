"""Free local text simulation before placing a real phone call."""

from __future__ import annotations

import argparse

from config import get_settings
from patient_brain import clean_response, get_patient_response, should_end_call
from scenarios import SCENARIOS


def choose_scenario(scenario_id: str) -> dict:
    for scenario in SCENARIOS:
        if scenario["id"].upper() == scenario_id.upper():
            return scenario
    raise ValueError(f"Unknown scenario: {scenario_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate a call in the terminal")
    parser.add_argument("--scenario", default="SCN-01")
    args = parser.parse_args()
    scenario = choose_scenario(args.scenario)
    settings = get_settings()

    history = [{"role": "assistant", "content": scenario["opening"]}]
    print(f"\nScenario: {scenario['name']}")
    print(f"Goal: {scenario['goal']}")
    print("Type the medical office agent's responses. Type /quit to stop.\n")
    print(f"PATIENT: {scenario['opening']}")

    while True:
        agent_text = input("AGENT: ").strip()
        if agent_text.lower() in {"/quit", "/exit"}:
            break
        if not agent_text:
            continue
        history.append({"role": "user", "content": agent_text})
        reply = get_patient_response(scenario, history, settings=settings)
        clean = clean_response(reply)
        print(f"PATIENT: {clean}")
        history.append({"role": "assistant", "content": clean})
        if should_end_call(reply):
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
