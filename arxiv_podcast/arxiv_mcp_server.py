# Fixed version of arxiv_mcp_server.py

import os
import asyncio
import logging
import re
import json
import arxiv
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
from langchain.memory import ConversationBufferMemory
from langchain_openai import ChatOpenAI
from datetime import datetime, timedelta

# Get the absolute path to the .env file
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')

# Load environment variables with verbose output for debugging
print(f"Loading environment variables from: {env_path}")
load_dotenv(dotenv_path=env_path, verbose=True, override=True)

# Get log directory from environment variable or use current directory
log_dir = os.environ.get("LOG_DIR", ".")
os.makedirs(log_dir, exist_ok=True)  # Ensure log directory exists

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "arxiv_mcp_server.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("arxiv-server")

# Initialize OpenAI client for natural language processing
openai_api_key = os.environ.get("OPENAI_API_KEY")
if not openai_api_key:
    print("ERROR: OPENAI_API_KEY environment variable is not set")
    print(f"Environment variables:")
    for key in sorted(os.environ.keys()):
        print(f"  {key}={os.environ[key][:5]}..." if "KEY" in key else f"  {key}=***")
    raise ValueError("OPENAI_API_KEY environment variable is not set")

try:
    llm = ChatOpenAI(
        model="gpt-4o", 
        temperature=0.3,
        openai_api_key=openai_api_key
    )
    logger.info("OpenAI client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {str(e)}")
    raise

# Initialize LangChain memory to maintain conversation context
memory = ConversationBufferMemory(return_messages=True)
logger.info("LangChain memory initialized")

# Track the last search results for follow-up actions
last_search_results = []
current_paper_focus = None


