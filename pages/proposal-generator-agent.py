import streamlit as st
import os
import tempfile
import sys
from typing import List
from io import StringIO
import importlib.util

# Import from existing files
from pdf_generator import create_formatted_pdf
import sys
sys.path.append('../proposal-creation-agent')
from section_based_agent import SectionBasedProposalGenerator, get_agentic_rag_agent
from agno.document import Document
from agno.document.reader.csv_reader import CSVReader
from agno.document.reader.pdf_reader import PDFReader
from agno.document.reader.text_reader import TextReader

# Page config with wider layout
st.set_page_config(
    page_title="AI Proposal Generator",
    page_icon="📄",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 1rem;
        padding-bottom: 1rem;
        border-bottom: 2px solid #E5E7EB;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #1E3A8A;
        padding-top: 1rem;
        margin-top: 1rem;
    }
    .step-header {
        font-size: 1.2rem;
        color: #2563EB;
        font-weight: 600;
        margin-top: 1rem;
    }
    .info-box {
        background-color: #F3F4F6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .step-box {
        background-color: #F3F4F6;
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1.5rem;
        border-left: 4px solid #2563EB;
    }
    .active-step {
        background-color: #EFF6FF;
        border-left: 4px solid #2563EB;
    }
    .completed-step {
        background-color: #F0FDF4;
        border-left: 4px solid #10B981;
    }
    .inactive-step {
        background-color: #F3F4F6;
        border-left: 4px solid #9CA3AF;
        opacity: 0.7;
    }
    .success-box {
        background-color: #ECFDF5;
        border-left: 4px solid #10B981;
        padding: 1rem;
        border-radius: 0.3rem;
        margin-bottom: 1rem;
    }
    .stButton>button {
        background-color: #2563EB;
        color: white;
        border-radius: 0.3rem;
        padding: 0.5rem 1rem;
        font-weight: 500;
    }
    .stButton>button:hover {
        background-color: #1D4ED8;
    }
    .next-button>button {
        background-color: #059669;
    }
    .next-button>button:hover {
        background-color: #047857;
    }
    .stProgress .st-bo {
        background-color: #2563EB;
    }
    .stTextArea textarea {
        border-radius: 0.3rem;
    }
    .stTextInput input {
        border-radius: 0.3rem;
    }
    .stFileUploader {
        border-radius: 0.3rem;
    }
    .step-progress {
        margin-bottom: 2rem;
    }
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# Initialize all session state variables with default values if they don't exist
if 'initialized' not in st.session_state:
    st.session_state['initialized'] = False
if 'agent' not in st.session_state:
    st.session_state['agent'] = None
if 'wizard_step' not in st.session_state:
    st.session_state['wizard_step'] = 1  # Track the current step in the wizard
if 'proposal_generated' not in st.session_state:
    st.session_state['proposal_generated'] = False
if 'section_being_reviewed' not in st.session_state:
    st.session_state['section_being_reviewed'] = None
if 'current_section_content' not in st.session_state:
    st.session_state['current_section_content'] = None
if 'proposal_sections' not in st.session_state:
    st.session_state['proposal_sections'] = {}
if 'section_index' not in st.session_state:
    st.session_state['section_index'] = 0
if 'sections_completed' not in st.session_state:
    st.session_state['sections_completed'] = False
if 'pdf_generated' not in st.session_state:
    st.session_state['pdf_generated'] = False
if 'pdf_path' not in st.session_state:
    st.session_state['pdf_path'] = None
if 'client_name' not in st.session_state:
    st.session_state['client_name'] = ""
if 'project_name' not in st.session_state:
    st.session_state['project_name'] = ""
if 'requirements_text' not in st.session_state:
    st.session_state['requirements_text'] = ""
if 'interactive' not in st.session_state:
    st.session_state['interactive'] = True
if 'output_dir' not in st.session_state:
    st.session_state['output_dir'] = "proposals"
if 'uploaded_files_processed' not in st.session_state:
    st.session_state['uploaded_files_processed'] = False
if 'proposal_gen' not in st.session_state:
    st.session_state['proposal_gen'] = None
    
