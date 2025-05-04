# agents/context.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class AppContext:
    """Application context shared across agents"""
    # PDF info
    pdf_path: Optional[str] = None
    paper_text: Optional[str] = None
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    sections: Dict[str, str] = field(default_factory=dict)
    
    # Paper info
    paper_id: Optional[str] = None
    paper_title: Optional[str] = None
    paper_authors: List[str] = field(default_factory=list)
    paper_summary: Optional[str] = None
    
    # Podcast info
    target_duration: Optional[int] = None
    speaker_count: int = 2
    speaker_genders: List[str] = field(default_factory=lambda: ["male", "female"])
    speaker_names: List[str] = field(default_factory=list)
    podcast_script: Optional[str] = None
    podcast_audio: Optional[str] = None
    
    # UI state
    search_results: List[Dict] = field(default_factory=list)
    current_stage: str = "search"  # search, download, generate, audio
    progress: int = 0
    status_message: str = ""