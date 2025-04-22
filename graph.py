import os
from typing import List, Literal, Optional, TypedDict, Annotated, Dict, Any
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage, HumanMessage, AIMessage
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langchain_community.utilities import GoogleSerperAPIWrapper
import json
import streamlit as st

# STATE DEFINITIONS
class State(TypedDict):
    messages: Annotated[list, add_messages]
    company_name: Optional[str]
    revenue_history_data: Optional[Dict]
    revenue_sources_data: Optional[Dict]
    competitor_genai_data: Optional[Dict]
    status: Optional[Dict]

serper_tool = GoogleSerperAPIWrapper(serper_api_key=st.secrets["serper_api_key"])
# TOOL DEFINITIONS
@tool
def search_tool(query: str) -> str:
    """Search for information using Google via Serper API"""
    try:
        # Use serper API key from Streamlit secrets
        serper = serper_tool
        results = serper.run(query)
        print("seatch tool results",results)
        return results
    except Exception as e:
        return f"Error during search: {str(e)}"

# AGENT DEFINITIONS
def create_llm():
    """Create and configure the Azure OpenAI model"""
    llm = AzureChatOpenAI(
    deployment_name= st.secrets["deployment_name"],  # Your Azure OpenAI deployment name
    api_key=st.secrets["azure_api_key"],  # Your Azure OpenAI API key
    azure_endpoint=st.secrets["endpoint"],
    openai_api_version=st.secrets["api_version"],# API version for Azure OpenAI
    max_tokens=6000,
)
    return llm 

def create_orchestrator_agent():
    """Creates the orchestrator agent that manages the workflow"""
    llm = create_llm()
    llm_with_tools = llm.bind_tools([search_tool])
    
    def orchestrator_node(state: State):
        system_prompt = {
            "role": "system",
            "content": """You are the Orchestrator Agent that coordinates the market research workflow.
            Your job is to:
            1. Extract the company name from the user's query
            2. Initialize the research process
            3. Delegate tasks to specialized agents
            4. Track the progress of each agent
            5. Consolidate the final report
            
            Respond to the user with a confirmation of the research initiation and expected timeline.
            """
        }
        
        messages = [system_prompt] + state["messages"]
        
        # Extract company name if not already present
        if not state.get("company_name"):
            last_user_msg = next((msg for msg in reversed(state["messages"]) 
                               if isinstance(msg, HumanMessage)), None)
            if last_user_msg:
                company_name = extract_company_name(last_user_msg.content)
                state["company_name"] = company_name
                state["status"] = {
                    "revenue_history": "pending",
                    "revenue_sources": "pending",
                    "competitor_genai": "pending"
                }
                
                confirmation = f"I'll research {company_name} focusing on:\n\n" + \
                              "1. Revenue history (past 3 years)\n" + \
                              "2. Major revenue sources\n" + \
                              "3. Competitors' GenAI use cases and benefits\n\n" + \
                              "Starting research now..."
                
                return {"messages": [AIMessage(content=confirmation)], 
                        "company_name": company_name,
                        "status": state["status"]}
        
        # If all agents have completed, consolidate the reports
        if state["status"] and all(v == "completed" for v in state["status"].values()):
            consolidated_report = consolidate_reports(
                state["company_name"],
                state.get("revenue_history_data", {}),
                state.get("revenue_sources_data", {}),
                state.get("competitor_genai_data", {})
            )
            
            return {"messages": [AIMessage(content=consolidated_report)]}
        
        # Handle any other messages - use simple messages to avoid tool calls here
        return {"messages": [AIMessage(content="Continuing research...")]}
    
    return orchestrator_node

