from typing import Optional, Dict, List
import os
import uuid
from agno.agent import Agent
from agno.knowledge import AgentKnowledge
from agno.memory.db.sqlite import SqliteMemoryDb
from agno.storage.sqlite import SqliteStorage
from agno.vectordb.lancedb import LanceDb  
from agno.embedder.google import GeminiEmbedder 
from agno.models.google import Gemini 
import streamlit as st
# Database file location
db_file = "data/agent_db.sqlite" 
# os.environ["GROQ_API_KEY"] = st.secrets.get("groq_api_key")
os.environ["GOOGLE_API_KEY"] = st.secrets.get("google_api_key")


class SectionBasedProposalGenerator:
    """Generate proposals by creating one section at a time."""
    
    def __init__(self, agent: Agent):
        """Initialize the proposal generator."""

        self.agent = agent
        self.sections = [
            "Introduction",
            "Scope/Objectives",
            "Proposal/Approach",
            "Deliverables from Client",
            "Timelines",
            "Quotation",
            "About AI Planet"
        ]
        self.section_descriptions = {
            "Introduction": "Create a powerful 2-3 sentence introduction that: 1) Clearly states the client's current challenge/pain point, 2) Immediately follows with AI Planet's proposed solution, and 3) Emphasizes the core business value. Use direct, professional language without technical jargon. Format: First sentence for client's need, second for our solution, optional third for key impact. Example style: 'Client X needs Y. AI Planet proposes Z solution to address this challenge.'",
            "Scope/Objectives": "Start with a clear 'Objective' statement followed by detailed 'Scope of Work' using bullet points. Focus on tangible outcomes and concrete deliverables. List specific functional areas that will be addressed by the solution.",
            "Proposal/Approach": "Structure it as 3-5 numbered components with bold headers and bullet points for implementation details. Include specific technologies, methodologies, and architectures while explaining data flows, integration points, and business impacts. Balance technical specificity with practical implementation details. Address customization options, quality controls, and evolution mechanisms.",
            "Deliverables from Client": "Create a concise list using bullet points of all information, access, resources, and ongoing client participation needed for project success. Each point should be specific and actionable, starting with a bold key phrase followed by a brief explanation.",
            "Timelines": "Present project timeline as distinct phases with bullet points. For each phase, include: 1) Phase name with duration (e.g., 'Phase 1 - Requirement Gathering: 2 weeks'), 2) Sub-bullet points (○) explaining key activities within that phase. Alternatively, present in a structured table format.",
            "Quotation": "Create a comprehensive quotation with a brief introduction. Present costs clearly using bullets, tables, or both. Include specific pricing, quantities, and timeframes. Break down complex costs into detailed subcategories. Bold key figures and important terms for emphasis.",
            "About AI Planet": "Present a concise company overview highlighting expertise in AI/ML technologies, notable clients, and relevant industry experience. Focus on credentials directly relevant to the proposed solution. Keep to 3-5 sentences or a short paragraph without excessive detail."
        }
        self.proposal_sections = {}
    
    def get_requirements_prompt(self, requirements_text: str) -> str:
        """Create a prompt for generating a specific proposal section."""
        
        prompt = f""" Analyze the following client requirements and extract the key information into a concise summary.

CLIENT REQUIREMENTS:
{requirements_text}

Please provide:

## Client Expectations
[Extract and summarize the specific expectations and requirements the client has communicated in a cohesive paragraph]

## Key Points to Address
[Identify and explain in paragraph form the essential elements that must be covered to meet these client requirements]"""
        
        from agno.agent import Agent, RunResponse  # noqa
       
        req_agent = Agent(model=Gemini(
            id="gemini-2.0-flash-exp",
            api_key=os.environ["GOOGLE_API_KEY"]
        ), markdown=True)

        req_response=req_agent.run(prompt)
        req_input=req_response.content
        
        return req_input

    def generate_section(self, section_name: str, req_input: str) -> str:
        """Generate content for a specific section."""
        # prompt = self.get_section_prompt(section_name, requirements_text)
        section_description = self.section_descriptions.get(section_name, "")
        section_input=req_input+section_description
        response = self.agent.run(section_input)
        return response.content
    
    def generate_all_sections(self, requirements_text: str, interactive: bool = True) -> Dict[str, str]:
        """Generate all sections for the proposal."""
        req_input= self.get_requirements_prompt(requirements_text)
        

        for section in self.sections:
            print(f"\nGenerating section: {section}")
            content = self.generate_section(section, req_input)
            
            if interactive:
                print("\n" + "=" * 50)
                print(f"SECTION: {section}")
                print("=" * 50)
                print(content)
                print("\n" + "=" * 50)
                
                # Get user approval
                while True:
                    approval = input("Approve this section? (yes/no/edit): ").lower()
                    if approval == "yes":
                        self.proposal_sections[section] = content
                        break
                    elif approval == "no":
                        print("Regenerating section...")
                        content = self.generate_section(section, requirements_text)
                        print("\n" + "=" * 50)
                        print(f"SECTION: {section}")
                        print("=" * 50)
                        print(content)
                        print("\n" + "=" * 50)
                    elif approval == "edit":
                        print("Enter your edited version (type 'DONE' on a new line when finished):")
                        edited_content = []
                        while True:
                            line = input()
                            if line == "DONE":
                                break
                            edited_content.append(line)
                        content = "\n".join(edited_content)
                        self.proposal_sections[section] = content
                        break
                    else:
                        print("Invalid input. Please enter 'yes', 'no', or 'edit'.")
            else:
                self.proposal_sections[section] = content
        print("#"*50)
        print("length of sections:",len(self.proposal_sections))
        print("#"*50)
        return self.proposal_sections


