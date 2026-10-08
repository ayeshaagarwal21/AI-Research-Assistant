from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter


def create_chunks(
    pages: List[dict], chunk_size: int = 1000, chunk_overlap: int = 200
) -> List[dict]:
    """Split page texts into overlapping chunks.

    Input : [{'source', 'page', 'text'}, ...]
    Output: [{'text', 'source', 'page'}, ...]  - each chunk remembers where it came from,
            which is what makes source citations possible later.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )

    chunks = []
    for page in pages:
        for piece in splitter.split_text(page["text"]):
            chunks.append(
                {"text": piece, "source": page["source"], "page": page["page"]}
            )
    return chunks
