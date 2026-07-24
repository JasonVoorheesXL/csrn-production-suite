from __future__ import annotations

from pathlib import Path


APP_PATH = Path("app.py")


def insert_after(source: str, anchor: str, addition: str, label: str) -> str:
    if addition.strip() in source:
        return source
    if anchor not in source:
        raise RuntimeError(f"{label} anchor not found")
    return source.replace(anchor, anchor + addition, 1)


def insert_before(source: str, anchor: str, addition: str, label: str) -> str:
    if addition.strip() in source:
        return source
    if anchor not in source:
        raise RuntimeError(f"{label} anchor not found")
    return source.replace(anchor, addition + anchor, 1)


def main() -> None:
    source = APP_PATH.read_text(encoding="utf-8")

    source = insert_after(
        source,
        "from association_supplement_service import AssociationSupplementService\n",
        (
            "from association_profile_service import AssociationProfileService\n"
            "from association_source_service import AssociationSourceService\n"
            "from association_workflow_service import AssociationWorkflowService\n"
        ),
        "association workflow imports",
    )

    source = insert_after(
        source,
        'IMPORTS_DIR = DATA_DIR / "Imports"\n',
        'ASSOCIATION_PROFILES_DIR = IMPORTS_DIR / "Profiles"\n',
        "association profiles directory",
    )

    source = insert_after(
        source,
        "        (DATA_DIR / name).mkdir(parents=True, exist_ok=True)\n",
        "    ASSOCIATION_PROFILES_DIR.mkdir(parents=True, exist_ok=True)\n",
        "association profiles architecture",
    )

    service_anchor = (
        "def get_association_supplement_service() -> AssociationSupplementService:\n"
        "    global ASSOCIATION_SUPPLEMENT_SERVICE\n"
        "\n"
        "    if ASSOCIATION_SUPPLEMENT_SERVICE is None:\n"
        "        ASSOCIATION_SUPPLEMENT_SERVICE = AssociationSupplementService(\n"
        "            load_schools=load_schools,\n"
        "            save_schools=save_schools,\n"
        "            load_venues=load_venues,\n"
        "            save_venues=save_venues,\n"
        "        )\n"
        "\n"
        "    return ASSOCIATION_SUPPLEMENT_SERVICE\n"
    )
    service_addition = (
        "\n\nASSOCIATION_PROFILE_SERVICE: AssociationProfileService | None = None\n"
        "\n\ndef get_association_profile_service() -> AssociationProfileService:\n"
        "    global ASSOCIATION_PROFILE_SERVICE\n"
        "\n"
        "    if ASSOCIATION_PROFILE_SERVICE is None:\n"
        "        ASSOCIATION_PROFILE_SERVICE = AssociationProfileService(\n"
        "            ASSOCIATION_PROFILES_DIR,\n"
        "            protected_ids={\"mhsaa-football-5a-2025-27\"},\n"
        "        )\n"
        "\n"
        "    return ASSOCIATION_PROFILE_SERVICE\n"
        "\n\nASSOCIATION_SOURCE_SERVICE: AssociationSourceService | None = None\n"
        "\n\ndef get_association_source_service() -> AssociationSourceService:\n"
        "    global ASSOCIATION_SOURCE_SERVICE\n"
        "\n"
        "    if ASSOCIATION_SOURCE_SERVICE is None:\n"
        "        ASSOCIATION_SOURCE_SERVICE = AssociationSourceService()\n"
        "\n"
        "    return ASSOCIATION_SOURCE_SERVICE\n"
        "\n\nASSOCIATION_WORKFLOW_SERVICE: AssociationWorkflowService | None = None\n"
        "\n\ndef get_association_workflow_service() -> AssociationWorkflowService:\n"
        "    global ASSOCIATION_WORKFLOW_SERVICE\n"
        "\n"
        "    if ASSOCIATION_WORKFLOW_SERVICE is None:\n"
        "        ASSOCIATION_WORKFLOW_SERVICE = AssociationWorkflowService(\n"
        "            source_service=get_association_source_service(),\n"
        "            import_service=get_association_import_service(),\n"
        "        )\n"
        "\n"
        "    return ASSOCIATION_WORKFLOW_SERVICE\n"
    )
    source = insert_after(
        source,
        service_anchor,
        service_addition,
        "association workflow runtime",
    )

    route_anchor = '@app.get("/api/imports/mhsaa/5A/analyze")\n'
    routes = '''def _association_error_status(code: str) -> int:
    if code == "PROFILE_NOT_FOUND":
        return 404
    if code in {
        "PROFILE_ALREADY_EXISTS",
        "PROFILE_ID_CONFLICT",
        "PROFILE_PROTECTED",
        "IMPORT_APPROVAL_REQUIRED",
        "SOURCE_PREVIEW_REQUIRED",
        "SOURCE_CHANGED_SINCE_PREVIEW",
    }:
        return 409
    if code in {"SOURCE_FETCH_FAILED", "SOURCE_HOST_UNRESOLVED"}:
        return 502
    if code in {
        "PROFILE_READ_FAILED",
        "PROFILE_SAVE_FAILED",
        "PROFILE_DELETE_FAILED",
    }:
        return 500
    return 400


def _association_error_response(code: str):
    return jsonify({"error": code}), _association_error_status(code)


def _association_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _association_request_payload():
    supplied_content: bytes | str | None = None
    supplied_content_type = ""

    if request.files or request.form:
        payload: dict[str, Any] = request.form.to_dict(flat=True)
        profile_text = str(payload.get("profile", "")).strip()
        if profile_text:
            try:
                parsed_profile = json.loads(profile_text)
            except json.JSONDecodeError:
                return {}, None, "", "INVALID_PROFILE_JSON"
            if not isinstance(parsed_profile, dict):
                return {}, None, "", "INVALID_PROFILE_PAYLOAD"
            payload["profile"] = parsed_profile

        upload = request.files.get("source")
        if upload is not None and upload.filename:
            supplied_content = upload.read()
            supplied_content_type = str(upload.mimetype or "")
        else:
            supplied_content = payload.get("source_content")
            supplied_content_type = str(
                payload.get("source_content_type", "")
            )
    else:
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return {}, None, "", "INVALID_REQUEST_PAYLOAD"
        supplied_content = payload.get("source_content")
        supplied_content_type = str(payload.get("source_content_type", ""))

    if supplied_content is not None and not isinstance(
        supplied_content,
        (bytes, str),
    ):
        return {}, None, "", "INVALID_SOURCE_CONTENT"
    return payload, supplied_content, supplied_content_type, ""


def _resolve_association_profile(payload: dict[str, Any]):
    inline_profile = payload.get("profile")
    if inline_profile is not None:
        if not isinstance(inline_profile, dict):
            return None, "INVALID_PROFILE_PAYLOAD"
        return inline_profile, ""

    profile_id = str(payload.get("profile_id", "")).strip()
    if not profile_id:
        return None, "PROFILE_ID_REQUIRED"
    result = get_association_profile_service().read(profile_id)
    if not result.ok:
        return None, result.code
    return result.data["profile"], ""


@app.get("/api/imports/associations/profiles")
@require_auth
def list_association_profiles():
    result = get_association_profile_service().list_profiles()
    if not result.ok:
        return _association_error_response(result.code)
    return jsonify(result.data)


@app.get("/api/imports/associations/profiles/<profile_id>")
@require_auth
def read_association_profile(profile_id: str):
    result = get_association_profile_service().read(profile_id)
    if not result.ok:
        return _association_error_response(result.code)
    return jsonify(result.data["profile"])


@app.post("/api/imports/associations/profiles")
@require_auth
def create_association_profile():
    incoming = request.get_json(silent=True) or {}
    result = get_association_profile_service().create(incoming)
    if not result.ok:
        return _association_error_response(result.code)
    return jsonify(result.data["profile"]), 201


@app.put("/api/imports/associations/profiles/<profile_id>")
@require_auth
def update_association_profile(profile_id: str):
    incoming = request.get_json(silent=True) or {}
    result = get_association_profile_service().update(profile_id, incoming)
    if not result.ok:
        return _association_error_response(result.code)
    return jsonify(result.data["profile"])


@app.delete("/api/imports/associations/profiles/<profile_id>")
@require_auth
def delete_association_profile(profile_id: str):
    result = get_association_profile_service().delete(profile_id)
    if not result.ok:
        return _association_error_response(result.code)
    return jsonify(result.data)


@app.post("/api/imports/associations/preview")
@require_auth
def preview_association_import():
    payload, supplied_content, supplied_content_type, error = (
        _association_request_payload()
    )
    if error:
        return _association_error_response(error)
    profile, error = _resolve_association_profile(payload)
    if error:
        return _association_error_response(error)

    result = get_association_workflow_service().preview(
        profile,
        supplied_content=supplied_content,
        supplied_content_type=supplied_content_type,
    )
    if not result.ok:
        return _association_error_response(result.code)
    return jsonify(result.data)


@app.post("/api/imports/associations/import")
@require_auth
def apply_association_import():
    payload, supplied_content, supplied_content_type, error = (
        _association_request_payload()
    )
    if error:
        return _association_error_response(error)
    profile, error = _resolve_association_profile(payload)
    if error:
        return _association_error_response(error)

    create_venues = None
    if "create_venues" in payload:
        create_venues = _association_bool(payload.get("create_venues"))

    result = get_association_workflow_service().apply(
        profile,
        approved=_association_bool(payload.get("approved")),
        expected_sha256=str(payload.get("expected_sha256", "")),
        supplied_content=supplied_content,
        supplied_content_type=supplied_content_type,
        create_venues=create_venues,
        allow_possible_duplicates=_association_bool(
            payload.get("allow_possible_duplicates")
        ),
    )
    if not result.ok:
        return _association_error_response(result.code)
    return jsonify(result.data)


'''
    source = insert_before(
        source,
        route_anchor,
        routes,
        "generic association routes",
    )

    APP_PATH.write_text(source, encoding="utf-8")
    print("Phase 4.4B6 generic association workflow routes wired.")


if __name__ == "__main__":
    main()