def load_documents_to_knowledge_base(uploaded_files, agent) -> bool:
    """Load uploaded documents into the knowledge base."""
    try:
        total_chunks = 0
        processed_files = []
        
        for uploaded_file in uploaded_files:
            temp_path = None
            try:
                # Create a temporary file
                with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    temp_path = tmp_file.name
                
                # Create Document object based on file type
                file_extension = uploaded_file.name.lower().split('.')[-1]
                if file_extension == 'pdf':
                    doc_reader = PDFReader()
                elif file_extension == 'csv':
                    doc_reader = CSVReader()
                elif file_extension == 'txt':
                    doc_reader = TextReader()
                else:
                    continue
                
                documents = doc_reader.read(temp_path)
                if documents:
                    agent.knowledge.load_documents(documents, upsert=True)
                    total_chunks += len(documents)
                    processed_files.append(uploaded_file.name)
                
                # Clean up the temporary file
                os.unlink(temp_path)
                
            except Exception as e:
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)
                continue
        
        if total_chunks > 0:
            st.success(f"Successfully processed {len(processed_files)} files with {total_chunks} chunks added to knowledge base")
            st.session_state['uploaded_files_processed'] = True
        return True
    except Exception as e:
        st.error(f"Error loading documents to knowledge base: {e}")
        return False

def reset_app_state():
    """Reset all proposal-related session state variables while keeping the agent."""
    agent = st.session_state['agent']
    initialized = st.session_state['initialized']
    
    # Reset all workflow variables
    st.session_state['wizard_step'] = 1
    st.session_state['proposal_generated'] = False
    st.session_state['section_being_reviewed'] = None
    st.session_state['current_section_content'] = None
    st.session_state['proposal_sections'] = {}
    st.session_state['section_index'] = 0
    st.session_state['sections_completed'] = False
    st.session_state['pdf_generated'] = False
    st.session_state['pdf_path'] = None
    st.session_state['client_name'] = ""
    st.session_state['project_name'] = ""
    st.session_state['requirements_text'] = ""
    st.session_state['interactive'] = True
    st.session_state['uploaded_files_processed'] = False
    st.session_state['proposal_gen'] = None
    
    # Keep the initialized state and agent
    st.session_state['initialized'] = initialized
    st.session_state['agent'] = agent

def generate_proposal():
    """Start the proposal generation process"""
    if not st.session_state['client_name'].strip():
        st.warning("Please enter a client name.")
        return False
    elif not st.session_state['requirements_text'].strip():
        st.warning("Please enter client requirements.")
        return False
    else:
        # Create output directory
        os.makedirs(st.session_state['output_dir'], exist_ok=True)
        
        # Initialize proposal generator
        st.session_state['proposal_gen'] = SectionBasedProposalGenerator(st.session_state['agent'])
        
        if not st.session_state['interactive']:
            # Generate all sections at once (non-interactive mode)
            with st.spinner("Generating proposal sections..."):
                st.session_state['proposal_sections'] = st.session_state['proposal_gen'].generate_all_sections(
                    requirements_text=st.session_state['requirements_text'],
                    interactive=False
                )
            st.session_state['proposal_generated'] = True
            st.session_state['sections_completed'] = True
            st.session_state['wizard_step'] = 4  # Skip to review sections
        else:
            # Mark as ready to start generating sections interactively
            st.session_state['proposal_generated'] = True
            st.session_state['section_index'] = 0
            st.session_state['wizard_step'] = 3  # Go to interactive section review
        
        return True

# Title with custom styling
st.markdown('<h1 class="main-header">AI Proposal Generator</h1>', unsafe_allow_html=True)

# Initialize AI agent if not already done
if not st.session_state['initialized']:
    with st.spinner("Initializing AI agent..."):
        try:
            st.session_state['agent'] = get_agentic_rag_agent()
            st.session_state['initialized'] = True
        except Exception as e:
            st.error(f"Error initializing AI agent: {str(e)}")

# Display wizard step progress
if st.session_state['initialized'] and not st.session_state['pdf_generated']:
    if st.session_state['proposal_generated'] and not st.session_state['sections_completed']:
        step = 3
    elif st.session_state['sections_completed'] and not st.session_state['pdf_generated']:
        step = 4
    else:
        step = st.session_state['wizard_step']
        
    # Display progress indicator
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            f"""<div class="{'active-step' if step == 1 else 'completed-step' if step > 1 else 'inactive-step'} step-box">
                <h3>Step 1: Knowledge Base</h3>
                <p>Upload reference documents for context</p>
            </div>""", 
            unsafe_allow_html=True
        )
    with col2:
        st.markdown(
            f"""<div class="{'active-step' if step == 2 else 'completed-step' if step > 2 else 'inactive-step'} step-box">
                <h3>Step 2: Requirements</h3>
                <p>Enter client info and project details</p>
            </div>""", 
            unsafe_allow_html=True
        )
    with col3:
        st.markdown(
            f"""<div class="{'active-step' if step == 3 else 'completed-step' if step > 3 else 'inactive-step'} step-box">
                <h3>Step 3: Generate & Review</h3>
                <p>Edit and approve proposal sections</p>
            </div>""", 
            unsafe_allow_html=True
        )
    with col4:
        st.markdown(
            f"""<div class="{'active-step' if step == 4 else 'completed-step' if step > 4 else 'inactive-step'} step-box">
                <h3>Step 4: Finalize</h3>
                <p>Create and download the PDF</p>
            </div>""", 
            unsafe_allow_html=True
        )

