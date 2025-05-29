from transcriber import Transcriber

if __name__ == "__main__":
    transcriber = Transcriber(model_name="base")  # You can use "tiny", "small", "medium", "large"
    transcriber.transcribe_realtime(duration=5)    # 5 seconds per chunk 