from maestro.domains._entity import Entity
from maestro.integrations._home_assistant.domain import Domain


class Sensor(Entity):
    domain = Domain.SENSOR
    allow_set_state = False
