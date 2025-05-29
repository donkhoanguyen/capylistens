import whisper
import numpy as np
import time
import asyncio
from queue import Queue
from threading import Thread
from typing import Optional, Dict, List, Any
import logging

# Assuming these are in the same relative directory or properly installed
from ..claim_extraction.gpt_extractor import ClaimExtractor
from ..fact_checking.graph_checker import graph

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.callbacks.base import BaseCallbackManager
from typing import Dict, TypedDict, Annotated, Sequence, List, Optional, Any, Union
Callbacks = Optional[Union[List[BaseCallbackHandler], BaseCallbackManager]]
from langchain_openai import ChatOpenAI
ChatOpenAI.model_rebuild()

# Try to import performance monitoring tools
try:
    import psutil
    HAVE_PSUTIL = True
except ImportError:
    HAVE_PSUTIL = False

class TranscriptionProcessor:
    """Processes audio chunks: transcribes, extracts claims, and fact-checks."""
    def __init__(self, whisper_model_name: str, claim_extractor: ClaimExtractor,): # fact_checker: FactChecker):
        self.model = whisper.load_model(whisper_model_name)
        self.extractor = claim_extractor
        self.checker = graph
        self.processing_times = {
            'transcribe': [],
            'extract': [],
            'check': []
        }

    async def transcribe(self, audio: np.ndarray) -> str:
        """Transcribes the given audio chunk."""
        start_time = time.time()
        result = self.model.transcribe(audio, fp16=False)  # Consider making fp16 configurable
        transcription = result["text"].strip()
        self.processing_times['transcribe'].append(time.time() - start_time)
        return transcription

    async def extract_and_check(self, transcription: str) -> Dict[str, Any]:
        """Extracts claims and fact-checks them."""
        extract_start = time.time()
        claims_data = await self.extractor.extract_claims(transcription)
        extract_time = time.time() - extract_start
        self.processing_times['extract'].append(extract_time)

        claims = [claim.replace('.\n', '. ').strip() for claim_list in claims_data for claim in claim_list.split('. ') if claim.strip()]
        fact_check_results = []

        check_start = time.time()

        for claim in claims:
            # here change claims into inputs for langgraph graph checker
            input = {
                "claim": claim
            }

            result = await self.checker.ainvoke(input)
            fact_check_results.append(result)

        check_time = time.time() - check_start
        self.processing_times['check'].append(check_time)

        return {"claims": claims, "fact_check_results": fact_check_results}