def create_revenue_history_agent():
    """Creates the agent specialized in retrieving revenue history"""
    llm = create_llm()
    
    def revenue_history_node(state: State):
        company_name = state["company_name"]
        
        system_prompt = {
            "role": "system",
            "content": f"""You are the Revenue History Agent specializing in financial analysis.
            
            TASK: Research the revenue history of {company_name} for at least the past three years.
            
            Follow these steps:
            1. Search for "{company_name} annual revenue history" and "{company_name} financial results past three years"
            2. Extract revenue figures for each year (2022, 2023, 2024 if available)
            3. Note any significant trends or changes
            4. Include the currency and provide sources
            
            Format your response as a structured JSON with:
            - yearly_revenue: Dict mapping years to revenue figures
            - currency: The currency of the reported figures
            - trends: Brief analysis of trends
            - sources: List of sources used
            
            If data is not available for certain years, explicitly state this.
            """
        }
        
        messages = [system_prompt]
        
        # Search for revenue history
        search_query = f"{company_name} annual revenue history past three years financial results"
        search_results = search_tool(search_query)
        
        # Analyze search results
        messages.append(HumanMessage(content=f"Here are the search results for {company_name}'s revenue history: {search_results}\n\nPlease analyze these results and extract the revenue figures for at least the past three years. Format your response as specified."))
        
        # Use the LLM to process the search results
        llm_response = llm.invoke(messages)
        
        # Parse the JSON from the response
        try:
            revenue_data = extract_json_from_text(llm_response.content)
            state["revenue_history_data"] = revenue_data
            state["status"]["revenue_history"] = "completed"
        except Exception as e:
            # If parsing fails, store the raw response
            state["revenue_history_data"] = {"raw_response": llm_response.content, "error": str(e)}
            state["status"]["revenue_history"] = "completed"
        
        return state
    
    return revenue_history_node

def create_revenue_sources_agent():
    """Creates the agent specialized in identifying revenue sources"""
    llm = create_llm()
    
    def revenue_sources_node(state: State):
        company_name = state["company_name"]
        
        system_prompt = {
            "role": "system",
            "content": f"""You are the Revenue Sources Agent specializing in business model analysis.
            
            TASK: Research the major sources of revenue for {company_name}.
            
            Follow these steps:
            1. Search for "{company_name} business model" and "{company_name} revenue breakdown"
            2. Identify the primary products, services, or business segments
            3. Determine the approximate percentage contribution of each source
            4. Identify any recent changes in revenue composition
            
            Format your response as a structured JSON with:
            - revenue_streams: List of major revenue sources with percentage contributions
            - primary_segment: The largest revenue segment
            - recent_changes: Any shifts in revenue composition
            - sources: List of sources used
            """
        }
        
        messages = [system_prompt]
        
        # Search for revenue sources
        search_query = f"{company_name} business model revenue breakdown segments"
        search_results = search_tool(search_query)
        
        # Analyze search results
        messages.append(HumanMessage(content=f"Here are the search results for {company_name}'s revenue sources: {search_results}\n\nPlease analyze these results and extract the major sources of revenue. Format your response as specified."))
        
        # Use the LLM to process the search results
        llm_response = llm.invoke(messages)
        
        # Parse the JSON from the response
        try:
            revenue_sources_data = extract_json_from_text(llm_response.content)
            state["revenue_sources_data"] = revenue_sources_data
            state["status"]["revenue_sources"] = "completed"
        except Exception as e:
            # If parsing fails, store the raw response
            state["revenue_sources_data"] = {"raw_response": llm_response.content, "error": str(e)}
            state["status"]["revenue_sources"] = "completed"
        
        return state
    
    return revenue_sources_node

def create_competitor_genai_agent():
    """Creates the agent specialized in competitor GenAI analysis"""
    llm = create_llm()
    
    def competitor_genai_node(state: State):
        company_name = state["company_name"]
        
        system_prompt = {
            "role": "system",
            "content": f"""You are the Competitor GenAI Agent specializing in AI implementation analysis.
            
            TASK: Research how competitors of {company_name} are using generative AI and the benefits they've received.
            
            Follow these steps:
            1. First identify the main competitors of {company_name}
            2. For each competitor, search for their generative AI initiatives
            3. Document specific use cases of generative AI in their business
            4. Analyze the reported benefits (e.g., efficiency gains, cost savings, new products)
            5. Note any competitive advantages gained through AI
            
            Format your response as a structured JSON with:
            - competitors: List of main competitors
            - genai_implementations: Dict mapping competitors to their GenAI use cases
            - reported_benefits: Dict mapping competitors to benefits they've reported
            - competitive_impact: Analysis of how GenAI is shifting the competitive landscape
            - sources: List of sources used
            """
        }
        
        messages = [system_prompt]
        
        # First search for competitors
        competitors_query = f"{company_name} main competitors industry peers"
        competitors_results = search_tool(competitors_query)
        
        messages.append(HumanMessage(content=f"Here are the search results for {company_name}'s competitors: {competitors_results}\n\nPlease identify the main competitors."))
        
        competitors_response = llm.invoke(messages)
        
        # Now search for GenAI use cases of these competitors
        messages.append(HumanMessage(content=f"Based on the competitors you identified, please search for how they're using generative AI and the benefits they've received."))
        
        # For each competitor, do a specific search
        genai_query = f"{company_name} competitors generative AI use cases benefits implementation"
        genai_results = search_tool(genai_query)
        
        messages.append(HumanMessage(content=f"Here are the search results for generative AI use cases among {company_name}'s competitors: {genai_results}\n\nPlease analyze these results and extract the GenAI use cases and benefits. Format your response as specified."))
        
        # Use the LLM to process the search results
        llm_response = llm.invoke(messages)
        
        # Parse the JSON from the response
        try:
            competitor_genai_data = extract_json_from_text(llm_response.content)
            state["competitor_genai_data"] = competitor_genai_data
            state["status"]["competitor_genai"] = "completed"
        except Exception as e:
            # If parsing fails, store the raw response
            state["competitor_genai_data"] = {"raw_response": llm_response.content, "error": str(e)}
            state["status"]["competitor_genai"] = "completed"
        
        return state
    
    return competitor_genai_node

