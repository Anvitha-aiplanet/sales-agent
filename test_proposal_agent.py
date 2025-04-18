# import os
# import argparse
# import uuid
# from agno.document.reader.pdf_reader import PDFReader
# from agno.document.reader.csv_reader import CSVReader
# from agno.document.reader.text_reader import TextReader
# from section_based_agent import get_agentic_rag_agent, SectionBasedProposalGenerator
# from pdf_generator import ProposalPDFGenerator

# # Database file location
# db_file = "data/agent_db.sqlite" 


# def add_document_to_knowledge_base(agent, file_path: str):
#     """Add a document to the agent's knowledge base."""
#     # Determine file type and use appropriate reader
#     if file_path.endswith('.pdf'):
#         reader = PDFReader()
#         documents = reader.read(file_path)
#     elif file_path.endswith('.csv'):
#         reader = CSVReader()
#         documents = reader.read(file_path)
#     else:
#         reader = TextReader()
#         documents = reader.read(file_path)

#     if documents:
#         agent.knowledge.load_documents(documents, upsert=True)
#     print(f"Added {len(documents)} chunks from {file_path} to knowledge base")


# def generate_proposal_from_file(agent, file_path: str, client_name: str, interactive: bool = True):
#     """Generate a proposal from a requirements file.
    
#     Args:
#         agent: The agent instance
#         file_path: Path to the requirements file
#         client_name: Name of the client
#         interactive: If True, get user approval for each section
        
#     Returns:
#         Path to the generated PDF proposal
#     """
#     # Read the requirements file
#     with open(file_path, 'r') as file:
#         requirements_text = file.read()
    
#     # Initialize proposal generator
#     proposal_gen = SectionBasedProposalGenerator(agent)
    
#     # Generate all sections
#     print(f"Generating proposal for client: {client_name}")
#     proposal_sections = proposal_gen.generate_all_sections(requirements_text, interactive=interactive)
    
#     # Generate PDF
#     pdf_gen = ProposalPDFGenerator()
#     pdf_path = pdf_gen.generate_pdf(proposal_sections, client_name)
    
#     print(f"Proposal PDF generated: {pdf_path}")
#     return pdf_path


# def load_past_proposals(agent):
#     """Load past proposals and company information into the knowledge base."""
#     # Directory containing past proposals
#     past_proposals_dir = "data/past_proposals"
    
#     # Check if directory exists
#     if not os.path.exists(past_proposals_dir):
#         print(f"Creating directory for past proposals: {past_proposals_dir}")
#         os.makedirs(past_proposals_dir, exist_ok=True)
#         print(f"Please add your past proposal documents to: {past_proposals_dir}")
#         return

#     # Load all documents in the directory
#     for filename in os.listdir(past_proposals_dir):
#         file_path = os.path.join(past_proposals_dir, filename)
#         if os.path.isfile(file_path):
#             try:
#                 add_document_to_knowledge_base(agent, file_path)
#                 print(f"Loaded {file_path}")
#             except Exception as e:
#                 print(f"Error loading {file_path}: {str(e)}")


# def interactive_session(agent):
#     """Run an interactive session with the agent."""
#     print("=" * 50)
#     print("Proposal Generator Interactive Session")
#     print("Commands:")
#     print("1. 'add file:<path>' to add a document to the knowledge base")
#     print("2. 'generate from file:<requirements_file>:<client_name>' to generate from file")
#     print("3. 'generate proposal:<client_name>' to generate from text input")
#     print("4. 'exit' or 'quit' to end session")
#     print("=" * 50)
    
#     while True:
#         user_input = input("\nYou: ")
        
#         # Check for exit command
#         if user_input.lower() in ['exit', 'quit']:
#             print("Ending session. Goodbye!")
#             break
        
#         # Check for add file command
#         if user_input.lower().startswith('add file:'):
#             file_path = user_input[9:].strip()
#             try:
#                 add_document_to_knowledge_base(agent, file_path)
#             except Exception as e:
#                 print(f"Error adding file: {str(e)}")
#             continue
            
#         # Check for generate from file command
#         if user_input.lower().startswith('generate from file:'):
#             try:
#                 # Parse command: generate from file:<requirements_file>:<client_name>
#                 parts = user_input[18:].split(':')
#                 if len(parts) != 2:
#                     print("Invalid format. Use: generate from file:<requirements_file>:<client_name>")
#                     continue
                    
