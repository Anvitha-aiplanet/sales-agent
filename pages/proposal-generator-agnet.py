import streamlit as st
import os
import tempfile
import sys
from typing import List
from io import StringIO

# Import from existing files
from pdf_generator import create_formatted_pdf
import sys
sys.path.append('../proposal-creation-agent')
from section_based_agent import SectionBasedProposalGenerator, get_agentic_rag_agent
from agno.document import Document
from agno.document.reader.csv_reader import CSVReader
from agno.document.reader.pdf_reader import PDFReader
from agno.document.reader.text_reader import TextReader

# Page config
st.set_page_config(page_title="AI Proposal Generator", page_icon="📄")

# Initialize session state
if 'initialized' not in st.session_state:
    st.session_state.initialized = False
    st.session_state.agent = None
    st.session_state.proposal_generated = False
    st.session_state.section_being_reviewed = None
    st.session_state.current_section_content = None
    st.session_state.proposal_sections = {}
    st.session_state.section_index = 0
    st.session_state.sections_completed = False
    st.session_state.pdf_generated = False
    st.session_state.pdf_path = None
    
def load_documents_to_knowledge_base(uploaded_files, agent) -> bool:
    """Load uploaded documents into the knowledge base."""
    try:
        for uploaded_file in uploaded_files:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as temp_file:
                temp_file.write(uploaded_file.getvalue())
                temp_path = temp_file.name
            
            st.info(f"Adding {uploaded_file.name} to knowledge base...")
            
            # Determine file type and use appropriate reader
            if temp_path.endswith('.pdf'):
                reader = PDFReader()
                documents = reader.read(temp_path)
            elif temp_path.endswith('.csv'):
                reader = CSVReader()
                documents = reader.read(temp_path)
            else:
                reader = TextReader()
                documents = reader.read(temp_path)

            if documents:
                agent.knowledge.load_documents(documents, upsert=True)
                st.success(f"Added {len(documents)} chunks from {uploaded_file.name} to knowledge base")
            
            # Clean up the temporary file
            os.unlink(temp_path)
                
        return True
    except Exception as e:
        st.error(f"Error loading documents to knowledge base: {e}")
        return False

# Title
st.title("AI Proposal Generator")
st.markdown("---")

# Initialize AI agent if not already done
if not st.session_state.initialized:
    with st.spinner("Initializing AI agent..."):
        try:
            st.session_state.agent = get_agentic_rag_agent()
            st.session_state.initialized = True
            st.success("AI agent initialized successfully!")
        except Exception as e:
            st.error(f"Error initializing AI agent: {str(e)}")

# Main form for input
if st.session_state.initialized and not st.session_state.proposal_generated:
    st.subheader("Create New Proposal")
    
    # Knowledge base files
    st.write("Step 1: Add files to knowledge base (optional)")
    uploaded_files = st.file_uploader("Upload files", 
                                     accept_multiple_files=True,
                                     type=["pdf", "csv", "txt"])
    
    if uploaded_files and st.button("Add Files to Knowledge Base"):
        load_documents_to_knowledge_base(uploaded_files, st.session_state.agent)
    
    # Client information
    st.write("Step 2: Client Information")
    client_name = st.text_input("Client Name", "")
    
    # Requirements
    st.write("Step 3: Requirements")
    requirements_text = st.text_area(
        "Enter client requirements",
        "",
        height=200,
        placeholder="Type the client requirements here..."
    )
    
    # Options
    st.write("Step 4: Generation Options")
    interactive = st.checkbox("Review each section interactively", value=True)
    output_dir = st.text_input("Output Directory", "proposals")
    
    # Generate button
    if st.button("Generate Proposal"):
        if not client_name.strip():
            st.warning("Please enter a client name.")
        elif not requirements_text.strip():
            st.warning("Please enter client requirements.")
        else:
            # Save input values to session state
            st.session_state.client_name = client_name
            st.session_state.requirements_text = requirements_text
            st.session_state.interactive = interactive
            st.session_state.output_dir = output_dir
            
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            # Initialize proposal generator
            st.session_state.proposal_gen = SectionBasedProposalGenerator(st.session_state.agent)
            
            if not interactive:
                # Generate all sections at once (non-interactive mode)
                with st.spinner("Generating proposal sections..."):
                    st.session_state.proposal_sections = st.session_state.proposal_gen.generate_all_sections(
                        requirements_text=requirements_text,
                        interactive=False
                    )
                st.session_state.proposal_generated = True
                st.session_state.sections_completed = True
            else:
                # Mark as ready to start generating sections interactively
                st.session_state.proposal_generated = True
                st.session_state.section_index = 0
                st.session_state.interactive_mode = True
                
            st.rerun()

