import os
from collections import Counter
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile

from backend.app.core import config
from backend.app.core.dependencies import get_current_user
from backend.app.schemas.chat import DocumentInfo
from utils.chunking import create_chunks
from utils.embeddings import create_embeddings, load_embedding_model
from utils.pdf_reader import PDFReadError, extract_pdf_pages
from utils.vector_store import (
    add_documents,
    clear_store,
    list_documents,
    remove_document,
)

router = APIRouter(tags=["documents"])


def _safe_name(filename: str) -> str:
    return os.path.basename((filename or "document.pdf").replace("\\", "/"))


def _size_bytes(file_obj) -> int:
    file_obj.seek(0, os.SEEK_END)
    size = file_obj.tell()
    file_obj.seek(0)
    return size


@router.post("/upload")
def upload_documents(
    files: List[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Process PDFs and add them to the user's own searchable store.

    Plain `def` (not `async def`): embedding is CPU-heavy, and FastAPI runs sync
    endpoints in a worker thread so the server stays responsive meanwhile.
    """
    user_id = current_user["id"]
    max_bytes = config.MAX_UPLOAD_MB * 1024 * 1024

    pages, skipped, seen = [], [], set()
    for upload in files:
        name = _safe_name(upload.filename)

        if name in seen:
            skipped.append({"filename": name, "reason": "Duplicate file name in this upload"})
            continue
        seen.add(name)

        if not name.lower().endswith(".pdf"):
            skipped.append({"filename": name, "reason": "Not a PDF file"})
            continue
        if _size_bytes(upload.file) > max_bytes:
            skipped.append(
                {"filename": name, "reason": f"Larger than {config.MAX_UPLOAD_MB} MB"}
            )
            continue

        try:
            pages.extend(extract_pdf_pages(upload.file, name))
        except PDFReadError as exc:
            skipped.append({"filename": name, "reason": str(exc)})

    if not pages:
        details = "; ".join(f"{s['filename']} ({s['reason']})" for s in skipped)
        raise HTTPException(
            status_code=422, detail=f"No documents could be processed: {details}"
        )

    chunks = create_chunks(pages)
    embeddings = create_embeddings(load_embedding_model(), [c["text"] for c in chunks])
    total_vectors = add_documents(user_id, embeddings, chunks, new_pages=pages)

    per_file = Counter(c["source"] for c in chunks)
    return {
        "message": "Documents processed successfully",
        "files": [{"filename": n, "chunks": c} for n, c in per_file.items()],
        "skipped": skipped,
        "characters": sum(len(p["text"]) for p in pages),
        "chunks": len(chunks),
        "vectors": total_vectors,
    }


@router.get("/documents", response_model=List[DocumentInfo])
def get_documents(current_user: dict = Depends(get_current_user)):
    return list_documents(current_user["id"])


@router.delete("/documents", status_code=204)
def delete_documents(
    filename: str = Query(None, description="Remove just this file; omit to remove all"),
    current_user: dict = Depends(get_current_user),
):
    if filename is None:
        clear_store(current_user["id"])
    elif remove_document(current_user["id"], filename) == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return Response(status_code=204)
