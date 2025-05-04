# core/parse.py
import os
import logging
import PyPDF2
from agents import function_tool, RunContextWrapper
from typing import Dict, List, Optional, Any

logger = logging.getLogger("ArXivParse")

@function_tool
async def extract_paper_text(
    ctx: RunContextWrapper[Any],
    pdf_path: str
) -> str:
    """Extract text content from a research paper PDF."""
    logger.info(f"Extracting text from PDF: {pdf_path}")
    ctx.context.status_message = "Extracting text from PDF..."
    ctx.context.progress = 10
    
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            page_count = len(reader.pages)
            logger.debug(f"PDF contains {page_count} pages")
            
            ctx.context.progress = 20
            ctx.context.status_message = f"Extracting text from {page_count} pages..."
            
            full_text = ""
            for page_num in range(page_count):
                # Update progress
                progress = 20 + int(70 * (page_num + 1) / page_count)
                ctx.context.progress = progress
                ctx.context.status_message = f"Extracting text from page {page_num+1}/{page_count}..."
                
                logger.debug(f"Extracting text from page {page_num+1}/{page_count}")
                full_text += reader.pages[page_num].extract_text()
            
            # Store in context
            ctx.context.paper_text = full_text
            ctx.context.page_count = page_count
            ctx.context.word_count = len(full_text.split())
            ctx.context.current_stage = "download"
            ctx.context.progress = 100
            ctx.context.status_message = f"Extracted {ctx.context.word_count} words from {page_count} pages"
            
            logger.info(f"Extracted approximately {ctx.context.word_count} words")
            return full_text
    except Exception as e:
        error_msg = f"Error extracting text from PDF: {e}"
        logger.error(error_msg)
        ctx.context.progress = 0
        ctx.context.status_message = error_msg
        return error_msg

@function_tool
async def parse_paper_sections(
    ctx: RunContextWrapper[Any],
    pdf_path: str
) -> Dict[str, str]:
    """Attempt to parse paper into logical sections."""
    logger.info(f"Parsing paper sections from: {pdf_path}")
    ctx.context.status_message = "Parsing paper sections..."
    ctx.context.progress = 10
    
    # First ensure we have the full text
    if not hasattr(ctx.context, 'paper_text') or not ctx.context.paper_text:
        ctx.context.status_message = "Extracting text before parsing sections..."
        await extract_paper_text(ctx, pdf_path)
    
    ctx.context.progress = 50
    ctx.context.status_message = "Identifying paper sections..."
    
    full_text = ctx.context.paper_text
    
    # Simple heuristic-based section detection
    common_sections = [
        "Abstract", "Introduction", "Related Work", "Background",
        "Methodology", "Methods", "Experiment", "Experiments", "Results",
        "Discussion", "Conclusion", "References"
    ]
    
    sections = {}
    lines = full_text.split("\n")
    current_section = "Header"
    sections[current_section] = ""
    
    for i, line in enumerate(lines):
        # Update progress
        if i % 50 == 0:
            progress = 50 + int(40 * i / len(lines))
            ctx.context.progress = min(progress, 90)
            
        matched = False
        for section_name in common_sections:
            if line.strip() == section_name or line.strip().startswith(section_name + ":"):
                current_section = section_name
                sections[current_section] = ""
                matched = True
                break
                
        if not matched:
            sections[current_section] += line + "\n"
    
    # Store in context
    ctx.context.sections = sections
    ctx.context.current_stage = "download"
    ctx.context.progress = 100
    ctx.context.status_message = f"Parsed paper into {len(sections)} sections"
    
    logger.info(f"Parsed paper into {len(sections)} sections")
    
    return sections