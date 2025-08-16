(() => {
  const uploadInput = document.getElementById('audio-upload');
  const recordBtn = document.getElementById('record-btn');
  const recordingStatus = document.getElementById('recording-status');
  const submitBtn = document.getElementById('submit-btn');
  const transcriptionResult = document.getElementById('transcription-result');
  const errorMsg = document.getElementById('error-msg');

  let recordedBlob = null;
  let mediaRecorder = null;

  // Enable submit if a file is chosen or recording is ready
  function updateSubmitState() {
    submitBtn.disabled = !(uploadInput.files.length > 0 || recordedBlob);
  }

  uploadInput.addEventListener('change', () => {
    recordedBlob = null; // reset recorded audio if upload chosen
    updateSubmitState();
  });

  // Recording logic
  recordBtn.addEventListener('click', async () => {
    errorMsg.classList.add('hidden');
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.stop();
      recordBtn.textContent = 'Start Recording';
      recordingStatus.classList.add('hidden');
      updateSubmitState();
    } else {
      // Request mic access
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        let chunks = [];

        mediaRecorder.ondataavailable = e => {
          chunks.push(e.data);
        };

        mediaRecorder.onstop = () => {
          recordedBlob = new Blob(chunks, { type: 'audio/webm' });
          chunks = [];
          updateSubmitState();
        };

        mediaRecorder.start();
        recordBtn.textContent = 'Stop Recording';
        recordingStatus.classList.remove('hidden');
        transcriptionResult.textContent = '';
        uploadInput.value = ''; // clear upload input
      } catch (err) {
        errorMsg.textContent = 'Microphone access denied or not available.';
        errorMsg.classList.remove('hidden');
      }
    }
  });

  submitBtn.addEventListener('click', async () => {
    errorMsg.classList.add('hidden');
    transcriptionResult.textContent = 'Transcribing...';

    const formData = new FormData();

    if (uploadInput.files.length > 0) {
      formData.append('audio_file', uploadInput.files[0]);
    } else if (recordedBlob) {
      // Convert webm blob to a file with name
      const file = new File([recordedBlob], 'recording.webm', { type: 'audio/webm' });
      formData.append('audio_file', file);
    } else {
      errorMsg.textContent = 'Please upload a file or record audio first.';
      errorMsg.classList.remove('hidden');
      transcriptionResult.textContent = '';
      return;
    }

    // We force Persian "fa" language, adjust if you want to add UI for language
    formData.append('language', 'fa');

    try {
      const response = await fetch('/News_Picture_Generator/transcribe/', {
        method: 'POST',
        headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
        body: formData,
        credentials: 'same-origin', // include cookies for auth if needed
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Transcription failed');
      }

      const data = await response.json();
      transcriptionResult.textContent = data.text || '[No transcription returned]';
    } catch (err) {
      transcriptionResult.textContent = '';
      errorMsg.textContent = err.message;
      errorMsg.classList.remove('hidden');
    }
  });
})();