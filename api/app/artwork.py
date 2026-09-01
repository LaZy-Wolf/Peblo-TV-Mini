import hashlib
import io
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

from app.errors import ApiError, ApiException
from app.reference import ArtworkSpec, reference

ASPECT_TOLERANCE = 0.01
DIMENSION_TOLERANCE = 0.10

_CONTENT_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


@dataclass(frozen=True)
class ArtworkMeta:
    width: int
    height: int
    bytes: int
    checksum: str
    content_type: str


def _orientation(width: int, height: int) -> str:
    if width > height:
        return "landscape"
    if height > width:
        return "portrait"
    return "square"


def _aspect_message(spec: ArtworkSpec, width: int, height: int) -> str:
    want = _orientation(spec.target_w, spec.target_h)
    got = _orientation(width, height)
    message = (
        f"Your {spec.kind} is {width} by {height} pixels ({got}). "
        f"{spec.kind.capitalize()}s need to be {want}, "
        f"about {spec.target_w} by {spec.target_h}."
    )
    if {got, want} == {"portrait", "landscape"}:
        message += " It looks like this image is rotated. Try the other orientation."
    return message


def _dimension_message(spec: ArtworkSpec, width: int, height: int) -> str:
    if width < spec.target_w:
        problem = "too small to look sharp on a TV"
    else:
        problem = "larger than we need"
    return (
        f"This {spec.kind} is {width} by {height} pixels, which is {problem}. "
        f"Please export it at about {spec.target_w} by {spec.target_h}."
    )


def validate_artwork(kind: str, data: bytes) -> ArtworkMeta:
    """Validate an uploaded image against its slot's spec.

    Raises ApiException(422) carrying every problem at once, so an editor
    fixes the image once rather than three times.
    """
    ref = reference()
    if kind not in ref.artwork_specs:
        raise ApiException(
            422,
            [
                ApiError(
                    "artwork_unknown_kind",
                    f"'{kind}' is not an artwork slot. "
                    f"Choose one of: {', '.join(sorted(ref.artwork_specs))}.",
                    "kind",
                )
            ],
        )
    spec = ref.artwork_specs[kind]

    try:
        Image.open(io.BytesIO(data)).verify()
        image = Image.open(io.BytesIO(data))
        width, height = image.size
        image_format = (image.format or "").upper()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ApiException(
            422,
            [
                ApiError(
                    "artwork_not_an_image",
                    "We could not read that file as an image. "
                    "Please upload a JPG, PNG or WebP.",
                    "file",
                )
            ],
        ) from exc

    errors: list[ApiError] = []

    wrong_aspect = abs((width / height) - spec.aspect) / spec.aspect > ASPECT_TOLERANCE
    if wrong_aspect:
        errors.append(
            ApiError("artwork_wrong_aspect", _aspect_message(spec, width, height), "file")
        )

    # Only report size once the shape is right. On a rotated image the size
    # message is derived noise ("larger than we need" for something that is
    # also too short), and the aspect message already names the target size.
    if not wrong_aspect:
        width_off = abs(width - spec.target_w) / spec.target_w > DIMENSION_TOLERANCE
        height_off = abs(height - spec.target_h) / spec.target_h > DIMENSION_TOLERANCE
        if width_off or height_off:
            errors.append(
                ApiError(
                    "artwork_wrong_dimensions", _dimension_message(spec, width, height), "file"
                )
            )

    size_kb = len(data) / 1024
    if size_kb > spec.max_kb:
        errors.append(
            ApiError(
                "artwork_too_large",
                f"This file is {size_kb:.0f} KB. Artwork needs to be under {spec.max_kb} KB "
                "so pages load quickly for children on slow connections. "
                "Try exporting as JPEG at 80% quality.",
                "file",
            )
        )

    if errors:
        raise ApiException(422, errors)

    return ArtworkMeta(
        width=width,
        height=height,
        bytes=len(data),
        checksum=hashlib.sha256(data).hexdigest(),
        content_type=_CONTENT_TYPES.get(image_format, "application/octet-stream"),
    )
