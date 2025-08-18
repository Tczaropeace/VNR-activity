import re
import io
import time
import unicodedata
from typing import List, Dict, Any

# Lightweight PDF processing - with better error handling
PDF_AVAILABLE = False
PDF_ERROR = None

try:
    import pdfplumber
    PDF_AVAILABLE = True
    print("pdfplumber successfully imported")
except ImportError as e:
    PDF_ERROR = f"pdfplumber import failed: {str(e)}"
    print(f"Error: {PDF_ERROR}")
except Exception as e:
    PDF_ERROR = f"pdfplumber import error: {str(e)}"
    print(f"Error: {PDF_ERROR}")

def parse_pdf_bytes(pdf_bytes: bytes, file_name: str) -> List[Dict[str, Any]]:
    """
    Extract sentences from PDF bytes with context parsing.
    
    This implementation focuses on sentence-level extraction with context support.
    SENTENCE PARSING + CONTEXT GENERATION OCCURS HERE.
    
    Args:
        pdf_bytes: Raw PDF file bytes
        file_name: Original filename of the PDF
        
    Returns:
        List of sentence dictionaries with structure:
        - file_name: str - original uploaded file name
        - activity_index: int - 0-based index for each sentence
        - activity_text: str - the extracted sentence
        - page_number: int - page number where sentence was found
        - document_name: str - document name without extension
        - context: str - surrounding sentences for ML prediction (internal use only)
        - error: str | None - None on success, error message on failure
    """
    try:
        print(f"Starting to parse {file_name}, size: {len(pdf_bytes)} bytes")
        
        # Basic validation
        if not pdf_bytes:
            print("File is empty")
            return [{
                'file_name': file_name,
                'activity_index': 0,
                'activity_text': f'Empty file: {file_name}',
                'page_number': 1,
                'document_name': file_name.rsplit('.', 1)[0],
                'context': '',
                'error': 'File is empty or could not be read'
            }]
        
        if not PDF_AVAILABLE:
            print(f"PDF processing not available: {PDF_ERROR}")
            return [{
                'file_name': file_name,
                'activity_index': 0,
                'activity_text': f'PDF processing unavailable: {PDF_ERROR}',
                'page_number': 1,
                'document_name': file_name.rsplit('.', 1)[0],
                'context': '',
                'error': f'pdfplumber not available - {PDF_ERROR}'
            }]
        
        print("pdfplumber available, starting text extraction")
        
        # Extract text from PDF using pdfplumber
        pages_text = extract_text_with_pdfplumber(pdf_bytes)
        
        if not pages_text:
            print("No pages extracted")
            return [{
                'file_name': file_name,
                'activity_index': 0,
                'activity_text': f'No text found in: {file_name}',
                'page_number': 1,
                'document_name': file_name.rsplit('.', 1)[0],
                'context': '',
                'error': 'No extractable text found in PDF'
            }]
        
        print(f"Extracted text from {len(pages_text)} pages")
        
        # Process each page and collect all sentences first (without context)
        all_sentences_raw = []
        
        for page_num, page_text in enumerate(pages_text, 1):
            print(f"Processing page {page_num}, text length: {len(page_text)}")
            
            if not page_text.strip():
                print(f"Page {page_num} is empty, skipping")
                continue
            
            # Check if entire page is OCR garbage (very conservative)
            page_is_garbage = is_ocr_garbage(page_text)
            if page_is_garbage:
                print(f"Entire page {page_num} appears to be OCR garbage")
                
            # Extract sentences from page text
            sentences = extract_sentences_from_text(page_text)
            print(f"Found {len(sentences)} potential sentences on page {page_num}")
            
            for sentence in sentences:
                if len(sentence.strip()) < 5:
                    continue
                    
                # Store raw sentence data for context processing
                all_sentences_raw.append({
                    'text': clean_sentence_text(sentence),
                    'page_number': page_num,
                    'has_ocr_issues': page_is_garbage
                })
        
        print(f"Collected {len(all_sentences_raw)} raw sentences across all pages")
        
        # NOW ADD CONTEXT - Process sentences with context from surrounding sentences
        all_sentences_with_context = []
        
        for i, sent_data in enumerate(all_sentences_raw):
            # Get previous, current, and next sentences
            prev_sentence = all_sentences_raw[i - 1]['text'] if i > 0 else ""
            current_sentence = sent_data['text']
            next_sentence = all_sentences_raw[i + 1]['text'] if i < len(all_sentences_raw) - 1 else ""
            
            # Create context by concatenating the three sentences
            context_parts = []
            if prev_sentence:
                context_parts.append(prev_sentence)
            context_parts.append(current_sentence)
            if next_sentence:
                context_parts.append(next_sentence)
            
            # Join context (this matches your trainer's context format)
            context = " ".join(context_parts)
            
            # Create final sentence entry with context
            all_sentences_with_context.append({
                'file_name': file_name,
                'activity_index': i,
                'activity_text': current_sentence,
                'page_number': sent_data['page_number'],
                'document_name': file_name.rsplit('.', 1)[0],
                'context': clean_sentence_text(context),  # Clean context for ML use
                'error': 'Possible OCR issues on page' if sent_data['has_ocr_issues'] else None
            })
        
        print(f"Total sentences with context: {len(all_sentences_with_context)}")
        
        if not all_sentences_with_context:
            print("No valid sentences found")
            return [{
                'file_name': file_name,
                'activity_index': 0,
                'activity_text': f'No valid sentences found in: {file_name}',
                'page_number': 1,
                'document_name': file_name.rsplit('.', 1)[0],
                'context': '',
                'error': 'No valid sentences could be extracted'
            }]
        
        return all_sentences_with_context
        
    except Exception as e:
        print(f"Parsing failed for {file_name}: {str(e)}")
        return [{
            'file_name': file_name,
            'activity_index': 0,
            'activity_text': f'Failed to parse: {file_name}',
            'page_number': 1,
            'document_name': file_name.rsplit('.', 1)[0],
            'context': '',
            'error': f'Parsing error: {str(e)}'
        }]

