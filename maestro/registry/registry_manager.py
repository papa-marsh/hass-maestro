import re
from datetime import timedelta
from pathlib import Path
from typing import Any, ClassVar

from maestro.config import get_config
from maestro.exceptions import (
    CustomDomainsNotConfiguredError,
    MalformedRegistryModule,
    RegistryPruneError,
)
from maestro.integrations.home_assistant.client import HomeAssistantClient
from maestro.integrations.home_assistant.types import EntityData, EntityId
from maestro.integrations.redis import CachePrefix, RedisClient
from maestro.utils.dates import IntervalSeconds, local_now, resolve_timestamp
from maestro.utils.logging import log


class RegistryManager:
    _redis_client: ClassVar[RedisClient | None] = None

    non_entity_modules: ClassVar = {"__init__.py"}
    prune_safety_threshold = 0.25

    header = "# THIS MODULE IS PROGRAMMATICALLY UPDATED BY MAESTRO - DO NOT EDIT ENTITY ENTRIES\n\n"
    attr_import_string = "from maestro.domains.entity import EntityAttribute"
    datetime_import_string = "from datetime import datetime"
    attributes_to_ignore: ClassVar = {
        "id",
        "friendly_name",
        "last_changed",
        "last_updated",
        "previous_state",
    }

    @classmethod
    def redis_client(cls) -> RedisClient:
        """Lazily construct the shared Redis client, deferring config reads to first use"""
        if cls._redis_client is None:
            cls._redis_client = RedisClient()
        return cls._redis_client

    @classmethod
    def registry_dir(cls) -> Path:
        """The user project directory that generated registry modules are written to"""
        registry_dir = get_config().registry_dir.resolve()
        registry_dir.mkdir(parents=True, exist_ok=True)
        return registry_dir

    @classmethod
    def upsert_entity(cls, entity_data: EntityData, force: bool = False) -> None:
        """Adds or updates an entity to its respective module: maestro/registry/<domain>.py"""
        entity_id = EntityId(entity_data.entity_id)
        module_filepath = cls.registry_dir() / f"{entity_id.domain}.py"
        cache_key = RedisClient.build_key(CachePrefix.REGISTERED, entity_id)

        if not force and (cached_value := cls.redis_client().get(key=cache_key)):
            last_updated = resolve_timestamp(cached_value)
            if last_updated > local_now() - timedelta(seconds=IntervalSeconds.ONE_DAY):
                return

        try:
            if not module_filepath.exists():
                cls.write_new_module(entity_data)
            else:
                cls.update_existing_module(entity_data)

            cls.redis_client().set(
                key=cache_key,
                value=local_now().isoformat(),
                ttl_seconds=IntervalSeconds.ONE_WEEK,
            )

        except Exception:
            log.exception(f"Failed to add entity {entity_id} to registry")

    @classmethod
    def write_new_module(cls, entity_data: EntityData) -> None:
        entity_id = EntityId(entity_data.entity_id)
        module_filepath = cls.registry_dir() / f"{entity_id.domain}.py"

        new_entry = cls._build_entry(
            entity_id=entity_id,
            attributes=entity_data.attributes,
            parent_class=entity_id.domain_class_name,
            type_as_value=False,
        )
        cls._write_module(module_filepath, [new_entry], {entity_id.domain_class_name})
        log.info("Created new registry file", filepath=module_filepath, entity=entity_id)

    @classmethod
    def update_existing_module(cls, entity_data: EntityData) -> None:
        entity_id = EntityId(entity_data.entity_id)
        module_filepath = cls.registry_dir() / f"{entity_id.domain}.py"

        new_entry_parent_class = entity_id.domain_class_name

        imports = set()
        entries = []
        for entry in cls._parse_module_entries(module_filepath.read_text()):
            if entry["entity_id"] == entity_id:
                new_entry_parent_class = entry["parent_class"]
                continue

            imports.add(entry["parent_class"])
            entries.append(
                cls._build_entry(
                    entity_id=EntityId(entry["entity_id"]),
                    attributes=entry["attributes"],
                    parent_class=entry["parent_class"],
                    type_as_value=True,
                )
            )

        entries.append(
            cls._build_entry(
                entity_id=entity_id,
                attributes=entity_data.attributes,
                parent_class=new_entry_parent_class,
                type_as_value=False,
            )
        )
        imports.add(new_entry_parent_class)

        cls._write_module(module_filepath, entries, imports)
        log.info("Added entity to registry", filepath=module_filepath, entity=entity_id)

    @classmethod
    def force_registry_update(cls, entity_id: str) -> None:
        """Fetch an entity from Home Assistant and update its registry entry"""
        entity_data = HomeAssistantClient().get_entity(entity_id)
        cls.upsert_entity(entity_data, force=True)

    @classmethod
    def prune(cls, force: bool = False) -> list[EntityId]:
        """
        Remove registry entries for entities that no longer exist in Home Assistant.
        Refuses to prune more than `prune_safety_threshold` of the registry unless forced.
        """
        from maestro.integrations.state_manager import StateManager

        state_manager = StateManager()

        live_entity_ids = {
            entity.entity_id for entity in state_manager.hass_client.get_all_entities()
        }
        if not live_entity_ids:
            raise RegistryPruneError("Fetched zero entities from Home Assistant")

        modules = {
            filepath: cls._parse_module_entries(filepath.read_text())
            for filepath in sorted(cls.registry_dir().glob("*.py"))
            if filepath.name not in cls.non_entity_modules
        }
        registered_ids = [
            EntityId(entry["entity_id"])
            for module_contents in modules.values()
            for entry in module_contents
        ]
        stale_ids = set(registered_ids) - live_entity_ids

        if not stale_ids:
            log.info("No stale entities found in registry", registered_count=len(registered_ids))
            return []

        stale_ratio = len(stale_ids) / len(registered_ids)
        if stale_ratio > cls.prune_safety_threshold and not force:
            raise RegistryPruneError(
                f"Refusing to prune {len(stale_ids)} of {len(registered_ids)} registered "
                f"entities ({stale_ratio:.0%}). Re-run with force=True to override."
            )

        for filepath, parsed_entries in modules.items():
            kept_entries = [e for e in parsed_entries if e["entity_id"] not in stale_ids]
            if len(kept_entries) == len(parsed_entries):
                continue

            removed = [e["entity_id"] for e in parsed_entries if e["entity_id"] in stale_ids]
            if not kept_entries:
                filepath.unlink()
                log.info("Deleted empty registry module", filepath=filepath, removed=removed)
                continue

            imports = {entry["parent_class"] for entry in kept_entries}
            entries = [
                cls._build_entry(
                    entity_id=EntityId(entry["entity_id"]),
                    attributes=entry["attributes"],
                    parent_class=entry["parent_class"],
                    type_as_value=True,
                )
                for entry in kept_entries
            ]
            cls._write_module(filepath, entries, imports)
            log.info(
                "Pruned stale entities from registry module",
                filepath=filepath,
                removed=removed,
            )

        state_manager.delete_cached_entities(*stale_ids)

        log.info(
            "Registry prune complete",
            pruned_count=len(stale_ids),
            registered_count=len(registered_ids),
        )
        return sorted(stale_ids)

    @classmethod
    def _parse_module_entries(cls, content: str) -> list[dict[str, Any]]:
        """
        Parse a registry module into dicts of entity_id, parent_class, and attribute types.

        Parsing is line-format-sensitive. If the module contains instantiations the parser
        can't account for (eg. statements re-wrapped by a code formatter), raise rather than
        return a partial result -- callers rewrite modules from parsed entries, so a silent
        partial parse would destroy the unparsed entries.
        """
        entries: list[dict[str, Any]] = []
        current: dict[str, Any] = {}
        for line in content.strip().split("\n"):
            if match := re.match(r"class\s+\w+\(([^)]+)\):", line):
                current = {"parent_class": match.group(1), "attributes": {}}
            elif match := re.match(r"\s+(\w+)\s*=\s*EntityAttribute\(([^)]+)\)", line):
                current["attributes"][match.group(1)] = match.group(2)
            elif match := re.match(r'\w+\s*=\s*\w+\("([^"]+)"\)', line):
                current["entity_id"] = match.group(1)
                entries.append(current)
                current = {}

        instantiation_count = len(re.findall(r"^\w+\s*=\s*\w+\(", content, re.MULTILINE))
        if len(entries) != instantiation_count:
            raise MalformedRegistryModule(
                f"Parsed {len(entries)} entries but found {instantiation_count} module-level "
                f"instantiations. The module's formatting has likely been altered; restore the "
                f"generated line format before maestro rewrites this module."
            )

        return entries

    @classmethod
    def _write_module(cls, module_filepath: Path, entries: list[str], imports: set[str]) -> None:
        lines = [
            cls.header,
            *cls._build_import_strings(imports),
            cls.attr_import_string,
            cls.datetime_import_string,
            *sorted(entries),
        ]
        module_filepath.write_text("\n".join(lines) + "\n")

    @classmethod
    def _build_import_strings(cls, imports: set[str]) -> list[str]:
        """
        Split parent class imports between maestro's built-in domains and the user's
        custom domains package, based on where each class is actually defined.
        """
        import maestro.domains

        builtin_parents = {name for name in imports if hasattr(maestro.domains, name)}
        custom_parents = imports - builtin_parents

        import_strings = []
        if builtin_parents:
            import_strings.append(
                "from maestro.domains import " + ", ".join(sorted(builtin_parents))
            )
        if custom_parents:
            custom_domains_dir = get_config().custom_domains_dir
            if custom_domains_dir is None:
                raise CustomDomainsNotConfiguredError(
                    f"Registry entries inherit from custom domain classes "
                    f"({', '.join(sorted(custom_parents))}) but `custom_domains_dir` "
                    f"is not configured"
                )
            import_strings.append(
                f"from {custom_domains_dir.name} import " + ", ".join(sorted(custom_parents))
            )

        return import_strings

    @classmethod
    def _build_entry(
        cls,
        entity_id: EntityId,
        attributes: dict,
        parent_class: str | None,
        type_as_value: bool,
    ) -> str:
        pascalcase_id = "".join(word.capitalize() for word in entity_id.entity.split("_"))
        entry_class_name = entity_id.domain_class_name + pascalcase_id
        parent_class = parent_class or entity_id.domain_class_name
        new_entry = f"\nclass {entry_class_name}({parent_class}):"
        attribute_added = False
        for attribute, value in attributes.items():
            if attribute not in cls.attributes_to_ignore:
                type_string = value if type_as_value else type(value).__name__
                if type_string != "NoneType":
                    new_entry += f"\n    {attribute} = EntityAttribute({type_string})"
                    attribute_added = True
        if not attribute_added:
            new_entry += " ..."
        new_entry += f'\n{entity_id.entity} = {entry_class_name}("{entity_id}")\n'

        return new_entry
