from __future__ import annotations

from functools import wraps
from typing import Any, Callable

import pytest
from flask import Blueprint, jsonify

from application_factory import (
    build_route_manifest,
    create_application,
    direct_route_endpoints,
    duplicate_route_methods,
)


def protected(view: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view)
    def wrapper(*args: Any, **kwargs: Any):
        return view(*args, **kwargs)

    setattr(wrapper, "_csrn_requires_auth", True)
    return wrapper


def example_blueprint(name: str = "example") -> Blueprint:
    routes = Blueprint(name, __name__)

    @routes.get("/public")
    def public_route():
        return jsonify({"public": True})

    @routes.post("/protected")
    @protected
    def protected_route():
        return jsonify({"protected": True})

    return routes


def test_factory_configures_session_and_overrides() -> None:
    application = create_application(
        "factory-test",
        blueprints=(example_blueprint(),),
        secret_key="secret",
        session_seconds=123,
        config_overrides={"TESTING": True},
    )
    assert application.secret_key == "secret"
    assert application.config["TESTING"] is True
    assert application.config["SESSION_COOKIE_HTTPONLY"] is True
    assert application.config["SESSION_COOKIE_SAMESITE"] == "Strict"
    assert application.permanent_session_lifetime.total_seconds() == 123


def test_factory_returns_independent_applications() -> None:
    blueprints = (example_blueprint(),)
    first = create_application(
        "first",
        blueprints=blueprints,
        secret_key="one",
        session_seconds=60,
    )
    second = create_application(
        "second",
        blueprints=blueprints,
        secret_key="two",
        session_seconds=60,
    )
    assert first is not second
    assert first.secret_key == "one"
    assert second.secret_key == "two"
    assert set(first.blueprints) == {"example"}
    assert set(second.blueprints) == {"example"}


def test_factory_rejects_duplicate_blueprint_names() -> None:
    with pytest.raises(RuntimeError, match="Duplicate Blueprint names"):
        create_application(
            "duplicate-blueprint-test",
            blueprints=(example_blueprint("same"), example_blueprint("same")),
            secret_key="secret",
            session_seconds=60,
        )


def test_factory_rejects_duplicate_route_methods() -> None:
    first = Blueprint("first", __name__)
    second = Blueprint("second", __name__)

    @first.get("/duplicate")
    def first_duplicate():
        return "first"

    @second.get("/duplicate")
    def second_duplicate():
        return "second"

    with pytest.raises(RuntimeError, match="Duplicate route methods"):
        create_application(
            "duplicate-route-test",
            blueprints=(first, second),
            secret_key="secret",
            session_seconds=60,
        )


def test_manifest_records_blueprint_methods_and_authentication() -> None:
    application = create_application(
        "manifest-test",
        blueprints=(example_blueprint(),),
        secret_key="secret",
        session_seconds=60,
    )
    manifest = build_route_manifest(application)
    public = next(entry for entry in manifest if entry.rule == "/public")
    protected_entry = next(
        entry for entry in manifest if entry.rule == "/protected"
    )
    assert public.blueprint == "example"
    assert public.methods == ("GET",)
    assert public.auth_required is False
    assert protected_entry.methods == ("POST",)
    assert protected_entry.auth_required is True
    assert duplicate_route_methods(manifest) == ()
    assert direct_route_endpoints(manifest) == ()


def test_factory_publishes_serializable_route_metadata() -> None:
    application = create_application(
        "metadata-test",
        blueprints=(example_blueprint(),),
        secret_key="secret",
        session_seconds=60,
    )
    manifest = application.extensions["csrn_route_manifest"]
    assert isinstance(manifest, tuple)
    assert any(row["endpoint"] == "example.public_route" for row in manifest)
    assert application.extensions["csrn_blueprints"] == ("example",)


