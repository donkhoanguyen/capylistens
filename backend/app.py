from fastapi import FastAPI, WebSocket, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
from typing import AsyncGenerator
import logging
from starlette.websockets import WebSocketDisconnect, WebSocketState
from src.transcription.transcriber import Transcriber
from src.claim_extraction.gpt_extractor import ClaimExtractor
from src.fact_checking.fact_checker import FactChecker
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import os

# Initialize FastAPI app
app = FastAPI(title="Audio Processing Pipeline")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
claim_extractor = ClaimExtractor()
fact_checker = FactChecker()
transcriber = Transcriber(claim_extractor, fact_checker)

@app.post("/upload-stream")
async def upload_audio_stream(
    file: UploadFile = File(...),
    segment_id: int = Form(...),
):
    """
    Receive a single WebM audio segment and stream results as they become available.
    Returns Server-Sent Events (SSE) stream.
    """
    try:
        audio_data = await file.read()
        
        # Compute chunk timing to match your WS logic:
        duration = 30.0  # seconds per segment
        chunk_idx = segment_id
        chunk_start = segment_id * duration
        chunk_end = chunk_start + duration

        # Create streaming generator
        async def generate_stream():
            try:
                transcriber.is_running = True
                
                # Send initial status
                yield f"data: {json.dumps({'type': 'status', 'message': 'Processing started', 'bytes': len(audio_data)})}\n\n"
                
                # Process audio and stream results
                async for result in transcriber.process_audio_data_streaming(
                    audio_data=audio_data,
                    chunk_idx=chunk_idx,
                    chunk_start=chunk_start,
                    chunk_end=chunk_end
                ):
                    yield f"data: {json.dumps(result)}\n\n"
                
                # Send completion status
                yield f"data: {json.dumps({'type': 'complete', 'message': 'Processing complete'})}\n\n"
                
            except Exception as e:
                logging.error(f"Error in streaming for segment {segment_id}: {e}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            }
        )
        
    except Exception as e:
        logging.error(f"Error setting up stream for segment {segment_id}: {e}", exc_info=True)
        return JSONResponse(
            {"status": "error", "detail": str(e)},
            status_code=500
        )

@app.post("/upload")
async def upload_audio(
    file: UploadFile = File(...),
    segment_id: int = Form(...),
):
    """
    Receive a single WebM audio segment, then hand it off to the
    same process_audio_data() call you use in WebSocket mode.
    """
    audio_data = await file.read()

    # Compute chunk timing to match your WS logic:
    duration = 30.0  # seconds per segment
    chunk_idx   = segment_id
    chunk_start = segment_id * duration
    chunk_end   = chunk_start + duration

    try:
        # Await the same processing you do per chunk over WS
        transcriber.is_running = True  # ensure background loop is allowed
        results = await transcriber.process_audio_data(
            audio_data=audio_data,
            chunk_idx=chunk_idx,
            chunk_start=chunk_start,
            chunk_end=chunk_end
        )
        # Return the results to the frontend
        return JSONResponse({
            "status": "ok",
            "bytes": len(audio_data),
            "results": {
                "transcription": results.get("transcription", ""),
                "claims": results.get("claims", []),
                "fact_check_results": results.get("fact_check_results", [])
            }
        })
    except Exception as e:
        logging.error(f"Error in /upload for segment {segment_id}: {e}", exc_info=True)
        return JSONResponse(
            {"status": "error", "detail": str(e)},
            status_code=500
        )

@app.get("/")
def serve_app():
    return FileResponse("web_frontend/app.html")

# WebSocket endpoint for real-time audio streaming
@app.websocket("/ws/start-listening")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        # Start transcription in background
        asyncio.create_task(transcriber.transcribe_realtime(duration=30))
        
        chunk_idx = 0
        start_time = asyncio.get_event_loop().time()
        
        while True:
            # Receive audio data from client
            audio_data = await websocket.receive_bytes()
            
            # Calculate timing information
            current_time = asyncio.get_event_loop().time()
            chunk_start = current_time - start_time
            chunk_end = chunk_start + 30  # Assuming 30-second chunks
            
            # Process the audio data
            await transcriber.process_audio_data(
                audio_data=audio_data,
                chunk_idx=chunk_idx,
                chunk_start=chunk_start,
                chunk_end=chunk_end
            )
            
            chunk_idx += 1
            
    except WebSocketDisconnect:
        logging.info(f"Client disconnected from /ws/start-listening. WebSocket state: {websocket.client_state}")
    except Exception as e:
        logging.error(f"WebSocket error in /ws/start-listening: {e}", exc_info=True)
    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()

@app.websocket("/ws/stop-listening")
async def stop_listening_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        # Wait for stop command from client
        while True:
            data = await websocket.receive_text()
            command = json.loads(data)
            
            if command.get("type") == "stop":
                # Send acknowledgment that we're stopping
                await websocket.send_text(json.dumps({
                    "type": "status",
                    "status": "stopping"
                }))
                
                # Cleanup any ongoing transcription
                if transcriber:
                    await transcriber.stop_transcription()
                    
                # Send final confirmation
                await websocket.send_text(json.dumps({
                    "type": "status",
                    "status": "stopped"
                }))
                break  # Exit the loop after stopping
                
    except WebSocketDisconnect:
        logging.info(f"Client disconnected from /ws/stop-listening. WebSocket state: {websocket.client_state}")
    except Exception as e:
        logging.error(f"Error in /ws/stop-listening: {e}", exc_info=True)
        try:
            # Attempt to send error status only if not a disconnect
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": str(e)
            }))
        except Exception as send_exc:
            logging.error(f"Failed to send error message to client after initial error: {send_exc}")
    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
