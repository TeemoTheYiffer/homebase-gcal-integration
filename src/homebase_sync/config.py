"""Runtime configuration loading for homebase-sync.

Auth uses Application Default Credentials (no key file or token to manage).
Only Homebase scrape credentials and the employee->calendar map are config.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class EmployeeConfig:
    name: str
    calendar_id: str


@dataclass(frozen=True, slots=True)
class AppConfig:
    homebase_email: str
    homebase_password: str
    employees: tuple[EmployeeConfig, ...]
    timezone: str
    log_level: str

    @property
    def employee_names(self) -> tuple[str, ...]:
        return tuple(e.name for e in self.employees)

    def calendar_for(self, employee_name: str) -> str:
        for e in self.employees:
            if e.name == employee_name:
                return e.calendar_id
        raise KeyError(f"no calendar mapped for employee {employee_name!r}")


class ConfigError(Exception):
    """Raised when required configuration is missing or malformed."""


def load_config() -> AppConfig:
    """Load configuration from environment + employees source."""
    load_dotenv()

    email = _required_env("HOMEBASE_EMAIL")
    password = _required_env("HOMEBASE_PASSWORD")
    employees_path = Path(os.environ.get("EMPLOYEES_CONFIG_PATH", "employees.toml"))
    tz = os.environ.get("SYNC_TIMEZONE", "America/Los_Angeles")
    log_level = os.environ.get("LOG_LEVEL", "INFO")

    employees_inline = os.environ.get("EMPLOYEES_CONFIG_TOML")
    if employees_inline:
        employees = _parse_employees(
            tomllib.loads(employees_inline), source="EMPLOYEES_CONFIG_TOML"
        )
    else:
        employees = _load_employees(employees_path)
    if not employees:
        raise ConfigError("no employees defined")

    return AppConfig(
        homebase_email=email,
        homebase_password=password,
        employees=employees,
        timezone=tz,
        log_level=log_level,
    )


def _required_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise ConfigError(f"required env var not set: {key}")
    return value


def _load_employees(path: Path) -> tuple[EmployeeConfig, ...]:
    if not path.exists():
        raise ConfigError(f"employees config not found: {path}")
    with path.open("rb") as f:
        data = tomllib.load(f)
    return _parse_employees(data, source=str(path))


def _parse_employees(data: dict, *, source: str) -> tuple[EmployeeConfig, ...]:
    raw = data.get("employees", [])
    if not isinstance(raw, list):
        raise ConfigError(f"'employees' must be an array of tables in {source}")
    out: list[EmployeeConfig] = []
    for i, entry in enumerate(raw):
        try:
            out.append(EmployeeConfig(name=entry["name"], calendar_id=entry["calendar_id"]))
        except (KeyError, TypeError) as exc:
            raise ConfigError(f"employees[{i}] missing 'name' or 'calendar_id': {exc}") from exc
    return tuple(out)