# ArXiv client wrapper
class ArxivClient:
    def __init__(self, page_size=100, delay_seconds=3.0):
        """Initialize ArXiv client with configurable parameters"""
        self.client = arxiv.Client(
            page_size=page_size, 
            delay_seconds=delay_seconds
        )
        logger.info("ArXiv client initialized")
    
    def search_by_title(self, title: str, max_results: int = 5) -> List[arxiv.Result]:
        """Search for papers with titles related to the given title"""
        logger.info(f"Searching by title: {title}")
        search = arxiv.Search(
            query=f'ti:"{title}"',
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance
        )
        return list(self.client.results(search))
    
    def search_by_author(self, author_name: str, max_results: int = 5) -> List[arxiv.Result]:
        """Search for all papers by a specific author"""
        logger.info(f"Searching by author: {author_name}")
        search = arxiv.Search(
            query=f'au:"{author_name}"',
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate
        )
        return list(self.client.results(search))
    
    def search_by_category(self, category: str, max_results: int = 5) -> List[arxiv.Result]:
        """Search papers in a specific research category"""
        logger.info(f"Searching by category: {category}")
        search = arxiv.Search(
            query=f'all:{category}',  # Changed from 'cat:' to 'all:' for better results
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate
        )
        return list(self.client.results(search))
    
    def search_by_date(self, date_query: str, max_results: int = 5) -> List[arxiv.Result]:
        """Search papers by date constraint"""
        logger.info(f"Searching by date: {date_query}")
        search = arxiv.Search(
            query=date_query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate
        )
        return list(self.client.results(search))
    
    def advanced_search(self, query: str, max_results: int = 5) -> List[arxiv.Result]:
        """Perform an advanced search with complex query"""
        logger.info(f"Performing advanced search: {query}")
        
        # Fix the query format for compatibility with arXiv API
        # The API doesn't support submittedDate directly
        if "submittedDate" in query:
            # Convert to standard arXiv date format
            query = query.replace("submittedDate:", "")
            query = re.sub(r'\[(\d{4}-\d{2}-\d{2}) TO (\d{4}-\d{2}-\d{2})\]', '', query)
            # Just keep the keywords and categories
            query = re.sub(r'AND\s+', '', query).strip()
        
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance
        )
        return list(self.client.results(search))
    
    def search_by_id(self, paper_id: str) -> Optional[arxiv.Result]:
        """Search for a specific paper by ID"""
        logger.info(f"Searching for paper with ID: {paper_id}")
        # Clean ID if necessary
        paper_id = paper_id.strip()
        
        search = arxiv.Search(
            query=f'id:{paper_id}',
            max_results=1
        )
        results = list(self.client.results(search))
        if results:
            return results[0]
        return None
    
    def format_paper_details(self, paper: arxiv.Result) -> Dict[str, Any]:
        """Format paper details into a dictionary"""
        # Get all authors
        all_authors = [author.name for author in paper.authors]
        # Get main author (first author) and additional authors
        main_author = all_authors[0] if all_authors else "Unknown"
        additional_authors = all_authors[1:] if len(all_authors) > 1 else []
        
        return {
            "id": paper.get_short_id(),
            "title": paper.title,
            "main_author": main_author,
            "additional_authors": additional_authors,
            "all_authors": ", ".join(all_authors),
            "date": paper.published.strftime("%Y-%m-%d"),
            "abstract": paper.summary,
            "pdf_url": paper.pdf_url,
            "categories": ", ".join(paper.categories)
        }
    
    def download_paper(self, paper_id: str, download_dir: str = "./downloads") -> Dict[str, Any]:
        """Download a paper by ID"""
        logger.info(f"Downloading paper: {paper_id}")
        # Create download directory if it doesn't exist
        os.makedirs(download_dir, exist_ok=True)
        
        # Get the paper
        paper = self.search_by_id(paper_id)
        
        if not paper:
            logger.error(f"Paper with ID {paper_id} not found")
            return {
                "success": False,
                "message": f"Paper with ID {paper_id} not found",
                "filepath": None,
                "title": None
            }
        
        # Generate filename
        filename = f"{paper.get_short_id().replace('/', '_')}.pdf"
        filepath = os.path.join(download_dir, filename)
        
        try:
            paper.download_pdf(dirpath=download_dir, filename=filename)
            logger.info(f"Paper downloaded to: {filepath}")
            return {
                "success": True,
                "message": f"Paper '{paper.title}' downloaded successfully to: {filepath}",
                "filepath": filepath,
                "title": paper.title
            }
        except Exception as e:
            logger.error(f"Failed to download paper: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to download paper: {str(e)}",
                "filepath": None,
                "title": None
            }
            
    def download_paper_by_title(self, title: str, download_dir: str = "./downloads") -> Dict[str, Any]:
        """Download a paper by searching for its title"""
        logger.info(f"Downloading paper by title: {title}")
        
        # Search for the paper by title
        papers = self.search_by_title(title, max_results=1)
        
        if not papers:
            logger.error(f"No papers found with title similar to: {title}")
            return {
                "success": False,
                "message": f"No papers found with title similar to: {title}",
                "filepath": None,
                "title": None
            }
        
        # Use the first result
        paper = papers[0]
        paper_id = paper.get_short_id()
        
        # Now download it using the ID
        return self.download_paper(paper_id, download_dir)

# Initialize ArXiv client
arxiv_client = ArxivClient()

