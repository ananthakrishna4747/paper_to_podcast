# core/audio.py
import os
import re
import tempfile
import logging
from pydub import AudioSegment
from openai import OpenAI
from typing import Dict, List, Optional, Any
from agents import function_tool, RunContextWrapper

logger = logging.getLogger("ArXivAudio")

@function_tool
async def generate_podcast_audio(
    ctx: RunContextWrapper[Any],
    output_dir: str  # No default value
) -> Dict:
    """Generate podcast audio from script."""
    # Set default inside function
    if not output_dir:
        output_dir = "./output"
        
    logger.info("Generating podcast audio")
    ctx.context.status_message = "Starting podcast audio generation..."
    ctx.context.progress = 10
    ctx.context.current_stage = "audio"
    
    if not hasattr(ctx.context, 'podcast_script') or not ctx.context.podcast_script:
        error_msg = "Error: No podcast script available."
        logger.error(error_msg)
        ctx.context.progress = 0
        ctx.context.status_message = error_msg
        return {"success": False, "error": error_msg}
    
    try:
        # Create audio generator
        audio_generator = PodcastAudioGenerator()
        
        # Generate audio
        ctx.context.status_message = "Generating audio from podcast script..."
        output_file = audio_generator.generate_full_podcast(
            ctx.context.podcast_script, 
            output_dir,
            ctx.context.speaker_names,
            ctx.context.speaker_genders,
            update_status_callback=lambda msg, prog: update_status(ctx, msg, prog)
        )
        
        # Store in context
        ctx.context.podcast_audio = output_file
        ctx.context.progress = 100
        ctx.context.status_message = f"Podcast audio saved to: {output_file}"
        
        logger.info(f"Podcast audio saved to: {output_file}")
        return {
            "success": True,
            "audio_path": output_file
        }
    except Exception as e:
        error_msg = f"Error generating podcast audio: {e}"
        logger.error(error_msg)
        ctx.context.progress = 0
        ctx.context.status_message = error_msg
        return {"success": False, "error": error_msg}

def update_status(ctx, message, progress):
    """Update status message and progress in context."""
    ctx.context.status_message = message
    ctx.context.progress = progress