#                 file_path, client_name = parts
#                 pdf_path = generate_proposal_from_file(agent, file_path.strip(), client_name.strip())
#                 print(f"Proposal generated successfully: {pdf_path}")
#             except Exception as e:
#                 print(f"Error generating proposal from file: {str(e)}")
#             continue
            
#         # Check for generate from text command
#         if user_input.lower().startswith('generate proposal:'):
#             try:
#                 client_name = user_input[17:].strip()
#                 print("\nEnter your requirements (type 'END' on a new line when finished):")
#                 requirements_text = []
#                 while True:
#                     line = input()
#                     if line.strip().upper() == 'END':
#                         break
#                     requirements_text.append(line)
                
#                 requirements = '\n'.join(requirements_text)
#                 print("\nGenerating proposal...")
                
#                 # Create proposal generator instance
#                 proposal_gen = SectionBasedProposalGenerator(agent)
                
#                 # Generate proposal sections
#                 proposal_sections = proposal_gen.generate_all_sections(requirements, interactive=True)
                
#                 # Generate PDF
#                 pdf_gen = ProposalPDFGenerator()
#                 pdf_path = pdf_gen.generate_pdf(proposal_sections, client_name)
#                 print(f"\nProposal generated successfully: {pdf_path}")
#             except Exception as e:
#                 print(f"Error generating proposal from text: {str(e)}")
#             continue

#         # For regular queries, show retrieved documents and generate response
#         try:
#             print("\nSearching knowledge base...")
#             docs = agent.knowledge.search(query=user_input, num_documents=3)
#             if docs:
#                 print("\nRetrieved Documents:")
#                 print("-" * 50)
#                 for i, doc in enumerate(docs, 1):
#                     print(f"\nDocument {i}:")
#                     print(f"Name: {doc.name}")
#                     print(f"Content: {doc.content[:200]}...")
#                     if hasattr(doc, 'metadata') and doc.metadata:
#                         print(f"Metadata: {doc.metadata}")
#                 print("-" * 50)
#             else:
#                 print("No relevant documents found in knowledge base.")

#             print("\nGenerating response...")
#             response_content = ""
#             for response_chunk in agent.run(user_input, stream=True):
#                 if response_chunk.content is not None:
#                     response_content += response_chunk.content
#                     # Print chunks as they come in
#                     print(response_chunk.content, end="", flush=True)
#             print("\n" + "=" * 50)
            
#         except Exception as e:
#             print(f"Error: {str(e)}")


# def main():
#     """Main function to initialize and run the proposal generator."""
#     parser = argparse.ArgumentParser(description="Proposal Generator")
#     parser.add_argument("--requirements", type=str, help="Path to requirements file")
#     parser.add_argument("--client", type=str, help="Client name for proposal")
#     parser.add_argument("--add-docs", nargs="+", help="Add documents to knowledge base")
#     parser.add_argument("--non-interactive", action="store_true", help="Generate proposal without user approval for each section")
#     parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
#     args = parser.parse_args()
    
#     # Initialize the agent
#     agent = get_agentic_rag_agent(
#         user_id=str(uuid.uuid4()),
#         session_id=str(uuid.uuid4()),
#         debug_mode=args.debug
#     )
    
#     # Load past proposals
#     load_past_proposals(agent)
    
#     # Add documents if specified
#     if args.add_docs:
#         for doc_path in args.add_docs:
#             try:
#                 add_document_to_knowledge_base(agent, doc_path)
#             except Exception as e:
#                 print(f"Error adding document {doc_path}: {str(e)}")
    
#     # Generate proposal if requirements and client are specified
#     if args.requirements and args.client:
#         try:
#             pdf_path = generate_proposal_from_file(
#                 agent, 
#                 args.requirements, 
#                 args.client,
#                 interactive=not args.non_interactive
#             )
#         except Exception as e:
#             print(f"Error generating proposal: {str(e)}")
#     else:
#         # Start interactive session
#         interactive_session(agent)


# if __name__ == "__main__":
#     main()

import os
import sys
from typing import List

