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
    print("✅ pdfplumber successfully imported")
except ImportError as e:
    PDF_ERROR = f"pdfplumber import failed: {str(e)}"
    print(f"❌ {PDF_ERROR}")
except Exception as e:
    PDF_ERROR = f"pdfplumber import error: {str(e)}"
    print(f"❌ {PDF_ERROR}")

def parse_pdf_bytes(pdf_bytes: bytes, file_name: str) -> List[Dict[str, Any]]:
    """
    Extract sentences from PDF bytes with OCR garbage detection.
    
    This implementation focuses on sentence-level extraction rather than file-level activities.
    SENTENCE PARSING OCCURS HERE - converts PDFs into individual sentences.
    
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
        - error: str | None - None on success, error message on failure
    """
    try:
        print(f"🔄 Starting to parse {file_name}, size: {len(pdf_bytes)} bytes")
        
        # Basic validation
        if not pdf_bytes:
            print("❌ File is empty")
            return [{
                'file_name': file_name,
                'activity_index': 0,
                'activity_text': f'Empty file: {file_name}',
                'page_number': 1,
                'document_name': file_name.rsplit('.', 1)[0],
                'error': 'File is empty or could not be read'
            }]
        
        if not PDF_AVAILABLE:
            print(f"❌ PDF processing not available: {PDF_ERROR}")
            # Return detailed error when pdfplumber not available
            return [{
                'file_name': file_name,
                'activity_index': 0,
                'activity_text': f'PDF processing unavailable: {PDF_ERROR}',
                'page_number': 1,
                'document_name': file_name.rsplit('.', 1)[0],
                'error': f'pdfplumber not available - {PDF_ERROR}'
            }]
        
        print("✅ pdfplumber available, starting text extraction")
        
        # Extract text from PDF using pdfplumber (lightweight alternative to PyMuPDF)
        pages_text = extract_text_with_pdfplumber(pdf_bytes)
        
        if not pages_text:
            print("❌ No pages extracted")
            return [{
                'file_name': file_name,
                'activity_index': 0,
                'activity_text': f'No text found in: {file_name}',
                'page_number': 1,
                'document_name': file_name.rsplit('.', 1)[0],
                'error': 'No extractable text found in PDF'
            }]
        
        print(f"✅ Extracted text from {len(pages_text)} pages")
        
        # Process each page and extract sentences
        all_sentences = []
        sentence_index = 0
        
        for page_num, page_text in enumerate(pages_text, 1):
            print(f"🔍 Processing page {page_num}, text length: {len(page_text)}")
            
            if not page_text.strip():
                print(f"⚠️ Page {page_num} is empty, skipping")
                continue
            
            # Check if entire page is OCR garbage (very conservative)
            page_is_garbage = is_ocr_garbage(page_text)
            if page_is_garbage:
                print(f"🗑️ Entire page {page_num} appears to be OCR garbage")
                # Still try to extract sentences, but flag them
                
            # Extract sentences from page text regardless of OCR garbage detection
            sentences = extract_sentences_from_text(page_text)
            print(f"📝 Found {len(sentences)} potential sentences on page {page_num}")
            
            for sentence in sentences:
                if len(sentence.strip()) < 10:  # Skip very short fragments
                    continue
                    
                # Apply sentence-level quality check
                is_sentence_garbage = is_sentence_garbage(sentence)
                
                if is_sentence_garbage:
                    print(f"🗑️ Skipping garbage sentence: '{sentence[:50]}...'")
                    continue  # Skip this sentence but keep processing others
                
                # This is a valid sentence
                all_sentences.append({
                    'file_name': file_name,
                    'activity_index': sentence_index,
                    'activity_text': clean_sentence_text(sentence),
                    'page_number': page_num,
                    'document_name': file_name.rsplit('.', 1)[0],
                    'error': 'Possible OCR issues on page' if page_is_garbage else None
                })
                sentence_index += 1
        
        print(f"✅ Total sentences extracted: {len(all_sentences)}")
        
        if not all_sentences:
            print("❌ No valid sentences found")
            return [{
                'file_name': file_name,
                'activity_index': 0,
                'activity_text': f'No valid sentences found in: {file_name}',
                'page_number': 1,
                'document_name': file_name.rsplit('.', 1)[0],
                'error': 'No valid sentences could be extracted'
            }]
        
        return all_sentences
        
    except Exception as e:
        print(f"❌ Parsing failed for {file_name}: {str(e)}")
        # Return error sentence on any exception
        return [{
            'file_name': file_name,
            'activity_index': 0,
            'activity_text': f'Failed to parse: {file_name}',
            'page_number': 1,
            'document_name': file_name.rsplit('.', 1)[0],
            'error': f'Parsing error: {str(e)}'
        }]

