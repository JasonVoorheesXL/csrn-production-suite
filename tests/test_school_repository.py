from __future__ import annotations

from pathlib import Path

import pytest

from persistence_engine import JsonPersistenceEngine
from school_repository import SchoolRepository, SchoolRepositoryValidationError


def engine(tmp_path: Path) -> JsonPersistenceEngine:
    return JsonPersistenceEngine(tmp_path / "backups", tmp_path / "quarantine")


def test_load_accepts_wrapped_legacy_payload_and_normalizes(tmp_path: Path) -> None:
    path = tmp_path / "schools.json"
    path.write_text('{"schools":[{"id":"caledonia","official_name":"Caledonia High School"}]}', encoding="utf-8")

    def normalize_school(school, schools):
        school.setdefault("active", True)
        return school

    repository = SchoolRepository(engine(tmp_path), path, school_normalizer=normalize_school)
    schools = repository.load()

    assert schools == [{"id": "caledonia", "official_name": "Caledonia High School", "active": True}]
    assert path.read_text(encoding="utf-8").lstrip().startswith("[")


def test_collection_normalizer_is_persisted(tmp_path: Path) -> None:
    path = tmp_path / "schools.json"
    path.write_text('[{"id":"b"},{"id":"a"}]', encoding="utf-8")

    def sort_schools(schools):
        before = [item["id"] for item in schools]
        schools.sort(key=lambda item: item["id"])
        return before != [item["id"] for item in schools]

    repository = SchoolRepository(engine(tmp_path), path, collection_normalizer=sort_schools)
    assert [item["id"] for item in repository.load()] == ["a", "b"]
    assert path.read_text(encoding="utf-8").find('"a"') < path.read_text(encoding="utf-8").find('"b"')


def test_save_rejects_duplicate_nonempty_ids(tmp_path: Path) -> None:
    repository = SchoolRepository(engine(tmp_path), tmp_path / "schools.json")
    with pytest.raises(SchoolRepositoryValidationError):
        repository.save([{"id": "same"}, {"id": "same"}])


def test_get_returns_copy(tmp_path: Path) -> None:
    repository = SchoolRepository(engine(tmp_path), tmp_path / "schools.json")
    repository.save([{"id": "caledonia", "official_name": "Caledonia"}])
    school = repository.get("caledonia")
    assert school is not None
    school["official_name"] = "Changed"
    assert repository.get("caledonia")["official_name"] == "Caledonia"


def test_invalid_payload_is_recovered_or_defaulted(tmp_path: Path) -> None:
    path = tmp_path / "schools.json"
    path.write_text('{"schools":"not-a-list"}', encoding="utf-8")
    repository = SchoolRepository(engine(tmp_path), path)
    assert repository.load() == []


