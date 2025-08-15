from typing import List, Dict, Any
import time

def parse_pdf_bytes(pdf_bytes: bytes, file_name: str) -> List[Dict[str, Any]]:
    """
    Parse PDF bytes and extract activities.
    
    This is a stub implementation that returns the filename as activity text.
    In a real implementation, this would extract actual text/activities from the PDF.
    
    Args:
        pdf_bytes: Raw PDF file bytes
        file_name: Original filename of the PDF
        
    Returns:
        List of activity dictionaries with required structure:
        - file_name: str - original uploaded file name
        - activity_index: int - 0-based index for each activity in that file
        - activity_text: str - human-readable activity description
        - error: str | None - None on success, error message on failure
    """
    try:
        # Simulate some processing time (remove in production)
        time.sleep(0.5)
        
        # Basic validation
        if not pdf_bytes:
            return [{
                'file_name': file_name,
                'activity_index': 0,
                'activity_text': f'Empty file: {file_name}',
                'error': 'File is empty or could not be read'
            }]
        
        # For now, just return a single activity with the filename
        # In a real implementation, this would:
        # 1. Use a PDF parsing library (PyPDF2, pdfplumber, etc.)
        # 2. Extract text content
        # 3. Parse activities using NLP/regex/rules
        # 4. Return multiple activities per file as needed
        
        activities = [
            {
                'file_name': file_name,
                'activity_index': 0,
                'activity_text': f'Parsed filename: {file_name}',
                'error': None
            }
        ]
        
        # For demo purposes, add a second activity for files with certain names
        if any(keyword in file_name.lower() for keyword in ['report', 'meeting', 'document']):
            activities.append({
                'file_name': file_name,
                'activity_index': 1,
                'activity_text': f'Additional content found in: {file_name}',
                'error': None
            })
        
        return activities
        
    except Exception as e:
        # Return error activity on any exception
        return [{
            'file_name': file_name,
            'activity_index': 0,
            'activity_text': f'Failed to parse: {file_name}',
            'error': f'Parsing error: {str(e)}'
        }]

def validate_activity_structure(activity: Dict[str, Any]) -> bool:
    """
    Validate that an activity dictionary has the required structure.
    
    Args:
        activity: Activity dictionary to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    required_keys = {'file_name', 'activity_index', 'activity_text', 'error'}
    
    if not isinstance(activity, dict):
        return False
    
    if set(activity.keys()) != required_keys:
        return False
    
    # Type checking
    if not isinstance(activity['file_name'], str):
        return False
    
    if not isinstance(activity['activity_index'], int):
        return False
    
    if not isinstance(activity['activity_text'], str):
        return False
    
    if activity['error'] is not None and not isinstance(activity['error'], str):
        return False
    
    return True
