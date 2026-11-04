"""Test grouping for the S1/S5 harness suite.

Tests that start child processes (stand-in hub/node stubs on 127.0.0.1, or
the orphan-guard check) get the `orchestration` marker, so CI can run them
in their own step after a memory pre-check. They test the harness itself;
they are not S1/S5 runs of the Nexus runtime.

    pytest -m "not orchestration" test_s1s5_harness.py   # no child processes
    pytest -m orchestration test_s1s5_harness.py         # child processes
"""

import pytest

ORCHESTRATION_FIXTURES = {"stub_env"}
ORCHESTRATION_TESTS = {"test_orphan_guard_kills_children_when_harness_dies"}


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "orchestration: harness test that starts child processes "
        "(stand-in stubs, not the Nexus runtime)",
    )


def pytest_collection_modifyitems(config, items):
    for item in items:
        fixtures = set(getattr(item, "fixturenames", ()))
        name = getattr(item, "originalname", None) or item.name
        if fixtures & ORCHESTRATION_FIXTURES or name in ORCHESTRATION_TESTS:
            item.add_marker(pytest.mark.orchestration)
