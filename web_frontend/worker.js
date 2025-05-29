// worker.js
self.onmessage = async (e) => {
  const { blob, segmentId } = e.data;
  const form = new FormData();
  form.append("file", blob, `segment-${segmentId}.webm`);
  form.append("segment_id", segmentId);

  try {
    const resp = await fetch("http://localhost:8000/upload", {
      method: "POST",
      body: form
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const json = await resp.json();
    
    // Send the full results back to the main thread
    self.postMessage({
      type: 'success',
      segmentId,
      results: json.results
    });
  } catch (err) {
    self.postMessage({
      type: 'error',
      segmentId,
      error: err.message
    });
  }
};