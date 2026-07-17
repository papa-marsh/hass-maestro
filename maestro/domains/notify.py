from maestro.domains.entity import Entity
from maestro.integrations.home_assistant.domain import Domain


class Notify(Entity):
    domain = Domain.NOTIFY
    allow_set_state = False
