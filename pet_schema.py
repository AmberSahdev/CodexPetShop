from jsonschema import Draft202012Validator

PET_JSON_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "displayName", "description", "spritesheetPath"],
    "properties": {
        "id": {"type": "string", "pattern": r"^[a-z0-9-]{2,24}$"},
        "displayName": {"type": "string", "minLength": 1, "maxLength": 40},
        "description": {"type": "string", "maxLength": 280},
        "spritesheetPath": {
            "type": "string",
            "minLength": 1,
            "maxLength": 200,
            "not": {"pattern": r"(^/|\.\.)"},
        },
    },
}

_validator = Draft202012Validator(PET_JSON_SCHEMA)


def validate_pet_json(data) -> list[str]:
    """Return a list of human-readable errors (empty if valid)."""
    errors = []
    for err in _validator.iter_errors(data):
        path = ".".join(str(p) for p in err.path) or "(root)"
        errors.append(f"{path}: {err.message}")
    return errors