# Define MCP tools
@mcp.tool()
async def search_papers(query: str, search_type: str = "title", max_results: int = 5) -> str:
    """Search for papers based on different criteria
    
    Args:
        query: The search query (title, author name, category, or advanced query)
        search_type: Type of search to perform (title, author, category, advanced)
        max_results: Maximum number of results to return
    """
    global last_search_results
    logger.info(f"Search papers request: type={search_type}, query={query}")
    
    # Default to 5 results unless explicitly requested otherwise
    if max_results > 5:
        logger.info(f"User explicitly requested {max_results} results")
        max_results = min(max_results, 20)  # Cap at 20 max
    else:
        max_results = 5  # Default to 5
    
    search_functions = {
        "title": arxiv_client.search_by_title,
        "author": arxiv_client.search_by_author,
        "category": arxiv_client.search_by_category,
        "advanced": arxiv_client.advanced_search
    }
    
    if search_type not in search_functions:
        return json.dumps({
            "message": f"Invalid search type: {search_type}. Valid types are: title, author, category, advanced",
            "papers": []
        }, indent=2)
    
    try:
        papers = search_functions[search_type](query, max_results)
        
        if not papers:
            return json.dumps({
                "message": f"No papers found for {search_type}: {query}",
                "papers": []
            }, indent=2)
        
        # Format results
        formatted_papers = [arxiv_client.format_paper_details(paper) for paper in papers]
        
        # Store the results for later reference
        last_search_results = formatted_papers
        
        # Add to conversation memory
        memory.save_context(
            {"input": f"Search for papers with {search_type} {query}"},
            {"output": f"Found {len(formatted_papers)} papers"}
        )
        
        # Return the papers as a JSON structure with better formatting
        result = {
            "message": f"I interpreted your query as searching for papers by {search_type}: '{query}'.",
            "total_found": len(formatted_papers),
            "papers": formatted_papers
        }
        
        return json.dumps(result, indent=2)
    
    except Exception as e:
        logger.error(f"Error in search_papers: {str(e)}")
        return json.dumps({
            "message": f"Error searching for papers: {str(e)}",
            "papers": []
        }, indent=2)

@mcp.tool()
async def get_paper_details(paper_id: str) -> str:
    """Get detailed information about a specific paper
    
    Args:
        paper_id: The ID of the paper to retrieve details for
    """
    global current_paper_focus
    logger.info(f"Get paper details request: id={paper_id}")
    
    try:
        # Clean paper ID (remove version if present)
        clean_paper_id = paper_id.split('v')[0] if 'v' in paper_id else paper_id
        
        # Search for the paper
        paper = arxiv_client.search_by_id(clean_paper_id)
        
        if not paper:
            error_message = f"Paper with ID {paper_id} not found"
            return json.dumps({
                "success": False,
                "message": error_message,
                "paper": None
            }, indent=2)
        
        # Set this as the currently focused paper
        current_paper_focus = clean_paper_id
        
        details = arxiv_client.format_paper_details(paper)
        
        # Add to conversation memory
        memory.save_context(
            {"input": f"Get details for paper {paper_id}"},
            {"output": f"Retrieved details for {details['title']}"}
        )
        
        # Return formatted details as JSON
        formatted_details = {
            "success": True,
            "message": f"Retrieved details for paper {paper_id}",
            "paper": details
        }
        
        return json.dumps(formatted_details, indent=2)
    
    except Exception as e:
        logger.error(f"Error in get_paper_details: {str(e)}")
        return json.dumps({
            "success": False,
            "message": f"Error retrieving paper details: {str(e)}",
            "paper": None
        }, indent=2)