# HELPER FUNCTIONS
def extract_company_name(user_message):
    """Extracts the company name from the user's message"""
    # In a real implementation, this would use NER or similar techniques
    # For simplicity, we'll assume the company name follows certain phrases
    
    lower_msg = user_message.lower()
    indicators = ["company", "about", "research", "looking for info on", "information about"]
    
    for indicator in indicators:
        if indicator in lower_msg:
            # Find the position of the indicator
            pos = lower_msg.find(indicator) + len(indicator)
            # Extract the text after the indicator, up to a punctuation or end of string
            remaining = user_message[pos:].strip()
            # This is a simplistic approach - a real implementation would be more sophisticated
            company_name = remaining.split('.')[0].split(',')[0].strip()
            return company_name
    
    # If no indicator found, just return the first few words
    # This is fallback logic - not ideal
    words = user_message.split()
    if len(words) > 2:
        return " ".join(words[:3])
    return user_message

def extract_json_from_text(text):
    """Extracts JSON from text that might contain other content"""
    try:
        # Try to find JSON in the text
        json_start = text.find('{')
        json_end = text.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_text = text[json_start:json_end]
            return json.loads(json_text)
        else:
            # If no JSON found, attempt to parse the whole text
            return json.loads(text)
    except Exception as e:
        # Create a simple JSON with the raw text
        return {"parsed_text": text, "error": str(e)}

