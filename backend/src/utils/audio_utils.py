import numpy as np
import subprocess
import io
import logging

def decode_webm_to_pcm(webm_data: bytes) -> np.ndarray:
    """
    Convert WebM audio data to PCM numpy array using ffmpeg.
    
    Args:
        webm_data: Raw WebM audio data as bytes
        
    Returns:
        numpy.ndarray: PCM audio data as float32 array
    """
    try:
        # Use ffmpeg to convert WebM to PCM
        process = subprocess.Popen(
            [
                'ffmpeg',
                '-i', 'pipe:0',  # Read from stdin
                '-f', 'f32le',   # Output format: 32-bit float PCM
                '-ac', '1',      # Mono audio
                '-ar', '16000',  # 16kHz sample rate
                'pipe:1'         # Write to stdout
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Send WebM data to ffmpeg and get PCM output
        stdout, stderr = process.communicate(input=webm_data)
        
        if process.returncode != 0:
            logging.error(f"FFmpeg error: {stderr.decode()}")
            return None
            
        # Convert PCM bytes to numpy array
        audio_array = np.frombuffer(stdout, dtype=np.float32)
        return audio_array
        
    except Exception as e:
        logging.error(f"Error decoding WebM audio: {str(e)}")
        return None 