# ui/app.py
import os
import streamlit as st
import asyncio
import logging
import time
from openai import OpenAI
from agents import Agent, Runner
from agents_l.context import AppContext
from agents_l.orchestrator import create_orchestrator
from agents_l.memory import save_to_memory

logger = logging.getLogger("Streamlit")

def run_app():
    # Setup page configuration
    st.set_page_config(
        page_title="ArXiv Podcast Generator",
        page_icon="📚",
        layout="wide"
    )
    
    # Initialize session state
    if "initialized" not in st.session_state:
        st.session_state.initialized = True
        st.session_state.context = AppContext()
        st.session_state.orchestrator = create_orchestrator()
        st.session_state.messages = [{
            "role": "assistant", 
            "content": "Hello! I can help you find arXiv papers and convert them into podcasts. What paper would you like to search for?"
        }]
        st.session_state.conversation_history = []
        st.session_state.last_user_input = None
        logger.info("Session initialized")
    
    # Create a clean interface
    st.title("📚 ArXiv Podcast Generator")
    
    # Sidebar with status
    with st.sidebar:
        st.header("Status")
        
        # Display current stage
        stage = st.session_state.context.current_stage
        stages = {
            "search": "🔍 Search for Papers",
            "download": "📥 Download and Parse",
            "generate": "📝 Generate Script",
            "audio": "🎙️ Create Podcast Audio"
        }
        
        st.subheader(stages.get(stage, "Getting Started"))
        
        # Show progress bar
        if st.session_state.context.progress > 0:
            st.progress(st.session_state.context.progress / 100)
            st.caption(st.session_state.context.status_message)
        
        # Show paper info if available
        if st.session_state.context.paper_title:
            st.markdown("---")
            st.subheader("Current Paper")
            st.markdown(f"**Title:** {st.session_state.context.paper_title}")
            st.markdown(f"**Authors:** {', '.join(st.session_state.context.paper_authors[:3])}")
            if len(st.session_state.context.paper_authors) > 3:
                st.markdown(f"and {len(st.session_state.context.paper_authors) - 3} more")
            st.markdown(f"**ID:** {st.session_state.context.paper_id}")
            
            if st.session_state.context.target_duration:
                st.markdown(f"**Podcast Duration:** {st.session_state.context.target_duration} minutes")
        
        # Show podcast player if available
        if st.session_state.context.podcast_audio and os.path.exists(st.session_state.context.podcast_audio):
            st.markdown("---")
            st.subheader("Podcast")
            
            # Audio player
            with open(st.session_state.context.podcast_audio, "rb") as audio_file:
                audio_bytes = audio_file.read()
                st.audio(audio_bytes, format="audio/mp3")
            
            # Download button
            with open(st.session_state.context.podcast_audio, "rb") as file:
                btn = st.download_button(
                    label="Download Podcast",
                    data=file,
                    file_name="arxiv_podcast.mp3",
                    mime="audio/mp3"
                )

    # Main chat interface
    chat_container = st.container()
    
    # Display chat messages
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    # Function to add messages to conversation history
    async def add_to_history(human_input, ai_response):
        # Use the save_to_memory tool from the agents library
        try:
            # Store latest messages for context
            st.session_state.conversation_history.append({"human": human_input, "ai": ai_response})
            await save_to_memory(st.session_state.context, human_input, ai_response)
            logger.info("Added messages to memory")
        except Exception as e:
            logger.error(f"E saving to memory: {e}")
    
    # Execute agent in background
    async def execute_agent(user_input):
        # Maintain history from session state
        history = ""
        for conv in st.session_state.conversation_history[-3:]:  # Last 3 exchanges for context
            history += f"User: {conv['human']}\nAssistant: {conv['ai']}\n\n"
        
        # Prepend history to provide context to the agent
        enriched_input = f"[CONVERSATION HISTORY]\n{history}\n[END HISTORY]\n\nUser's current message: {user_input}"
        
        try:
            logger.info(f"Executing agent with input: {user_input}")
            result = await Runner.run(
                st.session_state.orchestrator,
                input=enriched_input,  # Send enriched input including history
                context=st.session_state.context
            )
            
            # Add assistant message to chat history
            st.session_state.messages.append({"role": "assistant", "content": result.final_output})
            
            # Save to conversation history
            await add_to_history(user_input, result.final_output)
            
            # Force streamlit to rerun and display the new message
            st.rerun()
        except Exception as e:
            logger.error(f"Error running agent: {e}")
            error_message = f"I encountered an error: {str(e)}. Let's try again."
            
            # If error is about OpenAI API key, be more specific
            if "API key" in str(e).lower():
                error_message = "There seems to be an issue with the OpenAI API key. Please check your environment variables."
            
            st.session_state.messages.append({"role": "assistant", "content": error_message})
            st.rerun()
    
    # Chat input handler
    if prompt := st.chat_input("Ask me about searching for papers, generating podcasts, or anything else!"):
        # Save the user input
        st.session_state.last_user_input = prompt
        
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message immediately
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Display assistant thinking indicator
        with st.chat_message("assistant"):
            thinking_placeholder = st.empty()
            thinking_placeholder.markdown("⏳ Processing your request...")
        
        # Execute agent in background
        asyncio.run(execute_agent(prompt))

# Example user input handling for direct testing
if __name__ == "__main__":
    run_app()