# STEP 1: Knowledge Base (Upload Files)
if st.session_state['initialized'] and st.session_state['wizard_step'] == 1:
    st.markdown('<h2 class="sub-header">Step 1: Knowledge Base</h2>', unsafe_allow_html=True)
    
    st.markdown('<div class="info-box">Upload any relevant documents that can help the AI understand your business and create better proposals. This step is optional - you can skip if you don\'t have any documents to upload.</div>', unsafe_allow_html=True)
    
    uploaded_files = st.file_uploader("Upload reference files", 
                                     accept_multiple_files=True,
                                     type=["pdf", "csv", "txt"])
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if uploaded_files and st.button("Process Files", key="process_files"):
            load_documents_to_knowledge_base(uploaded_files, st.session_state['agent'])
    
    with col2:
        # Show the Next button (styled in a different color)
        if st.button("Next: Client Requirements →", key="next_to_step2", type="primary"):
            st.session_state['wizard_step'] = 2
            st.rerun()

# STEP 2: Client Information and Requirements
elif st.session_state['initialized'] and st.session_state['wizard_step'] == 2:
    st.markdown('<h2 class="sub-header">Step 2: Client Requirements</h2>', unsafe_allow_html=True)
    
    st.markdown('<div class="info-box">Enter information about your client and their project requirements. Be as detailed as possible to help the AI generate a tailored proposal.</div>', unsafe_allow_html=True)
    
    # Client Information
    col1, col2 = st.columns([1, 1])
    with col1:
        client_name = st.text_input("Client Name", 
                                    value=st.session_state['client_name'],
                                    placeholder="Enter client name")
    with col2:
        project_name = st.text_input("Project Name (optional)", 
                                    value=st.session_state['project_name'],
                                    placeholder="Enter project name")
    
    # Requirements
    st.markdown('<h3 class="step-header">Project Requirements</h3>', unsafe_allow_html=True)
    st.markdown("Describe the client's needs, project scope, budget constraints, timeline, and any other relevant details.")
    
    # Let user choose between text input or file upload for requirements
    req_input_method = st.radio(
        "How would you like to provide the requirements?",
        options=["Enter Text", "Upload File"],
        horizontal=True
    )
    
    if req_input_method == "Enter Text":
        requirements_text = st.text_area(
            "Client Requirements",
            value=st.session_state['requirements_text'],
            height=200,
            placeholder="Type the client requirements here..."
        )
    else:
        req_file = st.file_uploader("Upload requirements document", type=["txt", "pdf", "docx"], key="req_file")
        if req_file is not None:
            # Process the uploaded file
            file_extension = req_file.name.lower().split('.')[-1]
            
            try:
                # Create temporary file
                with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                    tmp_file.write(req_file.getvalue())
                    temp_path = tmp_file.name
                
                if file_extension == 'pdf':
                    doc_reader = PDFReader()
                    documents = doc_reader.read(temp_path)
                    if documents:
                        requirements_text = '\n\n'.join([doc.content for doc in documents])
                elif file_extension == 'txt':
                    with open(temp_path, 'r') as f:
                        requirements_text = f.read()
                elif file_extension == 'docx':
                    st.warning("DOCX support is limited. Plain text will be extracted but formatting may be lost.")
                    try:
                        # Simple docx text extraction
                        import docx
                        doc = docx.Document(temp_path)
                        requirements_text = '\n\n'.join([para.text for para in doc.paragraphs])
                    except Exception as e:
                        st.error(f"Error reading DOCX file: {str(e)}")
                        requirements_text = ""
                else:
                    requirements_text = ""
                
                # Clean up temp file
                os.unlink(temp_path)
                
                # Display the extracted text and allow editing
                requirements_text = st.text_area(
                    "Extracted Requirements (edit if needed)",
                    value=requirements_text,
                    height=300
                )
                
            except Exception as e:
                st.error(f"Error reading file: {str(e)}")
                requirements_text = ""
        else:
            requirements_text = st.session_state['requirements_text']
    
    # Output Directory and Options
    col1, col2 = st.columns([3, 1])
    with col1:
        interactive = st.checkbox("Review each section interactively", 
                                value=st.session_state['interactive'], 
                                help="If selected, you'll be able to review and edit each section of the proposal before finalizing.")
    with col2:
        output_dir = st.text_input("Output Directory", 
                                  value=st.session_state['output_dir'], 
                                  help="Directory where the final PDF will be saved")
    
    # Navigation buttons
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("← Back", key="back_to_step1"):
            st.session_state['wizard_step'] = 1
            st.rerun()
    
    with col3:
        # Save entered data and start generation
        if st.button("Generate Proposal →", type="primary", key="generate_proposal"):
            # Save input values to session state
            st.session_state['client_name'] = client_name
            st.session_state['project_name'] = project_name
            st.session_state['requirements_text'] = requirements_text
            st.session_state['interactive'] = interactive
            st.session_state['output_dir'] = output_dir
            
            if generate_proposal():
                st.rerun()

