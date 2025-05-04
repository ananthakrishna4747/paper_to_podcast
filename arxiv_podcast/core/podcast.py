# core/podcast.py
import os
import logging
from openai import OpenAI
from agents import function_tool, RunContextWrapper
from typing import Dict, Any, List

logger = logging.getLogger("ArXivPodcast")

@function_tool
async def generate_podcast_script(
    ctx: RunContextWrapper[Any],
    pdf_path: str,  # No default value
    duration: int,  # No default value
    speaker_count: int,  # No default value
    speaker_genders: List[str]  # No default value
) -> Dict:
    """Generate a podcast script from a research paper PDF."""
    # Set defaults inside the function
    if not pdf_path and hasattr(ctx.context, 'pdf_path'):
        pdf_path = ctx.context.pdf_path
    
    if not duration:
        duration = 10
    
    if not speaker_count:
        speaker_count = 2
    
    if not speaker_genders:
        speaker_genders = ["male", "female"]
    
    logger.info(f"Generating podcast script for {duration} minutes with {speaker_count} speakers")
    ctx.context.status_message = f"Starting podcast script generation for {duration} minute podcast..."
    ctx.context.progress = 10
    
    if not hasattr(ctx.context, 'paper_text') or not ctx.context.paper_text:
        if not pdf_path:
            error_msg = "Error: No PDF path provided and no paper text available."
            logger.error(error_msg)
            ctx.context.progress = 0
            ctx.context.status_message = error_msg
            return {"success": False, "error": error_msg}
        
        # Import extract_paper_text from parse module
        from core.parse import extract_paper_text
        ctx.context.status_message = "Extracting paper text before script generation..."
        await extract_paper_text(ctx, pdf_path)
    
    # Set these in context
    ctx.context.target_duration = duration
    ctx.context.speaker_count = speaker_count
    ctx.context.speaker_genders = speaker_genders
    ctx.context.current_stage = "generate"
    
    # Generate speaker names if not already set
    if not hasattr(ctx.context, 'speaker_names') or not ctx.context.speaker_names:
        ctx.context.speaker_names = _generate_speaker_names(speaker_count, speaker_genders)
    
    ctx.context.progress = 20
    ctx.context.status_message = f"Preparing script generation with {speaker_count} speakers..."
    
    # Get the model ID from environment or context
    model_id = os.getenv("OPENAI_MODEL_ID", "ft:gpt-4o-mini-2024-07-18:personal::BM4yUkOI")
    
    # Set word count targets based on duration (160 words per minute)
    target_word_count = duration * 160
    acceptable_deviation = 100  # Allowable deviation
    
    logger.info(f"Target podcast duration: {duration} minutes ({target_word_count} words)")
    
    # Generate system prompt for podcast script generation
    system_prompt = _generate_system_prompt(
        target_word_count, 
        acceptable_deviation, 
        speaker_count, 
        ctx.context.speaker_names, 
        speaker_genders,
        duration
    )
    
    ctx.context.progress = 30
    ctx.context.status_message = f"Generating script using model {model_id}..."
    
    try:
        logger.info(f"Using model: {model_id} for script generation")
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Create a generation prompt
        generation_prompt = f"""Create a {duration}-minute technical podcast script using the Feynman technique with EXACTLY {target_word_count}±{acceptable_deviation} words about this research paper. 

The script should be a natural conversation between {speaker_count} hosts: {', '.join(ctx.context.speaker_names)}.

Paper Text:
{ctx.context.paper_text[:50000]}"""

        ctx.context.progress = 40
        ctx.context.status_message = "Generating podcast script content..."
        
        # Generate the script
        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": generation_prompt}
            ],
            temperature=0.4,
            max_tokens=4096
        )
        
        generated_script = response.choices[0].message.content
        script_word_count = len(generated_script.split())
        logger.info(f"Generated script with {script_word_count} words (target: {target_word_count})")
        
        # Store in context
        ctx.context.podcast_script = generated_script
        ctx.context.progress = 100
        ctx.context.status_message = f"Generated podcast script with {script_word_count} words"
        
        return {
            "success": True,
            "script_word_count": script_word_count,
            "target_word_count": target_word_count,
            "deviation": abs(script_word_count - target_word_count)
        }
    except Exception as e:
        error_msg = f"Error generating podcast script: {e}"
        logger.error(error_msg)
        ctx.context.progress = 0
        ctx.context.status_message = error_msg
        return {"success": False, "error": error_msg}

