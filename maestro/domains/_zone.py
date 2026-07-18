from maestro.domains._entity import Entity
from maestro.integrations._home_assistant.domain import Domain


class Zone(Entity):
    domain = Domain.ZONE
    allow_set_state = False
