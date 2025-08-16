async function sendQwenRequest() {
  const systemPrompt = document.getElementById('system-prompt').value;
  const userPrompt = document.getElementById('user-prompt').value;
  const responseContent = document.getElementById('response-content');
  const loadingIndicator = document.getElementById('loading-indicator');
  const submitBtn = document.getElementById('submit-btn');

  if (!systemPrompt || !userPrompt) {
    responseContent.innerHTML = '<span class="text-red-500">Please fill in both prompts.</span>';
    return;
  }

  // Show loading state
  loadingIndicator.classList.remove('hidden');
  submitBtn.disabled = true;
  submitBtn.classList.add('opacity-50', 'cursor-not-allowed');
  responseContent.innerHTML = '<span class="text-gray-500">Waiting for response...</span>';

  try {
    const response = await fetch('http://79.175.177.113:17800/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'Qwen/Qwen2.5-14B-Instruct',
        messages: [
          {
            role: 'system',
            content: systemPrompt
          },
          {
            role: 'user',
            content: userPrompt
          }
        ]
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    
    // Display the response
    if (data.choices && data.choices[0] && data.choices[0].message) {
      responseContent.innerHTML = `<div class="text-gray-800 dark:text-gray-200 whitespace-pre-wrap">${data.choices[0].message.content}</div>`;
    } else {
      responseContent.innerHTML = '<span class="text-red-500">Invalid response format</span>';
    }
  } catch (error) {
    responseContent.innerHTML = `<span class="text-red-500">Error: ${error.message}</span>`;
  } finally {
    // Hide loading state
    loadingIndicator.classList.add('hidden');
    submitBtn.disabled = false;
    submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
  }
}

// Allow Enter key to submit (Ctrl/Cmd + Enter)
document.getElementById('user-prompt').addEventListener('keydown', function(e) {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    sendQwenRequest();
  }
});