def extract_text_with_pdfplumber(pdf_bytes: bytes) -> List[str]:
    """
    Extract text from PDF using pdfplumber.
    
    Returns:
        List of strings, one per page
    """
    if not PDF_AVAILABLE:
        raise Exception(f"pdfplumber not available: {PDF_ERROR}")
    
    try:
        print(f"Opening PDF with pdfplumber, size: {len(pdf_bytes)} bytes")
        
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages_text = []
            total_pages = len(pdf.pages)
            print(f"PDF has {total_pages} pages")
            
            for page_num, page in enumerate(pdf.pages):
                print(f"Processing page {page_num + 1}/{total_pages}")
                text = ""
                
                # Extract regular text
                page_text = page.extract_text()
                if page_text:
                    text += page_text
                    print(f"Extracted {len(page_text)} characters from page {page_num + 1}")
                else:
                    print(f"No text found on page {page_num + 1}")
                
                # Extract table content
                try:
                    tables = page.extract_tables()
                    if tables:
                        table_text = ""
                        for table in tables:
                            for row in table:
                                if row:
                                    table_text += "\n" + " ".join(str(cell or "") for cell in row)
                        text += table_text
                        print(f"Extracted {len(table_text)} characters from tables on page {page_num + 1}")
                except Exception as table_error:
                    print(f"Table extraction failed on page {page_num + 1}: {table_error}")
                
                pages_text.append(text)
            
            print(f"Successfully extracted text from all {total_pages} pages")
            return pages_text
            
    except Exception as e:
        print(f"PDF extraction failed: {str(e)}")
        raise Exception(f"PDF extraction failed: {str(e)}")

def is_ocr_garbage(text: str) -> bool:
    """
    Conservative OCR garbage detection.
    
    Args:
        text: Text to check for OCR garbage
        
    Returns:
        bool: True only if text is very obviously OCR garbage
    """
    if not text or len(text.strip()) < 50:
        return False
    
    # Convert to lowercase for analysis
    clean_text = text.lower().strip()
    
    # Conservative heuristics - only flag extreme cases
    
    # Heuristic 1: Extremely long consonant runs (10+ chars)
    extreme_consonant_runs = re.findall(r'[bcdfghjklmnpqrstvwxyz]{10,}', clean_text)
    if len(extreme_consonant_runs) > 1:
        return True
    
    # Heuristic 2: Very low alphabetic ratio (< 40%)
    alpha_chars = sum(1 for c in clean_text if c.isalpha())
    total_chars = len(clean_text.replace(' ', ''))
    if total_chars > 100 and alpha_chars / total_chars < 0.4:
        return True
    
    # Heuristic 3: Extremely high ratio of numbers/symbols (> 70%)
    non_alpha_non_space = sum(1 for c in clean_text if not c.isalpha() and not c.isspace())
    if len(clean_text) > 100 and non_alpha_non_space / len(clean_text) > 0.7:
        return True
    
    # Heuristic 4: Almost no vowels at all (< 8%)
    vowels = sum(1 for c in clean_text if c in 'aeiou')
    if alpha_chars > 100 and vowels / alpha_chars < 0.08:
        return True
    
    return False

