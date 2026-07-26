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


def test_social_post_repository_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "social_posts.json"
    repository = SocialPostRepository(JsonPersistenceEngine(), path)
    repository.save([post()])
    assert repository.load() == [post()]
    assert repository.get("social-1") == post()


def test_social_post_repository_accepts_legacy_wrapper(tmp_path: Path) -> None:
    path = tmp_path / "social_posts.json"
    path.write_text(json.dumps({"posts": [post()]}), encoding="utf-8")
    repository = SocialPostRepository(JsonPersistenceEngine(), path)
    assert repository.load() == [post()]
    assert json.loads(path.read_text(encoding="utf-8")) == [post()]


def test_social_post_repository_rejects_duplicate_ids(tmp_path: Path) -> None:
    repository = SocialPostRepository(
        JsonPersistenceEngine(),
        tmp_path / "social_posts.json",
    )
    with pytest.raises(SocialPostRepositoryValidationError):
        repository.save([post(), post()])


def test_social_post_repository_rejects_invalid_status(tmp_path: Path) -> None:
    repository = SocialPostRepository(
        JsonPersistenceEngine(),
        tmp_path / "social_posts.json",
    )
    with pytest.raises(SocialPostRepositoryValidationError):
        repository.save([post(status="unknown")])
