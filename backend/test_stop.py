import asyncio
import websockets
import json
import logging
from websockets.exceptions import ConnectionClosedError, WebSocketException

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_stop_listening():
    """Test the stop-listening WebSocket endpoint."""
    uri = "ws://127.0.0.1:8000/ws/stop-listening"
    
    try:
        # Connect to the WebSocket endpoint with a timeout
        async with websockets.connect(uri, ping_interval=None, close_timeout=5) as websocket:
            logger.info("Connected to stop-listening WebSocket")
            
            # Send stop command
            stop_command = {
                "type": "stop"
            }
            await websocket.send(json.dumps(stop_command))
            logger.info("Sent stop command")
            
            # Wait for and verify stopping status
            response = await websocket.recv()
            data = json.loads(response)
            logger.info(f"Received first response: {data}")
            assert data["type"] == "status"
            assert data["status"] == "stopping"
            logger.info("Received stopping status")
            
            # Wait for and verify stopped status
            response = await websocket.recv()
            data = json.loads(response)
            logger.info(f"Received second response: {data}")
            assert data["type"] == "status"
            assert data["status"] == "stopped"
            logger.info("Received stopped status")
            
            logger.info("Stop listening test completed successfully")
            
    except ConnectionClosedError as e:
        logger.error(f"WebSocket connection closed: {e}")
        raise
    except WebSocketException as e:
        logger.error(f"WebSocket error: {e}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        raise
    except AssertionError as e:
        logger.error(f"Assertion error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

async def test_stop_listening_invalid_command():
    """Test the stop-listening WebSocket endpoint with an invalid command."""
    uri = "ws://127.0.0.1:8000/ws/stop-listening"
    
    try:
        # Connect to the WebSocket endpoint with a timeout
        async with websockets.connect(uri, ping_interval=None, close_timeout=5) as websocket:
            logger.info("Connected to stop-listening WebSocket")
            
            # Send invalid command
            invalid_command = {
                "type": "invalid"
            }
            await websocket.send(json.dumps(invalid_command))
            logger.info("Sent invalid command")
            
            # Wait for error response
            response = await websocket.recv()
            data = json.loads(response)
            logger.info(f"Received response for invalid command: {data}")
            assert data["type"] == "error"
            logger.info("Received error response as expected")
            
            logger.info("Invalid command test completed successfully")
            
    except ConnectionClosedError as e:
        logger.error(f"WebSocket connection closed: {e}")
        raise
    except WebSocketException as e:
        logger.error(f"WebSocket error: {e}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        raise
    except AssertionError as e:
        logger.error(f"Assertion error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

if __name__ == "__main__":
    # Run the tests
    asyncio.run(test_stop_listening())
    asyncio.run(test_stop_listening_invalid_command()) 