class PodcastAudioGenerator:
    """Generates audio from podcast scripts using OpenAI's TTS API with support for multiple speakers."""
    
    def __init__(self, api_key: str = None):
        """Initialize with OpenAI API key."""
        logger.info("Initializing PodcastAudioGenerator")
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        
        # Define available voices by gender
        self.voice_options = {
            "male": ["onyx", "echo", "fable", "nova", "shimmer"],
            "female": ["nova", "shimmer", "alloy", "echo", "fable"]
        }
        logger.debug(f"Voice options configured")
    
    def assign_voices(self, speakers: List[Dict]) -> Dict[str, str]:
        """
        Assign voices to speakers based on their gender.
        
        Args:
            speakers: List of dictionaries with 'name' and 'gender' keys
            
        Returns:
            Dictionary mapping speaker names to voice IDs
        """
        logger.info(f"Assigning voices to {len(speakers)} speakers")
        
        voice_map = {}
        used_voices = set()
        
        for speaker in speakers:
            name = speaker["name"]
            gender = speaker["gender"].lower()
            
            # Get available voices for this gender
            available_voices = self.voice_options.get(gender, self.voice_options["male"])
            
            # Try to find an unused voice
            selected_voice = None
            for voice in available_voices:
                if voice not in used_voices:
                    selected_voice = voice
                    used_voices.add(voice)
                    break
            
            # If all voices are used, just pick the first one for this gender
            if not selected_voice:
                selected_voice = available_voices[0]
            
            voice_map[name] = selected_voice
            logger.debug(f"Assigned voice '{selected_voice}' to speaker '{name}' ({gender})")
        
        return voice_map
    
    def parse_script(self, script_text: str, speaker_names: List[str]) -> List[Dict]:
        """
        Parse the podcast script into segments by speaker.
        """
        logger.info("Parsing podcast script into segments")
        
        # Create a regex pattern that matches any of the speaker names
        speaker_pattern = "|".join([re.escape(name) for name in speaker_names])
        
        # Modified pattern to better match "**Speaker:**" format used in generated scripts
        pattern = f'(?:^|\n)\\*\\*({speaker_pattern})\\*\\*:\\s*(.+?)(?=\n\\*\\*(?:{speaker_pattern})\\*\\*:|\\Z)'
        
        # Use re.DOTALL to make the dot match newlines as well
        matches = re.findall(pattern, script_text, re.DOTALL)
        logger.debug(f"Found {len(matches)} segments in the script")
        
        # If no matches found with the new pattern, try the original pattern as fallback
        if not matches:
            pattern = f'(?:^|\n)\\*?\\*?({speaker_pattern})\\*?\\*?:\\s*(.+?)(?=\n\\*?\\*?(?:{speaker_pattern}):|\\Z)'
            matches = re.findall(pattern, script_text, re.DOTALL)
            logger.debug(f"Fallback pattern found {len(matches)} segments")
        
        # If still no matches, split the text into chunks to avoid TTS limit
        if not matches:
            logger.warning("No speaker segments found, splitting by character limit")
            # Create chunks of 4000 characters (under the 4096 limit)
            text_chunks = [script_text[i:i+4000] for i in range(0, len(script_text), 4000)]
            segments = []
            for i, chunk in enumerate(text_chunks):
                segments.append({
                    "speaker": speaker_names[i % len(speaker_names)],
                    "text": chunk
                })
            logger.info(f"Split script into {len(segments)} chunks")
            return segments
        
        segments = []
        for speaker, text in matches:
            # Clean up the text (remove stage directions)
            clean_text = self._clean_stage_directions(text)
            
            # Split long segments to stay under the 4096 character limit
            if len(clean_text) > 4000:
                chunks = [clean_text[i:i+4000] for i in range(0, len(clean_text), 4000)]
                for chunk in chunks:
                    segments.append({
                        "speaker": speaker,
                        "text": chunk
                    })
            else:
                segments.append({
                    "speaker": speaker,
                    "text": clean_text
                })
        
        logger.info(f"Script parsed into {len(segments)} segments")
        return segments
        
    def _clean_stage_directions(self, text: str) -> str:
        """Remove stage directions from the text."""
        logger.debug("Cleaning stage directions from text")
        
        # Remove content within brackets like [enthusiastic tone]
        cleaned_text = re.sub(r'\[.*?\]', '', text)
        
        # Remove content within parentheses like (laughs)
        cleaned_text = re.sub(r'\(.*?\)', '', cleaned_text)
        
        # Remove content within asterisks like *pauses*
        cleaned_text = re.sub(r'\*.*?\*', '', cleaned_text)
        
        # Clean up extra whitespace
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        return cleaned_text
    
    def generate_audio_segment(self, text: str, voice: str) -> bytes:
        """Generate audio for a single text segment using OpenAI's TTS API."""
        logger.info(f"Generating audio segment with voice '{voice}'")
        logger.debug(f"Text length: {len(text)} characters")
        
        try:
            response = self.client.audio.speech.create(
                model="tts-1-hd",  # Using high-definition model for better quality
                voice=voice,
                input=text
            )
            logger.info("Audio segment generated successfully")
            return response.content
        except Exception as e:
            # logger.error(f"Error generating audio segment: {e}")
            raise

    def generate_full_podcast(
        self, 
        script_text: str, 
        output_path: str, 
        speaker_names: List[str], 
        speaker_genders: List[str],
        update_status_callback=None
    ) -> str:
        """
        Generate a full podcast audio file from a script with multiple speakers.
        
        Args:
            script_text: The podcast script text
            output_path: Directory to save the output file
            speaker_names: List of speaker names in the script
            speaker_genders: List of corresponding speaker genders
            update_status_callback: Optional callback function for status updates
            
        Returns:
            Path to the generated audio file
        """
        logger.info(f"Generating full podcast audio to directory: {output_path}")
        
        if update_status_callback:
            update_status_callback("Creating speaker voice profiles...", 20)
        
        # Create speaker list from names and genders
        speakers = [{"name": name, "gender": gender} for name, gender in zip(speaker_names, speaker_genders)]
        
        # Assign voices to speakers
        voice_map = self.assign_voices(speakers)
        logger.info(f"Voice mapping: {voice_map}")
        
        if update_status_callback:
            update_status_callback("Parsing podcast script into segments...", 30)
        
        # Parse the script into segments
        segments = self.parse_script(script_text, speaker_names)
        
        if not segments:
            error_msg = "No valid script segments found"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info(f"Processing {len(segments)} audio segments")
        
        if update_status_callback:
            update_status_callback(f"Generating audio for {len(segments)} segments...", 40)
        
        # Create a temporary directory for audio segments
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.debug(f"Created temporary directory: {temp_dir}")
            audio_files = []
            
            # Generate audio for each segment
            for i, segment in enumerate(segments):
                # Update progress if callback provided
                if update_status_callback:
                    progress = 40 + int(40 * (i + 1) / len(segments))
                    update_status_callback(f"Generating audio for segment {i+1}/{len(segments)}...", progress)
                
                speaker = segment["speaker"]
                text = segment["text"]
                
                if not text.strip():
                    logger.warning(f"Skipping empty text for segment {i}")
                    continue  # Skip empty text
                
                voice = voice_map.get(speaker, "alloy")  # Default to alloy if speaker not recognized
                if speaker not in voice_map:
                    logger.warning(f"Unknown speaker '{speaker}', using default voice 'alloy'")
                
                logger.info(f"Generating audio for segment {i}: {speaker}")
                logger.debug(f"Text preview: {text[:50]}...")
                
                try:
                    # Generate audio
                    audio_data = self.generate_audio_segment(text, voice)
                    
                    # Save to temporary file
                    temp_file = os.path.join(temp_dir, f"segment_{i}.mp3")
                    with open(temp_file, "wb") as f:
                        f.write(audio_data)
                    
                    audio_files.append(temp_file)
                    logger.debug(f"Saved audio segment {i} to {temp_file}")
                except Exception as e:
                    logger.error(f"Error processing segment {i}: {e}")
                    raise
            
            if update_status_callback:
                update_status_callback("Combining audio segments into final podcast...", 80)
            
            logger.info(f"All {len(audio_files)} audio segments generated, combining into final podcast")
            
            # Combine audio segments
            try:
                combined = AudioSegment.empty()
                for audio_file in audio_files:
                    logger.debug(f"Adding {audio_file} to combined audio")
                    segment = AudioSegment.from_mp3(audio_file)
                    combined += segment
                
                # Save the combined audio
                os.makedirs(output_path, exist_ok=True)
                output_file = os.path.join(output_path, "podcast.mp3")
                
                if update_status_callback:
                    update_status_callback("Exporting final podcast audio...", 90)
                
                logger.info(f"Exporting combined audio to {output_file}")
                combined.export(output_file, format="mp3")
                
                if update_status_callback:
                    update_status_callback("Podcast generation completed successfully!", 100)
                
                logger.info("Podcast generation completed successfully")
                return output_file
            except Exception as e:
                logger.error(f"Error combining audio segments: {e}")
                raise