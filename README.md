## PDF Sentence Extractor

A Streamlit application that extracts individual sentences from multiple PDF files, with OCR garbage detection and structured Excel output.

Features

- Drag-and-drop multiple PDF file uploads
- Sequential processing with real-time progress tracking
- Sentence-level extraction
- OCR garbage detection with simple heuristics
- Structured sentence output with page numbers
- Excel download of extracted sentences
- Demo mode for testing without uploads
- Lightweight dependencies for fast deployment

OCR Garbage Detection
The app uses lightweight heuristics to detect OCR garbage text:
- Excessive consecutive consonants (e.g., `lieka;ofn;aodfnouaihdfao`)
- Low ratio of alphabetic to total characters
- Excessive punctuation sequences
- Extremely low vowel ratios
- Too many single-character words
