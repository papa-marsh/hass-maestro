from datetime import datetime

from maestro.domains.entity import Entity, EntityAttribute
from maestro.integrations.home_assistant.domain import Domain


class Sun(Entity):
    """The Home Assistant sun integration's singleton `sun.sun` entity"""

    domain = Domain.SUN
    allow_set_state = False

    next_dawn = EntityAttribute(datetime)
    next_dusk = EntityAttribute(datetime)
    next_midnight = EntityAttribute(datetime)
    next_noon = EntityAttribute(datetime)
    next_rising = EntityAttribute(datetime)
    next_setting = EntityAttribute(datetime)
    elevation = EntityAttribute(float)
    azimuth = EntityAttribute(float)
    rising = EntityAttribute(bool)

    @property
    def is_above_horizon(self) -> bool:
        return self.state == "above_horizon"
