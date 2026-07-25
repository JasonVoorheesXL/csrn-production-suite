from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"


class MigrationError(RuntimeError):
    pass


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise MigrationError(
            f"Expected one {label} anchor, found {count}."
        )
    return text.replace(old, new, 1)


def apply(path: Path = APP_FILE) -> bool:
    text = path.read_text(encoding="utf-8")
    integrated = all(
        marker in text
        for marker in (
            "from configuration_service import ConfigurationService",
            "CONFIGURATION_SERVICE: ConfigurationService | None = None",
            "get_configuration_service().read()",
            "get_configuration_service().update(incoming)",
        )
    )
    if integrated:
        return False

    text = replace_once(
        text,
        "from obs_service import OBSService\n",
        "from obs_service import OBSService\n"
        "from configuration_service import ConfigurationService\n",
        "ConfigurationService import",
    )

    configuration_anchor = '''def update_config_values(
    patch: dict[str, Any],
) -> dict[str, Any]:
    ensure_data_architecture()
    return CONFIG_REPOSITORY.update(patch)


'''
    configuration_block = configuration_anchor + '''CONFIGURATION_SERVICE: ConfigurationService | None = None


def get_configuration_service() -> ConfigurationService:
    global CONFIGURATION_SERVICE
    if CONFIGURATION_SERVICE is None:
        CONFIGURATION_SERVICE = ConfigurationService(
            load_config=load_config,
            save_config=save_config,
            runtime_version=RUNTIME_VERSION,
            runtime_build=RUNTIME_BUILD,
        )
    return CONFIGURATION_SERVICE


'''
    text = replace_once(
        text,
        configuration_anchor,
        configuration_block,
        "configuration service factory",
    )

    social_start = text.find("def normalize_social_url(")
    social_end = text.find("PERSONNEL_SERVICE: PersonnelService | None = None")
    if social_start < 0 or social_end < 0 or social_end <= social_start:
        raise MigrationError("Could not locate the social normalization block.")
    social_wrappers = '''def normalize_social_url(
    platform: str,
    value: str,
) -> tuple[str, bool, str]:
    return ConfigurationService.normalize_social_url(platform, value)


def normalize_social_block(
    block: dict[str, Any],
) -> tuple[dict[str, str], dict[str, str]]:
    return ConfigurationService.normalize_social_block(block)


'''
    text = text[:social_start] + social_wrappers + text[social_end:]

    old_routes = '''@app.get("/api/config")
@require_auth
def get_config():
    return jsonify(load_config())

@app.post("/api/config")
@require_auth
def update_config():
    incoming = request.get_json(force=True)
    current = load_config()
    if "social" in incoming:
        normalized_social, social_errors = normalize_social_block(incoming.get("social") or {})
        if social_errors:
            return jsonify({"error": "INVALID_SOCIAL_URL", "fields": social_errors}), 400
        incoming["social"] = normalized_social
    for section in current:
        if section in incoming and isinstance(incoming[section], dict):
            current[section].update(incoming[section])
    # Protect application identity fields.
    current["application"]["version"] = RUNTIME_VERSION
    current["application"]["build"] = RUNTIME_BUILD
    save_config(current)
    return jsonify(current)
'''
    new_routes = '''@app.get("/api/config")
@require_auth
def get_config():
    result = get_configuration_service().read()
    return jsonify(result.data["config"])


@app.post("/api/config")
@require_auth
def update_config():
    incoming = request.get_json(force=True)
    result = get_configuration_service().update(incoming)
    if result.code == "CONFIG_PAYLOAD_REQUIRED":
        return jsonify({"error": result.code}), 400
    if result.code == "INVALID_SOCIAL_URL":
        return jsonify(
            {
                "error": result.code,
                "fields": result.data.get("fields", {}),
            }
        ), 400
    return jsonify(result.data["config"])
'''
    text = replace_once(text, old_routes, new_routes, "configuration routes")

    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    changed = apply()
    if changed:
        print("Phase 4.14 ConfigurationService integration applied.")
    else:
        print("Phase 4.14 ConfigurationService integration already present.")


if __name__ == "__main__":
    main()
