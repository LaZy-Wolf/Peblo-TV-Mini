from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.artwork import validate_artwork
from app.auth import require_editor
from app.db import get_session
from app.errors import ApiError, ApiException
from app.models import Artwork, Episode, Show, User
from app.storage import get_storage

router = APIRouter(prefix="/admin/artwork", tags=["artwork"])

_EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


@router.post("", status_code=201)
async def upload_artwork(
    kind: str = Form(...),
    show_id: int | None = Form(None),
    episode_id: int | None = Form(None),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> dict:
    if (show_id is None) == (episode_id is None):
        raise ApiException(
            422,
            [
                ApiError(
                    "artwork_missing_owner",
                    "Choose whether this image belongs to a show or to an episode.",
                )
            ],
        )

    owner = session.get(Show, show_id) if show_id else session.get(Episode, episode_id)
    if owner is None:
        raise ApiException(
            404,
            [ApiError("not_found", "We could not find the show or episode for this image.")],
        )

    data = await file.read()
    # Validation runs before storage is touched, so a rejected upload never
    # leaves an orphan file behind.
    meta = validate_artwork(kind, data)

    folder = f"shows/{show_id}" if show_id else f"episodes/{episode_id}"
    extension = _EXTENSIONS[meta.content_type]
    key = f"artwork/{folder}/{kind}-{meta.checksum[:12]}.{extension}"
    url = get_storage().put(key, data, meta.content_type)

    # Re-uploading a corrected image is the common case, so replace rather
    # than making the editor delete first.
    existing = session.scalar(
        select(Artwork).where(
            Artwork.kind == kind,
            Artwork.show_id == show_id,
            Artwork.episode_id == episode_id,
        )
    )
    if existing is not None:
        session.delete(existing)
        session.flush()

    record = Artwork(
        show_id=show_id,
        episode_id=episode_id,
        kind=kind,
        storage_key=key,
        width=meta.width,
        height=meta.height,
        bytes=meta.bytes,
        checksum=meta.checksum,
    )
    session.add(record)
    session.flush()
    return {
        "id": record.id,
        "kind": kind,
        "url": url,
        "width": meta.width,
        "height": meta.height,
        "bytes": meta.bytes,
    }


@router.delete("/{artwork_id}", status_code=204)
def delete_artwork(
    artwork_id: int,
    session: Session = Depends(get_session),
    _: User = Depends(require_editor),
) -> None:
    record = session.get(Artwork, artwork_id)
    if record is None:
        raise ApiException(404, [ApiError("not_found", "That image no longer exists.")])
    get_storage().delete(record.storage_key)
    session.delete(record)
    session.flush()