def _generate_speaker_names(speaker_count, speaker_genders):
    """Generate speaker names based on gender preferences."""
    male_names = ["David", "Michael", "John", "Robert", "James"]
    female_names = ["Emma", "Sarah", "Jennifer", "Maria", "Lisa"]
    
    speaker_names = []
    for i, gender in enumerate(speaker_genders[:speaker_count]):
        if gender.lower() == "male":
            name = male_names[i % len(male_names)]
        else:
            name = female_names[i % len(female_names)]
        speaker_names.append(name)
    
    return speaker_names

def _generate_system_prompt(target_word_count, acceptable_deviation, speaker_count, speaker_names, speaker_genders, duration):
    """Generate system prompt for podcast script generation."""
    # Define section allocations based on podcast duration
    if duration <= 5:
        focus_style = "technical and minimalist"
    elif duration <= 10:
        focus_style = "technical with essential context"
    elif duration <= 15:
        focus_style = "comprehensive technical explanation"
    elif duration <= 20:
        focus_style = "in-depth technical analysis"
    else:
        focus_style = "comprehensive expert discussion"
    
    # Build speaker structure string
    speaker_structure = ""
    for i, (name, gender) in enumerate(zip(speaker_names, speaker_genders)):
        if i == 0:
            role = "Main host who guides the conversation"
        elif i == 1:
            role = "Subject matter expert who explains concepts clearly"
        else:
            role = f"Additional expert providing specialized perspective"
        
        speaker_structure += f"{name.upper()} ({gender.capitalize()} host):\n"
        speaker_structure += f"- {role}\n"
        speaker_structure += f"- {'Asks insightful questions and facilitates discussion' if i == 0 else 'Uses the Feynman technique to break down complex ideas'}\n"
        speaker_structure += f"- {'Shows authentic interest in the technical content' if i == 0 else 'Responds with clear, accurate explanations'}\n\n"
    
    # Generate the complete system prompt
    return f"""
    Generate a technical podcast script explaining a research paper using the Richard Feynman technique. The script must contain EXACTLY {target_word_count}±{acceptable_deviation} words total and take the form of a natural conversation between {speaker_count} hosts.
    
    Podcast Format:
    • Show Name: "Capstone 5082"
    • Style: {focus_style}, technically accurate yet accessible
    • Hosts: {", ".join([f'"{name}" ({gender})' for name, gender in zip(speaker_names, speaker_genders)])}
    
    CONVERSATION STRUCTURE:
    
    The podcast should be a natural flowing conversation between {speaker_count} hosts:
    
    {speaker_structure}
    
    RICHARD FEYNMAN TECHNIQUE REQUIREMENTS:
    
    1. Explain complex concepts using simple, clear language that a smart undergraduate could understand
    2. Break down complicated ideas into their fundamental components
    3. Avoid jargon whenever possible; when technical terms are necessary, define them immediately
    4. Use concrete examples instead of abstract explanations
    5. Focus on building understanding from first principles rather than relying on analogies
    6. Identify and clarify the core concepts that make everything else make sense
    7. Test understanding by applying concepts to new situations or problems
    
    Format Requirements:
    • Use the format "**{speaker_names[0]}:** Text..." for speaker indicators
    • Use minimal stage directions, focusing on technical content
    
    ABSOLUTELY CRITICAL: The script MUST contain EXACTLY {target_word_count}±{acceptable_deviation} words total. Count carefully!
    """