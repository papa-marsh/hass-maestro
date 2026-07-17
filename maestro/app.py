import atexit
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.executors.pool import ThreadPoolExecutor  # type:ignore[import-untyped]
from apscheduler.jobstores.redis import RedisJobStore  # type:ignore[import-untyped]
from apscheduler.schedulers.background import BackgroundScheduler  # type:ignore[import-untyped]
from flask import Flask

from maestro.config import MaestroConfig, get_config, register_config
from maestro.integrations.home_assistant.websocket_manager import WebSocketManager
from maestro.triggers.cron import CronTriggerManager
from maestro.triggers.maestro import MaestroEvent, MaestroTriggerManager
from maestro.triggers.sun import SunTriggerManager
from maestro.utils import internal
from maestro.utils.exceptions import MaestroAlreadyConstructedError, MaestroNotConstructedError
from maestro.utils.logging import build_process_id, log, set_process_id

_app: MaestroApp | None = None


def get_app() -> MaestroApp:
    """Return the current MaestroApp, available once constructed"""
    if _app is None:
        raise MaestroNotConstructedError("MaestroApp has not been constructed")
    return _app


class MaestroApp(Flask):
    """
    The Maestro application. Constructing one initializes the full framework:
    configuration, logging, optional database, user script loading, and (unless
    disabled) the background scheduler and Home Assistant websocket connection.

    Directly servable by any WSGI server since it subclasses Flask.
    """

    scheduler: BackgroundScheduler
    websocket_manager: WebSocketManager

    def __init__(
        self,
        *,
        hass_url: str,
        hass_token: str,
        redis_host: str,
        redis_port: int,
        db_url: str | None = None,
        scripts_dir: Path | str = Path("scripts"),
        registry_dir: Path | str = Path("registry"),
        custom_domains_dir: Path | str | None = None,
        redis_key_prefix: str = "maestro",
        timezone: str = "America/New_York",
        background_services: bool = True,
        configure_logging: bool = True,
        autopopulate_registry: bool = False,
        domain_ignore_list: Sequence[str] = (),
        notify_action_mappings: Mapping[str, str] | None = None,
        default_notif_sound: str = "3rdParty_Failure_Haptic.caf",
        critical_notif_sound: str = "3rd_party_critical.caf",
        default_notif_url: str = "overview",
    ) -> None:
        global _app
        if _app is not None:
            raise MaestroAlreadyConstructedError("Only one MaestroApp allowed per process")

        super().__init__("maestro")

        config = MaestroConfig(
            hass_url=hass_url,
            hass_token=hass_token,
            redis_host=redis_host,
            redis_port=redis_port,
            db_url=db_url,
            scripts_dir=Path(scripts_dir),
            registry_dir=Path(registry_dir),
            custom_domains_dir=Path(custom_domains_dir) if custom_domains_dir else None,
            redis_key_prefix=redis_key_prefix,
            timezone=ZoneInfo(timezone),
            autopopulate_registry=autopopulate_registry,
            domain_ignore_list=tuple(domain_ignore_list),
            notify_action_mappings=dict(notify_action_mappings or {}),
            default_notif_sound=default_notif_sound,
            critical_notif_sound=critical_notif_sound,
            default_notif_url=default_notif_url,
        )
        register_config(config)
        _app = self

        set_process_id(build_process_id("startup"))
        if configure_logging:
            internal.configure_logging()

        if config.db_url is not None:
            self._initialize_db()

        self._add_project_paths()
        internal.import_custom_domains()
        internal.load_script_modules(config.scripts_dir)

        if background_services:
            self._initialize_scheduler()
            self._initialize_websocket()
            with self.app_context():
                MaestroTriggerManager.fire_triggers(MaestroEvent.STARTUP)
            atexit.register(self._shutdown_handler)
        else:
            # Idle in-memory scheduler so job scheduling code paths stay usable (eg. in a REPL)
            self.scheduler = BackgroundScheduler(timezone=config.timezone)

        log.info("Maestro app fully initialized")

    def _add_project_paths(self) -> None:
        """Make the user's project packages (scripts, registry, custom domains) importable"""
        config = get_config()
        project_dirs = [config.scripts_dir, config.registry_dir]
        if config.custom_domains_dir is not None:
            project_dirs.append(config.custom_domains_dir)

        for project_dir in project_dirs:
            parent = str(project_dir.resolve().parent)
            if parent not in sys.path:
                sys.path.insert(0, parent)
                log.info("Added project path to sys.path", path=parent)

    def _initialize_db(self) -> None:
        from maestro import db

        log.info("Initializing database connection")
        self.config["SQLALCHEMY_DATABASE_URI"] = get_config().db_url
        self.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        db.init_app(self)
        log.info("Database connection initialized")

    def _initialize_scheduler(self) -> None:
        log.info("Initializing job scheduler")
        config = get_config()
        self.scheduler = BackgroundScheduler(
            jobstores={
                "default": RedisJobStore(
                    host=config.redis_host,
                    port=config.redis_port,
                    jobs_key=f"{config.redis_key_prefix}:apscheduler.jobs",
                    run_times_key=f"{config.redis_key_prefix}:apscheduler.run_times",
                )
            },
            executors={"default": ThreadPoolExecutor(max_workers=100)},
            timezone=config.timezone,
        )
        self.scheduler.start()
        log.info("Job scheduler initialized")
        CronTriggerManager.register_jobs(self.scheduler)
        SunTriggerManager.register_jobs(self.scheduler)
        all_scheduled_jobs = [str(j) for j in self.scheduler.get_jobs()]
        log.debug("Jobs scheduled", job_list=json.dumps(all_scheduled_jobs))
        atexit.register(self.scheduler.shutdown)

    def _initialize_websocket(self) -> None:
        self.websocket_manager = WebSocketManager()
        self.websocket_manager.start()
        log.info("Websocket manager initialized")
        atexit.register(self.websocket_manager.stop)

    def _shutdown_handler(self) -> None:
        self.websocket_manager.set_last_connected()
        with self.app_context():
            MaestroTriggerManager.fire_triggers(MaestroEvent.SHUTDOWN, self)
