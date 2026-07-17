import atexit
import json
import os
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.executors.pool import ThreadPoolExecutor  # type:ignore[import-untyped]
from apscheduler.jobstores.redis import RedisJobStore  # type:ignore[import-untyped]
from apscheduler.schedulers.background import BackgroundScheduler  # type:ignore[import-untyped]
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from maestro.config import MaestroConfig, get_config, register_config
from maestro.integrations.home_assistant.websocket_manager import WebSocketManager
from maestro.triggers.cron import CronTriggerManager
from maestro.triggers.maestro import MaestroEvent, MaestroTriggerManager
from maestro.triggers.sun import SunTriggerManager
from maestro.utils.internal import (
    configure_logging,
    load_script_modules,
    shell_mode_active,
    test_mode_active,
)
from maestro.utils.logging import build_process_id, log, set_process_id


class MaestroFlask(Flask):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        process_id = build_process_id("startup")
        set_process_id(process_id)
        self._initialize_db()

        if test_mode_active():
            self._initialize_test_environment()
            return

        if shell_mode_active():
            self._initialize_shell_environment()
            return

        load_script_modules()
        self._initialize_scheduler()
        self._initialize_websocket()
        with self.app_context():
            MaestroTriggerManager.fire_triggers(MaestroEvent.STARTUP)
        atexit.register(self._shutdown_handler)

        log.info("Maestro app fully initialized")

    def _initialize_db(self) -> None:
        log.info("Initializing database connection")
        self.config["SQLALCHEMY_DATABASE_URI"] = get_config().db_url
        self.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        db.init_app(self)
        log.info("Database connection initialized")

    def _initialize_scheduler(self) -> None:
        log.info("Initializing job scheduler")
        config = get_config()
        self.scheduler = BackgroundScheduler(
            jobstores={"default": RedisJobStore(host=config.redis_host, port=config.redis_port)},
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

    def _initialize_test_environment(self) -> None:
        """Initialize in-memory scheduler for registering decorators while testing."""
        log.info("Initializing test environment")
        self.scheduler = BackgroundScheduler(timezone=get_config().timezone)
        log.info("Test environment initialized")

    def _initialize_shell_environment(self) -> None:
        """Initialize Flask shell environment with scripts loaded but no background services"""
        log.info("Initializing shell environment")
        load_script_modules()
        self.scheduler = BackgroundScheduler(timezone=get_config().timezone)
        log.info("Shell environment initialized - background services disabled")


def _config_from_env() -> MaestroConfig:
    """Transitional env-var bridge until MaestroApp accepts constructor kwargs"""
    return MaestroConfig(
        hass_url=os.environ.get("HOME_ASSISTANT_URL", ""),
        hass_token=os.environ.get("HOME_ASSISTANT_TOKEN", ""),
        redis_host=os.environ.get("REDIS_HOST", ""),
        redis_port=int(os.environ.get("REDIS_PORT", "0")),
        db_url=os.environ.get("DATABASE_URL", ""),
        timezone=ZoneInfo(os.environ.get("TIMEZONE", "America/New_York")),
        autopopulate_registry=os.environ.get("AUTOPOPULATE_REGISTRY", "").lower() in ["true", "1"],
        domain_ignore_list=tuple(os.environ.get("DOMAIN_IGNORE_LIST", "").split(",")),
        notify_action_mappings={
            notify_mapping.split(":")[0]: notify_mapping.split(":")[1]
            for notify_mapping in os.environ.get("NOTIFY_ACTION_MAPPINGS", "").split(",")
            if ":" in notify_mapping
        },
    )


register_config(_config_from_env())
configure_logging()


db = SQLAlchemy()
app = MaestroFlask(__name__)


@app.shell_context_processor
def make_shell_context() -> dict:
    """Pre-load common imports for flask shell command"""
    from maestro.integrations.home_assistant.client import HomeAssistantClient
    from maestro.integrations.home_assistant.types import (
        AttributeId,
        EntityData,
        EntityId,
        StateChangeEvent,
        StateId,
    )
    from maestro.integrations.redis import RedisClient
    from maestro.integrations.state_manager import StateManager
    from maestro.registry.registry_manager import RegistryManager
    from maestro.triggers.sun import SolarEvent
    from maestro.triggers.trigger_manager import TriggerManager
    from maestro.utils import (
        IntervalSeconds,
        JobScheduler,
        Notif,
        local_now,
        resolve_timestamp,
    )

    hass = HomeAssistantClient()
    redis = RedisClient()
    sm = StateManager(hass_client=hass, redis_client=redis)
    rm = RegistryManager()
    triggers = TriggerManager.get_registry()

    print("Pre-loaded variables: hass, redis, sm, rm, triggers")  # noqa: T201

    return locals()
