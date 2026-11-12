import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.entities import AuditLog, MediaAsset, User
from app.services.authorization import require_dependent_access

router = APIRouter(tags=["private media"])


@router.get("/dependents/{dependent_id}/media")
def list_media(dependent_id: uuid.UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict[str, object]]:
    require_dependent_access(db, current, dependent_id, "media")
    items = db.scalars(select(MediaAsset).where(MediaAsset.dependent_id == dependent_id).order_by(MediaAsset.created_at.desc())).all()
    return [{"id": str(item.id), "filename": item.original_filename, "content_type": item.content_type,
             "size_bytes": item.size_bytes, "category": item.category, "created_at": item.created_at.isoformat()} for item in items]


def _safe_original_name(filename: str | None) -> str:
    name = Path(filename or "upload").name.replace("\\", "_").replace("/", "_")
    cleaned = "".join(character for character in name if character.isalnum() or character in " ._-()")
    return cleaned[:240] or "upload"


def _signature_ok(content_type: str, data: bytes) -> bool:
    if content_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if content_type == "audio/wav":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    if content_type == "audio/ogg":
        return data.startswith(b"OggS")
    if content_type == "audio/mpeg":
        return data.startswith(b"ID3") or (len(data) > 1 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0)
    if content_type == "audio/webm":
        return data.startswith(b"\x1aE\xdf\xa3")
    return False


@router.post("/dependents/{dependent_id}/media", status_code=201)
async def upload_media(
    dependent_id: uuid.UUID,
    file: UploadFile = File(...),
    category: str = Form(default="photo"),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    require_dependent_access(db, current, dependent_id, "media")
    content_type = (file.content_type or "").lower()
    allowed = settings.image_type_set | settings.audio_type_set
    if content_type not in allowed:
        raise HTTPException(status_code=415, detail="This media type is not allowed")
    data = await file.read(settings.max_upload_bytes + 1)
    if not data:
        raise HTTPException(status_code=422, detail="The uploaded file is empty")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="The uploaded file exceeds the configured size limit")
    if not _signature_ok(content_type, data):
        raise HTTPException(status_code=415, detail="The file content does not match the declared media type")
    storage_key = uuid.uuid4().hex
    storage_root = settings.storage_root.resolve()
    storage_root.mkdir(parents=True, exist_ok=True)
    destination = storage_root / storage_key
    with destination.open("xb") as stream:
        stream.write(data)
    asset = MediaAsset(dependent_id=dependent_id, uploaded_by=current.id, storage_key=storage_key,
                       original_filename=_safe_original_name(file.filename), content_type=content_type,
                       size_bytes=len(data), category=category[:32])
    try:
        db.add(asset)
        db.flush()
        db.add(AuditLog(actor_id=current.id, action="media.upload", resource_type="media_asset", resource_id=str(asset.id), dependent_id=dependent_id))
        db.commit()
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise
    db.refresh(asset)
    return {"id": str(asset.id), "filename": asset.original_filename, "content_type": asset.content_type,
            "size_bytes": asset.size_bytes, "sha256": hashlib.sha256(data).hexdigest()}


@router.get("/media/{asset_id}/content")
def read_media(asset_id: uuid.UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> FileResponse:
    asset = db.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Media not found")
    require_dependent_access(db, current, asset.dependent_id, "media")
    path = settings.storage_root.resolve() / asset.storage_key
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Media content is unavailable")
    db.add(AuditLog(actor_id=current.id, action="media.read", resource_type="media_asset", resource_id=str(asset.id), dependent_id=asset.dependent_id))
    db.commit()
    return FileResponse(path, media_type=asset.content_type, filename=asset.original_filename, content_disposition_type="inline")


@router.delete("/media/{asset_id}", status_code=204)
def delete_media(asset_id: uuid.UUID, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    asset = db.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Media not found")
    require_dependent_access(db, current, asset.dependent_id, "media")
    if current.id not in {asset.uploaded_by, asset.dependent_id}:
        raise HTTPException(status_code=403, detail="Only the uploader or dependent can remove this file")
    path = settings.storage_root.resolve() / asset.storage_key
    db.add(AuditLog(actor_id=current.id, action="media.delete", resource_type="media_asset", resource_id=str(asset.id), dependent_id=asset.dependent_id))
    db.delete(asset)
    db.commit()
    path.unlink(missing_ok=True)
    return Response(status_code=204)