@mcp.tool()
async def download_paper(paper_id: str, download_dir: str = "./downloads") -> str:
    """Download a paper by ID
    
    Args:
        paper_id: The ID of the paper to download
        download_dir: Directory to save the downloaded paper
    """
    logger.info(f"Download paper request: id={paper_id}, dir={download_dir}")
    
    try:
        # Clean the paper ID (remove version if present)
        clean_paper_id = paper_id.split('v')[0] if 'v' in paper_id else paper_id
        
        if not clean_paper_id:
            return json.dumps({
                "success": False,
                "message": "Invalid paper ID. Please provide a valid arXiv ID.",
                "filepath": None,
                "title": None
            }, indent=2)
        
        # Create download directory if it doesn't exist
        os.makedirs(download_dir, exist_ok=True)
        
        # Ensure the download directory has proper permissions
        try:
            # Make sure the directory is readable and writable
            os.chmod(download_dir, 0o755)
        except Exception as e:
            logger.warning(f"Could not set permissions on download directory: {str(e)}")
        
        # Get the paper
        paper = arxiv_client.search_by_id(clean_paper_id)
        
        if not paper:
            return json.dumps({
                "success": False,
                "message": f"Paper with ID {clean_paper_id} not found.",
                "filepath": None,
                "title": None
            }, indent=2)
        
        # Generate filename
        filename = f"{clean_paper_id.replace('/', '_')}.pdf"
        filepath = os.path.join(download_dir, filename)
        
        # Record that we're about to download this paper
        memory.save_context(
            {"input": f"Download paper {clean_paper_id}"},
            {"output": f"Attempting to download paper {paper.title} to {filepath}"}
        )
        
        try:
            # Download the paper
            paper.download_pdf(dirpath=download_dir, filename=filename)
            logger.info(f"Paper downloaded to: {filepath}")
            
            return json.dumps({
                "success": True,
                "message": f"Paper '{paper.title}' downloaded successfully to: {filepath}",
                "filepath": filepath,
                "title": paper.title
            }, indent=2)
            
        except PermissionError:
            logger.error(f"Permission denied when downloading to {download_dir}")
            return json.dumps({
                "success": False,
                "message": f"Permission denied: Cannot write to {download_dir}. Please ensure you have proper write permissions for this directory.",
                "filepath": None,
                "title": None
            }, indent=2)
        except Exception as e:
            logger.error(f"Failed to download paper: {str(e)}")
            return json.dumps({
                "success": False,
                "message": f"Failed to download paper: {str(e)}",
                "filepath": None,
                "title": None
            }, indent=2)
    
    except Exception as e:
        logger.error(f"Error in download_paper: {str(e)}")
        return json.dumps({
            "success": False,
            "message": f"Error downloading paper: {str(e)}",
            "filepath": None,
            "title": None
        }, indent=2)

@mcp.tool()
async def download_paper_by_title(title: str, download_dir: str = "./downloads") -> str:
    """Download a paper by searching for its title
    
    Args:
        title: The title of the paper to download
        download_dir: Directory to save the downloaded paper
    """
    logger.info(f"Download paper by title request: title={title}, dir={download_dir}")
    
    try:
        # Create download directory if it doesn't exist
        os.makedirs(download_dir, exist_ok=True)
        
        # Use the download by title function
        result = arxiv_client.download_paper_by_title(title, download_dir)
        
        # Return as JSON
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Error in download_paper_by_title: {str(e)}")
        return json.dumps({
            "success": False,
            "message": f"Error downloading paper: {str(e)}",
            "filepath": None,
            "title": None
        }, indent=2)

