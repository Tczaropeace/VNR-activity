import streamlit as st
import pandas as pd
import io
from typing import List, Dict, Any
from utils.parser import parse_pdf_bytes
from utils.activity_classifier import (
    load_activity_classifier, 
    classify_sentences, 
    filter_activities,
    create_activity_excel,
    get_classification_summary
)

# Page configuration
st.set_page_config(
    page_title="PDF Activity Extractor",
    page_icon="images/IEP icon.jpg",
    layout="centered"
)

def main():
    """Main Streamlit application entry point."""
    st.title("PDF Activity Extractor")
    st.markdown("Upload multiple PDF files to extract sentences and filter for activities.")
    
    # Initialize session state
    if 'upload_files' not in st.session_state:
        st.session_state.upload_files = []
    if 'processing_results' not in st.session_state:
        st.session_state.processing_results = []
    if 'processing_complete' not in st.session_state:
        st.session_state.processing_complete = False
    if 'model' not in st.session_state:
        st.session_state.model = None
    if 'tokenizer' not in st.session_state:
        st.session_state.tokenizer = None
    if 'model_loaded' not in st.session_state:
        st.session_state.model_loaded = False
    if 'classification_results' not in st.session_state:
        st.session_state.classification_results = []
    
    # Load model at startup if not already loaded
    if not st.session_state.model_loaded:
        with st.spinner("Loading activity classification model..."):
            model, tokenizer, success = load_activity_classifier()
            if success:
                st.session_state.model = model
                st.session_state.tokenizer = tokenizer
                st.session_state.model_loaded = True
            else:
                st.error("⚠️ Warning: Activity classification model could not be loaded. Only sentence extraction will be available.")
    
    # File upload section
    uploaded_files = st.file_uploader(
        "Drag and drop PDF files here or click to browse",
        type=['pdf'],
        accept_multiple_files=True,
        key="pdf_uploader"
    )
    
    # Update session state with uploaded files
    if uploaded_files:
        st.session_state.upload_files = uploaded_files
        # Reset processing state when new files are uploaded
        st.session_state.processing_complete = False
        st.session_state.processing_results = []
        st.session_state.classification_results = []
    
    # Display uploaded files and processing button
    if st.session_state.upload_files:
        st.subheader("Uploaded Files")
        for i, file in enumerate(st.session_state.upload_files):
            file_size = format_file_size(file.size)
            st.write(f"**{file.name}** ({file_size})")
        
        # Single button for both extraction and classification
        button_label = "Extract Sentences & Filter Activities" if st.session_state.model_loaded else "Extract Sentences Only"
        if st.button(button_label, type="primary", use_container_width=True):
            process_files_and_classify()
    
    # Show results if processing is complete
    if st.session_state.processing_complete:
        display_all_results()

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    if size_bytes == 0:
        return "0 B"
    size_names = ["B", "KB", "MB", "GB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 1)
    return f"{s} {size_names[i]}"

def check_file_size(file_bytes: bytes, max_size_mb: int = 50) -> bool:
    """Check if file size is within acceptable limits."""
    max_size_bytes = max_size_mb * 1024 * 1024
    return len(file_bytes) <= max_size_bytes

def get_unique_filename(filename: str, existing_names: List[str]) -> str:
    """Generate unique filename if duplicates exist."""
    if filename not in existing_names:
        return filename
    
    base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
    extension = f".{filename.rsplit('.', 1)[1]}" if '.' in filename else ""
    
    counter = 1
    while f"{base_name}#{counter}{extension}" in existing_names:
        counter += 1
    
    return f"{base_name}#{counter}{extension}"

def process_files_and_classify():
    """Process uploaded files and classify if model is available - all in one operation."""
    files = st.session_state.upload_files
    total_files = len(files)
    
    # Initialize progress tracking
    progress_bar = st.progress(0)
    status_placeholder = st.empty()
    file_status_placeholder = st.empty()
    results = []
    processed_names = []
    
    st.markdown("### Processing Files")
    
    # STEP 1: Extract sentences from all PDFs
    for i, file in enumerate(files):
        file_name = file.name
        try:
            file_bytes = file.read()
            file.seek(0)  # Reset file pointer
        except Exception as e:
            file_bytes = b''
            file_name = getattr(file, 'name', f'unknown_file_{i}')
        
        # Generate unique filename
        unique_name = get_unique_filename(file_name, processed_names)
        processed_names.append(unique_name)
        
        # Update main status
        status_placeholder.write(f"Extracting from: **{unique_name}** ({i+1}/{total_files})")
        
        try:
            # Check file size
            if not check_file_size(file_bytes):
                # File too large - create error entry
                error_result = [{
                    'file_name': unique_name,
                    'activity_index': 0,
                    'activity_text': f'File too large: {unique_name}',
                    'page_number': 1,
                    'document_name': unique_name.rsplit('.', 1)[0],
                    'context': '',
                    'error': 'File size exceeds 50MB limit'
                }]
                results.extend(error_result)
            else:
                # Parse the PDF and extract sentences WITH CONTEXT
                parse_results = parse_pdf_bytes(file_bytes, unique_name)
                results.extend(parse_results)
                
                # Update file status with sentence count
                sentence_count = len([r for r in parse_results if r.get('error') is None])
                error_count = len(parse_results) - sentence_count
                
                if sentence_count > 0:
                    file_status_placeholder.write(
                        f"**{unique_name}**: {sentence_count} sentences extracted" + 
                        (f", {error_count} errors" if error_count > 0 else "")
                    )
                else:
                    file_status_placeholder.write(f"**{unique_name}**: No sentences extracted")
            
            # Update progress for extraction
            progress = (i + 1) / (total_files * 2)  # First half of progress
            progress_bar.progress(progress)
                
        except Exception as e:
            # Handle parsing errors
            error_result = [{
                'file_name': unique_name,
                'activity_index': 0,
                'activity_text': f'Error processing: {unique_name}',
                'page_number': 1,
                'document_name': unique_name.rsplit('.', 1)[0],
                'context': '',
                'error': str(e)
            }]
            results.extend(error_result)
            file_status_placeholder.write(f"**{unique_name}**: Processing failed")
            
            # Update progress even on error
            progress = (i + 1) / (total_files * 2)
            progress_bar.progress(progress)
    
    # Store extraction results
    st.session_state.processing_results = results
    
    # STEP 2: Classify sentences if model is available
    if st.session_state.model_loaded and results:
        status_placeholder.write("**Classifying sentences for activities...**")
        
        # Filter out error sentences for classification
        valid_sentences = [r for r in results if r.get('error') is None]
        
        if valid_sentences:
            # Classify sentences
            classified_results, progress_info = classify_sentences(
                valid_sentences, 
                st.session_state.model, 
                st.session_state.tokenizer
            )
            
            # Store classification results
            st.session_state.classification_results = classified_results
            
            # Update progress to complete
            progress_bar.progress(1.0)
            
            # Get summary
            summary = get_classification_summary(classified_results)
            status_placeholder.write(
                f"**Complete!** Extracted {len(results)} sentences, "
                f"found {summary['activities']} activities ({summary['activity_percentage']:.1f}%)"
            )
        else:
            status_placeholder.write("**Extraction Complete!** No valid sentences to classify.")
            st.session_state.classification_results = []
    else:
        # No classification, just extraction
        st.session_state.classification_results = []
        progress_bar.progress(1.0)
        status_placeholder.write(f"**Extraction Complete!** Extracted {len(results)} sentences.")
    
    # Mark processing as complete
    st.session_state.processing_complete = True

def display_all_results():
    """Display all results with download options."""
    extraction_results = st.session_state.processing_results
    classification_results = st.session_state.classification_results
    
    if not extraction_results:
        return
    
    st.markdown("---")
    st.markdown("## Results")
    
    # Calculate summary statistics
    total_sentences = len(extraction_results)
    successful_sentences = len([r for r in extraction_results if r['error'] is None])
    error_sentences = total_sentences - successful_sentences
    unique_files = len(set(r['file_name'] for r in extraction_results))
    
    # Display extraction summary
    st.markdown("### Extraction Summary")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Files", unique_files)
    with col2:
        st.metric("Total Sentences", total_sentences)
    with col3:
        st.metric("Successful", successful_sentences)
    with col4:
        st.metric("Errors", error_sentences)
    
    # Display classification summary if available
    if classification_results:
        summary = get_classification_summary(classification_results)
        st.markdown("### Classification Summary")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Activities Found", summary['activities'])
        with col2:
            st.metric("Non-Activities", summary['non_activities'])
        with col3:
            st.metric("Activity Rate", f"{summary['activity_percentage']:.1f}%")
    
    # Show preview of results
    st.markdown("### Preview (First 10 Sentences)")
    display_data = []
    for r in extraction_results[:10]:
        row_data = {
            'Document': r['document_name'],
            'Page': r['page_number'],
            'Sentence': r['activity_text'][:100] + "..." if len(r['activity_text']) > 100 else r['activity_text'],
            'Status': 'Error' if r['error'] else 'Success'
        }
        
        # Add classification result if available
        if classification_results:
            # Find matching classification result
            matching = [c for c in classification_results if c.get('activity_index') == r.get('activity_index')]
            if matching:
                row_data['Is Activity'] = 'Yes' if matching[0].get('activity_prediction') == 1 else 'No'
        
        display_data.append(row_data)
    
    df_preview = pd.DataFrame(display_data)
    st.dataframe(df_preview, use_container_width=True)
    
    # Download options
    st.markdown("### Download Options")
    
    col1, col2 = st.columns(2)
    
    # Always offer all sentences download
    with col1:
        excel_buffer_all = create_excel_download(extraction_results)
        st.download_button(
            label="📄 Download All Sentences (XLSX)",
            data=excel_buffer_all,
            file_name="pdf_all_sentences.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    
    # Offer activities-only download if classification was done
    with col2:
        if classification_results:
            activities_only = filter_activities(classification_results)
            if activities_only:
                excel_buffer_activities = create_activity_excel(
                    activities_only, 
                    len(extraction_results)
                )
                st.download_button(
                    label="🎯 Download Activities Only (XLSX)",
                    data=excel_buffer_activities,
                    file_name="pdf_activities_only.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    type="primary"
                )
            else:
                st.info("No activities found in the classified sentences.")
        else:
            st.info("Classification not performed. Upload files and process to filter activities.")

def create_excel_download(results: List[Dict[str, Any]]) -> bytes:
    """Create Excel file in memory and return as bytes (for all sentences)."""
    # Create DataFrame from results - exclude context column from output
    output_data = []
    for r in results:
        output_data.append({
            'text_sentence': r['activity_text'],
            'page_number': r['page_number'],
            'document_name': r['document_name'],
            'error': r['error']  # Include error column for debugging
        })
    
    df = pd.DataFrame(output_data)
    
    # Create Excel file in memory
    excel_buffer = io.BytesIO()
    
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='All_Sentences', index=False)
        
        # Get the worksheet to apply formatting
        worksheet = writer.sheets['All_Sentences']
        
        # Adjust column widths
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            
            adjusted_width = min(max_length + 2, 80)  # Cap at 80 characters for text sentences
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    excel_buffer.seek(0)
    return excel_buffer.getvalue()

if __name__ == "__main__":
    main()
    
