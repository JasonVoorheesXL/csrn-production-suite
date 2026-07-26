from __future__ import annotations

import json
from pathlib import Path

import pytest

from persistence_engine import JsonPersistenceEngine
from social_post_repository import (
    SocialPostRepository,
    SocialPostRepositoryValidationError,
)


def post(post_id: str = "social-1", status: str = "draft") -> dict:
    return {
        "id": post_id,
        "status": status,
        "platforms": ["x", "facebook"],
        "attempts": [],
    }


def repository(tmp_path: Path) -> SocialPostRepository:
    return SocialPostRepository(
        JsonPersistenceEngine(tmp_path / "backups"),
        tmp_path / "social_posts.json",
    )


def test_social_post_repository_round_trip(tmp_path: Path) -> None:
    storage = repository(tmp_path)
    storage.save([post()])
    assert storage.load() == [post()]
    assert storage.get("social-1") == post()


def test_social_post_repository_accepts_legacy_wrapper(tmp_path: Path) -> None:
    path = tmp_path / "social_posts.json"
    path.write_text(json.dumps({"posts": [post()]}), encoding="utf-8")
    storage = repository(tmp_path)
    assert storage.load() == [post()]
    assert json.loads(path.read_text(encoding="utf-8")) == [post()]


def test_social_post_repository_rejects_duplicate_ids(tmp_path: Path) -> None:
    storage = repository(tmp_path)
    with pytest.raises(SocialPostRepositoryValidationError):
        storage.save([post(), post()])


def test_social_post_repository_rejects_invalid_status(tmp_path: Path) -> None:
    storage = repository(tmp_path)
    with pytest.raises(SocialPostRepositoryValidationError):
        storage.save([post(status="unknown")])