def extract_sentences_from_text(text: str) -> List[str]:
    """
    Extract individual sentences from page text with robust cleaning and normalization.
    
    Args:
        text: Raw text from PDF page
        
    Returns:
        List of cleaned sentences
    """
    print(f"Starting sentence extraction from {len(text)} characters")
    
    if not text or not text.strip():
        print("Empty text provided")
        return []
    
    # Unicode normalization
    try:
        text = unicodedata.normalize('NFC', text)
    except:
        pass
    
    # Clean whitespace and line breaks
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\r\n|\r', '\n', text)
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    
    # Protect periods that shouldn't end sentences
    
    # 1. Common abbreviations
    abbreviations = [
        'Dr', 'Mr', 'Mrs', 'Ms', 'Prof', 'Inc', 'Ltd', 'Corp', 'Co', 'LLC',
        'etc', 'vs', 'e\.g', 'i\.e', 'cf', 'viz', 'al', 'Jr', 'Sr', 'Ph\.D',
        'M\.D', 'B\.A', 'M\.A', 'M\.S', 'B\.S', 'U\.S', 'U\.K', 'U\.N'
    ]
    for abbr in abbreviations:
        text = re.sub(rf'\b{abbr}\. ', f'{abbr}DOTPLACEHOLDER ', text, flags=re.IGNORECASE)
    
    # 2. Numbers with decimals
    text = re.sub(r'\b(\d+)\.(\d+)\b', r'\1DECIMALDOT\2', text)
    
    # 3. Decimal numbers with units
    decimal_units = [
        'million', 'billion', 'trillion', 'thousand', 'hundred',
        'percent', '%', 'degrees', 'inches', 'feet', 'yards', 'miles', 'km', 'meters',
        'kg', 'lbs', 'pounds', 'tons', 'ounces', 'grams',
        'seconds', 'minutes', 'hours', 'days', 'weeks', 'months', 'years',
        'dollars', 'cents', 'euros', 'pounds'
    ]
    for unit in decimal_units:
        text = re.sub(rf'\b(\d+)DECIMALDOT(\d+)\s+{unit}\b', rf'\1DECIMALDOT\2 {unit}', text, flags=re.IGNORECASE)
    
    # 4. Time formats and version numbers
    text = re.sub(r'\b(\d{1,2})\.(\d{2})\s*(AM|PM|am|pm)\b', r'\1DECIMALDOT\2 \3', text)
    text = re.sub(r'\b(v|version)\s*(\d+)\.(\d+)', r'\1 \2DECIMALDOT\3', text, flags=re.IGNORECASE)
    
    # Split into sentences
    print(f"Splitting text into sentences...")
    sentence_boundaries = re.split(r'[.!?]+(?=\s|\n|$)', text)
    print(f"Found {len(sentence_boundaries)} potential sentence boundaries")
    
    sentences = []
    for i, potential_sentence in enumerate(sentence_boundaries):
        if not potential_sentence.strip():
            continue
            
        # Restore protected periods
        sentence = potential_sentence.replace('DOTPLACEHOLDER', '.')
        sentence = sentence.replace('DECIMALDOT', '.')
        sentence = sentence.strip()
        
        if len(sentence) < 5:
            continue
            
        # Add punctuation if missing
        if sentence and sentence[-1] not in '.!?':
            sentence += '.'
            
        sentences.append(sentence)
    
    # Handle paragraph breaks
    additional_sentences = []
    for sentence in sentences:
        parts = sentence.split('\n\n')
        for part in parts:
            part = part.replace('\n', ' ').strip()
            if len(part) >= 5:
                if part[-1] not in '.!?':
                    part += '.'
                additional_sentences.append(part)
    
    print(f"Final sentence extraction complete: {len(additional_sentences)} sentences")
    
    return additional_sentences

def clean_sentence_text(sentence: str) -> str:
    """
    Clean sentence text for CSV output and ML processing.
    
    Args:
        sentence: Raw sentence text
        
    Returns:
        Cleaned sentence text
    """
    if not isinstance(sentence, str):
        sentence = str(sentence)
    
    # Remove control characters
    sentence = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', sentence)
    
    # Normalize whitespace
    sentence = re.sub(r'\s+', ' ', sentence.strip())
    
    # Truncate if too long
    max_length = 32000
    if len(sentence) > max_length:
        sentence = sentence[:max_length] + "... [TRUNCATED]"
    
    return sentence

def validate_sentence_structure(sentence_dict: Dict[str, Any]) -> bool:
    """
    Validate that a sentence dictionary has the required structure.
    
    Args:
        sentence_dict: Sentence dictionary to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    required_keys = {'file_name', 'activity_index', 'activity_text', 'page_number', 'document_name', 'context', 'error'}
    
    if not isinstance(sentence_dict, dict):
        return False
    
    if set(sentence_dict.keys()) != required_keys:
        return False
    
    # Type checking
    return (isinstance(sentence_dict['file_name'], str) and
            isinstance(sentence_dict['activity_index'], int) and
            isinstance(sentence_dict['activity_text'], str) and
            isinstance(sentence_dict['page_number'], int) and
            isinstance(sentence_dict['document_name'], str) and
            isinstance(sentence_dict['context'], str) and
            (sentence_dict['error'] is None or isinstance(sentence_dict['error'], str)))
    