@mcp.tool()
async def process_natural_language_query(query: str) -> str:
    """Process a natural language query to find papers
    
    Args:
        query: Natural language query about papers
    """
    global current_paper_focus, last_search_results
    logger.info(f"Natural language query: {query}")
    
    try:
        # First, check if this is explicitly about downloading a specific paper
        download_patterns = [
            r'download\s+(?:paper|article)?\s*(?:with)?\s*(?:id|arxiv id|number)?\s*:?\s*(\d+\.\d+v?\d*)',
            r'download\s+(?:the)?\s*(?:paper|article)\s+(\d+\.\d+v?\d*)',
            r'get\s+(?:paper|article)\s+(\d+\.\d+v?\d*)'
        ]
        
        for pattern in download_patterns:
            match = re.search(pattern, query.lower())
            if match:
                paper_id = match.group(1)
                logger.info(f"Detected download request for paper ID: {paper_id}")
                return await download_paper(paper_id)
        
        # Check for download by title requests 
        title_download_patterns = [
            r'download\s+(?:paper|article)\s+(?:titled|called|with\s+title)\s+"([^"]+)"',
            r'download\s+(?:paper|article)\s+(?:titled|called|with\s+title)\s+\'([^\']+)\'',
            r'download\s+(?:paper|article)\s+(?:titled|called|with\s+title)\s+([^"\'\.]+)',
            r'download\s+"([^"]+)"',
            r'download\s+\'([^\']+)\'',
        ]
        
        for pattern in title_download_patterns:
            match = re.search(pattern, query.lower())
            if match:
                title = match.group(1).strip()
                logger.info(f"Detected download request for paper title: {title}")
                return await download_paper_by_title(title)
        
        # Check for "download it" or "download the paper" type requests
        if re.search(r'download\s+(?:it|this|that|the\s+paper)', query.lower()):
            if current_paper_focus:
                return await download_paper(current_paper_focus)
            elif last_search_results:
                # If there's only one result, download it
                if len(last_search_results) == 1:
                    return await download_paper(last_search_results[0]["id"])
                else:
                    return json.dumps({
                        "message": "Please specify which paper you'd like to download by providing its ID number.",
                        "papers": []
                    }, indent=2)
            else:
                return json.dumps({
                    "message": "Please specify which paper you'd like to download by providing its ID number or title.",
                    "papers": []
                }, indent=2)
        
        # Add handling for date-specific queries
        date_patterns = [
            r'from\s+(\d{4})(?:-(\d{1,2}))?',
            r'in\s+(\d{4})(?:-(\d{1,2}))?',
            r'published\s+in\s+(\d{4})(?:-(\d{1,2}))?',
            r'since\s+(\d{4})(?:-(\d{1,2}))?',
            r'after\s+(\d{4})(?:-(\d{1,2}))?',
            r'before\s+(\d{4})(?:-(\d{1,2}))?',
            r'year\s+(\d{4})',
            r'month\s+(\d{1,2})(?:\s+of\s+(\d{4}))?',
            r'(\d{4})(?:-(\d{1,2}))?'
        ]
        
        date_constraints = []
        for pattern in date_patterns:
            matches = re.findall(pattern, query)
            if matches:
                for match in matches:
                    if isinstance(match, tuple):
                        year = match[0]
                        month = match[1] if len(match) > 1 and match[1] else None
                        
                        # Skip if this doesn't look like a year
                        if not (1900 <= int(year) <= 2030):
                            continue
                            
                        if month and month.strip():
                            # Ensure month is two digits
                            month = month.zfill(2) if len(month) == 1 else month
                            date_constraints.append(f"{year}-{month}")
                        else:
                            date_constraints.append(year)
                    else:
                        # Single string match
                        if 1900 <= int(match) <= 2030:  # Looks like a year
                            date_constraints.append(match)
                            
        # Use OpenAI to understand the query
        prompt = f"""
        Based on the following user query about academic papers, extract the search intent and parameters:
        
        User query: "{query}"
        
        Extract:
        1. Search type (title, author, category, or advanced)
        2. Search query (the specific title, author name, category, or advanced query)
        3. Date constraints (year, month, range if applicable)
        4. Any additional instructions or constraints
        
        Respond in the following JSON format:
        {{
            "search_type": "title or author or category or advanced",
            "search_query": "the extracted query",
            "date_constraint": "YYYY or YYYY-MM or range if applicable",
            "additional_info": "any additional instructions or constraints"
        }}
        """
        
        response = llm.invoke(prompt).content
        logger.debug(f"LLM response: {response}")
        
        # Extract the JSON from the response
        try:
            # Find JSON pattern in the response
            json_match = re.search(r'({.*})', response.replace('\n', ''), re.DOTALL)
            if json_match:
                extracted_json = json_match.group(1)
                parsed_info = json.loads(extracted_json)
            else:
                # Fallback to direct parsing if no clear JSON pattern
                parsed_info = json.loads(response)
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON from LLM response, using fallback parsing")
            # Fallback to regex pattern matching
            search_type_match = re.search(r'"search_type":\s*"([^"]+)"', response)
            search_query_match = re.search(r'"search_query":\s*"([^"]+)"', response)
            date_constraint_match = re.search(r'"date_constraint":\s*"([^"]*)"', response)
            additional_info_match = re.search(r'"additional_info":\s*"([^"]+)"', response)
            
            parsed_info = {
                "search_type": search_type_match.group(1) if search_type_match else "title",
                "search_query": search_query_match.group(1) if search_query_match else query,
                "date_constraint": date_constraint_match.group(1) if date_constraint_match else "",
                "additional_info": additional_info_match.group(1) if additional_info_match else ""
            }
        
        search_type = parsed_info.get("search_type", "title").lower()
        search_query = parsed_info.get("search_query", "")
        date_constraint = parsed_info.get("date_constraint", "")
        additional_info = parsed_info.get("additional_info", "")
        
        # If we have date constraints from regex but not from LLM, use the regex ones
        if not date_constraint and date_constraints:
            date_constraint = date_constraints[0]  # Use the first one found
            
        # Convert max_results from additional_info if possible
        max_results = 5  # Default
        results_match = re.search(r'(?:show|display|return|get|find)\s+(\d+)', additional_info.lower())
        if results_match:
            try:
                max_results = int(results_match.group(1))
                max_results = min(max_results, 20)  # Cap at 20
            except:
                pass
        
        # Check for direct keyword to use all: instead of specific search type
        if (search_type == "category" or search_type == "title") and \
           all(keyword not in search_query.lower() for keyword in ["cs.", "math.", "physics.", "q-bio."]):
            # This is likely a general topic, use simple query
            search_query_clean = search_query
            search_type = "advanced" 
            
            # For date constraints, use an appropriate format for arXiv
            if date_constraint:
                year = date_constraint[:4]  # Get the year
                search_query_clean = f"all:{search_query_clean} AND all:{year}"
            else:
                search_query_clean = f"all:{search_query_clean}" 
                
            logger.info(f"Modified to use all: prefix - query: {search_query_clean}")
            search_query = search_query_clean
        
        # Validate search type
        valid_search_types = ["title", "author", "category", "advanced"]
        if search_type not in valid_search_types:
            search_type = "title"
        
        # Perform the search
        logger.info(f"Performing search with type: {search_type}, query: {search_query}, max_results: {max_results}")
        search_result = await search_papers(search_query, search_type, max_results)
        
        # Add to conversation memory
        memory.save_context(
            {"input": query},
            {"output": f"Interpreted as searching for {search_type}: {search_query}"}
        )
        
        return search_result
    
    except Exception as e:
        logger.error(f"Error processing natural language query: {str(e)}")
        return json.dumps({
            "message": f"Error processing your query: {str(e)}",
            "papers": []
        }, indent=2)

