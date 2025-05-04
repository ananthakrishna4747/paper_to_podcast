# main.py
import os
import logging
import streamlit as st
from dotenv import load_dotenv

# Import UI app
from ui.app import run_app

# Setup logging
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("arxiv_podcast.log"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("ArXivPodcast")

# Main function
def main():
    # Load environment variables
    load_dotenv(override=True)  # Force override existing env vars to ensure .env is used
    
    # Setup logging
    logger = setup_logging()
    
    # Check for required environment variables
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY not found in environment variables!")
        print("WARNING: OPENAI_API_KEY not found. Please set it in .env file or environment.")
        # Explicitly set it for this process if it's in .env but not in environment
        with open('.env') as f:
            for line in f:
                if line.startswith('OPENAI_API_KEY='):
                    api_key = line.strip().split('=')[1].strip('"\'')
                    os.environ['OPENAI_API_KEY'] = api_key
                    logger.info("Set OPENAI_API_KEY from .env file")
                    break
    
    # Create directories if they don't exist
    os.makedirs("downloads", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    
    logger.info("Starting ArXiv Podcast Generator")
    
    # Run Streamlit app
    run_app()

if __name__ == "__main__":
    main()