def extract_text_with_pdfplumber(pdf_bytes: bytes) -> List[str]:
    """
    Extract text from PDF using pdfplumber (lightweight alternative to PyMuPDF).
    
    Returns:
        List of strings, one per page
    """
    if not PDF_AVAILABLE:
        raise Exception(f"pdfplumber not available: {PDF_ERROR}")
    
    try:
        print(f"📖 Opening PDF with pdfplumber, size: {len(pdf_bytes)} bytes")
        
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages_text = []
            total_pages = len(pdf.pages)
            print(f"📄 PDF has {total_pages} pages")
            
            for page_num, page in enumerate(pdf.pages):
                print(f"📝 Processing page {page_num + 1}/{total_pages}")
                text = ""
                
                # Extract regular text
                page_text = page.extract_text()
                if page_text:
                    text += page_text
                    print(f"✅ Extracted {len(page_text)} characters from page {page_num + 1}")
                else:
                    print(f"⚠️ No text found on page {page_num + 1}")
                
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
                        print(f"📊 Extracted {len(table_text)} characters from tables on page {page_num + 1}")
                except Exception as table_error:
                    print(f"⚠️ Table extraction failed on page {page_num + 1}: {table_error}")
                
                pages_text.append(text)
            
            print(f"✅ Successfully extracted text from all {total_pages} pages")
            return pages_text
            
    except Exception as e:
        print(f"❌ PDF extraction failed: {str(e)}")
        raise Exception(f"PDF extraction failed: {str(e)}")

def is_sentence_garbage(sentence: str) -> bool:
    """
    Lightweight sentence-level garbage detection.
    
    Filters out obviously corrupted individual sentences while preserving
    most valid content. Much more conservative than page-level detection.
    
    Args:
        sentence: Individual sentence to check
        
    Returns:
        bool: True if this specific sentence appears to be garbage
    """
    if not sentence or len(sentence.strip()) < 5:
        return True
    
    clean_sentence = sentence.lower().strip()
    
    # Very conservative checks for individual sentences
    
    # Check 1: Sentence is mostly non-alphabetic characters
    alpha_chars = sum(1 for c in clean_sentence if c.isalpha())
    total_chars = len(clean_sentence.replace(' ', ''))
    if total_chars > 10 and alpha_chars / total_chars < 0.3:
        return True
    
    # Check 2: Sentence has extreme consonant clusters (8+ consecutive)
    extreme_consonants = re.findall(r'[bcdfghjklmnpqrstvwxyz]{8,}', clean_sentence)
    if len(extreme_consonants) > 0:
        return True
    
    # Check 3: Sentence is mostly repeated characters
    if len(set(clean_sentence.replace(' ', ''))) < 3 and len(clean_sentence) > 10:
        return True
    
    # Check 4: Sentence has no vowels at all (very rare in real text)
    if alpha_chars > 5 and not any(c in 'aeiou' for c in clean_sentence):
        return True
    
    return False  # Default to keeping sentences

