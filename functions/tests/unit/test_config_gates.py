"""The dev auth bypass is a real authentication bypass. These tests are the
reason it can be allowed to exist at all.

The gate is deliberately three independent conditions rather than one flag, so
that any single misconfiguration fails closed rather than open. Two of them are
hard refusals at startup: a service that boots in a broken state and serves
traffic is worse than one that will not boot.
"""

import pytest

from api.core.config import Environment, Settings


def test_bypass_is_off_without_a_secret() -> None:
    assert Settings(environment=Environment.LOCAL).dev_auth_bypass_enabled is False


def test_bypass_is_on_only_in_local_with_a_secret() -> None:
    assert Settings(
        environment=Environment.LOCAL, dev_auth_bypass_secret="s"
    ).dev_auth_bypass_enabled is True


@pytest.mark.parametrize(
    "env", [Environment.DEVELOPMENT, Environment.TESTING, Environment.UAT]
)
def test_bypass_is_off_outside_local_even_with_a_secret(env: Environment) -> None:
    assert Settings(environment=env, dev_auth_bypass_secret="s").dev_auth_bypass_enabled is False


def test_bypass_is_off_on_cloud_run_even_in_local_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """K_SERVICE is injected by the runtime, not by us. Keying off it means a
    mistakenly-deployed local config still cannot open the bypass."""
    monkeypatch.setenv("K_SERVICE", "frame-api")
    settings = Settings(environment=Environment.LOCAL, dev_auth_bypass_secret="s")
    assert settings.dev_auth_bypass_enabled is False


def test_production_refuses_to_start_with_a_bypass_secret() -> None:
    with pytest.raises(ValueError, match="authentication bypass"):
        Settings(environment=Environment.PRODUCTION, dev_auth_bypass_secret="s")


def test_deployed_environments_refuse_to_start_pointed_at_an_emulator() -> None:
    """A deployed service pointed at an emulator reads and writes nothing, and
    looks healthy while doing it."""
    with pytest.raises(ValueError, match="emulator"):
        Settings(environment=Environment.UAT, firestore_emulator_host="localhost:6310")


def test_ports_come_from_the_shared_allocation() -> None:
    """Not restated in Python. Two lists of ports drift, and the symptom is a
    seeder writing into one emulator while the API reads from another."""
    ports = Settings().ports
    assert ports["backend"] == 6301
    assert ports["firestore"] == 6310


def test_port_offset_shifts_python_and_node_together(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRAME_PORT_OFFSET", "100")
    ports = Settings().ports
    assert ports["backend"] == 6401
    assert ports["firestore"] == 6410
