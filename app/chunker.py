# app/chunker.py
import io
import pdfplumber
import re
from typing import Dict, Generator, Tuple

def extract_pages_from_pdf_bytes(pdf_bytes: bytes) -> Dict[int, str]:
    """
    Extract all pages from PDF using pdfplumber (better for code extraction).
    Returns dict: page_number (1-based) -> text
    """
    pages = {}
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                # Use layout=True for better structure preservation (especially for code)
                text = page.extract_text(layout=True) or ""
                # Normalize whitespace for embeddings (but preserve structure)
                text = re.sub(r"[ \t]+", " ", text)  # Normalize spaces/tabs
                text = re.sub(r"\n\s*\n", "\n", text)  # Remove excessive blank lines
                text = re.sub(r"\s+", " ", text).strip()  # Final normalization
                pages[i + 1] = text
    except Exception as e:
        # Fallback to pypdf if pdfplumber fails
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(pdf_bytes))
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                text = re.sub(r"\s+", " ", text).strip()
                pages[i + 1] = text
        except Exception as fallback_error:
            raise Exception(f"PDF extraction failed with both pdfplumber and pypdf: {e}, {fallback_error}")
    return pages

def extract_pages_streaming(pdf_bytes: bytes) -> Generator[Tuple[int, str], None, None]:
    """
    Stream pages from PDF one at a time to avoid loading all pages into memory.
    Uses pdfplumber for better code extraction.
    Yields (page_number, page_text) tuples.
    """
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                # Use layout=True for better structure preservation (especially for code)
                text = page.extract_text(layout=True) or ""
                # Normalize whitespace for embeddings (but preserve structure)
                text = re.sub(r"[ \t]+", " ", text)  # Normalize spaces/tabs
                text = re.sub(r"\n\s*\n", "\n", text)  # Remove excessive blank lines
                text = re.sub(r"\s+", " ", text).strip()  # Final normalization
                yield (i + 1, text)  # page_number is 1-based
    except Exception as e:
        # Fallback to pypdf if pdfplumber fails
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(pdf_bytes))
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                text = re.sub(r"\s+", " ", text).strip()
                yield (i + 1, text)
        except Exception as fallback_error:
            raise Exception(f"PDF extraction failed with both pdfplumber and pypdf: {e}, {fallback_error}")

def get_pdf_page_count(pdf_bytes: bytes) -> int:
    """Get total number of pages in PDF without extracting text."""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return len(pdf.pages)
    except Exception as e:
        # Fallback to pypdf if pdfplumber fails
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(pdf_bytes))
            return len(reader.pages)
        except Exception as fallback_error:
            raise Exception(f"PDF page count failed with both pdfplumber and pypdf: {e}, {fallback_error}")

def split_into_sentences(text: str):
    # naive sentence splitter
    sentences = re.split(r'(?<=[.?!])\s+', text)
    return [s.strip() for s in sentences if s.strip()]

def chunks_from_page(page_text: str, page_number: int, start_chunk_idx: int = 0, max_tokens: int = 500, overlap: int = 50):
    """
    Chunk a single page of text. Returns list of chunks.
    start_chunk_idx: Starting chunk index (for maintaining global chunk numbering across pages)
    """
    if not page_text or not page_text.strip():
        return []
    
    if overlap >= max_tokens:
        raise ValueError(f"Overlap ({overlap}) must be less than max_tokens ({max_tokens})")
    
    chunks = []
    chunk_idx = start_chunk_idx
    sents = split_into_sentences(page_text)
    i = 0
    
    while i < len(sents):
        chunk_sentences = []
        token_count = 0
        while i < len(sents) and token_count < max_tokens:
            sent_words = len(sents[i].split())
            chunk_sentences.append(sents[i])
            token_count += sent_words
            i += 1
        
        chunk_text = " ".join(chunk_sentences).strip()
        if chunk_text:
            chunks.append({
                "page_number": page_number,
                "chunk_index": chunk_idx,
                "text": chunk_text,
                "tokens": token_count
            })
            chunk_idx += 1
        
        # Backtrack for overlap
        back_words = overlap
        original_i = i
        while back_words > 0 and i > 0:
            i -= 1
            back_words -= len(sents[i].split())
            if i == 0 and back_words > 0:
                break
        
        # Ensure forward progress
        if i < original_i - len(chunk_sentences) // 2:
            i = original_i - len(chunk_sentences) // 2
        if i < 0:
            i = 0
    
    return chunks

def chunks_from_pages(pages: Dict[int,str], max_tokens:int=500, overlap:int=50):
    # approximate tokens by words count (simple)
    if not pages:
        return []
    
    if overlap >= max_tokens:
        raise ValueError(f"Overlap ({overlap}) must be less than max_tokens ({max_tokens})")
    
    all_chunks = []
    chunk_idx = 0
    for page_no in sorted(pages.keys()):
        text = pages[page_no]
        sents = split_into_sentences(text)
        i = 0
        while i < len(sents):
            chunk_sentences = []
            token_count = 0
            while i < len(sents) and token_count < max_tokens:
                sent_words = len(sents[i].split())
                chunk_sentences.append(sents[i])
                token_count += sent_words
                i += 1
            chunk_text = " ".join(chunk_sentences).strip()
            if chunk_text:
                all_chunks.append({
                    "page_number": page_no,
                    "chunk_index": chunk_idx,
                    "text": chunk_text,
                    "tokens": token_count
                })
                chunk_idx += 1
            # backtrack for overlap: move i back by approx overlap words (in sentences)
            # simple approach: step back by `overlap` words worth of sentences
            # convert overlap words to sentences estimate:
            back_words = overlap
            original_i = i  # Track original position to prevent infinite loops
            while back_words > 0 and i > 0:
                i -= 1
                back_words -= len(sents[i].split())
                # Safety check: prevent infinite loop if we can't make progress
                if i == 0 and back_words > 0:
                    break
            # ensure forward progress - don't go backwards more than half the chunk
            if i < original_i - len(chunk_sentences) // 2:
                i = original_i - len(chunk_sentences) // 2
            if i < 0:
                i = 0
    return all_chunks
