from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, jsonify, request


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]
ManifestLoader = Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class AssociationRoutesDependencies:
    """Injected application boundaries used by association import routes."""

    require_auth: RouteDecorator
    get_profile_service: Callable[[], Any]
    get_workflow_service: Callable[[], Any]
    get_import_service: Callable[[], Any]
    get_supplement_service: Callable[[], Any]
    get_dragonfly_service: Callable[[], Any]
    get_dragonfly_sync_service: Callable[[], Any]
    get_school_service: Callable[[], Any]
    load_mhsaa_profile: ManifestLoader
    load_mhsaa_manifest: ManifestLoader
    load_mhsaa_branding_manifest: ManifestLoader
    load_mhsaa_enrichment_manifest: ManifestLoader


def association_error_status(code: str) -> int:
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


def association_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def create_association_blueprint(
    dependencies: AssociationRoutesDependencies,
) -> Blueprint:
    """Create generic and legacy association import HTTP routes."""

    routes = Blueprint("association_routes", __name__)

    def error_response(code: str):
        return jsonify({"error": code}), association_error_status(code)

    def request_payload():
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

    def resolve_profile(payload: dict[str, Any]):
        inline_profile = payload.get("profile")
        if inline_profile is not None:
            if not isinstance(inline_profile, dict):
                return None, "INVALID_PROFILE_PAYLOAD"
            return inline_profile, ""

        profile_id = str(payload.get("profile_id", "")).strip()
        if not profile_id:
            return None, "PROFILE_ID_REQUIRED"
        result = dependencies.get_profile_service().read(profile_id)
        if not result.ok:
            return None, result.code
        return result.data["profile"], ""

    @routes.get("/api/imports/associations/profiles")
    @dependencies.require_auth
    def list_association_profiles():
        result = dependencies.get_profile_service().list_profiles()
        if not result.ok:
            return error_response(result.code)
        return jsonify(result.data)

    @routes.get("/api/imports/associations/profiles/<profile_id>")
    @dependencies.require_auth
    def read_association_profile(profile_id: str):
        result = dependencies.get_profile_service().read(profile_id)
        if not result.ok:
            return error_response(result.code)
        return jsonify(result.data["profile"])

    @routes.post("/api/imports/associations/profiles")
    @dependencies.require_auth
    def create_association_profile():
        incoming = request.get_json(silent=True) or {}
        result = dependencies.get_profile_service().create(incoming)
        if not result.ok:
            return error_response(result.code)
        return jsonify(result.data["profile"]), 201

    @routes.put("/api/imports/associations/profiles/<profile_id>")
    @dependencies.require_auth
    def update_association_profile(profile_id: str):
        incoming = request.get_json(silent=True) or {}
        result = dependencies.get_profile_service().update(profile_id, incoming)
        if not result.ok:
            return error_response(result.code)
        return jsonify(result.data["profile"])

    @routes.delete("/api/imports/associations/profiles/<profile_id>")
    @dependencies.require_auth
    def delete_association_profile(profile_id: str):
        result = dependencies.get_profile_service().delete(profile_id)
        if not result.ok:
            return error_response(result.code)
        return jsonify(result.data)

    @routes.post("/api/imports/associations/preview")
    @dependencies.require_auth
    def preview_association_import():
        payload, supplied_content, supplied_content_type, error = (
            request_payload()
        )
        if error:
            return error_response(error)
        profile, error = resolve_profile(payload)
        if error:
            return error_response(error)

        result = dependencies.get_workflow_service().preview(
            profile,
            supplied_content=supplied_content,
            supplied_content_type=supplied_content_type,
        )
        if not result.ok:
            return error_response(result.code)
        return jsonify(result.data)

    @routes.post("/api/imports/associations/import")
    @dependencies.require_auth
    def apply_association_import():
        payload, supplied_content, supplied_content_type, error = (
            request_payload()
        )
        if error:
            return error_response(error)
        profile, error = resolve_profile(payload)
        if error:
            return error_response(error)

        create_venues = None
        if "create_venues" in payload:
            create_venues = association_bool(payload.get("create_venues"))

        result = dependencies.get_workflow_service().apply(
            profile,
            approved=association_bool(payload.get("approved")),
            expected_sha256=str(payload.get("expected_sha256", "")),
            supplied_content=supplied_content,
            supplied_content_type=supplied_content_type,
            create_venues=create_venues,
            allow_possible_duplicates=association_bool(
                payload.get("allow_possible_duplicates")
            ),
        )
        if not result.ok:
            return error_response(result.code)
        return jsonify(result.data)

    @routes.post("/api/imports/dragonfly/preview")
    @dependencies.require_auth
    def preview_dragonfly_school():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return error_response("INVALID_REQUEST_PAYLOAD")

        school_name = str(payload.get("school_name", "")).strip()
        if not school_name:
            return error_response("SCHOOL_NAME_REQUIRED")

        result = dependencies.get_dragonfly_service().preview_school(
            school_name,
            association=str(
                payload.get("association", "MHSAA")
            ).strip() or "MHSAA",
            city=str(payload.get("city", "")).strip(),
            state=str(payload.get("state", "MS")).strip() or "MS",
            sport=str(payload.get("sport", "FB")).strip() or "FB",
        )

        if not result.ok:
            return error_response(result.code)

        return jsonify(result.data)

    @routes.post("/api/imports/dragonfly/sync-preview")
    @dependencies.require_auth
    def preview_dragonfly_sync():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return error_response("INVALID_REQUEST_PAYLOAD")

        school_name = str(payload.get("school_name", "")).strip()
        if not school_name:
            return error_response("SCHOOL_NAME_REQUIRED")

        result = dependencies.get_dragonfly_sync_service().preview(
            school_name,
            school_id=str(payload.get("school_id", "")).strip(),
            association=str(
                payload.get("association", "MHSAA")
            ).strip() or "MHSAA",
            city=str(payload.get("city", "")).strip(),
            state=str(payload.get("state", "MS")).strip() or "MS",
            sport=str(payload.get("sport", "FB")).strip() or "FB",
            csrn_sport=str(
                payload.get("csrn_sport", "Football")
            ).strip() or "Football",
            season=str(payload.get("season", "2026")).strip() or "2026",
            level=str(payload.get("level", "Varsity")).strip() or "Varsity",
            division=str(
                payload.get("division", "Boys")
            ).strip() or "Boys",
        )

        if not result.ok:
            return error_response(result.code)

        return jsonify(result.data)

    @routes.post("/api/imports/dragonfly/replace-roster")
    @dependencies.require_auth
    def replace_dragonfly_roster():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return error_response("INVALID_REQUEST_PAYLOAD")

        school_name = str(payload.get("school_name", "")).strip()
        if not school_name:
            return error_response("SCHOOL_NAME_REQUIRED")

        result = dependencies.get_dragonfly_sync_service().replace_roster(
            school_name,
            approved=association_bool(payload.get("approved")),
            school_id=str(payload.get("school_id", "")).strip(),
            association=str(
                payload.get("association", "MHSAA")
            ).strip() or "MHSAA",
            city=str(payload.get("city", "")).strip(),
            state=str(payload.get("state", "MS")).strip() or "MS",
            sport=str(payload.get("sport", "FB")).strip() or "FB",
            csrn_sport=str(
                payload.get("csrn_sport", "Football")
            ).strip() or "Football",
            season=str(payload.get("season", "2026")).strip() or "2026",
            level=str(payload.get("level", "Varsity")).strip() or "Varsity",
            division=str(
                payload.get("division", "Boys")
            ).strip() or "Boys",
        )

        if not result.ok:
            return error_response(result.code)

        return jsonify(result.data)

    @routes.post("/api/imports/dragonfly/school-info-preview")
    @dependencies.require_auth
    def preview_dragonfly_school_info():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return error_response("INVALID_REQUEST_PAYLOAD")

        school_name = str(payload.get("school_name", "")).strip()
        if not school_name:
            return error_response("SCHOOL_NAME_REQUIRED")

        result = dependencies.get_dragonfly_sync_service().preview_school_info(
            school_name,
            school_id=str(payload.get("school_id", "")).strip(),
            association=str(
                payload.get("association", "MHSAA")
            ).strip() or "MHSAA",
            city=str(payload.get("city", "")).strip(),
            state=str(payload.get("state", "MS")).strip() or "MS",
        )

        if not result.ok:
            return error_response(result.code)

        return jsonify(result.data)

    @routes.post("/api/imports/dragonfly/school-info-apply")
    @dependencies.require_auth
    def apply_dragonfly_school_info():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return error_response("INVALID_REQUEST_PAYLOAD")

        school_name = str(payload.get("school_name", "")).strip()
        if not school_name:
            return error_response("SCHOOL_NAME_REQUIRED")

        result = dependencies.get_dragonfly_sync_service().apply_safe_school_info(
            school_name,
            approved=association_bool(payload.get("approved")),
            school_id=str(payload.get("school_id", "")).strip(),
            association=str(
                payload.get("association", "MHSAA")
            ).strip() or "MHSAA",
            city=str(payload.get("city", "")).strip(),
            state=str(payload.get("state", "MS")).strip() or "MS",
            school_service=dependencies.get_school_service(),
        )

        if not result.ok:
            return error_response(result.code)

        return jsonify(result.data)

    @routes.get("/api/imports/mhsaa/5A/analyze")
    @dependencies.require_auth
    def analyze_mhsaa_5a():
        profile = dependencies.load_mhsaa_profile()
        manifest = dependencies.load_mhsaa_manifest()
        result = dependencies.get_import_service().analyze(
            profile,
            manifest.get("schools", []),
        )
        if not result.ok:
            return jsonify({"error": result.code}), 400

        schools = []
        for item in result.data.get("schools", []):
            candidate = dict(item.get("candidate") or {})
            candidate["status"] = item.get("status", "invalid")
            candidate["matches"] = item.get("matches", [])
            schools.append(candidate)

        return jsonify(
            {
                "classification": manifest.get("classification", "5A"),
                "source": manifest.get("source", {}),
                "found": result.data.get("found", len(schools)),
                "new": result.data.get("new", 0),
                "existing": result.data.get("existing", 0),
                "possible_duplicates": result.data.get(
                    "possible_duplicates",
                    0,
                ),
                "schools": schools,
            }
        )

    @routes.post("/api/imports/mhsaa/5A")
    @dependencies.require_auth
    def import_mhsaa_5a():
        options = request.get_json(silent=True) or {}
        profile = dependencies.load_mhsaa_profile()
        manifest = dependencies.load_mhsaa_manifest()
        result = dependencies.get_import_service().apply(
            profile,
            manifest.get("schools", []),
            create_venues=bool(options.get("create_venues", True)),
            allow_possible_duplicates=True,
        )
        if not result.ok:
            return jsonify({"error": result.code}), 400

        return jsonify(
            {
                "imported": result.data.get("imported", 0),
                "skipped_existing": (
                    result.data.get("enriched_existing", 0)
                    + result.data.get("skipped_existing", 0)
                ),
                "created_ids": result.data.get("created_ids", []),
                "total_schools": result.data.get("total_schools", 0),
            }
        )

    @routes.get("/api/imports/mhsaa/5A/branding/analyze")
    @dependencies.require_auth
    def analyze_mhsaa_5a_branding():
        manifest = dependencies.load_mhsaa_branding_manifest()
        result = dependencies.get_supplement_service().analyze_branding(
            manifest.get("schools", []),
            source=manifest.get("source", {}),
        )
        if not result.ok:
            return jsonify({"error": result.code}), 400
        return jsonify(result.data)

    @routes.post("/api/imports/mhsaa/5A/branding")
    @dependencies.require_auth
    def import_mhsaa_5a_branding():
        manifest = dependencies.load_mhsaa_branding_manifest()
        result = dependencies.get_supplement_service().apply_branding(
            manifest.get("schools", []),
            source=manifest.get("source", {}),
        )
        if not result.ok:
            return jsonify({"error": result.code}), 400
        return jsonify(result.data)

    @routes.get("/api/imports/mhsaa/5A/enrichment/analyze")
    @dependencies.require_auth
    def analyze_mhsaa_5a_enrichment():
        manifest = dependencies.load_mhsaa_enrichment_manifest()
        result = dependencies.get_supplement_service().analyze_enrichment(
            manifest.get("schools", []),
            source=manifest.get("source", {}),
            classification=str(manifest.get("classification", "5A")),
        )
        if not result.ok:
            return jsonify({"error": result.code}), 400
        return jsonify(result.data)

    @routes.post("/api/imports/mhsaa/5A/enrichment")
    @dependencies.require_auth
    def enrich_mhsaa_5a():
        manifest = dependencies.load_mhsaa_enrichment_manifest()
        result = dependencies.get_supplement_service().apply_enrichment(
            manifest.get("schools", []),
            source=manifest.get("source", {}),
            venue_sport="Football",
        )
        if not result.ok:
            return jsonify({"error": result.code}), 400
        return jsonify(result.data)

    return routes
