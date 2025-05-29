interface ProcessingResult {
    transcription: string;
    claims: string[];
    fact_check_results: {
        claim: string;
        fact_check: any; // Replace with actual fact check result type
    }[];
}

export class AudioProcessor {
    private ws: WebSocket | null = null;
    private mediaRecorder: MediaRecorder | null = null;
    private stream: MediaStream | null = null;
    private isRecording: boolean = false;
    private readonly CHUNK_DURATION = 30000; // 30 seconds in milliseconds

    constructor(private wsUrl: string) {}

    async startRecording(): Promise<void> {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.connectWebSocket();
            this.setupMediaRecorder();
            this.isRecording = true;
        } catch (error) {
            console.error('Error starting recording:', error);
            throw error;
        }
    }

    private connectWebSocket(): void {
        this.ws = new WebSocket(this.wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket connection established');
        };

        this.ws.onmessage = (event) => {
            const result: ProcessingResult = JSON.parse(event.data);
            this.handleProcessingResult(result);
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        this.ws.onclose = () => {
            console.log('WebSocket connection closed');
        };
    }

    private setupMediaRecorder(): void {
        if (!this.stream) return;

        this.mediaRecorder = new MediaRecorder(this.stream);
        
        this.mediaRecorder.ondataavailable = async (event) => {
            if (event.data.size > 0 && this.ws?.readyState === WebSocket.OPEN) {
                // Convert Blob to ArrayBuffer
                const arrayBuffer = await event.data.arrayBuffer();
                this.ws.send(arrayBuffer);
            }
        };

        // Start recording in chunks
        this.mediaRecorder.start(this.CHUNK_DURATION);
    }

    stopRecording(): void {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;
        }

        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }

        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    private handleProcessingResult(result: ProcessingResult): void {
        // Emit events or call callbacks with the results
        console.log('Transcription:', result.transcription);
        console.log('Claims:', result.claims);
        console.log('Fact Check Results:', result.fact_check_results);
        
        // You can add custom event handling here
        const event = new CustomEvent('processingResult', { detail: result });
        window.dispatchEvent(event);
    }
}

// Example usage:
/*
const processor = new AudioProcessor('ws://localhost:8000/ws');

// Start recording
processor.startRecording().catch(console.error);

// Listen for results
window.addEventListener('processingResult', ((event: CustomEvent) => {
    const result = event.detail;
    // Handle the results
    console.log('New processing result:', result);
}) as EventListener);

// Stop recording when done
processor.stopRecording();
*/ 