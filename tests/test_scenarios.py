from scenarios import SCENARIOS


def test_scenario_ids_are_unique() -> None:
    ids = [scenario["id"] for scenario in SCENARIOS]
    assert len(ids) == len(set(ids))


def test_all_scenarios_have_required_fields() -> None:
    required = {
        "id",
        "name",
        "persona",
        "goal",
        "opening",
        "follow_ups",
        "success_criteria",
        "edge_to_watch",
    }
    assert len(SCENARIOS) >= 10
    for scenario in SCENARIOS:
        assert required.issubset(scenario)
        assert scenario["opening"].strip()
        assert scenario["follow_ups"]
