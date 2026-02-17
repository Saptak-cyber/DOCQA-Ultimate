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
                # 1. Handle hyphenated line breaks (word- \n word -> word-word)
                text = re.sub(r"-\s*\n\s*", "-", text)
                # 2. Handle regular line breaks (join words split across lines)
                text = re.sub(r"(\w)\s*\n\s*(\w)", r"\1 \2", text)
                # 3. Normalize spaces/tabs
                text = re.sub(r"[ \t]+", " ", text)
                # 4. Remove excessive blank lines
                text = re.sub(r"\n+", "\n", text)
                # 5. Final normalization - collapse remaining whitespace
                text = re.sub(r"\s+", " ", text).strip()
                pages[i + 1] = text
    except Exception as e:
        # Fallback to pypdf if pdfplumber fails
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(pdf_bytes))
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                # Apply same normalization as pdfplumber
                text = re.sub(r"-\s*\n\s*", "-", text)
                text = re.sub(r"(\w)\s*\n\s*(\w)", r"\1 \2", text)
                text = re.sub(r"[ \t]+", " ", text)
                text = re.sub(r"\n+", "\n", text)
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
                # 1. Handle hyphenated line breaks (word- \n word -> word-word)
                text = re.sub(r"-\s*\n\s*", "-", text)
                # 2. Handle regular line breaks (join words split across lines)
                text = re.sub(r"(\w)\s*\n\s*(\w)", r"\1 \2", text)
                # 3. Normalize spaces/tabs
                text = re.sub(r"[ \t]+", " ", text)
                # 4. Remove excessive blank lines
                text = re.sub(r"\n+", "\n", text)
                # 5. Final normalization - collapse remaining whitespace
                text = re.sub(r"\s+", " ", text).strip()
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
                # Apply same normalization as pdfplumber
                text = re.sub(r"-\s*\n\s*", "-", text)
                text = re.sub(r"(\w)\s*\n\s*(\w)", r"\1 \2", text)
                text = re.sub(r"[ \t]+", " ", text)
                text = re.sub(r"\n+", "\n", text)
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
    - Paragraphs (kept as complete units)
    - Numbered/bulleted lists (kept as complete units)
    - Headers and sections
    
    Each block is a complete semantic unit (paragraph or list).
    """
    blocks = []
    
    # Split by double newlines (paragraphs) or list boundaries
    paragraphs = re.split(r'\n\s*\n', text)
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # Check if this is a list (numbered or bulleted)
        list_pattern = r'^[\s]*(?:\d+[\.\)]\s+|[-•*]\s+)'
        if re.match(list_pattern, para):
            # This is a list - keep it as one complete block
            blocks.append(para)
        else:
            # Regular paragraph - keep as one complete block
            blocks.append(para)
    
    return blocks

def split_into_sentences(text: str):
    # naive sentence splitter (kept for backward compatibility)
    sentences = re.split(r'(?<=[.?!])\s+', text)
    return [s.strip() for s in sentences if s.strip()]

def chunks_from_page(page_text: str, page_number: int, start_chunk_idx: int = 0, max_tokens: int = 500, overlap: int = 50):
    """
    Chunk a single page of text using semantic blocks.
    
    Strategy:
    - Target chunk size is max_tokens (500 words)
    - When we reach 500 words, we CONTINUE to add the next paragraph/list to complete it
    - This ensures chunks don't cut off mid-paragraph or mid-list
    - Chunks will typically be >= 500 words (unless the page ends)
    
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
        reached_target = False
        
        # Add blocks until we complete a semantic unit after reaching the target
        while i < len(blocks):
            block_words = len(blocks[i].split())
            
            # Add this block
            chunk_blocks.append(blocks[i])
            token_count += block_words
            i += 1
            
            # Check if we've reached the target size
            if token_count >= max_tokens:
                reached_target = True
                # We've reached target, but we completed this block, so stop here
                break
        
        chunk_text = " ".join(chunk_blocks).strip()
        if chunk_text:
            chunks.append({
                "page_number": page_number,
                "chunk_index": chunk_idx,
                "text": chunk_text,
                "tokens": token_count
            })
            chunk_idx += 1
        
        # Backtrack for overlap (go back by overlap words worth of blocks)
        if i < len(blocks) and overlap > 0:
            back_words = overlap
            temp_i = i - 1
            while back_words > 0 and temp_i >= 0:
                block_words = len(blocks[temp_i].split())
                back_words -= block_words
                temp_i -= 1
            # Move back but ensure forward progress (at least move forward by 1 block)
            i = max(temp_i + 1, i - len(chunk_blocks) + 1)
    
    return chunks

def chunks_from_pages(pages: Dict[int,str], max_tokens:int=500, overlap:int=50):
    """
    Create semantic chunks from pages that respect document structure.
    
    Strategy:
    - Target chunk size is max_tokens (500 words)
    - When we reach 500 words, we CONTINUE to add the next paragraph/list to complete it
    - This ensures chunks don't cut off mid-paragraph or mid-list
    - Chunks will typically be >= 500 words (unless the page ends)
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
            reached_target = False
            
            # Add blocks until we complete a semantic unit after reaching the target
            while i < len(blocks):
                block_words = len(blocks[i].split())
                
                # Add this block
                chunk_blocks.append(blocks[i])
                token_count += block_words
                i += 1
                
                # Check if we've reached the target size
                if token_count >= max_tokens:
                    reached_target = True
                    # We've reached target, but we completed this block, so stop here
                    break
            
            chunk_text = " ".join(chunk_blocks).strip()
            if chunk_text:
                all_chunks.append({
                    "page_number": page_no,
                    "chunk_index": chunk_idx,
                    "text": chunk_text,
                    "tokens": token_count
                })
                chunk_idx += 1
            
            # Backtrack for overlap (go back by overlap words worth of blocks)
            if i < len(blocks) and overlap > 0:
                back_words = overlap
                temp_i = i - 1
                while back_words > 0 and temp_i >= 0:
                    block_words = len(blocks[temp_i].split())
                    back_words -= block_words
                    temp_i -= 1
                # Move back but ensure forward progress (at least move forward by 1 block)
                i = max(temp_i + 1, i - len(chunk_blocks) + 1)
    
    return all_chunks
