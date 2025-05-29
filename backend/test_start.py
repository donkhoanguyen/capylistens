import asyncio
import websockets
import json
import sounddevice as sd
import numpy as np
import time
import threading
import signal

# --- Configuration ---
SERVER_URL = "ws://localhost:8000"
START_LISTENING_ENDPOINT = f"{SERVER_URL}/ws/start-listening"
STOP_LISTENING_ENDPOINT = f"{SERVER_URL}/ws/stop-listening"
AUDIO_SAMPLERATE = 16000  # Must match your server's expected samplerate (16kHz for Whisper)
AUDIO_CHANNELS = 1        # Mono audio
AUDIO_DTYPE = 'int16'     # 16-bit PCM, as expected by server

# --- Timing Parameters ---
RECORD_DURATION = 35    # seconds to record audio for each segment
SCHEDULE_INTERVAL = 30  # seconds between the START of each new recording

# Flag to control the overall client loop
client_running = threading.Event()
client_running.set() # Set to True initially

async def record_and_send_segment(websocket: websockets.WebSocketClientProtocol, segment_id: int):
    """
    Records audio for RECORD_DURATION and sends it to the server.
    This function is intended to be run as an independent task.
    """
    print(f"--- Segment {segment_id} ---")
    print(f"Starting recording for {RECORD_DURATION} seconds...")
    
    current_segment_buffer = []
    samples_read_for_current_segment = 0
    segment_start_time = time.time()

    try:
        with sd.InputStream(samplerate=AUDIO_SAMPLERATE, channels=AUDIO_CHANNELS, dtype=AUDIO_DTYPE) as stream:
            # Read in small internal buffers to avoid very large reads
            internal_buffer_duration = 0.1 
            samples_per_internal_buffer = int(AUDIO_SAMPLERATE * internal_buffer_duration)
            
            while (time.time() - segment_start_time < RECORD_DURATION) and client_running.is_set():
                audio_internal_buffer_np, overflowed = stream.read(samples_per_internal_buffer)
                
                if overflowed:
                    print(f"Warning: Audio input stream overflowed by {overflowed} frames for segment {segment_id}!")

                if audio_internal_buffer_np.ndim > 1:
                    audio_internal_buffer_np = audio_internal_buffer_np.squeeze()

                current_segment_buffer.append(audio_internal_buffer_np)
                samples_read_for_current_segment += len(audio_internal_buffer_np)
                
                await asyncio.sleep(0.001) # Small sleep to yield control
            
            if not client_running.is_set():
                print(f"Client stopping during recording of segment {segment_id}.")
                return # Exit early if client was stopped

            print(f"Finished recording segment {segment_id}. Total samples: {samples_read_for_current_segment}")
            
            if current_segment_buffer:
                full_audio_segment_np = np.concatenate(current_segment_buffer)
                audio_bytes_to_send = full_audio_segment_np.tobytes()
                
                print(f"Sending {len(audio_bytes_to_send)} bytes for segment {segment_id}...")
                await websocket.send(audio_bytes_to_send)
                print(f"Segment {segment_id} sent.")
            else:
                print(f"No audio recorded for segment {segment_id}.")
                
    except Exception as e:
        print(f"Error during record_and_send_segment {segment_id}: {e}")

async def main_scheduler():
    """
    Schedules new recording tasks every SCHEDULE_INTERVAL.
    """
    print(f"Connecting to {START_LISTENING_ENDPOINT}")
    try:
        async with websockets.connect(START_LISTENING_ENDPOINT) as websocket:
            print(f"Connected to {START_LISTENING_ENDPOINT}. Client will start new recordings every {SCHEDULE_INTERVAL} seconds, each lasting {RECORD_DURATION} seconds.")
            print("Press Ctrl+C to stop the client.")
            
            segment_id_counter = 0
            
            # Start the first segment immediately
            segment_id_counter += 1
            asyncio.create_task(record_and_send_segment(websocket, segment_id_counter))
            
            # Schedule subsequent segments
            while client_running.is_set():
                # Wait for the next scheduled start time
                await asyncio.sleep(SCHEDULE_INTERVAL) 
                
                if not client_running.is_set():
                    break # Exit if Ctrl+C pressed during sleep

                segment_id_counter += 1
                # Start a new recording task, independent of the previous one
                asyncio.create_task(record_and_send_segment(websocket, segment_id_counter))
                
            print("\nClient scheduler loop terminated.")

    except websockets.exceptions.ConnectionClosedOK:
        print(f"WebSocket connection to {START_LISTENING_ENDPOINT} closed gracefully.")
    except websockets.exceptions.ConnectionClosed as e:
        print(f"WebSocket connection to {START_LISTENING_ENDPOINT} closed unexpectedly: {e}")
    except Exception as e:
        print(f"An error occurred in the main scheduler: {e}")
    finally:
        client_running.clear() # Ensure the flag is cleared on exit


# Optional: Send a stop command (likely not used in this continuous overlap scenario)
async def send_stop_command():
    """Sends a stop command to the server."""
    print(f"\nConnecting to {STOP_LISTENING_ENDPOINT} to send stop command...")
    try:
        async with websockets.connect(STOP_LISTENING_ENDPOINT) as websocket:
            stop_message = json.dumps({"type": "stop"})
            await websocket.send(stop_message)
            print("Stop command sent.")
            
            response = await websocket.recv()
            data = json.loads(response)
            print(f"Server response to stop command: {data}")
            if data.get("status") == "stopped":
                print("Server confirmed stopping.")
            else:
                print("Server did not confirm stopping as expected.")

    except websockets.exceptions.ConnectionClosedOK:
        print(f"WebSocket connection to {STOP_LISTENING_ENDPOINT} closed gracefully.")
    except websockets.exceptions.ConnectionClosed as e:
        print(f"WebSocket connection to {STOP_LISTENING_ENDPOINT} closed unexpectedly: {e}")
    except Exception as e:
        print(f"An error occurred while sending stop command: {e}")

# Register Ctrl+C handler
def signal_handler(sig, frame):
    print("\nCtrl+C detected. Signalling client to stop...")
    client_running.clear() # Set the flag to False to break loops

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler) # Register Ctrl+C handler

    # Check if sounddevice is installed and microphone accessible
    try:
        sd.query_devices()
    except Exception as e:
        print("Error: sounddevice not found or microphone not accessible.")
        print("Please install it using: pip install sounddevice numpy")
        print("You might also need portaudio: sudo apt-get install libportaudio2 (Linux) or brew install portaudio (macOS)")
        exit(1)

    input("Press Enter to start the overlapping recording cycle...")
    
    asyncio.run(main_scheduler())
    print("\nClient gracefully exited.")