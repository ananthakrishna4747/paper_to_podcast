# agents_l/orchestrator.py
import logging
import re
from agents import Agent
from agents_l.context import AppContext
from agents_l.memory import save_to_memory, get_memory
from core.search import search_arxiv_by_query, search_arxiv_by_id, download_paper
from core.parse import extract_paper_text, parse_paper_sections
from core.podcast import generate_podcast_script
from core.audio import generate_podcast_audio

logger = logging.getLogger("AgentOrchestrator")

def create_arxiv_search_agent():
    """Create an agent for searching arXiv papers."""
    return Agent[AppContext](
        name="ArXiv Search Agent",
        instructions="""
        You are a helpful assistant that helps users find academic papers on arXiv.
        
        Your capabilities:
        1. Search arXiv using keywords, author names, categories, or other criteria
        2. Look up specific papers by arXiv ID
        3. Provide detailed information about papers
        
        Guidelines:
        - When presenting search results, use a numbered list format
        - ALWAYS include the arXiv ID with each paper (e.g., "arXiv ID: 1706.03762")
        - Include key information like title, authors, publication date, and a brief summary
        - Help users refine their searches if they get too many or irrelevant results
        - If a user mentions a specific paper ID (like 2107.05580v1 or quant-ph/0201082v1), 
          use the search_arxiv_by_id tool directly
        - If a user mentions they want to download a specific paper, go ahead and offer to download it
        - After finding a paper, always ask if the user would like to download it
        """,
        tools=[search_arxiv_by_query, search_arxiv_by_id, download_paper]
    )

def create_paper_download_agent():
    """Create an agent for downloading papers."""
    return Agent[AppContext](
        name="Paper Download Agent",
        instructions="""
        You help users download and process papers from arXiv.
        
        Your responsibilities:
        1. Download papers by arXiv ID
        2. Extract text content from the downloaded PDF
        3. Parse the paper into logical sections
        4. Confirm successful downloads and processing
        
        Guidelines:
        - When downloading a paper, ALWAYS use the paper's arXiv ID with the download_paper function
        - After downloading, ALWAYS use extract_paper_text to process the text
        - After text extraction, ALWAYS proceed to parse_paper_sections
        - After successful processing, ALWAYS ask the user for their preferred podcast duration
        - Suggest 5, 10, 15, 20, or 30 minute durations
        - Recommend 10 minutes as a balanced overview (default)
        - Be very concise in your responses - focus on getting to the podcast generation quickly
        - If a user just wants to download a paper, proceed through all steps to get to podcast generation
        - Do not wait for explicit user confirmation after each step - keep the workflow moving
        """,
        tools=[download_paper, extract_paper_text, parse_paper_sections]
    )

def create_podcast_generator_agent():
    """Create an agent for generating podcast scripts and audio."""
    return Agent[AppContext](
        name="Podcast Generator",
        instructions="""
        You create engaging podcast content from academic papers.
        
        Your responsibilities:
        1. Generate podcast scripts based on user-specified duration
        2. Create audio podcasts with multiple speakers
        3. Provide the resulting podcast to the user
        
        Guidelines:
        - If the user hasn't specified a podcast duration, default to 10 minutes
        - Use 2 speakers (one male, one female) unless the user specifies otherwise
        - Use generate_podcast_script to create the script
        - After script generation ALWAYS proceed immediately to generate_podcast_audio
        - Be concise in your communications - focus on delivering the podcast
        - After podcast generation, provide a very brief confirmation and point to the audio player
        - Do not wait for explicit user confirmation between script and audio generation
        """,
        tools=[generate_podcast_script, generate_podcast_audio]
    )

def create_orchestrator():
    """Create the main orchestrator agent that coordinates the workflow."""
    search_agent = create_arxiv_search_agent()
    download_agent = create_paper_download_agent()
    podcast_agent = create_podcast_generator_agent()
    
    return Agent[AppContext](
        name="ArXiv Podcast Assistant",
        instructions="""
        You are an intelligent assistant that helps users find academic papers
        and convert them into engaging podcasts.
        
        Follow this workflow:
        1. Help users search for papers on arXiv
        2. Assist with downloading their selected paper
        3. Process the paper by extracting text and identifying sections
        4. Ask for podcast duration (5, 10, 15, 20, or 30 minutes)
        5. Generate a podcast script and audio
        6. Provide the result to the user
        
        Key instructions:
        - Be proactive and keep the workflow moving forward
        - If a user asks to download a paper, proceed with downloading using its arXiv ID
        - If a user asks for a podcast of a paper, handle the entire workflow from search to audio
        - When presenting search results, ALWAYS include the arXiv ID
        - CRITICAL: When using the download_paper function, always use the full arXiv ID
        - Do not stop or wait for confirmation between steps unless absolutely necessary
        - If a paper is downloaded successfully, automatically proceed to text extraction
        - If text extraction is successful, automatically proceed to section parsing
        - After parsing, ask for podcast duration and then proceed to generation
        - Keep your responses concise and focused on delivering the podcast
        - Default to 10 minutes for podcast duration if not specified
        
        Remember: The goal is to provide a seamless experience from paper search to podcast delivery.
        """,
        tools=[save_to_memory, get_memory],
        handoffs=[search_agent, download_agent, podcast_agent]
    )