# STEP 3: Interactive Section Generation
elif st.session_state['initialized'] and st.session_state['proposal_generated'] and not st.session_state['sections_completed'] and st.session_state['interactive']:
    st.markdown('<h2 class="sub-header">Step 3: Review Proposal Sections</h2>', unsafe_allow_html=True)
    
    # Get the proposal generator sections
    all_sections = st.session_state['proposal_gen'].sections
    
    # If we haven't started this section yet
    if st.session_state['section_being_reviewed'] is None:
        current_section = all_sections[st.session_state['section_index']]
        
        with st.spinner(f"Generating '{current_section}' section..."):
            # Process requirements
            req_input = st.session_state['proposal_gen'].get_requirements_prompt(st.session_state['requirements_text'])
            
            # Generate this section content
            section_content = st.session_state['proposal_gen'].generate_section(
                section_name=current_section,
                req_input=req_input
            )
            
            # Save the current section being reviewed
            st.session_state['section_being_reviewed'] = current_section
            st.session_state['current_section_content'] = section_content
            
            st.rerun()
    
    # Display the current section for review
    current_section = st.session_state['section_being_reviewed']
    section_content = st.session_state['current_section_content']
    
    # Progress bar and section counter
    progress = (st.session_state['section_index'] + 1) / len(all_sections)
    st.progress(progress)
    st.write(f"Reviewing section {st.session_state['section_index'] + 1} of {len(all_sections)}: **{current_section}**")
    
    # Display section content in a framed box
    st.markdown(f"### {current_section}")
    
    # Editor for content
    edited_content = st.text_area(
        "Review and edit the generated content:",
        value=section_content,
        height=400
    )
    
    # Action buttons in columns
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        # First show a button to open feedback form
        if st.button("⟲ Regenerate Section", use_container_width=True):
            st.session_state['show_regenerate_feedback'] = True
            st.rerun()
    
    # Show feedback form if button was clicked
    if st.session_state.get('show_regenerate_feedback', False):
        feedback = st.text_area(
            "What would you like to change in this section?",
            placeholder="e.g., Make it more formal, add more details about X, focus more on Y, etc.",
            key="section_feedback"
        )
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Cancel", use_container_width=True):
                st.session_state['show_regenerate_feedback'] = False
                st.rerun()
        with col2:
            if st.button("Submit & Regenerate", use_container_width=True, type="primary"):
                if feedback:
                    with st.spinner(f"Regenerating '{current_section}' section..."):
                        # Process requirements with feedback
                        req_input = st.session_state['proposal_gen'].get_requirements_prompt(
                            st.session_state['requirements_text']
                        )
                        # Append feedback to requirements
                        req_input += f"\n\nAdditional Requirements for this section:\n{feedback}"
                        
                        # Generate new section content
                        section_content = st.session_state['proposal_gen'].generate_section(
                            section_name=current_section,
                            req_input=req_input
                        )
                        
                        # Update session state
                        st.session_state['current_section_content'] = section_content
                        st.session_state['show_regenerate_feedback'] = False
                        st.rerun()
                else:
                    st.warning("Please provide feedback for regeneration.")
    
    with col2:
        if st.button("✓ Approve Section", use_container_width=True, type="primary"):
            # Save the approved section
            st.session_state['proposal_sections'][current_section] = edited_content
            
            # Move to the next section or finish
            st.session_state['section_index'] += 1
            if st.session_state['section_index'] >= len(all_sections):
                st.session_state['sections_completed'] = True
                st.session_state['wizard_step'] = 4
            else:
                st.session_state['section_being_reviewed'] = None
                st.session_state['current_section_content'] = None
            
            st.rerun()
    
    with col3:
        if st.button("Skip to Final PDF →", use_container_width=True):
            # Save the current section
            st.session_state['proposal_sections'][current_section] = edited_content
            
            # Generate any remaining sections without interaction
            remaining_sections = all_sections[st.session_state['section_index']+1:]
            
            if remaining_sections:
                with st.spinner("Generating remaining sections..."):
                    # Process requirements once
                    req_input = st.session_state['proposal_gen'].get_requirements_prompt(st.session_state['requirements_text'])
                    
                    for section_name in remaining_sections:
                        section_content = st.session_state['proposal_gen'].generate_section(
                            section_name=section_name,
                            req_input=req_input
                        )
                        st.session_state['proposal_sections'][section_name] = section_content
            
            st.session_state['sections_completed'] = True
            st.session_state['wizard_step'] = 4
            st.rerun()