# Define MCP resources
@mcp.resource("arxiv://paper/{paper_id}")
async def paper_resource(paper_id: str) -> str:
    """Resource for retrieving paper details
    
    Args:
        paper_id: The ID of the paper to retrieve
    """
    logger.info(f"Paper resource request: id={paper_id}")
    return await get_paper_details(paper_id)

# Define MCP prompts
@mcp.prompt()
def search_prompt(search_type: str = "title") -> str:
    """Create a prompt for searching arXiv papers
    
    Args:
        search_type: Type of search to perform (title, author, category)
    """
    prompts = {
        "title": """I'm looking for papers with titles related to: [YOUR TOPIC]
Example: "Attention Mechanisms in Neural Networks" or "Quantum Computing Applications" """,
        
        "author": """I'm looking for papers by the author: [AUTHOR NAME]
Example: "Geoffrey Hinton" or "Yoshua Bengio" """,
        
        "category": """I'm looking for papers in the category: [CATEGORY]
Examples:
- cs.AI (Artificial Intelligence)
- cs.ML (Machine Learning)
- cs.CV (Computer Vision)
- physics.atom-ph (Atomic Physics)
- math.AG (Algebraic Geometry)
- q-bio.BM (Biomolecules) """
    }
    
    if search_type not in prompts:
        return prompts["title"]
    
    return prompts[search_type]

# Run the server
if __name__ == "__main__":
    logger.info("Starting arXiv MCP server")
    mcp.run(transport='stdio')