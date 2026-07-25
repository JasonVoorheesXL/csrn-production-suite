from __future__ import annotations

import copy
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from PIL import Image, ImageChops, ImageDraw


Record = dict[str, Any]
SchoolLoader = Callable[[], list[Record]]
SchoolSaver = Callable[[list[Record]], None]
LogoLoader = Callable[[], list[Record]]
LogoSaver = Callable[[list[Record]], None]
IdNormalizer = Callable[[str], str]
OriginalWriter = Callable[[str, bytes], str]
ImageWriter = Callable[[Image.Image], str]


@dataclass(frozen=True)
class LogoResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class LogoService:
    """School-logo processing and catalog behavior independent of Flask."""

    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

    def __init__(
        self,
        *,
        load_schools: SchoolLoader,
        save_schools: SchoolSaver,
        load_logos: LogoLoader,
        save_logos: LogoSaver,
        normalize_school_id: IdNormalizer,
    ) -> None:
        self._load_schools = load_schools
        self._save_schools = save_schools
        self._load_logos = load_logos
        self._save_logos = save_logos
        self._normalize_school_id = normalize_school_id

    @classmethod
    def safe_extension(cls, filename: Any) -> str:
        extension = Path(str(filename or "")).suffix.lower()
        return extension if extension in cls.IMAGE_EXTENSIONS else ".png"

    @staticmethod
    def decode_image(raw: bytes) -> Image.Image:
        if not isinstance(raw, (bytes, bytearray)) or not raw:
            raise ValueError("Image payload is empty.")
        try:
            image = Image.open(io.BytesIO(bytes(raw)))
            image.load()
        except Exception as exc:  # Pillow raises several format-specific errors.
            raise ValueError("Image payload is invalid.") from exc
        return image

    @staticmethod
    def _hex(rgb: tuple[int, int, int]) -> str:
        return "#%02X%02X%02X" % rgb

    @classmethod
    def extract_colors(cls, image: Image.Image) -> list[str]:
        rgba = image.convert("RGBA")
        sample = rgba.copy()
        sample.thumbnail((240, 240))

        chromatic: list[tuple[int, int, int]] = []
        white_count = 0
        black_count = 0
        visible = 0

        for r, g, b, a in sample.getdata():
            if a < 64:
                continue
            visible += 1
            maximum = max(r, g, b)
            minimum = min(r, g, b)
            saturation = maximum - minimum
            if r >= 238 and g >= 238 and b >= 238:
                white_count += 1
                continue
            if r <= 28 and g <= 28 and b <= 28:
                black_count += 1
                continue
            if saturation < 16 and 45 < maximum < 225:
                continue
            chromatic.append((r, g, b))

        ranked: list[tuple[int, int, int]] = []
        if chromatic:
            strip = Image.new("RGB", (len(chromatic), 1))
            strip.putdata(chromatic)
            quantized = strip.quantize(
                colors=10,
                method=Image.Quantize.MEDIANCUT,
            ).convert("RGB")
            counts = quantized.getcolors(maxcolors=256) or []
            ranked = [rgb for _, rgb in sorted(counts, reverse=True)]

        chosen: list[tuple[int, int, int]] = []
        for rgb in ranked:
            if all(
                sum((rgb[index] - other[index]) ** 2 for index in range(3))
                > 2600
                for other in chosen
            ):
                chosen.append(rgb)
            if len(chosen) == 2:
                break

        if not chosen:
            chosen = [(128, 128, 128)]

        neutral = (255, 255, 255) if white_count >= black_count else (0, 0, 0)
        neutral_share = (
            max(white_count, black_count) / visible
            if visible
            else 0
        )
        if neutral_share >= 0.035:
            secondary = neutral
        elif len(chosen) > 1:
            secondary = chosen[1]
        else:
            secondary = (255, 255, 255)

        return [cls._hex(chosen[0]), cls._hex(secondary)]

    @staticmethod
    def normalize_round_logo(source: Image.Image, size: int) -> Image.Image:
        target_size = max(1, int(size))
        image = source.convert("RGBA")
        bounding_box = image.getbbox()
        if bounding_box:
            image = image.crop(bounding_box)

        max_content = int(target_size * 0.92)
        scale = min(
            max_content / max(1, image.width),
            max_content / max(1, image.height),
        )
        resized = (
            max(1, round(image.width * scale)),
            max(1, round(image.height * scale)),
        )
        image = image.resize(resized, Image.Resampling.LANCZOS)

        canvas = Image.new(
            "RGBA",
            (target_size, target_size),
            (0, 0, 0, 0),
        )
        canvas.alpha_composite(
            image,
            (
                (target_size - image.width) // 2,
                (target_size - image.height) // 2,
            ),
        )
        mask = Image.new("L", (target_size, target_size), 0)
        ImageDraw.Draw(mask).ellipse(
            (0, 0, target_size - 1, target_size - 1),
            fill=255,
        )
        canvas.putalpha(ImageChops.multiply(canvas.getchannel("A"), mask))
        return canvas

    def list_records(
        self,
        *,
        school_id: str = "",
        designation: str = "",
        approval_status: str = "",
    ) -> LogoResult:
        target_school = str(school_id or "").strip().lower()
        target_designation = str(designation or "").strip().lower()
        target_status = str(approval_status or "").strip().lower()

        records: list[Record] = []
        for source in self._load_logos():
            record = copy.deepcopy(source)
            if target_school and str(record.get("school_id", "")).strip().lower() != target_school:
                continue
            if target_designation and str(record.get("designation", "")).strip().lower() != target_designation:
                continue
            if target_status and str(record.get("approval_status", "")).strip().lower() != target_status:
                continue
            records.append(record)

        records.sort(
            key=lambda row: (
                str(row.get("school_id", "")).lower(),
                str(row.get("designation", "")).lower(),
                str(row.get("id", "")).lower(),
            )
        )
        return LogoResult("OK", {"logos": records})

    def read(self, logo_id: str) -> LogoResult:
        target = str(logo_id or "").strip()
        record = next(
            (
                copy.deepcopy(item)
                for item in self._load_logos()
                if str(item.get("id", "")).strip() == target
            ),
            None,
        )
        if record is None:
            return LogoResult("LOGO_NOT_FOUND")
        return LogoResult("OK", {"logo": record})

    def process_candidate(
        self,
        school_id: str,
        *,
        raw: bytes,
        original_filename: str,
        write_original: OriginalWriter,
        write_master: ImageWriter,
        write_scorebug: ImageWriter,
    ) -> LogoResult:
        schools = copy.deepcopy(self._load_schools())
        target = str(school_id or "").strip()
        school = next(
            (
                item
                for item in schools
                if str(item.get("id", "")).strip() == target
            ),
            None,
        )
        if school is None:
            return LogoResult("SCHOOL_NOT_FOUND")

        try:
            source = self.decode_image(raw)
        except ValueError:
            return LogoResult("INVALID_IMAGE")

        master = self.normalize_round_logo(source, 1024)
        scorebug = self.normalize_round_logo(source, 256)
        colors = self.extract_colors(master)
        extension = self.safe_extension(original_filename)

        try:
            original_path = str(write_original(extension, bytes(raw)))
            round_master_path = str(write_master(master))
            scorebug_path = str(write_scorebug(scorebug))
        except Exception as exc:
            return LogoResult(
                "LOGO_STORAGE_FAILED",
                {"message": str(exc)},
            )

        normalized_school_id = self._normalize_school_id(target)
        logo_id = f"{school.get('csrn_id') or target}-primary"
        school["primary_logo"] = round_master_path
        school["default_broadcast_logo_id"] = logo_id
        school["logo_status"] = "candidate"
        school["primary_color"] = colors[0]
        school["secondary_color"] = colors[1]
        school.setdefault("logo_metadata", {}).update(
            {
                "original_filename": str(original_filename or ""),
                "original_path": original_path,
                "round_master_path": round_master_path,
                "scorebug_path": scorebug_path,
                "approval_status": "candidate",
                "transparent_background_status": "normalized",
                "shape_standard": "round",
                "master_canvas": "1024x1024-round",
                "safe_area": "circle-92-percent",
                "scorebug_derivative": "256x256-round",
                "extracted_colors": colors,
            }
        )

        logos = copy.deepcopy(self._load_logos())
        record = next(
            (
                item
                for item in logos
                if str(item.get("id", "")).strip() == logo_id
            ),
            None,
        )
        payload = {
            "id": logo_id,
            "school_id": target,
            "csrn_school_id": school.get("csrn_id", ""),
            "designation": "primary",
            "approval_status": "candidate",
            "original_path": original_path,
            "round_master_path": round_master_path,
            "scorebug_path": scorebug_path,
            "extracted_colors": colors,
        }
        if record is None:
            logos.append(copy.deepcopy(payload))
            record = logos[-1]
        else:
            record.update(payload)

        self._save_schools(schools)
        self._save_logos(logos)
        return LogoResult(
            "OK",
            {
                "school": copy.deepcopy(school),
                "logo": copy.deepcopy(record),
                "primary_color": colors[0],
                "secondary_color": colors[1],
                "preview_url": round_master_path,
                "normalized_school_id": normalized_school_id,
                "message": (
                    "Round candidate logo created; review colors and approve "
                    "before broadcast use."
                ),
            },
        )
