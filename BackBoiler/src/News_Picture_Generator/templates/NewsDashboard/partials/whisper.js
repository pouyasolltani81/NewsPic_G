(() => {
  // DOM elements
  const uploadInput = document.getElementById('audio-upload');
  const recordBtn = document.getElementById('record-btn');
  const recordText = document.getElementById('record-text');
  const recordIcon = document.getElementById('record-icon');
  const recordingStatus = document.getElementById('recording-status');
  const recordingTimer = document.getElementById('recording-timer');
  const submitBtn = document.getElementById('submit-btn');
  const clearBtn = document.getElementById('clear-btn');
  const transcriptionResult = document.getElementById('transcription-result');
  const copyBtn = document.getElementById('copy-btn');
  const errorMsg = document.getElementById('error-msg');
  const errorText = document.getElementById('error-text');
  const successMsg = document.getElementById('success-msg');
  const successText = document.getElementById('success-text');
  const fileInfo = document.getElementById('file-info');
  const fileName = document.getElementById('file-name');

  // State
  let recordedBlob = null;
  let mediaRecorder = null;
  let recordingStartTime = null;
  let recordingInterval = null;
  let audioChunks = [];

  // Utility functions
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }

  function showError(message) {
    errorText.textContent = message;
    errorMsg.classList.remove('hidden');
    successMsg.classList.add('hidden');
    setTimeout(() => errorMsg.classList.add('hidden'), 5000);
  }

  function showSuccess(message) {
    successText.textContent = message;
    successMsg.classList.remove('hidden');
    errorMsg.classList.add('hidden');
    setTimeout(() => successMsg.classList.add('hidden'), 3000);
  }

    function updateSubmitState() {
    const hasAudio = uploadInput.files.length > 0 || recordedBlob !== null;
    submitBtn.disabled = !hasAudio;
  }

  function updateRecordingTimer() {
    if (recordingStartTime) {
      const elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
      recordingTimer.textContent = formatTime(elapsed);
    }
  }

  function resetUI() {
    uploadInput.value = '';
    recordedBlob = null;
    transcriptionResult.textContent = '';
    fileInfo.classList.add('hidden');
    copyBtn.classList.add('opacity-0', 'invisible');
    errorMsg.classList.add('hidden');
    successMsg.classList.add('hidden');
    updateSubmitState();
  }

  // Event listeners
  // Replace the current uploadInput event listener with this:
uploadInput.addEventListener('change', (e) => {
  if (e.target.files.length > 0) {
    const file = e.target.files[0];
    fileName.textContent = file.name;
    fileInfo.classList.remove('hidden');
    // Don't reset recordedBlob here - remove this line:
    // recordedBlob = null; 
    updateSubmitState();
  } else {
    fileInfo.classList.add('hidden');
    updateSubmitState();
  }
});

  // Recording functionality
  recordBtn.addEventListener('click', async () => {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      // Stop recording
      mediaRecorder.stop();
      clearInterval(recordingInterval);
      recordingInterval = null;
      
      recordText.textContent = 'Start Recording';
      recordIcon.innerHTML = '<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd"></path>';
      recordBtn.classList.remove('from-red-500', 'to-red-600', 'hover:from-red-600', 'hover:to-red-700');
      recordBtn.classList.add('from-green-500', 'to-green-600', 'hover:from-green-600', 'hover:to-green-700');
      recordingStatus.classList.add('hidden');
    } else {
      // Start recording
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
        audioChunks = [];

        mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0) {
            audioChunks.push(e.data);
          }
        };

        mediaRecorder.onstop = () => {
          recordedBlob = new Blob(audioChunks, { type: 'audio/webm' });
          audioChunks = [];
          updateSubmitState();
          showSuccess('Recording saved successfully!');
          
          // Stop all tracks
          stream.getTracks().forEach(track => track.stop());
        };

        mediaRecorder.start();
        recordingStartTime = Date.now();
        recordingInterval = setInterval(updateRecordingTimer, 1000);
        
        recordText.textContent = 'Stop Recording';
        recordIcon.innerHTML = '<rect x="6" y="6" width="8" height="8" rx="1" fill="currentColor"></rect>';
        recordBtn.classList.remove('from-green-500', 'to-green-600', 'hover:from-green-600', 'hover:to-green-700');
        recordBtn.classList.add('from-red-500', 'to-red-600', 'hover:from-red-600', 'hover:to-red-700');
        recordingStatus.classList.remove('hidden');
        recordingTimer.textContent = '00:00';
        
        // Clear file upload
        uploadInput.value = '';
        fileInfo.classList.add('hidden');
        transcriptionResult.textContent = '';
        copyBtn.classList.add('opacity-0', 'invisible');
      } catch (err) {
        console.error('Microphone error:', err);
        showError('Microphone access denied or not available. Please check your browser settings.');
      }
    }
  });

  // Clear button
  clearBtn.addEventListener('click', () => {
    resetUI();
    showSuccess('All cleared!');
  });

  // Copy button
  copyBtn.addEventListener('click', () => {
    const text = transcriptionResult.textContent;
    if (text && text !== 'Transcribing...' && text !== 'Processing your audio...') {
      navigator.clipboard.writeText(text).then(() => {
        showSuccess('Transcription copied to clipboard!');
      }).catch(() => {
        showError('Failed to copy text');
      });
    }
  });

  // Show/hide copy button on hover
  transcriptionResult.addEventListener('mouseenter', () => {
    if (transcriptionResult.textContent && 
        transcriptionResult.textContent !== 'Transcribing...' && 
        transcriptionResult.textContent !== 'Processing your audio...') {
      copyBtn.classList.remove('opacity-0', 'invisible');
    }
  });

  transcriptionResult.parentElement.addEventListener('mouseleave', () => {
    copyBtn.classList.add('opacity-0', 'invisible');
  });

  // Submit button
  submitBtn.addEventListener('click', async () => {
    errorMsg.classList.add('hidden');
    successMsg.classList.add('hidden');
    
    // Show loading state
    transcriptionResult.textContent = 'Processing your audio...';
    submitBtn.disabled = true;
    submitBtn.innerHTML = `
      <svg class="animate-spin h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      Transcribing...
    `;

    const formData = new FormData();

    try {
      if (uploadInput.files.length > 0) {
        formData.append('audio_file', uploadInput.files[0]);
      } else if (recordedBlob) {
        const file = new File([recordedBlob], 'recording.webm', { type: 'audio/webm' });
        formData.append('audio_file', file);
      } else {
        throw new Error('Please upload a file or record audio first.');
      }

      // Force Persian language
      formData.append('language', 'fa');

      const response = await fetch('/News_Picture_Generator/transcribe/', {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCookie('csrftoken')
        },
        body: formData,
        credentials: 'same-origin'
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Transcription failed');
      }

      const data = await response.json();
      const transcribedText = data.text || '[No transcription returned]';
      
      // Animate text appearance
      transcriptionResult.textContent = '';
      let index = 0;
      const typeInterval = setInterval(() => {
        if (index < transcribedText.length) {
          transcriptionResult.textContent += transcribedText[index];
          index++;
        } else {
          clearInterval(typeInterval);
          showSuccess('Transcription completed successfully!');
        }
      }, 10);

    } catch (err) {
      transcriptionResult.textContent = '';
      showError(err.message);
    } finally {
      // Reset submit button
      submitBtn.disabled = false;
      submitBtn.innerHTML = `
        <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>
        </svg>
        Transcribe Audio
      `;
      updateSubmitState();
    }
  });

  // Initialize
  updateSubmitState();
})();