def is_ocr_garbage(text: str) -> bool:
    """
    Much more conservative OCR garbage detection.
    
    Only flags extremely obvious OCR garbage to avoid dismissing valid content.
    Uses very strict thresholds to minimize false positives.
    
    Args:
        text: Text to check for OCR garbage
        
    Returns:
        bool: True only if text is very obviously OCR garbage
    """
    if not text or len(text.strip()) < 50:  # Increased minimum length
        return False
    
    # Convert to lowercase for analysis
    clean_text = text.lower().strip()
    
    # Much more conservative heuristics - only flag extreme cases
    
    # Heuristic 1: Extremely long consonant runs (10+ chars) - very rare in real text
    extreme_consonant_runs = re.findall(r'[bcdfghjklmnpqrstvwxyz]{10,}', clean_text)
    if len(extreme_consonant_runs) > 1:  # Allow one, flag if multiple
        return True
    
    # Heuristic 2: Very low alphabetic ratio (< 40%) - most text is at least 40% letters
    alpha_chars = sum(1 for c in clean_text if c.isalpha())
    total_chars = len(clean_text.replace(' ', ''))
    if total_chars > 100 and alpha_chars / total_chars < 0.4:  # More lenient threshold
        return True
    
    # Heuristic 3: Extremely high ratio of numbers/symbols (> 70%)
    non_alpha_non_space = sum(1 for c in clean_text if not c.isalpha() and not c.isspace())
    if len(clean_text) > 100 and non_alpha_non_space / len(clean_text) > 0.7:
        return True
    
    # Heuristic 4: Almost no vowels at all (< 8%) - real text always has vowels
    vowels = sum(1 for c in clean_text if c in 'aeiou')
    if alpha_chars > 100 and vowels / alpha_chars < 0.08:  # Much more lenient
        return True
    
    return False  # Default to keeping text

def extract_sentences_from_text(text: str) -> List[str]:
    """
    Extract individual sentences from page text with robust cleaning and normalization.
    
    Handles common edge cases like abbreviations, numbers, and decimal points.
    
    Args:
        text: Raw text from PDF page
        
    Returns:
        List of cleaned sentences
    """
    if not text or not text.strip():
        return []
    
    # Unicode normalization
    try:
        text = unicodedata.normalize('NFC', text)
    except:
        pass
    
    # Clean whitespace and line breaks (more conservative)
    text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces/tabs to single space
    text = re.sub(r'\r\n|\r', '\n', text)  # Normalize line endings
    text = re.sub(r'\n{4,}', '\n\n\n', text)  # Limit excessive line breaks but keep some
    
    # Comprehensive protection of periods that shouldn't end sentences
    
    # 1. Common abbreviations
    abbreviations = [
        'Dr', 'Mr', 'Mrs', 'Ms', 'Prof', 'Inc', 'Ltd', 'Corp', 'Co', 'LLC',
        'etc', 'vs', 'e\.g', 'i\.e', 'cf', 'viz', 'al', 'Jr', 'Sr', 'Ph\.D',
        'M\.D', 'B\.A', 'M\.A', 'M\.S', 'B\.S', 'U\.S', 'U\.K', 'U\.N'
    ]
    for abbr in abbreviations:
        text = re.sub(rf'\b{abbr}\. ', f'{abbr}DOTPLACEHOLDER ', text, flags=re.IGNORECASE)
    
    # 2. Numbers with decimals - comprehensive patterns
    # Simple decimals: 1.5, 3.14, 0.75, etc.
    text = re.sub(r'\b(\d+)\.(\d+)\b', r'\1DECIMALDOT\2', text)
    
    # Decimals followed by common units/words
    decimal_units = [
        'million', 'billion', 'trillion', 'thousand', 'hundred',
        'percent', '%', 'degrees', 'inches', 'feet', 'yards', 'miles', 'km', 'meters',
        'kg', 'lbs', 'pounds', 'tons', 'ounces', 'grams',
        'seconds', 'minutes', 'hours', 'days', 'weeks', 'months', 'years',
        'dollars', 'cents', 'euros', 'pounds'
    ]
    for unit in decimal_units:
        # Handle patterns like "1.5 million", "3.14 percent", etc.
        text = re.sub(rf'\b(\d+)DECIMALDOT(\d+)\s+{unit}\b', rf'\1DECIMALDOT\2 {unit}', text, flags=re.IGNORECASE)
    
    # 3. Ordinal numbers: 1st, 2nd, 3rd, etc. (though these use . less commonly)
    text = re.sub(r'\b(\d+)(st|nd|rd|th)\.', r'\1\2DOTPLACEHOLDER', text)
    
    # 4. Time formats: 1.30 PM, 14.45, etc.
    text = re.sub(r'\b(\d{1,2})\.(\d{2})\s*(AM|PM|am|pm)\b', r'\1DECIMALDOT\2 \3', text)
    
    # 5. Version numbers: v1.5, version 2.3, etc.
    text = re.sub(r'\b(v|version)\s*(\d+)\.(\d+)', r'\1 \2DECIMALDOT\3', text, flags=re.IGNORECASE)
    
    # 6. Dates in some formats: 1.5.2023, etc. (though less common)
    text = re.sub(r'\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b', r'\1DECIMALDOT\2DECIMALDOT\3', text)
    
    # Now split into potential sentences - improved regex
    sentence_boundaries = re.split(r'[.!?]+(?=\s|\n|$)', text)
    
    sentences = []
    for potential_sentence in sentence_boundaries:
        if not potential_sentence.strip():
            continue
            
        # Restore all the protected periods
        sentence = potential_sentence.replace('DOTPLACEHOLDER', '.')
        sentence = sentence.replace('DECIMALDOT', '.')
        sentence = sentence.strip()
        
        if len(sentence) < 5:  # Skip very short fragments
            continue
            
        # Handle sentences that might be missing punctuation
        if sentence and sentence[-1] not in '.!?':
            sentence += '.'
            
        sentences.append(sentence)
    
    # Additional split for sentences separated by multiple line breaks
    additional_sentences = []
    for sentence in sentences:
        # Split on double line breaks (paragraph boundaries)
        parts = sentence.split('\n\n')
        for part in parts:
            part = part.replace('\n', ' ').strip()  # Join line-broken sentences
            if len(part) >= 5:
                if part[-1] not in '.!?':
                    part += '.'
                additional_sentences.append(part)
    
    return additional_sentences