def consolidate_reports(company_name, revenue_history, revenue_sources, competitor_genai):
    """Consolidates the reports from the three agents into a single report"""
    report = f"# Market Research Report: {company_name}\n\n"
    
    # Add revenue history section
    report += "## Revenue History (Past 3 Years)\n\n"
    if isinstance(revenue_history, dict):
        if "yearly_revenue" in revenue_history:
            report += "### Annual Revenue\n\n"
            for year, revenue in revenue_history["yearly_revenue"].items():
                report += f"- **{year}**: {revenue}\n"
            
            if "currency" in revenue_history:
                report += f"\nAll figures in {revenue_history['currency']}\n\n"
                
            if "trends" in revenue_history:
                report += f"### Trends\n\n{revenue_history['trends']}\n\n"
        else:
            # Handle raw response
            if "raw_response" in revenue_history:
                report += revenue_history["raw_response"] + "\n\n"
            elif "parsed_text" in revenue_history:
                report += revenue_history["parsed_text"] + "\n\n"
    
    # Add revenue sources section
    report += "## Major Revenue Sources\n\n"
    if isinstance(revenue_sources, dict):
        if "revenue_streams" in revenue_sources:
            for stream in revenue_sources["revenue_streams"]:
                report += f"- {stream}\n"
            
            if "primary_segment" in revenue_sources:
                report += f"\n**Primary Revenue Segment**: {revenue_sources['primary_segment']}\n\n"
                
            if "recent_changes" in revenue_sources:
                report += f"### Recent Changes in Revenue Composition\n\n{revenue_sources['recent_changes']}\n\n"
        else:
            # Handle raw response
            if "raw_response" in revenue_sources:
                report += revenue_sources["raw_response"] + "\n\n"
            elif "parsed_text" in revenue_sources:
                report += revenue_sources["parsed_text"] + "\n\n"
    
    # Add competitor GenAI section
    report += "## Competitor GenAI Use Cases & Benefits\n\n"
    if isinstance(competitor_genai, dict):
        if "competitors" in competitor_genai:
            report += "### Main Competitors\n\n"
            for competitor in competitor_genai["competitors"]:
                report += f"- {competitor}\n"
            
            if "genai_implementations" in competitor_genai:
                report += "\n### GenAI Implementations\n\n"
                for competitor, implementations in competitor_genai["genai_implementations"].items():
                    report += f"#### {competitor}\n\n"
                    if isinstance(implementations, list):
                        for impl in implementations:
                            report += f"- {impl}\n"
                    else:
                        report += f"- {implementations}\n"
                    report += "\n"
                    
            if "reported_benefits" in competitor_genai:
                report += "### Reported Benefits\n\n"
                for competitor, benefits in competitor_genai["reported_benefits"].items():
                    report += f"#### {competitor}\n\n"
                    if isinstance(benefits, list):
                        for benefit in benefits:
                            report += f"- {benefit}\n"
                    else:
                        report += f"- {benefits}\n"
                    report += "\n"
                    
            if "competitive_impact" in competitor_genai:
                report += f"### Competitive Impact of GenAI\n\n{competitor_genai['competitive_impact']}\n\n"
        else:
            # Handle raw response
            if "raw_response" in competitor_genai:
                report += competitor_genai["raw_response"] + "\n\n"
            elif "parsed_text" in competitor_genai:
                report += competitor_genai["parsed_text"] + "\n\n"
    
    # Add sources section
    report += "## Sources\n\n"
    sources = []
    
    if isinstance(revenue_history, dict) and "sources" in revenue_history:
        sources.extend(revenue_history["sources"])
    
    if isinstance(revenue_sources, dict) and "sources" in revenue_sources:
        sources.extend(revenue_sources["sources"])
        
    if isinstance(competitor_genai, dict) and "sources" in competitor_genai:
        sources.extend(competitor_genai["sources"])
    
    # Deduplicate sources
    unique_sources = list(set(sources))
    for source in unique_sources:
        report += f"- {source}\n"
    
    return report

def build_market_research_graph():
    # Initialize the StateGraph
    graph_builder = StateGraph(State)
    
    # Create nodes
    orchestrator_node = create_orchestrator_agent()
    revenue_history_node = create_revenue_history_agent()
    revenue_sources_node = create_revenue_sources_agent()
    competitor_genai_node = create_competitor_genai_agent()
    
    # Add nodes to the graph
    graph_builder.add_node("orchestrator", orchestrator_node)
    graph_builder.add_node("revenue_history_agent", revenue_history_node)
    graph_builder.add_node("revenue_sources_agent", revenue_sources_node)
    graph_builder.add_node("competitor_genai_agent", competitor_genai_node)
    
    # Define routing logic
    def route_from_orchestrator(state: State):
        # Check if we have a company name and status
        if not state.get("company_name") or not state.get("status"):
            return "orchestrator"
        
        # Check if all tasks are completed - return END instead of "orchestrator"
        if all(v == "completed" for v in state["status"].values()):
            return END
        
        # Check which tasks need to be executed
        if state["status"]["revenue_history"] == "pending":
            return "revenue_history_agent"
        
        if state["status"]["revenue_sources"] == "pending":
            return "revenue_sources_agent"
        
        if state["status"]["competitor_genai"] == "pending":
            return "competitor_genai_agent"
        
        # Default to orchestrator
        return "orchestrator"
    
    # Add edges
    graph_builder.add_edge(START, "orchestrator")
    graph_builder.add_conditional_edges(
        "orchestrator",
        route_from_orchestrator,
        {
            "orchestrator": "orchestrator",
            "revenue_history_agent": "revenue_history_agent",
            "revenue_sources_agent": "revenue_sources_agent",
            "competitor_genai_agent": "competitor_genai_agent",
            END: END  # Make sure to include END in the mapping
        }
    )
    graph_builder.add_edge("revenue_history_agent", "orchestrator")
    graph_builder.add_edge("revenue_sources_agent", "orchestrator")
    graph_builder.add_edge("competitor_genai_agent", "orchestrator")
    
    # Compile the graph (no recursion_limit parameter)
    memory = MemorySaver()
    return graph_builder.compile(checkpointer=memory)