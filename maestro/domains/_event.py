from maestro.domains._entity import Entity
from maestro.integrations._home_assistant.domain import Domain


class Event(Entity):
    domain = Domain.EVENT
    allow_set_state = False