def clean_sentence_text(sentence: str) -> str:
    """
    Clean sentence text for CSV output and remove problematic characters.
    
    Args:
        sentence: Raw sentence text
        
    Returns:
        Cleaned sentence text safe for CSV output
    """
    if not isinstance(sentence, str):
        sentence = str(sentence)
    
    # Remove control characters that can break CSV
    sentence = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', sentence)
    
    # Normalize whitespace
    sentence = re.sub(r'\s+', ' ', sentence.strip())
    
    # Truncate if too long (prevent Excel issues)
    max_length = 32000
    if len(sentence) > max_length:
        sentence = sentence[:max_length] + "... [TRUNCATED]"
    
    return sentence

def create_demo_sentences(file_name: str) -> List[Dict[str, Any]]:
    """
    Create demo sentences when PDF processing is not available.
    
    Used as fallback when pdfplumber is not installed.
    """
    document_name = file_name.rsplit('.', 1)[0]
    
    # Generate different demo sentences based on filename
    if 'report' in file_name.lower():
        demo_sentences = [
            "This is the executive summary of our quarterly report.",
            "Key findings indicate a 15% increase in performance metrics.",
            "Recommendations for next quarter are outlined in section 4."
        ]
    elif 'meeting' in file_name.lower():
        demo_sentences = [
            "The meeting was called to order at 9:00 AM.",
            "Discussion focused on project timeline and resource allocation.",
            "Action items were assigned to respective team members."
        ]
    else:
        demo_sentences = [
            f"This is the first sentence extracted from {document_name}.",
            f"The document {file_name} contains multiple pages of content.",
            f"Sentence extraction completed for {document_name}."
        ]
    
    results = []
    for i, sentence in enumerate(demo_sentences):
        results.append({
            'file_name': file_name,
            'activity_index': i,
            'activity_text': sentence,
            'page_number': i + 1,  # Spread across different pages
            'document_name': document_name,
            'error': None
        })
    
    return results

def validate_sentence_structure(sentence_dict: Dict[str, Any]) -> bool:
    """
    Validate that a sentence dictionary has the required structure.
    
    Args:
        sentence_dict: Sentence dictionary to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    required_keys = {'file_name', 'activity_index', 'activity_text', 'page_number', 'document_name', 'error'}
    
    if not isinstance(sentence_dict, dict):
        return False
    
    if set(sentence_dict.keys()) != required_keys:
        return False
    
    # Type checking
    if not isinstance(sentence_dict['file_name'], str):
        return False
    
    if not isinstance(sentence_dict['activity_index'], int):
        return False
    
    if not isinstance(sentence_dict['activity_text'], str):
        return False
    
    if not isinstance(sentence_dict['page_number'], int):
        return False
    
    if not isinstance(sentence_dict['document_name'], str):
        return False
    
    if sentence_dict['error'] is not None and not isinstance(sentence_dict['error'], str):
        return False
    
    return True
