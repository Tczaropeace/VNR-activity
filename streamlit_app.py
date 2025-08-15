import streamlit as st
import pandas as pd
import io
from typing import List, Dict, Any
from utils.parser import parse_pdf_bytes

# Page configuration
st.set_page_config(
    page_title="PDF Activity Extractor",
    page_icon="📄",
    layout="centered"
)

def main():
    """Main Streamlit application entry point."""
    st.title("📄 PDF Activity Extractor")
    st.markdown("Upload multiple PDF files to extract activities and download results as Excel.")
    
    # Initialize session state
    if 'upload_files' not in st.session_state:
        st.session_state.upload_files = []
    if 'processing_results' not in st.session_state:
        st.session_state.processing_results = []
    if 'processing_complete' not in st.session_state:
        st.session_state.processing_complete = False
    
    # Custom CSS for drag-and-drop card
    st.markdown("""
    <style>
    .upload-card {
        border: 2px dashed #cccccc;
        border-radius: 10px;
        padding: 2rem;
        text-align: center;
        background-color: #f8f9fa;
        margin: 1rem 0;
        transition: border-color 0.3s ease;
    }
    .upload-card:hover {
        border-color: #007bff;
        background-color: #f0f8ff;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # File upload section
    st.markdown('<div class="upload-card">', unsafe_allow_html=True)
    uploaded_files = st.file_uploader(
        "Drag and drop PDF files here or click to browse",
        type=['pdf'],
        accept_multiple_files=True,
        key="pdf_uploader"
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Demo data button for testing
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Use Demo Data"):
            st.session_state.upload_files = create_demo_files()
            st.session_state.processing_complete = False
            st.session_state.processing_results = []
            st.rerun()
    
    # Update session state with uploaded files
    if uploaded_files:
        st.session_state.upload_files = uploaded_files
        st.session_state.processing_complete = False
        st.session_state.processing_results = []
    
    # Display uploaded files
    if st.session_state.upload_files:
        st.subheader("📁 Uploaded Files")
        for i, file in enumerate(st.session_state.upload_files):
            if hasattr(file, 'size'):  # Real uploaded file
                file_size = format_file_size(file.size)
                st.write(f"**{file.name}** ({file_size})")
            else:  # Demo file
                st.write(f"**{file['name']}** ({file['size']})")
        
        # Confirm & Extract button
        if st.button("🚀 Confirm & Extract", type="primary", use_container_width=True):
            process_files()
    
    # Show results if processing is complete
    if st.session_state.processing_complete and st.session_state.processing_results:
        display_results()

def create_demo_files() -> List[Dict[str, Any]]:
    """Create demo file objects for testing purposes."""
    return [
        {'name': 'sample_document_1.pdf', 'size': '1.2 MB', 'bytes': b'demo_content_1'},
        {'name': 'report_2024.pdf', 'size': '0.8 MB', 'bytes': b'demo_content_2'},
        {'name': 'meeting_notes.pdf', 'size': '0.5 MB', 'bytes': b'demo_content_3'}
    ]

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
    results = []
    processed_names = []
    
    st.markdown("### 🔄 Processing Files")
    
    for i, file in enumerate(files):
        # Determine file properties based on type (real upload vs demo)
        if hasattr(file, 'read'):  # Real uploaded file
            file_name = file.name
            try:
                file_bytes = file.read()
                file.seek(0)  # Reset file pointer
            except Exception as e:
                file_bytes = b''
                file_name = getattr(file, 'name', f'unknown_file_{i}')
        else:  # Demo file
            file_name = file['name']
            file_bytes = file['bytes']
        
        # Generate unique filename
        unique_name = get_unique_filename(file_name, processed_names)
        processed_names.append(unique_name)
        
        # Update status
        status_placeholder.write(f"📝 Processing: **{unique_name}** ({i+1}/{total_files})")
        
        try:
            with st.spinner(f"Parsing {unique_name}..."):
                # Check file size
                if not check_file_size(file_bytes):
                    # File too large - create error entry
                    error_result = [{
                        'file_name': unique_name,
                        'activity_index': 0,
                        'activity_text': f'File too large: {unique_name}',
                        'error': 'File size exceeds 50MB limit'
                    }]
                    results.extend(error_result)
                else:
                    # Parse the PDF
                    parse_results = parse_pdf_bytes(file_bytes, unique_name)
                    results.extend(parse_results)
                
                # Update progress
                progress = (i + 1) / total_files
                progress_bar.progress(progress)
                
        except Exception as e:
            # Handle parsing errors
            error_result = [{
                'file_name': unique_name,
                'activity_index': 0,
                'activity_text': f'Error processing: {unique_name}',
                'error': str(e)
            }]
            results.extend(error_result)
            
            # Update progress even on error
            progress = (i + 1) / total_files
            progress_bar.progress(progress)
    
    # Complete processing
    status_placeholder.write("✅ **Processing Complete!**")
    st.session_state.processing_results = results
    st.session_state.processing_complete = True

def display_results():
    """Display processing results and provide download option."""
    results = st.session_state.processing_results
    
    st.markdown("### 📊 Results Summary")
    
    # Calculate summary statistics
    total_activities = len(results)
    successful_activities = len([r for r in results if r['error'] is None])
    error_activities = total_activities - successful_activities
    unique_files = len(set(r['file_name'] for r in results))
    
    # Display summary
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Files", unique_files)
    with col2:
        st.metric("Total Activities", total_activities)
    with col3:
        st.metric("Successful", successful_activities)
    with col4:
        st.metric("Errors", error_activities)
    
    # Show preview of results
    if results:
        st.markdown("### 📋 Preview (First 10 Rows)")
        df_preview = pd.DataFrame(results).head(10)
        st.dataframe(df_preview, use_container_width=True)
        
        # Create and offer download
        excel_buffer = create_excel_download(results)
        
        st.markdown("### 💾 Download Results")
        st.download_button(
            label="📥 Download XLSX",
            data=excel_buffer,
            file_name="pdf_activity_extraction_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

def create_excel_download(results: List[Dict[str, Any]]) -> bytes:
    """Create Excel file in memory and return as bytes."""
    # Create DataFrame from results
    df = pd.DataFrame(results)
    
    # Create Excel file in memory
    excel_buffer = io.BytesIO()
    
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Activity_Extraction', index=False)
        
        # Get the worksheet to apply formatting
        worksheet = writer.sheets['Activity_Extraction']
        
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
            
            adjusted_width = min(max_length + 2, 50)  # Cap at 50 characters
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    excel_buffer.seek(0)
    return excel_buffer.getvalue()

if __name__ == "__main__":
    main()
