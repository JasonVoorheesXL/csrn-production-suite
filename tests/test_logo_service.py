from __future__ import annotations

import copy
import io
from pathlib import Path

from PIL import Image

from logo_service import LogoService


class Store:
    def __init__(self, rows=None) -> None:
        self.rows = copy.deepcopy(rows or [])
        self.saved: list[list[dict]] = []

    def load(self):
        return copy.deepcopy(self.rows)

    def save(self, rows):
        self.rows = copy.deepcopy(rows)
        self.saved.append(copy.deepcopy(rows))


def school() -> dict:
    return {
        "id": "caledonia",
        "csrn_id": "MS-LOW-CAL",
        "official_name": "Caledonia High School",
    }


def logo(logo_id: str = "MS-LOW-CAL-primary") -> dict:
    return {
        "id": logo_id,
        "school_id": "caledonia",
        "designation": "primary",
        "approval_status": "approved",
    }


def service(schools: Store, logos: Store) -> LogoService:
    return LogoService(
        load_schools=schools.load,
        save_schools=schools.save,
        load_logos=logos.load,
        save_logos=logos.save,
        normalize_school_id=lambda value: str(value).strip().lower(),
    )


def image_bytes(color=(220, 20, 60, 255), *, size=(80, 60)) -> bytes:
    image = Image.new("RGBA", size, color)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def writers():
    calls: list[tuple[str, object]] = []

    def original(extension: str, raw: bytes) -> str:
        calls.append(("original", (extension, raw)))
        return f"Data/Logos/caledonia/original{extension}"

    def master(image: Image.Image) -> str:
        calls.append(("master", image.size))
        return "/school-logos/caledonia/round-master.png"

    def scorebug(image: Image.Image) -> str:
        calls.append(("scorebug", image.size))
        return "/school-logos/caledonia/round-scorebug.png"

    return calls, original, master, scorebug


def test_safe_extension_accepts_supported_and_falls_back() -> None:
    assert LogoService.safe_extension("mark.JPEG") == ".jpeg"
    assert LogoService.safe_extension("mark.svg") == ".png"
    assert LogoService.safe_extension("") == ".png"


def test_decode_image_accepts_valid_payload_and_rejects_invalid() -> None:
    decoded = LogoService.decode_image(image_bytes())
    assert decoded.size == (80, 60)

    try:
        LogoService.decode_image(b"not-an-image")
    except ValueError as exc:
        assert "invalid" in str(exc).lower()
    else:
        raise AssertionError("Invalid image payload was accepted.")


def test_normalize_round_logo_creates_requested_canvas_and_circle_alpha() -> None:
    source = Image.new("RGBA", (100, 50), (255, 0, 0, 255))
    normalized = LogoService.normalize_round_logo(source, 256)
    assert normalized.size == (256, 256)
    assert normalized.mode == "RGBA"
    assert normalized.getpixel((0, 0))[3] == 0
    assert normalized.getpixel((128, 128))[3] > 0


def test_extract_colors_prefers_chromatic_primary_and_visible_neutral() -> None:
    image = Image.new("RGBA", (100, 100), (255, 255, 255, 255))
    for x in range(75):
        for y in range(100):
            image.putpixel((x, y), (255, 0, 0, 255))
    colors = LogoService.extract_colors(image)
    assert colors[0] == "#FF0000"
    assert colors[1] == "#FFFFFF"


def test_list_records_filters_and_sorts() -> None:
    records = [
        {
            "id": "z-secondary",
            "school_id": "other",
            "designation": "secondary",
            "approval_status": "candidate",
        },
        logo("b-primary"),
        logo("a-primary"),
    ]
    result = service(Store([school()]), Store(records)).list_records(
        school_id="CALEDONIA",
        designation="PRIMARY",
        approval_status="APPROVED",
    )
    assert [row["id"] for row in result.data["logos"]] == [
        "a-primary",
        "b-primary",
    ]


def test_read_reports_existing_and_missing_records() -> None:
    subject = service(Store([school()]), Store([logo()]))
    assert subject.read("MS-LOW-CAL-primary").ok
    assert subject.read("missing").code == "LOGO_NOT_FOUND"


def test_process_candidate_reports_missing_school_without_writes() -> None:
    school_store = Store([])
    logo_store = Store([])
    calls, original, master, scorebug = writers()
    result = service(school_store, logo_store).process_candidate(
        "missing",
        raw=image_bytes(),
        original_filename="mark.png",
        write_original=original,
        write_master=master,
        write_scorebug=scorebug,
    )
    assert result.code == "SCHOOL_NOT_FOUND"
    assert calls == []
    assert school_store.saved == []
    assert logo_store.saved == []


def test_process_candidate_reports_invalid_image_without_saving() -> None:
    school_store = Store([school()])
    logo_store = Store([])
    calls, original, master, scorebug = writers()
    result = service(school_store, logo_store).process_candidate(
        "caledonia",
        raw=b"broken",
        original_filename="mark.png",
        write_original=original,
        write_master=master,
        write_scorebug=scorebug,
    )
    assert result.code == "INVALID_IMAGE"
    assert calls == []
    assert school_store.saved == []
    assert logo_store.saved == []


def test_process_candidate_updates_school_and_inserts_logo_record() -> None:
    school_store = Store([school()])
    logo_store = Store([])
    calls, original, master, scorebug = writers()
    result = service(school_store, logo_store).process_candidate(
        "caledonia",
        raw=image_bytes(),
        original_filename="mark.png",
        write_original=original,
        write_master=master,
        write_scorebug=scorebug,
    )
    assert result.ok
    assert [name for name, _ in calls] == ["original", "master", "scorebug"]
    assert calls[1][1] == (1024, 1024)
    assert calls[2][1] == (256, 256)
    saved_school = school_store.rows[0]
    assert saved_school["primary_logo"] == "/school-logos/caledonia/round-master.png"
    assert saved_school["default_broadcast_logo_id"] == "MS-LOW-CAL-primary"
    assert saved_school["logo_status"] == "candidate"
    assert saved_school["logo_metadata"]["approval_status"] == "candidate"
    assert logo_store.rows[0]["id"] == "MS-LOW-CAL-primary"
    assert result.data["preview_url"].endswith("round-master.png")


def test_process_candidate_updates_existing_logo_without_losing_extra_fields() -> None:
    current = logo()
    current["review_note"] = "keep"
    school_store = Store([school()])
    logo_store = Store([current])
    _, original, master, scorebug = writers()
    result = service(school_store, logo_store).process_candidate(
        "caledonia",
        raw=image_bytes(),
        original_filename="new.webp",
        write_original=original,
        write_master=master,
        write_scorebug=scorebug,
    )
    assert result.ok
    assert len(logo_store.rows) == 1
    assert logo_store.rows[0]["review_note"] == "keep"
    assert logo_store.rows[0]["approval_status"] == "candidate"


def test_storage_failure_does_not_persist_school_or_logo_changes() -> None:
    school_store = Store([school()])
    logo_store = Store([logo()])

    def fail(_extension: str, _raw: bytes) -> str:
        raise OSError("disk unavailable")

    result = service(school_store, logo_store).process_candidate(
        "caledonia",
        raw=image_bytes(),
        original_filename="mark.png",
        write_original=fail,
        write_master=lambda _image: "master",
        write_scorebug=lambda _image: "scorebug",
    )
    assert result.code == "LOGO_STORAGE_FAILED"
    assert school_store.saved == []
    assert logo_store.saved == []
