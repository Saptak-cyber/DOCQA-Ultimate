# app/chunker.py
import io
import pdfplumber
import re
from typing import Dict, Generator, Tuple, Union

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

def extract_pages_streaming(pdf_source: Union[str, bytes]) -> Generator[Tuple[int, str], None, None]:
    """
    Stream pages from PDF one at a time to avoid loading all pages into memory.
    Uses pdfplumber for better code extraction.
    
    Args:
        pdf_source: Either a file path (str) or PDF bytes (bytes)
    
    Yields (page_number, page_text) tuples.
    """
    try:
        # Support both file paths and bytes
        if isinstance(pdf_source, str):
            pdf_context = pdfplumber.open(pdf_source)
        else:
            pdf_context = pdfplumber.open(io.BytesIO(pdf_source))
        
        with pdf_context as pdf:
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
            if isinstance(pdf_source, str):
                reader = PdfReader(pdf_source)
            else:
                reader = PdfReader(io.BytesIO(pdf_source))
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                text = re.sub(r"\s+", " ", text).strip()
                yield (i + 1, text)
        except Exception as fallback_error:
            raise Exception(f"PDF extraction failed with both pdfplumber and pypdf: {e}, {fallback_error}")

def get_pdf_page_count(pdf_source: Union[str, bytes]) -> int:
    """
    Get total number of pages in PDF without extracting text.
    
    Args:
        pdf_source: Either a file path (str) or PDF bytes (bytes)
    
    Returns:
        Total number of pages
    """
    try:
        if isinstance(pdf_source, str):
            pdf_context = pdfplumber.open(pdf_source)
        else:
            pdf_context = pdfplumber.open(io.BytesIO(pdf_source))
        
        with pdf_context as pdf:
            return len(pdf.pages)
    except Exception as e:
        # Fallback to pypdf if pdfplumber fails
        try:
            from pypdf import PdfReader
            if isinstance(pdf_source, str):
                reader = PdfReader(pdf_source)
            else:
                reader = PdfReader(io.BytesIO(pdf_source))
            return len(reader.pages)
        except Exception as fallback_error:
            raise Exception(f"PDF page count failed with both pdfplumber and pypdf: {e}, {fallback_error}")

def split_into_semantic_blocks(text: str):
    """
    Split text into semantic blocks that respect document structure:
    - Paragraphs (double newlines)
    - Numbered/bulleted lists (keep together)
    - Headers and sections
    """
    blocks = []
    
    # Split by double newlines (paragraphs) first
    paragraphs = re.split(r'\n\s*\n', text)
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # Check if this is a list (numbered or bulleted)
        # Pattern: starts with number/bullet and has multiple items
        list_pattern = r'^[\s]*(?:\d+[\.\)]\s+|[-•*]\s+)'
        if re.match(list_pattern, para):
            # Check if it contains multiple list items
            list_items = re.split(r'\n(?=[\s]*(?:\d+[\.\)]\s+|[-•*]\s+))', para)
            if len(list_items) > 1:
                # Keep the entire list together as one block
                blocks.append(para)
                continue
        
        # For regular paragraphs, split into sentences if too long
        sentences = re.split(r'(?<=[.?!])\s+', para)
        blocks.extend([s.strip() for s in sentences if s.strip()])
    
    return blocks

def split_into_sentences(text: str):
    # naive sentence splitter (kept for backward compatibility)
    sentences = re.split(r'(?<=[.?!])\s+', text)
    return [s.strip() for s in sentences if s.strip()]

def chunks_from_page(page_text: str, page_number: int, start_chunk_idx: int = 0, max_tokens: int = 500, overlap: int = 50):
    """
    Chunk a single page of text using semantic blocks (respects paragraphs, lists, etc.).
    start_chunk_idx: Starting chunk index (for maintaining global chunk numbering across pages)
    """
    if not page_text or not page_text.strip():
        return []
    
    if overlap >= max_tokens:
        raise ValueError(f"Overlap ({overlap}) must be less than max_tokens ({max_tokens})")
    
    chunks = []
    chunk_idx = start_chunk_idx
    blocks = split_into_semantic_blocks(page_text)
    i = 0
    
    while i < len(blocks):
        chunk_blocks = []
        token_count = 0
        
        # Add blocks until we hit the token limit
        while i < len(blocks):
            block_words = len(blocks[i].split())
            
            # If adding this block would exceed limit and we already have content, stop
            if token_count > 0 and token_count + block_words > max_tokens:
                break
            
            # If a single block is larger than max_tokens, split it by sentences
            if block_words > max_tokens:
                sentences = split_into_sentences(blocks[i])
                for sent in sentences:
                    sent_words = len(sent.split())
                    if token_count + sent_words > max_tokens and token_count > 0:
                        break
                    chunk_blocks.append(sent)
                    token_count += sent_words
                i += 1
                break
            
            chunk_blocks.append(blocks[i])
            token_count += block_words
            i += 1
        
        chunk_text = " ".join(chunk_blocks).strip()
        if chunk_text:
            chunks.append({
                "page_number": page_number,
                "chunk_index": chunk_idx,
                "text": chunk_text,
                "tokens": token_count
            })
            chunk_idx += 1
        
        # Backtrack for overlap (by words, not blocks)
        if i < len(blocks):
            back_words = overlap
            temp_i = i - 1
            while back_words > 0 and temp_i >= 0:
                block_words = len(blocks[temp_i].split())
                back_words -= block_words
                temp_i -= 1
            # Move back but ensure forward progress
            i = max(temp_i + 1, i - len(chunk_blocks) // 2)
    
    return chunks

def chunks_from_pages(pages: Dict[int,str], max_tokens:int=500, overlap:int=50):
    """
    Create semantic chunks from pages that respect document structure.
    Uses semantic blocks (paragraphs, lists) instead of just sentences.
    """
    if not pages:
        return []
    
    if overlap >= max_tokens:
        raise ValueError(f"Overlap ({overlap}) must be less than max_tokens ({max_tokens})")
    
    all_chunks = []
    chunk_idx = 0
    
    for page_no in sorted(pages.keys()):
        text = pages[page_no]
        blocks = split_into_semantic_blocks(text)
        i = 0
        
        while i < len(blocks):
            chunk_blocks = []
            token_count = 0
            
            # Add blocks until we hit the token limit
            while i < len(blocks):
                block_words = len(blocks[i].split())
                
                # If adding this block would exceed limit and we already have content, stop
                if token_count > 0 and token_count + block_words > max_tokens:
                    break
                
                # If a single block is larger than max_tokens, split it by sentences
                if block_words > max_tokens:
                    sentences = split_into_sentences(blocks[i])
                    for sent in sentences:
                        sent_words = len(sent.split())
                        if token_count + sent_words > max_tokens and token_count > 0:
                            break
                        chunk_blocks.append(sent)
                        token_count += sent_words
                    i += 1
                    break
                
                chunk_blocks.append(blocks[i])
                token_count += block_words
                i += 1
            
            chunk_text = " ".join(chunk_blocks).strip()
            if chunk_text:
                all_chunks.append({
                    "page_number": page_no,
                    "chunk_index": chunk_idx,
                    "text": chunk_text,
                    "tokens": token_count
                })
                chunk_idx += 1
            
            # Backtrack for overlap (by words, not blocks)
            if i < len(blocks):
                back_words = overlap
                temp_i = i - 1
                while back_words > 0 and temp_i >= 0:
                    block_words = len(blocks[temp_i].split())
                    back_words -= block_words
                    temp_i -= 1
                # Move back but ensure forward progress
                i = max(temp_i + 1, i - len(chunk_blocks) // 2)
    
    return all_chunks
