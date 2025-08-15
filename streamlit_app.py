import streamlit as st
import pandas as pd
import io
from typing import List, Dict, Any
from utils.parser import parse_pdf_bytes

# Page configuration
st.set_page_config(
    page_title="PDF Sentence Extractor",
    page_icon=st.set_page_config(page_icon="images/IEP icon.jpg")
    layout="centered"
)

def main():
    """Main Streamlit application entry point."""
    st.title("PDF Sentence Extractor")
    st.markdown("Upload multiple PDF files to extract sentences and download results as Excel.")
    
    # Initialize session state
    if 'upload_files' not in st.session_state:
        st.session_state.upload_files = []
    if 'processing_results' not in st.session_state:
        st.session_state.processing_results = []
    if 'processing_complete' not in st.session_state:
        st.session_state.processing_complete = False
    
    # File upload section
    st.markdown('<div class="upload-card">', unsafe_allow_html=True)
    uploaded_files = st.file_uploader(
        "Drag and drop PDF files here or click to browse",
        type=['pdf'],
        accept_multiple_files=True,
        key="pdf_uploader"
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Update session state with uploaded files
    if uploaded_files:
        st.session_state.upload_files = uploaded_files
        st.session_state.processing_complete = False
        st.session_state.processing_results = []
    
    # Display uploaded files
    if st.session_state.upload_files:
        st.subheader("Uploaded Files")
        for i, file in enumerate(st.session_state.upload_files):
            if hasattr(file, 'size'):  # Real uploaded file
                file_size = format_file_size(file.size)
                st.write(f"**{file.name}** ({file_size})")
        
        # Confirm & Extract button
        if st.button("Extract Sentences", type="primary", use_container_width=True):
            process_files()
    
    # Show results if processing is complete
    if st.session_state.processing_complete and st.session_state.processing_results:
        display_results()

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

def process_files():
    """Process uploaded files sequentially with progress tracking."""
    files = st.session_state.upload_files
    total_files = len(files)
    
    # Initialize progress tracking
    progress_bar = st.progress(0)
    status_placeholder = st.empty()
    file_status_placeholder = st.empty()
    results = []
    processed_names = []
    
    st.markdown("### Processing Files")
    
    for i, file in enumerate(files):
        # Determine file properties based on type (real upload)
        if hasattr(file, 'read'):  # Real uploaded file
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
        status_placeholder.write(f"Processing: **{unique_name}** ({i+1}/{total_files})")
        
        try:
            with st.spinner(f"Extracting sentences from {unique_name}..."):
                # Check file size
                if not check_file_size(file_bytes):
                    # File too large - create error entry
                    error_result = [{
                        'file_name': unique_name,
                        'activity_index': 0,
                        'activity_text': f'File too large: {unique_name}',
                        'page_number': 1,
                        'document_name': unique_name.rsplit('.', 1)[0],
                        'error': 'File size exceeds 50MB limit'
                    }]
                    results.extend(error_result)
                else:
                    # Parse the PDF and extract sentences
                    # SENTENCE PARSING OCCURS HERE - uses new sentence-based processing
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
                        file_status_placeholder.write(f"⚠**{unique_name}**: No sentences extracted")
                
                # Update progress
                progress = (i + 1) / total_files
                progress_bar.progress(progress)
                
        except Exception as e:
            # Handle parsing errors
            error_result = [{
                'file_name': unique_name,
                'activity_index': 0,
                'activity_text': f'Error processing: {unique_name}',
                'page_number': 1,
                'document_name': unique_name.rsplit('.', 1)[0],
                'error': str(e)
            }]
            results.extend(error_result)
            file_status_placeholder.write(f"**{unique_name}**: Processing failed")
            
            # Update progress even on error
            progress = (i + 1) / total_files
            progress_bar.progress(progress)
    
    # Complete processing
    status_placeholder.write("**Processing Complete!**")
    st.session_state.processing_results = results
    st.session_state.processing_complete = True

def display_results():
    """Display processing results and provide download option."""
    results = st.session_state.processing_results
    
    st.markdown("### Results Summary")
    
    # Calculate summary statistics
    total_sentences = len(results)
    successful_sentences = len([r for r in results if r['error'] is None])
    error_sentences = total_sentences - successful_sentences
    unique_files = len(set(r['file_name'] for r in results))
    
    # Display summary
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Files", unique_files)
    with col2:
        st.metric("Total Sentences", total_sentences)
    with col3:
        st.metric("Successful", successful_sentences)
    with col4:
        st.metric("Errors", error_sentences)
    
    # Show preview of results
    if results:
        st.markdown("### Preview (First 10 Sentences)")
        # Create display DataFrame with only the columns we want to show
        display_data = []
        for r in results[:10]:
            display_data.append({
                'Document': r['document_name'],
                'Page': r['page_number'],
                'Sentence': r['activity_text'][:100] + "..." if len(r['activity_text']) > 100 else r['activity_text'],
                'Status': 'Error' if r['error'] else 'Success'
            })
        
        df_preview = pd.DataFrame(display_data)
        st.dataframe(df_preview, use_container_width=True)
        
        # Create and offer download
        excel_buffer = create_excel_download(results)
        
        st.markdown("### Download Results")
        st.download_button(
            label="Download XLSX",
            data=excel_buffer,
            file_name="pdf_sentence_extraction_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

def create_excel_download(results: List[Dict[str, Any]]) -> bytes:
    """Create Excel file in memory and return as bytes."""
    # Create DataFrame from results - only include the columns we want in output
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
        df.to_excel(writer, sheet_name='Sentence_Extraction', index=False)
        
        # Get the worksheet to apply formatting
        worksheet = writer.sheets['Sentence_Extraction']
        
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
