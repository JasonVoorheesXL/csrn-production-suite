from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"


FACTORY_BLOCK = '''def create_app(
    config_overrides: dict[str, Any] | None = None,
) -> Flask:
    """Build a configured CSRN application from the consolidated Blueprints."""

    security = load_security()
    return create_application(
        __name__,
        blueprints=tuple(APPLICATION_BLUEPRINTS),
        secret_key=str(security["secret_key"]),
        session_seconds=SESSION_SECONDS,
        config_overrides=config_overrides,
    )


app = create_app()


'''


def apply(path: Path = APP_FILE) -> bool:
    text = path.read_text(encoding="utf-8")
    if "app = create_app()" in text:
        return False

    old_flask_import = (
        "from flask import Flask, jsonify, render_template, request, session, "
        "send_from_directory, Response\n"
    )
    if old_flask_import not in text:
        raise RuntimeError("Legacy Flask import marker was not found.")
    text = text.replace(
        old_flask_import,
        "from flask import Flask, current_app, jsonify, session\n"
        "from application_factory import create_application\n",
        1,
    )

    app_marker = "app = Flask(__name__)\n"
    if app_marker not in text:
        raise RuntimeError("Legacy Flask construction marker was not found.")
    text = text.replace(
        app_marker,
        "APPLICATION_BLUEPRINTS: list[Any] = []\n",
        1,
    )

    security_block = '''security = load_security()
app.secret_key = security["secret_key"]
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
    SESSION_COOKIE_SECURE=False,
    PERMANENT_SESSION_LIFETIME=SESSION_SECONDS,
)

'''
    if security_block not in text:
        raise RuntimeError("Legacy application configuration block was not found.")
    text = text.replace(security_block, "", 1)

    auth_marker = '''        return func(*args, **kwargs)
    return wrapper
'''
    if auth_marker not in text:
        raise RuntimeError("Authentication wrapper marker was not found.")
    text = text.replace(
        auth_marker,
        '''        return func(*args, **kwargs)
    setattr(wrapper, "_csrn_requires_auth", True)
    return wrapper
''',
        1,
    )

    registration_count = text.count("app.register_blueprint(")
    if registration_count != 18:
        raise RuntimeError(
            f"Expected 18 Blueprint registrations, found {registration_count}."
        )
    text = text.replace(
        "app.register_blueprint(",
        "APPLICATION_BLUEPRINTS.append(",
    )

    secret_marker = "    app.secret_key = secret_key\n"
    if secret_marker not in text:
        raise RuntimeError("Upgrade secret-key marker was not found.")
    text = text.replace(
        secret_marker,
        "    current_app.secret_key = secret_key\n",
        1,
    )

    startup_marker = 'if __name__ == "__main__":\n'
    if startup_marker not in text:
        raise RuntimeError("Application startup marker was not found.")
    text = text.replace(startup_marker, FACTORY_BLOCK + startup_marker, 1)

    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    changed = apply()
    if changed:
        print("Phase 5.10 application factory integration applied.")
    else:
        print("Phase 5.10 application factory integration was already present.")


if __name__ == "__main__":
    main()
