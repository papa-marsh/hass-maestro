from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class MaestroConfig:
    """
    Runtime configuration for the framework, registered during `MaestroApp` construction.
    Internal plumbing for constructor kwargs -- read via `get_config()` at call time.
    """

    hass_url: str
    hass_token: str
    redis_host: str
    redis_port: int
    db_url: str | None = None
    scripts_dir: Path = Path("scripts")
    registry_dir: Path = Path("registry")
    custom_domains_dir: Path | None = None
    redis_key_prefix: str = "maestro"
    timezone: ZoneInfo = field(default_factory=lambda: ZoneInfo("America/New_York"))
    autopopulate_registry: bool = False
    domain_ignore_list: tuple[str, ...] = ()
    notify_action_mappings: Mapping[str, str] = field(default_factory=dict)
    default_notif_sound: str = "3rdParty_Failure_Haptic.caf"
    critical_notif_sound: str = "3rd_party_critical.caf"
    default_notif_url: str = "overview"

    def __post_init__(self) -> None:
        object.__setattr__(self, "hass_url", self.hass_url.rstrip("/"))


_config: MaestroConfig | None = None


def register_config(config: MaestroConfig) -> None:
    """Register the active config. Called during `MaestroApp` construction."""
    global _config
    _config = config


def get_config() -> MaestroConfig:
    """Return the active config"""
    if _config is None:
        # Imported lazily: `maestro.utils` pulls in modules that read config at call time
        from maestro.utils.exceptions import MaestroNotConstructedError

        raise MaestroNotConstructedError(
            "MaestroApp has not been constructed. "
            "Configuration is available only after `MaestroApp(...)` has been created."
        )
    return _config
