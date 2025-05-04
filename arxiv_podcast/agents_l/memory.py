# agents_l/memory.py
import logging
import os
from langchain.memory import ConversationBufferMemory
from agents import function_tool, RunContextWrapper
from typing import Any, Dict, Optional, List, Tuple

logger = logging.getLogger("AgentMemory")

# Create conversation memory with a higher buffer size
MEMORY_SIZE = 10  # Number of conversation turns to remember
memory = ConversationBufferMemory(
    return_messages=True, 
    memory_key="chat_history", 
    input_key="input", 
    output_key="output", 
    k=MEMORY_SIZE
)

# Backup memory in case the ConversationBufferMemory fails
backup_memory = []

@function_tool
async def save_to_memory(
    ctx: RunContextWrapper[Any],
    human_input: str,
    ai_response: str
) -> bool:
    """Save conversation to memory."""
    try:
        logger.info(f"Saving to memory: Human: {human_input[:50]}... AI: {ai_response[:50]}...")
        
        # Save to langchain memory
        memory.save_context({"input": human_input}, {"output": ai_response})
        
        # Also save to backup memory
        backup_memory.append((human_input, ai_response))
        if len(backup_memory) > MEMORY_SIZE:
            backup_memory.pop(0)  # Remove oldest conversation

        # If the conversation is related to a specific paper, save that in context
        if ctx.context.paper_id and "paper_id" not in ctx.context.__dict__:
            ctx.context.paper_id = ctx.context.paper_id
            
        # Save if we're in a particular stage of the process
        if "download" in human_input.lower() or "download" in ai_response.lower():
            ctx.context.current_stage = "download"
        elif "podcast" in human_input.lower() or "podcast" in ai_response.lower():
            ctx.context.current_stage = "generate"
            
        logger.info("Successfully saved to memory")
        return True
    except Exception as e:
        # logger.error(f"Error saving to memory: {e}")
        return False

@function_tool
async def get_memory(ctx: RunContextWrapper[Any]) -> str:
    """Retrieve conversation history."""
    try:
        logger.info("Retrieving conversation history")
        
        # Try getting from langchain memory
        try:
            buffer = memory.buffer
            logger.info(f"Retrieved memory buffer of length: {len(buffer)}")
            
            # If empty, try backup
            if not buffer:
                buffer = format_backup_memory()
                logger.info(f"Using backup memory: {len(buffer)} chars")
                
            return buffer
        except Exception as e:
            # logger.error(f"Error retrieving from langchain memory: {e}")
            
            # Use backup memory
            buffer = format_backup_memory()
            logger.info(f"Using backup memory: {len(buffer)} chars")
            return buffer
    except Exception as e:
        logger.error(f"Error retrieving memory: {e}")
        # return "Error retrieving conversation history."

def format_backup_memory() -> str:
    """Format backup memory into a string."""
    buffer = ""
    for i, (human, ai) in enumerate(backup_memory):
        buffer += f"Human {i+1}: {human}\nAI {i+1}: {ai}\n\n"
    return buffer

# Helper functions to extract important information from memory
def extract_paper_id_from_memory():
    """Extract paper ID from memory if present."""
    try:
        # Check both memories
        buffer = memory.buffer
        if not buffer:
            buffer = format_backup_memory()
            
        # Look for arXiv ID patterns in the buffer
        import re
        # Modern arXiv ID pattern (YYMM.NNNNN)
        modern_pattern = r'\b\d{4}\.\d{4,5}(?:v\d+)?\b'
        modern_matches = re.findall(modern_pattern, buffer)
        
        # Old arXiv ID pattern (archive/XXXXXXX)
        old_pattern = r'\b[a-z-]+(?:\.[a-z]{2})?\/\d{7}(?:v\d+)?\b'
        old_matches = re.findall(old_pattern, buffer)
        
        all_matches = modern_matches + old_matches
        return all_matches[-1] if all_matches else None
    except Exception as e:
        # logger.error(f"Error extracting paper ID from memory: {e}")
        return None

def is_attention_paper_mentioned():
    """Check if the Attention paper is mentioned in memory."""
    try:
        # Check both memories
        buffer = memory.buffer
        if not buffer:
            buffer = format_backup_memory()
            
        # Look for mentions of the paper
        # attention_pattern = r'attention is all you need|ashish vaswani|transformer model'
        # return bool(re.search(attention_pattern, buffer.lower()))
    except Exception as e:
        # logger.error(f"Error checking for paper mention: {e}")
        return False