def get_agentic_rag_agent(
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    debug_mode: bool = True,
) -> Agent:
    """Get an Agentic RAG Agent with Memory."""
    # Use Gemini as the model
    model = Gemini(
        id="gemini-2.0-flash-exp",
        api_key=os.environ["GOOGLE_API_KEY"]  # Explicitly set the API key
    )
    
    # Define the knowledge base
    knowledge_base = AgentKnowledge(
        vector_db=LanceDb(
            uri="data/vector_store",  # Local file path for LanceDB
            table_name="proposal_documents",
            embedder=GeminiEmbedder(
                api_key=os.environ["GOOGLE_API_KEY"]
            ),
        ),
        num_documents=5,  # Retrieve more documents for comprehensive proposals
    )

    # Create the Agent with proposal-specific instructions
    agent: Agent = Agent(
        name="proposal_section_agent",
        session_id=session_id or str(uuid.uuid4()),
        user_id=user_id or str(uuid.uuid4()),
        model=model,
        storage=SqliteStorage(
            table_name="proposal_agent_sessions",
            db_file=db_file
        ),
        knowledge=knowledge_base,
        description="You are a specialized proposal writer that creates professional, detailed proposal sections based on client requirements.",
        instructions=[
             "1. Knowledge Base Examples:",
            "   - Study the provided examples from past proposals VERY CAREFULLY",
            "   - Pay close attention to formatting, structure, bullet style, and level of detail",
            "   - Your output should look INDISTINGUISHABLE from these past examples",
            "   - Match the density of information and conciseness from examples",
            "2. Section Quality:",
            "   - Never use unnecessary subheadings - follow example structure exactly",
            "   - Keep paragraphs short and focused like in examples",
            "   - Use the same bullet/numbering style as seen in examples",
            "   - Ensure the format follows company conventions precisely",
            "   - Be technically precise but avoid unnecessary explanations",
            "3. Content Customization:",
            "   - While matching format exactly, customize content to client's specific needs",
            "   - Reference relevant past projects when this would strengthen the proposal",
            "4. Knowledge Search:",
            "   - Use search_knowledge_base for additional relevant examples as needed",
            "   - If examples are insufficient, use external search for industry specifics"
            "5. CRITICAL - Output Format:",
            "   - Start DIRECTLY with the section content with NO preamble or meta-commentary",
            "   - NO statements like 'I will generate' or explanations of your approach",
            "   - Output ONLY content that would appear in the final proposal document"
        ],
        search_knowledge=True,
        markdown=True,
        show_tool_calls=True,
        debug_mode=debug_mode,
    )

    return agent


# # Example usage
# if __name__ == "__main__":
#     # Initialize the agent
#     agent = get_agentic_rag_agent()
    
#     # Initialize the proposal generator
#     proposal_gen = SectionBasedProposalGenerator(agent)
    
#     # Example requirements text
#     requirements_text = """
#     We need an AI solution for customer support automation that can handle email classification, 
#     sentiment analysis, and automated responses for simple queries. 
#     We want to integrate this with our existing Zendesk system.
#     Our team consists of 5 customer support representatives who handle around 500 emails per day.
#     We want to reduce manual handling by at least 40%.
#     Our budget is approximately $50,000 for this project.
#     We need this implemented within 3 months.
#     """
    
#     # Generate all sections interactively
#     proposal_sections = proposal_gen.generate_all_sections(requirements_text)
    
#     # You could now pass these approved sections to a PDF generator
#     print("\nAll sections approved! Ready to generate PDF.")
