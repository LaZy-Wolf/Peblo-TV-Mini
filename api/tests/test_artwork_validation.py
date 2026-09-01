import io
from pathlib import Path

import pytest
from PIL import Image

from app.artwork import validate_artwork
from app.config import settings
from app.errors import ApiException

ASSETS = Path(settings.data_dir) / "assets"


def _read(name: str) -> bytes:
    return (ASSETS / name).read_bytes()


def _codes(exc: ApiException) -> set[str]:
    return {e.code for e in exc.errors}


def _noisy_png(width: int, height: int) -> bytes:
    """Noise does not compress, which is how we get a file over the ceiling."""
    buffer = io.BytesIO()
    Image.effect_noise((width, height), 120).convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def test_good_poster_is_accepted():
    meta = validate_artwork("poster", _read("poster_good.jpg"))
    assert (meta.width, meta.height) == (600, 900)
    assert meta.content_type == "image/jpeg"
    assert len(meta.checksum) == 64


def test_good_banner_is_accepted():
    meta = validate_artwork("banner", _read("banner_good.jpg"))
    assert (meta.width, meta.height) == (1280, 720)


def test_good_thumbnail_is_accepted():
    meta = validate_artwork("thumbnail", _read("thumb_good.jpg"))
    assert (meta.width, meta.height) == (640, 360)


def test_rotated_poster_is_rejected_on_aspect():
    with pytest.raises(ApiException) as exc:
        validate_artwork("poster", _read("poster_wrong_ratio.jpg"))
    assert "artwork_wrong_aspect" in _codes(exc.value)
    assert "rotated" in exc.value.errors[0].message


def test_oversized_banner_is_rejected_on_dimensions_not_bytes():
    """banner_too_big.png is 2560x1440 at 13.8 KB.

    It passes the byte ceiling comfortably, so a validator that only weighed
    files would wave it straight through.
    """
    with pytest.raises(ApiException) as exc:
        validate_artwork("banner", _read("banner_too_big.png"))
    codes = _codes(exc.value)
    assert "artwork_wrong_dimensions" in codes
    assert "artwork_too_large" not in codes


def test_tiny_thumbnail_is_rejected_on_dimensions():
    with pytest.raises(ApiException) as exc:
        validate_artwork("thumbnail", _read("thumb_tiny.jpg"))
    assert "artwork_wrong_dimensions" in _codes(exc.value)


def test_file_over_200kb_is_rejected():
    """No supplied asset reaches the ceiling, so the fixture is generated.

    Without this the 200 KB rule would ship having never once executed.
    """
    data = _noisy_png(600, 900)
    assert len(data) > 200 * 1024, "fixture must actually exceed the ceiling"
    with pytest.raises(ApiException) as exc:
        validate_artwork("poster", data)
    assert "artwork_too_large" in _codes(exc.value)


def test_non_image_is_rejected():
    with pytest.raises(ApiException) as exc:
        validate_artwork("poster", b"this is not an image")
    assert "artwork_not_an_image" in _codes(exc.value)


def test_unknown_kind_is_rejected():
    with pytest.raises(ApiException) as exc:
        validate_artwork("billboard", _read("poster_good.jpg"))
    assert "artwork_unknown_kind" in _codes(exc.value)


def test_all_problems_are_returned_together():
    """An editor should fix the image once, not three times.

    Correct 2:3 shape, but far too large and far too heavy, so both
    independent problems must arrive in one response.
    """
    with pytest.raises(ApiException) as exc:
        validate_artwork("poster", _noisy_png(1200, 1800))
    assert _codes(exc.value) == {"artwork_wrong_dimensions", "artwork_too_large"}


def test_a_rotated_image_reports_shape_only():
    """The size message on a rotated image is derived noise: it would say
    'larger than we need' about something that is also too short. The aspect
    message already names the target size."""
    with pytest.raises(ApiException) as exc:
        validate_artwork("poster", _read("poster_wrong_ratio.jpg"))
    assert _codes(exc.value) == {"artwork_wrong_aspect"}


def test_messages_are_written_for_a_non_technical_editor():
    with pytest.raises(ApiException) as exc:
        validate_artwork("thumbnail", _read("thumb_tiny.jpg"))
    message = exc.value.errors[0].message
    assert "—" not in message
    assert "aspect" not in message.lower()
    assert "640" in message and "360" in message


def test_within_ten_percent_of_target_is_accepted():
    """The spec says 'about' these sizes, so a small deviation is fine."""
    buffer = io.BytesIO()
    Image.new("RGB", (620, 930), "white").save(buffer, format="JPEG")
    meta = validate_artwork("poster", buffer.getvalue())
    assert (meta.width, meta.height) == (620, 930)