class Transcriber:
    def __init__(self, extractor: ClaimExtractor, # checker: FactChecker,
                 config: Optional[Dict] = None, model_name: str = "base",
                 output_markdown: str = "transcription.md"):
        self.config = config
        self.processor = TranscriptionProcessor(model_name, extractor)
        self.transcriptions = []
        self.audio_queue = Queue()
        self.is_running = False
        self.output_file = None
        self.output_markdown_path = output_markdown
        self.queue_stats = {"max_size": 0, "current_size": 0}
        self.start_time = 0

    async def process_audio_chunk(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """
        Process a single chunk of audio data.
        
        Args:
            audio_data: numpy array of audio data (float32, mono, 16kHz)
            
        Returns:
            Dictionary containing transcription, claims, and fact check results
        """
        try:
            # Transcribe the audio
            transcription = await self.processor.transcribe(audio_data)
            if not transcription:
                return None

            # Extract claims and fact check
            results = await self.processor.extract_and_check(transcription)
            
            return {
                "transcription": transcription,
                "claims": results["claims"],
                "fact_check_results": results["fact_check_results"]
            }
        except Exception as e:
            logging.error(f"Error processing audio chunk: {str(e)}")
            return None
        
    # Modified transcriber method
    async def process_audio_data_streaming(self, audio_data: bytes, chunk_idx: int, chunk_start: float, chunk_end: float, duration: float = 35):
        """Process audio data and yield results as they become available."""
        if not self.is_running:
            return
        
        # Open output file
        self.output_file = open(self.output_markdown_path, "w")
        self._write_markdown_header(duration, duration, 0)

        # Convert bytes to numpy array
        with open(f"debug_segment_{int(time.time())}.webm", "wb") as f:
            f.write(audio_data)
        
        try:
            audio = decode_webm_to_pcm(audio_data)
            
            # Step 1: Transcription
            yield {
                "type": "progress", 
                "step": "transcription_started",
                "message": "Starting transcription..."
            }
            
            transcription = await self.processor.transcribe(audio)
            self.transcriptions.append(transcription)
            self._write_transcription_to_markdown(chunk_start, chunk_end, transcription)
            
            # Yield transcription result
            yield {
                "type": "transcription",
                "chunk_idx": chunk_idx,
                "transcription": transcription,
                "chunk_start": chunk_start,
                "chunk_end": chunk_end
            }
            
            print(f"Transcription for chunk {chunk_idx+1} completed: {transcription}")
            
            # Step 2: Claims extraction and fact checking
            yield {
                "type": "progress",
                "step": "fact_checking_started", 
                "message": "Starting claims extraction and fact checking..."
            }
            
            processing_results = await self.processor.extract_and_check(transcription)
            claims = processing_results['claims']
            fact_check_results = processing_results['fact_check_results']
            
            self._write_claims_and_results_to_markdown(chunk_idx, chunk_start, claims, fact_check_results)
            
            # Yield fact checking results
            yield {
                "type": "fact_check",
                "chunk_idx": chunk_idx,
                "claims": claims,
                "fact_check_results": fact_check_results,
                "chunk_start": chunk_start,
                "chunk_end": chunk_end
            }
            
            print(f"Fact check results for chunk {chunk_idx+1}: {fact_check_results}")
            
        except Exception as e:
            print(f"Error processing audio chunk: {e}")
            if self.output_file:
                self.output_file.write(f"\nError processing chunk: {e}\n")
                self.output_file.flush()
            
            yield {
                "type": "error",
                "chunk_idx": chunk_idx,
                "message": str(e)
            }
        
    async def process_audio_data(self, audio_data: bytes, chunk_idx: int, chunk_start: float, chunk_end: float, duration: float = 35):
        """Process audio data received from WebSocket."""
        if not self.is_running:
            return None
        
        # Open output file
        self.output_file = open(self.output_markdown_path, "w")
        self._write_markdown_header(duration, duration, 0)

        # Convert bytes to numpy array (assuming 16-bit PCM audio)
        with open(f"debug_segment_{int(time.time())}.webm", "wb") as f:
            f.write(audio_data)
        audio = decode_webm_to_pcm(audio_data)

        # Process the audio directly instead of queuing it
        try:
            transcription = await self.processor.transcribe(audio)
            self.transcriptions.append(transcription)
            print(f"Transcription for chunk {chunk_idx+1} completed: {transcription}")
            self._write_transcription_to_markdown(chunk_start, chunk_end, transcription)

            processing_results = await self.processor.extract_and_check(transcription)
            claims = processing_results['claims']
            fact_check_results = processing_results['fact_check_results']
            print(f"Fact check results for chunk {chunk_idx+1}: {fact_check_results}")

            self._write_claims_and_results_to_markdown(chunk_idx, chunk_start, claims, fact_check_results)

            return {
                "transcription": transcription,
                "claims": claims,
                "fact_check_results": fact_check_results
            }
        except Exception as e:
            print(f"Error processing audio chunk: {e}")
            if self.output_file:
                self.output_file.write(f"\nError processing chunk: {e}\n")
                self.output_file.flush()
            return None

    # async def process_audio_data(self, audio_data: bytes, chunk_idx: int, chunk_start: float, chunk_end: float, duration: float = 35):
    #     """Process audio data received from WebSocket."""
    #     if not self.is_running:
    #         return
        
    #     # Open output file
    #     self.output_file = open(self.output_markdown_path, "w")
    #     self._write_markdown_header(duration, duration, 0)

    #     # Convert bytes to numpy array (assuming 16-bit PCM audio)
    #     # audio = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
    #     with open(f"debug_segment_{int(time.time())}.webm", "wb") as f:
    #         f.write(audio_data)
    #     audio = decode_webm_to_pcm(audio_data)

    #     self.audio_queue.put({
    #         'audio': audio,
    #         'chunk_idx': chunk_idx,
    #         'start_time': chunk_start,
    #         'end_time': chunk_end
    #     })

    #     if not hasattr(self, "_queue_task") or self._queue_task.done():
    #         self._queue_task = asyncio.create_task(self._process_audio_queue())

    async def transcribe_realtime(self, duration: float = 30):
        """
        Processes audio data received from WebSocket in real-time.
        """
        print(f"Setting up real-time transcription with {duration}s chunks...")
        self.is_running = True
        self.start_time = time.time()

        # Print system info
        self._print_system_info()

        # Open output file
        self.output_file = open(self.output_markdown_path, "w")
        self._write_markdown_header(duration, duration, 0)

        # Start the processing thread
        processing_thread = Thread(target=asyncio.run, args=(self._process_audio_queue(),))
        processing_thread.daemon = True
        processing_thread.start()

        try:
            while self.is_running:
                await asyncio.sleep(0.1)  # Small sleep to prevent CPU spinning
        except KeyboardInterrupt:
            print("Stopping real-time transcription...")
            self.is_running = False
            if self.output_file:
                self.output_file.close()
            print(f"Transcription stopped. Output saved to {self.output_markdown_path}")

    async def _process_audio_queue(self):
        """Processes audio chunks from the queue."""
        while self.is_running or not self.audio_queue.empty():
            try:
                item = self.audio_queue.get(timeout=0.1) # Non-blocking get with a timeout
                audio = item['audio']
                chunk_idx = item['chunk_idx']
                chunk_start = item['start_time']
                chunk_end = item['end_time']

                chunk_processing_start = time.time()
                print(f"Processing chunk {chunk_idx+1}...")
                queue_wait_time = chunk_processing_start - chunk_start
                if queue_wait_time > 10:
                    print(f"WARNING: Chunk waited in queue for {queue_wait_time:.2f}s")

                transcription = await self.processor.transcribe(audio)
                self.transcriptions.append(transcription)
                print(f"Transcription for chunk {chunk_idx+1} completed in {self.processor.processing_times['transcribe'][-1]:.2f}s: {transcription}")
                self._write_transcription_to_markdown(chunk_start, chunk_end, transcription)

                processing_results = await self.processor.extract_and_check(transcription)
                claims = processing_results['claims']
                fact_check_results = processing_results['fact_check_results']
                print(f"Fact check results for chunk {chunk_idx+1}: {fact_check_results}")

                self._write_claims_and_results_to_markdown(chunk_idx, chunk_start, claims, fact_check_results)

                if chunk_idx > 0 and chunk_idx % 5 == 0:
                    self._report_performance()

                self.audio_queue.task_done()
            except Empty:
                await asyncio.sleep(0.01) # Small sleep when queue is empty
            except Exception as e:
                print(f"Error processing audio chunk: {e}")
                if self.output_file:
                    self.output_file.write(f"\nError processing chunk: {e}\n")
                    self.output_file.flush()

    def _report_performance(self):
        """Reports on performance metrics."""
        if not self.processor.processing_times['transcribe']:
            return

        avg_transcribe = sum(self.processor.processing_times['transcribe']) / len(self.processor.processing_times['transcribe'])
        avg_extract = sum(self.processor.processing_times['extract']) / len(self.processor.processing_times['extract']) if self.processor.processing_times['extract'] else 0
        avg_check = sum(self.processor.processing_times['check']) / len(self.processor.processing_times['check']) if self.processor.processing_times['check'] else 0

        print("\n--- PERFORMANCE REPORT ---")
        print(f"Average transcription time: {avg_transcribe:.2f}s")
        print(f"Average claim extraction time: {avg_extract:.2f}s")
        print(f"Average fact checking time: {avg_check:.2f}s")
        print(f"Total average API processing time: {(avg_transcribe + avg_extract + avg_check):.2f}s")
        print(f"Current queue size: {self.audio_queue.qsize()} chunks")

        if HAVE_PSUTIL:
            print(f"CPU usage: {psutil.cpu_percent()}%")
            print(f"Memory usage: {psutil.virtual_memory().percent}%")

        if avg_transcribe + avg_extract + avg_check > 30:
            print("\nWARNING: Average processing time exceeds recording interval!")
            print("The processing queue will continue to grow unless processing speeds up.")
            print("Consider using a faster model, reducing recording quality, or increasing chunk_interval.")

        print("-------------------------\n")

    def _print_system_info(self):
        """Prints system information if psutil is available."""
        import os
        try:
            import psutil
            cpu_count = os.cpu_count()
            memory = psutil.virtual_memory()
            print(f"System info: {cpu_count} CPU cores, {memory.total / (1024**3):.1f} GB RAM")
            print(f"Current CPU usage: {psutil.cpu_percent()}%")
        except ImportError:
            print("Could not retrieve detailed system info. Consider installing psutil with: pip install psutil")

    def _write_markdown_header(self, recording_duration: float, chunk_interval: float, overlap: float):
        """Writes the markdown header to the output file."""
        self.output_file.write("# Real-Time Transcription with Overlapping Audio\n\n")
        self.output_file.write(f"Recording {recording_duration}s chunks every {chunk_interval}s (overlap: {overlap:.1f}s)\n\n")
        self.output_file.write("| Start Time (s) | End Time (s) | Transcription |\n")
        self.output_file.write("|:-------------:|:-------------:|:--------------|\n")
        self.output_file.flush()

    def _write_transcription_to_markdown(self, start_time: float, end_time: float, transcription: str):
        """Writes a single transcription to the markdown file."""
        self.output_file.write(f"| {start_time:.2f} | {end_time:.2f} | {transcription} |\n")
        self.output_file.flush()

    def _write_claims_and_results_to_markdown(self, chunk_idx: int, chunk_start: float, claims: List[str], fact_check_results: Any):
        """Writes extracted claims and fact-checking results to the markdown file."""
        self.output_file.write(f"\n## Claims from chunk {chunk_idx+1} ({chunk_start:.2f}s):\n")
        for claim in claims:
            self.output_file.write(f"- {claim}\n")
        self.output_file.write(f"\n### Fact check results for chunk {chunk_idx+1}:\n")
        self.output_file.write(f"{fact_check_results}\n\n")
        self.output_file.flush()

    async def stop_transcription(self):
        """Stop the transcription process and clean up resources."""
        self.is_running = False
        if self.output_file:
            self.output_file.close()
            self.output_file = None
        # Clear the audio queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
                self.audio_queue.task_done()
            except Empty:
                break
        return True

from queue import Empty # Import here to avoid circular dependency issues

import subprocess
import numpy as np

def decode_webm_to_pcm(audio_data: bytes, sample_rate=16000) -> np.ndarray:
    if len(audio_data) < 100:
        raise ValueError("Audio blob too small to decode")

    process = subprocess.Popen(
        [
            "ffmpeg",
            "-f", "webm",
            "-i", "pipe:0",
            "-ac", "1",                # Mono
            "-ar", str(sample_rate),  # Resample to 16kHz
            "-f", "s16le",             # Raw PCM output
            "pipe:1"
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    out, err = process.communicate(input=audio_data)

    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg failed:\n{err.decode('utf-8')}")

    if not out:
        raise ValueError("FFmpeg returned empty audio output")

    return np.frombuffer(out, dtype=np.int16).astype(np.float32) / 32768.0