# STEP 4: Generate PDF and Finalize
elif st.session_state['initialized'] and st.session_state['sections_completed'] and not st.session_state['pdf_generated']:
    st.markdown('<h2 class="sub-header">Step 4: Finalize Proposal</h2>', unsafe_allow_html=True)
    
    st.markdown('<div class="success-box">All proposal sections have been generated! Review them below before generating the final PDF.</div>', unsafe_allow_html=True)
    
    # Show all sections in expandable containers with better styling
    for i, (section_name, content) in enumerate(st.session_state['proposal_sections'].items()):
        with st.expander(f"Section {i+1}: {section_name}", expanded=False):
            st.markdown(content)
    
    # Navigation and generation buttons
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        if st.button("← Back to Edit", key="back_to_edit"):
            # Reset to editing mode
            st.session_state['sections_completed'] = False
            st.session_state['section_index'] = 0
            st.session_state['section_being_reviewed'] = None
            st.session_state['current_section_content'] = None
            st.session_state['wizard_step'] = 3
            st.rerun()
    
    with col2:
        if st.button("Generate Final PDF", use_container_width=True, type="primary"):
            with st.spinner("Generating PDF..."):
                try:
                    # Convert sections to markdown format
                    markdown_content = f"# Proposal for {st.session_state['client_name']}\n\n"
                    if st.session_state['project_name']:
                        markdown_content += f"## {st.session_state['project_name']}\n\n"
                    
                    for section_name, content in st.session_state['proposal_sections'].items():
                        markdown_content += f"## {section_name}\n\n{content}\n\n"
                    
                    # Generate PDF with simplified options
                    pdf_buffer = create_formatted_pdf(markdown_content)
                    
                    # Save the PDF to a file
                    os.makedirs(st.session_state['output_dir'], exist_ok=True)
                    
                    # Create a nicer filename
                    client_part = st.session_state['client_name'].lower().replace(' ', '_')
                    project_part = ""
                    if st.session_state['project_name']:
                        project_part = f"_{st.session_state['project_name'].lower().replace(' ', '_')}"
                    
                    pdf_path = os.path.join(
                        st.session_state['output_dir'], 
                        f"proposal_{client_part}{project_part}.pdf"
                    )
                    
                    with open(pdf_path, 'wb') as f:
                        f.write(pdf_buffer.getvalue())
                    
                    st.session_state['pdf_path'] = pdf_path
                    st.session_state['pdf_generated'] = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Error generating PDF: {str(e)}")

# FINAL STEP: Display PDF download option
elif st.session_state['initialized'] and st.session_state['pdf_generated']:
    st.markdown('<h2 class="sub-header">Proposal Complete! 🎉</h2>', unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="success-box">
        <h3>Proposal Generated Successfully</h3>
        <p>Your proposal has been generated and saved to: <code>{st.session_state['pdf_path']}</code></p>
    </div>
    """, unsafe_allow_html=True)
    
    # PDF preview and download options
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Download button with styling
        try:
            with open(st.session_state['pdf_path'], "rb") as file:
                st.download_button(
                    label="📥 Download Proposal PDF",
                    data=file,
                    file_name=os.path.basename(st.session_state['pdf_path']),
                    mime="application/pdf",
                    use_container_width=True,
                    type="primary"
                )
        except Exception as e:
            st.error(f"Error reading PDF file: {str(e)}")
    
    with col2:
        # Start over button
        if st.button("🔄 Create New Proposal", use_container_width=True):
            # Reset app state while keeping the agent
            reset_app_state()
            st.rerun()