# Interactive section generation
elif st.session_state.initialized and st.session_state.proposal_generated and not st.session_state.sections_completed and st.session_state.interactive:
    st.subheader("Interactive Section Review")
    
    # Get the proposal generator sections
    all_sections = st.session_state.proposal_gen.sections
    
    # If we haven't started this section yet
    if st.session_state.section_being_reviewed is None:
        current_section = all_sections[st.session_state.section_index]
        
        with st.spinner(f"Generating '{current_section}' section..."):
            # First process the requirements through get_requirements_prompt
            req_input = st.session_state.proposal_gen.get_requirements_prompt(st.session_state.requirements_text)
            
            # Generate this section content
            section_content = st.session_state.proposal_gen.generate_section(
                section_name=current_section,
                req_input=req_input
            )
            
            # Save the current section being reviewed
            st.session_state.section_being_reviewed = current_section
            st.session_state.current_section_content = section_content
            
            st.rerun()
    
    # Display the current section for review
    current_section = st.session_state.section_being_reviewed
    section_content = st.session_state.current_section_content
    
    st.markdown(f"### Section: {current_section}")
    st.markdown("---")
    
    # Display section content in a text area that can be edited
    edited_content = st.text_area(
        "Review the generated content and make any edits if needed:",
        value=section_content,
        height=400
    )
    
    # Action buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Approve Section"):
            # Save the approved section
            st.session_state.proposal_sections[current_section] = edited_content
            
            # Move to the next section or finish
            st.session_state.section_index += 1
            if st.session_state.section_index >= len(all_sections):
                st.session_state.sections_completed = True
            else:
                st.session_state.section_being_reviewed = None
                st.session_state.current_section_content = None
            
            st.rerun()
    
    with col2:
        if st.button("Regenerate Section"):
            # Reset the current section to regenerate
            st.session_state.section_being_reviewed = None
            st.session_state.current_section_content = None
            st.rerun()
    
    with col3:
        if st.button("Skip to Final PDF"):
            # Save the current section
            st.session_state.proposal_sections[current_section] = edited_content
            
            # Generate any remaining sections without interaction
            remaining_sections = all_sections[st.session_state.section_index+1:]
            
            if remaining_sections:
                with st.spinner("Generating remaining sections..."):
                    # Process requirements once
                    req_input = st.session_state.proposal_gen.get_requirements_prompt(st.session_state.requirements_text)
                    
                    for section_name in remaining_sections:
                        section_content = st.session_state.proposal_gen.generate_section(
                            section_name=section_name,
                            req_input=req_input
                        )
                        st.session_state.proposal_sections[section_name] = section_content
            
            st.session_state.sections_completed = True
            st.rerun()
    
    # Display progress indicator
    progress = (st.session_state.section_index + 1) / len(all_sections)
    st.progress(progress)
    st.write(f"Section {st.session_state.section_index + 1} of {len(all_sections)}")

# Generate PDF when all sections are complete
elif st.session_state.initialized and st.session_state.sections_completed and not st.session_state.pdf_generated:
    st.subheader("Proposal Sections Complete")
    
    # Show all sections in expandable containers
    for section_name, content in st.session_state.proposal_sections.items():
        with st.expander(section_name, expanded=False):
            st.markdown(content)
    
    # Button to generate PDF
    if st.button("Generate PDF"):
        with st.spinner("Generating PDF..."):
            try:
                # Convert sections to markdown format
                markdown_content = ""
                for section_name, content in st.session_state.proposal_sections.items():
                    markdown_content += f"### {section_name}\n\n{content}\n\n"
                
                # Generate PDF using the new function
                pdf_buffer = create_formatted_pdf(markdown_content)
                
                # Save the PDF to a file
                os.makedirs(st.session_state.output_dir, exist_ok=True)
                pdf_path = os.path.join(
                    st.session_state.output_dir, 
                    f"proposal_{st.session_state.client_name.lower().replace(' ', '_')}.pdf"
                )
                
                with open(pdf_path, 'wb') as f:
                    f.write(pdf_buffer.getvalue())
                
                st.session_state.pdf_path = pdf_path
                st.session_state.pdf_generated = True
                st.rerun()
            except Exception as e:
                st.error(f"Error generating PDF: {str(e)}")

# Display PDF download option
elif st.session_state.initialized and st.session_state.pdf_generated:
    st.subheader("Proposal PDF Generated")
    
    st.success(f"Proposal PDF generated successfully: {st.session_state.pdf_path}")
    
    # Download button
    try:
        with open(st.session_state.pdf_path, "rb") as file:
            st.download_button(
                label="Download PDF",
                data=file,
                file_name=os.path.basename(st.session_state.pdf_path),
                mime="application/pdf"
            )
    except Exception as e:
        st.error(f"Error reading PDF file: {str(e)}")
    
    # Start over button
    if st.button("Create New Proposal"):
        # Keep the agent but reset everything else
        agent = st.session_state.agent
        st.session_state.clear()
        st.session_state.agent = agent
        st.session_state.initialized = True
        st.rerun()
