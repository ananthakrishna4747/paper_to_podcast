Installation
Prerequisites

Python 3.8 or higher
An OpenAI API key (for script generation and audio synthesis)

Clone the Repository
bashgit clone https://github.com/yourusername/arxiv-podcast-generator.git
cd arxiv-podcast-generator
Set Up Environment

Create a virtual environment:

bashpython -m venv venv

Activate the virtual environment:

On Windows:
bashvenv\Scripts\activate
On macOS/Linux:
bashsource venv/bin/activate

Install dependencies:

bashpip install -r requirements.txt
Configuration

Create a .env file in the project root directory with the following content:

OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL_ID=ft:gpt-4o-mini-2024-07-18:personal::BM4yUkOI  # Or your preferred model

Set up logging (optional):

Logs are stored in arxiv_podcast.log by default. You can adjust log levels in main.py.
Usage
Starting the Application
bashstreamlit run main.py
This will start the web interface on http://localhost:8501 by default.
Workflow

Search for Papers: Enter keywords or a paper ID in the chat interface
Select a Paper: Choose a paper from the search results
Download and Process: The application will download and extract the paper content
Set Podcast Parameters: Choose the podcast duration and speaker preferences
Generate Podcast: The system will create a script and synthesize audio
Listen and Download: Play the podcast directly in the browser or download the MP3 file

Architecture
The application is structured as follows:

main.py: Application entry point
core/: Core functionality modules

search.py: ArXiv search functions
parse.py: PDF text extraction
podcast.py: Script generation
audio.py: Audio synthesis


agents_l/: Agent framework components

context.py: Application context
memory.py: Conversation memory
orchestrator.py: Agent workflow orchestration


ui/: User interface

app.py: Streamlit application



Customization
You can customize the podcast generation by modifying:

Duration: Set podcast length (5, 10, 15, 20, or 30 minutes)
Speaker Count: Choose how many speakers to include
Speaker Genders: Select gender distribution for voice variety
Voice Models: Modify the voice assignment in audio.py

Requirements
The application uses the following key dependencies:

openai: For GPT models and text-to-speech
openai-agents: Agent framework
arxiv: ArXiv API client
pypdf2: PDF text extraction
pydub: Audio processing
streamlit: Web interface
arxiv_mcp server for direct access to arxiv library for agents
