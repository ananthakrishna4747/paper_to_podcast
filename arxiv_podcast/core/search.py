# core/search.py
import os
import logging
import re
import arxiv
from agents import function_tool, RunContextWrapper
from typing import List, Dict, Optional, Any

logger = logging.getLogger("ArXivSearch")

@function_tool
async def search_arxiv_by_query(
    ctx: RunContextWrapper[Any], 
    query: str,
    max_results: int  # No default value
) -> List[Dict]:
    """Search arXiv papers using a query string."""
    logger.info(f"Searching arXiv for: {query}")
    
    # Handle default value inside the function
    if not max_results or max_results <= 0:
        max_results = 10
    
    ctx.context.status_message = f"Searching arXiv for: {query}"
    ctx.context.progress = 10
    
    # Extract specific paper ID if present in the query
    paper_id = extract_arxiv_id_from_text(query)
    if paper_id:
        logger.info(f"Found arXiv ID in query: {paper_id}")
        paper_info = await search_arxiv_by_id(ctx, paper_id)
        if paper_info:
            return [paper_info]
    
    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance
        )
        
        results = []
        for r in client.results(search):
            # Extract and format the paper ID
            paper_id = r.get_short_id()
            
            # Build paper info with prominent ID placement
            paper_info = {
                "arxiv_id": paper_id,
                "title": r.title,
                "authors": [author.name for author in r.authors],
                "summary": r.summary[:300] + "..." if len(r.summary) > 300 else r.summary,
                "published": r.published.strftime("%Y-%m-%d"),
                "download_command": f"Download paper {paper_id}"
            }
            
            results.append(paper_info)
            
            # Limit to max_results
            if len(results) >= max_results:
                break
        
        # Store results in context
        ctx.context.search_results = results
        ctx.context.current_stage = "search"
        ctx.context.progress = 100
        ctx.context.status_message = f"Found {len(results)} papers matching the query"
        
        logger.info(f"Found {len(results)} papers matching the query")
        

        # if "attention is all you need" in query.lower() or "vaswani" in query.lower():
        #     logger.info("Query appears to be looking for the Transformer paper")
        #     # Find papers with matching titles or authors
        #     attention_papers = [p for p in results if 
        #                        "attention is all you need" in p["title"].lower() or
        #                        any("vaswani" in author.lower() for author in p["authors"])]
            
        #     if attention_papers:
        #         target_paper = attention_papers[0]
        #         logger.info(f"Found target paper: {target_paper['arxiv_id']}")
                
        #         # Move the target paper to the top of results
        #         if results[0] != target_paper:
        #             results.remove(target_paper)
        #             results.insert(0, target_paper)
        
        return results
    except Exception as e:
        logger.error(f"Error searching arXiv: {e}")
        ctx.context.progress = 0
        ctx.context.status_message = f"Error searching arXiv: {e}"
        return []

@function_tool
async def search_arxiv_by_id(
    ctx: RunContextWrapper[Any], 
    paper_id: str
) -> Optional[Dict]:
    """Find a specific paper on arXiv by its ID."""
    logger.info(f"Searching for paper with ID: {paper_id}")
    ctx.context.status_message = f"Searching for paper with ID: {paper_id}"
    ctx.context.progress = 10
    
    try:
        client = arxiv.Client()
        search = arxiv.Search(id_list=[paper_id])
        
        result = next(client.results(search))
        paper_info = {
            "arxiv_id": paper_id,
            "title": result.title,
            "authors": [author.name for author in result.authors],
            "summary": result.summary,
            "published": result.published.strftime("%Y-%m-%d"),
            "download_command": f"Download paper {paper_id}"
        }
        
        # Store paper info in context
        ctx.context.paper_id = paper_id
        ctx.context.paper_title = result.title
        ctx.context.paper_authors = [author.name for author in result.authors]
        ctx.context.paper_summary = result.summary
        ctx.context.current_stage = "search"
        ctx.context.progress = 100
        ctx.context.status_message = f"Found paper: {result.title}"
        
        logger.info(f"Found paper: {result.title}")
        return paper_info
    except StopIteration:
        logger.warning(f"No paper found with ID: {paper_id}")
        ctx.context.progress = 0
        ctx.context.status_message = f"No paper found with ID: {paper_id}"
        return None
    except Exception as e:
        logger.error(f"Error searching for paper: {e}")
        ctx.context.progress = 0
        ctx.context.status_message = f"Error searching for paper: {e}"
        return None

@function_tool
async def download_paper(
    ctx: RunContextWrapper[Any], 
    paper_id: str,
    output_dir: str  # No default value
) -> Optional[str]:
    """Download a paper PDF by its arXiv ID."""
    logger.info(f"Downloading paper with ID: {paper_id}")
    
    # Handle default value inside the function
    if not output_dir:
        output_dir = "./downloads"
        
    ctx.context.status_message = f"Downloading paper {paper_id}..."
    ctx.context.progress = 10
    
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        client = arxiv.Client()
        search = arxiv.Search(id_list=[paper_id])
        
        ctx.context.progress = 20
        paper = next(client.results(search))
        filename = f"{paper_id.replace('/', '_')}.pdf"
        filepath = os.path.join(output_dir, filename)
        
        # Store paper info in context
        ctx.context.paper_id = paper_id
        ctx.context.paper_title = paper.title
        ctx.context.paper_authors = [author.name for author in paper.authors]
        ctx.context.paper_summary = paper.summary
        
        ctx.context.progress = 40
        ctx.context.status_message = f"Downloading {paper.title}..."
        
        # Download the PDF
        paper.download_pdf(dirpath=output_dir, filename=filename)
        
        # Store in context for later use
        ctx.context.pdf_path = filepath
        ctx.context.current_stage = "download"
        ctx.context.progress = 100
        ctx.context.status_message = f"Downloaded paper to {filepath}"
        
        logger.info(f"Downloaded paper to: {filepath}")
        
        return filepath
    except StopIteration:
        ctx.context.progress = 0
        ctx.context.status_message = f"No paper found with ID: {paper_id}"
        logger.warning(f"No paper found with ID: {paper_id}")
        return None
    except Exception as e:
        ctx.context.progress = 0
        ctx.context.status_message = f"Error downloading paper: {e}"
        logger.error(f"Error downloading paper: {e}")
        return None

def extract_arxiv_id_from_text(text):
    """
    Extract arXiv ID from text if present.
    Common patterns: 1234.56789, 1234.56789v1, cond-mat/9912345v1
    """
    # Look for modern arXiv ID format: YYMM.NNNNN or YYMM.NNNNNvN
    modern_pattern = r'\b\d{4}\.\d{4,5}(?:v\d+)?\b'
    modern_match = re.search(modern_pattern, text)
    if modern_match:
        return modern_match.group(0)
    
    # Look for old arXiv ID format: archive/XXXXXXX or archive/XXXXXXXvN
    old_pattern = r'\b[a-z-]+(?:\.[a-z]{2})?\/\d{7}(?:v\d+)?\b'
    old_match = re.search(old_pattern, text)
    if old_match:
        return old_match.group(0)
    
    return None