# Import from existing files
from pdf_generator import ProposalPDFGenerator
from section_based_agent import SectionBasedProposalGenerator, get_agentic_rag_agent
from agno.document import Document
from agno.document.reader.csv_reader import CSVReader
from agno.document.reader.pdf_reader import PDFReader
from agno.document.reader.text_reader import TextReader
from agno.document.reader.website_reader import WebsiteReader
from agno.utils.log import logger

def load_documents_to_knowledge_base(document_paths: List[str], agent) -> bool:
    """Load documents into the knowledge base."""
    try:
        for doc_path in document_paths:
            if not os.path.exists(doc_path):
                print(f"Warning: Document {doc_path} does not exist, skipping.")
                continue
                
            print(f"Adding {doc_path} to knowledge base...")
            
            # Determine file type and use appropriate reader
            if doc_path.endswith('.pdf'):
                reader = PDFReader()
                documents = reader.read(doc_path)
            elif doc_path.endswith('.csv'):
                reader = CSVReader()
                documents = reader.read(doc_path)
            else:
                reader = TextReader()
                documents = reader.read(doc_path)

            if documents:
                agent.knowledge.load_documents(documents, upsert=True)
                print(f"Added {len(documents)} chunks from {doc_path} to knowledge base")
                
        return True
    except Exception as e:
        print(f"Error loading documents to knowledge base: {e}")
        return False

def main():
    print("=" * 50)
    print("AI Proposal Generator")
    print("=" * 50)
    
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # Step 6: Initialize the agent
    print("\nInitializing AI agent...")
    agent = get_agentic_rag_agent()
    # Step 1: Ask if user wants to add files to knowledge base
    kb_files = []
    add_kb = input("Do you want to add files to the knowledge base? (y/n): ").lower()
    
    if add_kb == 'y':
        print("Enter file paths one by one (type 'done' when finished):")
        while True:
            file_path = input("File path: ")
            if file_path.lower() == 'done':
                break
            kb_files.append(file_path)
        
        # Load knowledge base files
        if kb_files:
            print("\nLoading documents to knowledge base...")
            if not load_documents_to_knowledge_base(kb_files,agent):
                print("Failed to load documents to knowledge base. Proceeding without them.")
            else:
                print("Knowledge base updated successfully.")
    
    # Step 2: Get client name
    client_name = input("\nEnter client name: ")
    if not client_name.strip():
        client_name = "Client"
    
    # Step 3: Get requirements
    print("\nEnter client requirements (type 'END' on a new line when finished):")
    requirements_lines = []
    while True:
        line = input()
        if line == "END":
            break
        requirements_lines.append(line)
    requirements_text = "\n".join(requirements_lines)
    
    # Step 4: Ask if user wants interactive mode
    interactive = input("\nDo you want to review each section before generating the PDF? (y/n): ").lower() == 'y'
    
    # Step 5: Get output directory
    output_dir = input("\nEnter output directory (default: proposals): ")
    if not output_dir.strip():
        output_dir = "proposals"
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    
    # Step 7: Initialize the proposal generator
    proposal_gen = SectionBasedProposalGenerator(agent)
    
    # Step 8: Generate proposal sections
    print("\nGenerating proposal sections...")
    proposal_sections = proposal_gen.generate_all_sections(
        requirements_text=requirements_text,
        interactive=interactive
    )
    print(proposal_sections)
    
    # Step 9: Initialize the PDF generator
    pdf_gen = ProposalPDFGenerator(output_dir=output_dir)
    
    # Step 10: Generate PDF
    # try:
    #     print("\nGenerating PDF...")
    #     pdf_path = pdf_gen.generate_pdf(
    #         proposal_sections=proposal_sections,
    #         client_name=client_name
    #     )
    #     print(f"\nProposal PDF generated successfully: {pdf_path}")
    # except Exception as e:
    #     print(f"Error generating PDF: {str(e)}")
    #     sys.exit(1)
    # print("\nGenerating PDF...")
    # pdf_path = pdf_gen.generate_pdf(
    #     proposal_sections=proposal_sections,
    #     client_name=client_name
    # )
    
    # print(f"\nProposal PDF generated successfully: {pdf_path}")

if __name__ == "__main__":
    main()
