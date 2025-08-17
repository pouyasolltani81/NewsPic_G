
document.addEventListener('DOMContentLoaded', function() {
    const generateForm = document.getElementById('generateForm');
    const generateBtn = document.getElementById('generateBtn');
    const generateText = document.getElementById('generateText');
    const generateSpinner = document.getElementById('generateSpinner');
    
    const emptyImageState = document.getElementById('emptyImageState');
    const loadingState = document.getElementById('loadingState');
    const generatedImageDisplay = document.getElementById('generatedImageDisplay');
    
    let pollInterval = null;
    let currentGenerationId = null;

    // Handle form submission
    generateForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Show loading state
        emptyImageState.classList.add('hidden');
        generatedImageDisplay.classList.add('hidden');
        loadingState.classList.remove('hidden');
        
        generateText.textContent = 'Generating...';
        generateSpinner.classList.remove('hidden');
        generateBtn.disabled = true;
        
        const formData = new FormData(generateForm);
        const data = {
                        prompt: formData.get('prompt'),
            width: parseInt(formData.get('width')),
            height: parseInt(formData.get('height')),
            negative_prompt: formData.get('negative_prompt'),
            seed: parseInt(formData.get('seed')),
            steps: parseInt(formData.get('steps')),
            guidance_scale: parseFloat(formData.get('guidance_scale'))
        };
        
        try {
            const response = await fetch('/News_Picture_Generator/custom-images/generate/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify(data)
            });
            
            if (response.ok) {
                const result = await response.json();
                
                if (result.generation_id) {
                    currentGenerationId = result.generation_id;
                    startPolling(currentGenerationId);
                } else {
                    throw new Error('No generation ID received');
                }
            } else {
                throw new Error('Generation failed');
            }
        } catch (error) {
            alert('Error generating image. Please try again.');
            console.error('Error:', error);
            resetGenerateButton();
            showEmptyState();
        }
    });

    // Start polling for generation result
    function startPolling(generationId) {
        stopPolling();
        checkGenerationStatus(generationId);
        pollInterval = setInterval(() => {
            checkGenerationStatus(generationId);
        }, 10000);
    }

    // Stop polling
    function stopPolling() {
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
    }

    // Check generation status
    async function checkGenerationStatus(generationId) {
        try {
            const searchData = {
                search_text: "",
                generation_id: generationId,
                include_negative: false
            };
            
            const response = await fetch('/News_Picture_Generator/custom-images/search/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify(searchData)
            });
            
            if (response.ok) {
                const result = await response.json();
                
                if (result.count > 0 && result.results && result.results.length > 0) {
                    stopPolling();
                    displayGeneratedImage(result.results[0]);
                    resetGenerateButton();
                }
            } else {
                console.error('Error checking status:', response.status);
            }
        } catch (error) {
            console.error('Error polling for result:', error);
        }
    }

    // Display the generated image
    function displayGeneratedImage(imageData) {
        // Hide loading state
        loadingState.classList.add('hidden');
        
        // Update image
        const generatedImage = document.getElementById('generatedImage');
        generatedImage.src = imageData.url;
        
        // Update details
        document.getElementById('displayPrompt').textContent = imageData.prompt;
        
        if (imageData.negative_prompt) {
            document.getElementById('displayNegativePromptContainer').classList.remove('hidden');
            document.getElementById('displayNegativePrompt').textContent = imageData.negative_prompt;
        } else {
            document.getElementById('displayNegativePromptContainer').classList.add('hidden');
        }
        
        document.getElementById('displayDimensions').textContent = `${imageData.width} × ${imageData.height}`;
        document.getElementById('displaySeed').textContent = imageData.seed;
        document.getElementById('displayTime').textContent = new Date(imageData.generated_at).toLocaleString();
        
        // Show generated image display
        generatedImageDisplay.classList.remove('hidden');
        
        // Setup download button
        const downloadBtn = document.getElementById('downloadBtn');
        downloadBtn.onclick = () => {
            const a = document.createElement('a');
            a.href = imageData.url;
            a.download = imageData.filename || 'generated-image.png';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        };
        
        // Setup fullscreen button
        const fullscreenBtn = document.getElementById('fullscreenBtn');
        fullscreenBtn.onclick = () => {
            if (generatedImage.requestFullscreen) {
                generatedImage.requestFullscreen();
            } else if (generatedImage.webkitRequestFullscreen) {
                generatedImage.webkitRequestFullscreen();
            } else if (generatedImage.msRequestFullscreen) {
                generatedImage.msRequestFullscreen();
            }
        };
    }

    // Reset generate button
    function resetGenerateButton() {
        generateText.textContent = 'Generate Image';
        generateSpinner.classList.add('hidden');
        generateBtn.disabled = false;
    }

    // Show empty state
    function showEmptyState() {
        loadingState.classList.add('hidden');
        generatedImageDisplay.classList.add('hidden');
        emptyImageState.classList.remove('hidden');
    }

    // Helper function to get CSRF token
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
});