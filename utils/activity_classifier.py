import os
import torch
import logging
import streamlit as st
from pathlib import Path
from typing import List, Dict, Any, Optional
from transformers import BertTokenizer, BertForSequenceClassification
import pandas as pd

logger = logging.getLogger(__name__)

@st.cache_resource
def load_activity_classifier():
    """
    Load the trained BERT activity classifier.
    Cached to avoid reloading on every use.
    
    Returns:
        tuple: (model, tokenizer, success_flag)
    """
    try:
        # Get model path relative to this file
        current_dir = Path(__file__).parent.parent
        model_path = current_dir / "models"
        
        st.info("Loading activity classification model...")
        
        if not model_path.exists():
            st.error(f"Model directory not found: {model_path}")
            return None, None, False
        
        # Check for required model files
        required_files = ['config.json', 'model.safetensors', 'tokenizer_config.json']
        missing_files = [f for f in required_files if not (model_path / f).exists()]
        
        if missing_files:
            st.error(f"Missing model files: {missing_files}")
            return None, None, False
        
        # Load tokenizer and model
        tokenizer = BertTokenizer.from_pretrained(str(model_path))
        model = BertForSequenceClassification.from_pretrained(str(model_path))
        
        # Set to evaluation mode
        model.eval()
        
        # Use CPU for Streamlit Cloud compatibility
        device = torch.device('cpu')
        model.to(device)
        
        st.success("Activity classification model loaded successfully!")
        logger.info(f"Model loaded from: {model_path}")
        logger.info(f"Using device: {device}")
        
        return model, tokenizer, True
        
    except Exception as e:
        error_msg = f"Failed to load activity classification model: {str(e)}"
        st.error(f"{error_msg}")
        logger.error(error_msg)
        return None, None, False

def classify_sentences(sentences_data: List[Dict[str, Any]], 
                      model, tokenizer, 
                      batch_size: int = 16) -> List[Dict[str, Any]]:
    """
    Classify sentences as activities (1) or non-activities (0) using the trained model.
    
    Args:
        sentences_data: List of sentence dictionaries with 'activity_text' and 'context'
        model: Loaded BERT model
        tokenizer: Loaded BERT tokenizer  
        batch_size: Batch size for processing (smaller for memory efficiency)
        
    Returns:
        List of sentence dictionaries with added 'activity_prediction' field
    """
    if not sentences_data:
        return []
    
    try:
        device = next(model.parameters()).device
        
        # Prepare texts for classification using context-enhanced format
        enhanced_texts = []
        for sent_data in sentences_data:
            text = sent_data.get('activity_text', '')
            context = sent_data.get('context', '')
            
            # Use context-enhanced format matching the trainer
            if context and len(context.strip()) > 3:
                enhanced_text = f"{text} [ACTIVITY CONTEXT: {context}]"
            else:
                enhanced_text = text
                
            enhanced_texts.append(enhanced_text)
        
        # Process in batches for memory efficiency
        all_predictions = []
        total_batches = (len(enhanced_texts) + batch_size - 1) // batch_size
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i in range(0, len(enhanced_texts), batch_size):
            batch_texts = enhanced_texts[i:i + batch_size]
            batch_num = i // batch_size + 1
            
            status_text.text(f"Classifying batch {batch_num}/{total_batches} ({len(batch_texts)} sentences)")
            
            # Tokenize batch
            encodings = tokenizer(
                batch_texts,
                truncation=True,
                padding=True,
                max_length=128,  # Match training settings
                return_tensors='pt'
            )
            
            # Move to device
            input_ids = encodings['input_ids'].to(device)
            attention_mask = encodings['attention_mask'].to(device)
            
            # Get predictions
            with torch.no_grad():
                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                predictions = torch.argmax(outputs.logits, dim=-1)
                batch_predictions = predictions.cpu().numpy().tolist()
            
            all_predictions.extend(batch_predictions)
            
            # Update progress
            progress = min(1.0, (i + batch_size) / len(enhanced_texts))
            progress_bar.progress(progress)
        
        # Clear progress indicators
        progress_bar.empty()
        status_text.empty()
        
        # Add predictions to sentence data
        results = []
        for i, sent_data in enumerate(sentences_data):
            result = sent_data.copy()
            result['activity_prediction'] = all_predictions[i] if i < len(all_predictions) else 0
            results.append(result)
        
        return results
        
    except Exception as e:
        st.error(f"Classification failed: {str(e)}")
        logger.error(f"Classification error: {str(e)}")
        
        # Return original data with no predictions on error
        return [dict(sent_data, activity_prediction=0) for sent_data in sentences_data]

def filter_activities(sentences_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter sentences to only those classified as activities (prediction = 1).
    
    Args:
        sentences_data: List of sentence dictionaries with 'activity_prediction'
        
    Returns:
        List of sentences classified as activities
    """
    activities = [
        sent_data for sent_data in sentences_data 
        if sent_data.get('activity_prediction', 0) == 1
    ]
    
    logger.info(f"Filtered {len(activities)} activities from {len(sentences_data)} total sentences")
    return activities

def create_activity_excel(filtered_sentences: List[Dict[str, Any]], 
                         original_total: int) -> bytes:
    """
    Create Excel file containing only sentences classified as activities.
    
    Args:
        filtered_sentences: List of activity sentences
        original_total: Total number of sentences before filtering
        
    Returns:
        bytes: Excel file content
    """
    # Create DataFrame with essential columns only (no context, no prediction scores)
    output_data = []
    for sent_data in filtered_sentences:
        output_data.append({
            'text_sentence': sent_data.get('activity_text', ''),
            'page_number': sent_data.get('page_number', 1),
            'document_name': sent_data.get('document_name', ''),
            'error': sent_data.get('error', None)
        })
    
    df = pd.DataFrame(output_data)
    
    # Create Excel file in memory
    import io
    excel_buffer = io.BytesIO()
    
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        # Write main data
        df.to_excel(writer, sheet_name='Activities_Only', index=False)
        
        # Add summary sheet
        summary_df = pd.DataFrame({
            'Metric': ['Total Sentences Processed', 'Activities Found', 'Activity Percentage'],
            'Value': [original_total, len(filtered_sentences), 
                     f"{len(filtered_sentences)/original_total*100:.1f}%" if original_total > 0 else "0%"]
        })
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # Format main sheet
        worksheet = writer.sheets['Activities_Only']
        
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
            
            adjusted_width = min(max_length + 2, 80)  # Cap at 80 characters
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    excel_buffer.seek(0)
    return excel_buffer.getvalue()

def get_classification_summary(sentences_data: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Get summary statistics of classification results.
    
    Args:
        sentences_data: List of sentence dictionaries with predictions
        
    Returns:
        Dictionary with classification statistics
    """
    total = len(sentences_data)
    activities = len([s for s in sentences_data if s.get('activity_prediction', 0) == 1])
    non_activities = total - activities
    
    return {
        'total_sentences': total,
        'activities': activities,
        'non_activities': non_activities,
        'activity_percentage': (activities / total * 100) if total > 0 else 0
    }
    
