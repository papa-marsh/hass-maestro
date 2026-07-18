from maestro.domains._entity import Entity
from maestro.integrations._home_assistant.domain import Domain


class Maestro(Entity):
    domain = Domain.MAESTRO
