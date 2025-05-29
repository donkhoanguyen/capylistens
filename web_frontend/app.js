// app.js - Updated to handle streaming results
const SERVER_URL = "ws://localhost:8000";
const START_LISTENING_ENDPOINT = `${SERVER_URL}/ws/start-listening`;

const SEND_INTERVAL = 30 * 1000;
const DEBUG = true;

// DOM
const startButton = document.getElementById('startButton');
const stopButton = document.getElementById('stopButton');
const statusParagraph = document.getElementById('status');
const responseList = document.getElementById('responseList');
const timeLeftDisplay = document.getElementById('timeLeft');

// State
let mediaRecorder;
let websocket;
let isRecording = false;
let requestIntervalId;
let countdownIntervalId;
let segmentCounter = 0;
let retryAttempts = 0;
const MAX_RETRIES = 3;

// Track segment processing status
const segmentStatus = new Map();

// Worker
const worker = new Worker("worker.js");
worker.onmessage = (e) => {
    const data = e.data;
    
    switch (data.type) {
        case 'status':
            addMessage(`Segment ${data.segmentId}: ${data.message} (${data.bytes} bytes)`);
            updateSegmentStatus(data.segmentId, 'processing');
            break;
            
        case 'progress':
            addMessage(`Segment ${data.segmentId}: ${data.message}`);
            updateSegmentStatus(data.segmentId, data.step);
            break;
            
        case 'transcription':
            console.log(`Transcription ready for segment ${data.segmentId}:`, data.transcription);
            addMessage(`📝 Transcription ${data.segmentId}: ${data.transcription}`);
            updateSegmentStatus(data.segmentId, 'transcribed');
            
            // Add transcription to a dedicated section if you want
            displayTranscription(data.transcription, data.segmentId);
            break;
            
        case 'fact_check':
            console.log(`Fact check ready for segment ${data.segmentId}:`, data.fact_check_results);
            addMessage(`✅ Fact Check ${data.segmentId}: ${data.claims.length} claims, ${data.fact_check_results.length} results`);
            updateSegmentStatus(data.segmentId, 'fact_checked');
            
            // Display detailed results
            displayFactCheckResults(data.claims, data.fact_check_results, data.segmentId);
            break;
            
        case 'success':
            // Final completion message (for backward compatibility)
            console.log(`Segment ${data.segmentId} fully processed:`, data.results);
            addMessage(`✨ Segment ${data.segmentId} completed successfully`);
            updateSegmentStatus(data.segmentId, 'completed');
            break;
            
        case 'error':
            console.error(`Error for segment ${data.segmentId}:`, data.error);
            addMessage(`❌ Upload failed ${data.segmentId}: ${data.error}`);
            updateSegmentStatus(data.segmentId, 'error');
            break;
    }
};

// New helper functions for better UI organization
function updateSegmentStatus(segmentId, status) {
    segmentStatus.set(segmentId, status);
    updateStatus(`Recording... (Segment ${segmentId}: ${status})`);
}

function displayTranscription(transcription, segmentId) {
    // Create or update transcription display
    let transcriptionSection = document.getElementById('transcriptions');
    if (!transcriptionSection) {
        transcriptionSection = document.createElement('div');
        transcriptionSection.id = 'transcriptions';
        transcriptionSection.innerHTML = '<h3>Transcriptions</h3>';
        document.body.appendChild(transcriptionSection);
    }
    
    const transcriptionDiv = document.createElement('div');
    transcriptionDiv.className = 'transcription-item';
    transcriptionDiv.innerHTML = `
        <div class="segment-header">
            <strong>Segment ${segmentId}</strong>
            <span class="timestamp">${new Date().toLocaleTimeString()}</span>
        </div>
        <div class="transcription-text">${transcription}</div>
    `;
    
    transcriptionSection.appendChild(transcriptionDiv);
}

function displayFactCheckResults(claims, results, segmentId) {
    // Create or update fact check display
    let factCheckSection = document.getElementById('fact-checks');
    if (!factCheckSection) {
        factCheckSection = document.createElement('div');
        factCheckSection.id = 'fact-checks';
        factCheckSection.innerHTML = '<h3>Fact Check Results</h3>';
        document.body.appendChild(factCheckSection);
    }
    
    const factCheckDiv = document.createElement('div');
    factCheckDiv.className = 'fact-check-item';
    
    const claimsHtml = claims.map((claim, index) => 
        `<li><strong>Claim ${index + 1}:</strong> ${claim}</li>`
    ).join('');
    
    const resultsHtml = results.map((result, index) => 
        `<li><strong>Result ${index + 1}:</strong> ${JSON.stringify(result)}</li>`
    ).join('');
    
    factCheckDiv.innerHTML = `
        <div class="segment-header">
            <strong>Segment ${segmentId} Fact Check</strong>
            <span class="timestamp">${new Date().toLocaleTimeString()}</span>
        </div>
        <div class="claims">
            <h5>Claims (${claims.length}):</h5>
            <ul>${claimsHtml}</ul>
        </div>
        <div class="results">
            <h5>Fact Check Results (${results.length}):</h5>
            <ul>${resultsHtml}</ul>
        </div>
    `;
    
    factCheckSection.appendChild(factCheckDiv);
}

