from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from maestro.app import MaestroApp, get_app  # noqa: E402

__all__ = [
    MaestroApp.__name__,
    get_app.__name__,
    "db",
]