// Existing helper functions
function updateStatus(msg) {
    console.log("Status update:", msg);
    statusParagraph.textContent = `Status: ${msg}`;
}

function addMessage(msg) {
    console.log("Message:", msg);
    const li = document.createElement("li");
    li.textContent = msg;
    li.className = getMessageClass(msg);
    responseList.prepend(li);
    if (responseList.children.length > 50) responseList.removeChild(responseList.lastChild);
    if (DEBUG) console.log(msg);
}

function getMessageClass(msg) {
    if (msg.includes('❌') || msg.toLowerCase().includes('error')) return 'error-message';
    if (msg.includes('📝')) return 'transcription-message';
    if (msg.includes('✅')) return 'fact-check-message';
    if (msg.includes('✨')) return 'success-message';
    return 'info-message';
}

function updateCountdown(seconds) {
    if (timeLeftDisplay) timeLeftDisplay.textContent = seconds;
}

// WebSocket functions remain the same
function connectWebSocket() {
    updateStatus("Connecting to server...");
    return new Promise((resolve, reject) => {
        websocket = new WebSocket(START_LISTENING_ENDPOINT);

        websocket.onopen = () => {
            addMessage("WebSocket connected.");
            updateStatus("Connected.");
            retryAttempts = 0;
            resolve();
        };

        websocket.onmessage = (e) => addMessage(`Server: ${e.data}`);

        websocket.onerror = (e) => {
            updateStatus("WebSocket error.");
            reject(e);
        };

        websocket.onclose = (e) => {
            addMessage(`WebSocket closed: ${e.code}`);
            if (retryAttempts < MAX_RETRIES) {
                retryAttempts++;
                setTimeout(connectWebSocket, 1000);
            } else {
                addMessage("Max retries reached. Giving up.");
                updateStatus("Disconnected.");
            }
        };
    });
}

// Recording functions remain the same
async function recordSegment(segmentId) {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const options = { mimeType: 'audio/webm;codecs=opus' };
    const recorder = new MediaRecorder(stream, options);

    return new Promise((resolve, reject) => {
        recorder.ondataavailable = (e) => {
            resolve({ blob: e.data, segmentId });
            recorder.stop();
            stream.getTracks().forEach(t => t.stop());
        };

        recorder.onerror = (e) => reject(e.error);

        recorder.start();
        setTimeout(() => recorder.requestData(), SEND_INTERVAL);
    });
}

async function startRecording() {
    if (isRecording) return;

    isRecording = true;
    startButton.disabled = true;
    stopButton.disabled = false;
    updateStatus("Recording...");
    addMessage("Recording started. Capturing 30s segments with streaming results...");

    let segmentId = 0;

    async function loopSegments() {
        while (isRecording) {
            try {
                updateStatus(`Recording segment ${segmentId + 1}...`);
                const { blob, segmentId: id } = await recordSegment(++segmentId);
                worker.postMessage({ blob, segmentId: id });
                addMessage(`🎤 Queued segment ${id} for streaming processing`);
            } catch (err) {
                addMessage(`Error during segment ${segmentId}: ${err.message}`);
                updateStatus("Recording error.");
                stopRecording();
            }
        }
    }

    loopSegments();
}

function stopRecording() {
    isRecording = false;
    startButton.disabled = false;
    stopButton.disabled = true;
    updateStatus("Stopped.");
    addMessage("Recording stopped.");
}

// Events
startButton.addEventListener("click", startRecording);
stopButton.addEventListener("click", stopRecording);
window.addEventListener("beforeunload", () => {
    if (isRecording) stopRecording();
});

// Add some basic CSS for better visual organization
const style = document.createElement('style');
style.textContent = `
    .transcription-item, .fact-check-item {
        border: 1px solid #ddd;
        margin: 10px 0;
        padding: 10px;
        border-radius: 5px;
        background: #f9f9f9;
    }
    
    .segment-header {
        display: flex;
        justify-content: space-between;
        margin-bottom: 10px;
        font-weight: bold;
    }
    
    .timestamp {
        color: #666;
        font-size: 0.9em;
        font-weight: normal;
    }
    
    .transcription-text {
        background: white;
        padding: 8px;
        border-radius: 3px;
        font-style: italic;
    }
    
    .error-message { color: red; }
    .transcription-message { color: blue; }
    .fact-check-message { color: green; }
    .success-message { color: purple; }
    .info-message { color: black; }
    
    #transcriptions, #fact-checks {
        margin-top: 20px;
        max-height: 400px;
        overflow-y: auto;
    }
`;
document.head.appendChild(style);