// Modal elements
const modal = document.getElementById('generateModal');
const generateBtn = document.getElementById('generateBtn');
const closeModal = document.getElementById('closeModal');
const cancelBtn = document.getElementById('cancelBtn');
const generateForm = document.getElementById('generateForm');
const generateText = document.getElementById('generateText');
const generateSpinner = document.getElementById('generateSpinner');

// Filter functionality
const imageFilter = document.getElementById('imageFilter');
const imageCards = document.querySelectorAll('.image-card');

// Polling variables
let pollInterval = null;
let currentGenerationId = null;

// Show/hide modal
generateBtn.addEventListener('click', () => {
    modal.classList.remove('hidden');
    modal.classList.add('flex');
});

closeModal.addEventListener('click', () => {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    stopPolling();
});

cancelBtn.addEventListener('click', () => {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    stopPolling();
});

// Close modal on outside click
modal.addEventListener('click', (e) => {
    if (e.target === modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
        stopPolling();
    }
});

// Handle form submission
generateForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    // Show loading state
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
            
            // Get generation_id from response
            if (result.generation_id) {
                currentGenerationId = result.generation_id;
                
                // Update UI to show polling status
                generateText.textContent = 'Waiting for image...';
                
                // Start polling for the result
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
    }
});

// Start polling for generation result
function startPolling(generationId) {
    // Clear any existing interval
    stopPolling();
    
    // Poll immediately
    checkGenerationStatus(generationId);
    
    // Then poll every 10 seconds
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
            
            // Check if we have results
            if (result.count > 0 && result.results && result.results.length > 0) {
                // Stop polling
                stopPolling();
                
                // Display the result
                displayGeneratedImage(result.results[0]);
                
                // Reset button
                resetGenerateButton();
            }
        } else {
            console.error('Error checking status:', response.status);
        }
    } catch (error) {
        console.error('Error polling for result:', error);
    }
}

// Display the generated image with all details
function displayGeneratedImage(imageData) {
    // Close the modal
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    
    // Create a result modal or update the page
    const resultHTML = `
        <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" id="resultModal">
            <div class="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto">
                <div class="p-6">
                    <div class="flex justify-between items-center mb-4">
                        <h2 class="text-2xl font-bold text-gray-800 dark:text-white">Generated Image</h2>
                        <button onclick="closeResultModal()" class="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200">
                            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                            </svg>
                        </button>
                    </div>
                    
                    <div class="grid md:grid-cols-2 gap-6">
                        <!-- Image -->
                        <div>
                            <img src="${imageData.url}" alt="${imageData.prompt}" class="w-full rounded-lg shadow-lg">
                        </div>
                        
                        <!-- Details -->
                        <div class="space-y-4">
                            <div>
                                <h3 class="font-semibold text-gray-700 dark:text-gray-300">Prompt</h3>
                                <p class="text-gray-600 dark:text-gray-400">${imageData.prompt}</p>
                            </div>
                            
                            ${imageData.negative_prompt ? `
                            <div>
                                <h3 class="font-semibold text-gray-700 dark:text-gray-300">Negative Prompt</h3>
                                <p class="text-gray-600 dark:text-gray-400">${imageData.negative_prompt}</p>
                            </div>
                            ` : ''}
                            
                            <div class="grid grid-cols-2 gap-4">
                                <div>
                                    <h3 class="font-semibold text-gray-700 dark:text-gray-300">Dimensions</h3>
                                    <p class="text-gray-600 dark:text-gray-400">${imageData.width} × ${imageData.height}</p>
                                </div>
                                
                                <div>
                                    <h3 class="font-semibold text-gray-700 dark:text-gray-300">Seed</h3>
                                    <p class="text-gray-600 dark:text-gray-400">${imageData.seed}</p>
                                </div>
                            </div>
                            
                            <div>
                                <h3 class="font-semibold text-gray-700 dark:text-gray-300">Generated At</h3>
                                <p class="text-gray-600 dark:text-gray-400">${imageData.generated_at}</p>
                            </div>
                            
                            <div>
                                <h3 class="font-semibold text-gray-700 dark:text-gray-300">Generation ID</h3>
                                <p class="text-gray-600 dark:text-gray-400 font-mono text-sm">${imageData.generation_id}</p>
                            </div>
                            
                            <div class="pt-4">
                                <a href="${imageData.url}" download="${imageData.filename}" 
                                   class="inline-flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors">
                                    <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
                                    </svg>
                                    Download Image
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Add result modal to body
    document.body.insertAdjacentHTML('beforeend', resultHTML);
}

// Close result modal
function closeResultModal() {
    const resultModal = document.getElementById('resultModal');
    if (resultModal) {
        resultModal.remove();
        // Optionally reload the page to show the new image in the gallery
        // window.location.reload();
    }
}

// Reset generate button
function resetGenerateButton() {
    generateText.textContent = 'Generate';
    generateSpinner.classList.add('hidden');
    generateBtn.disabled = false;
}

// Filter functionality
imageFilter.addEventListener('change', (e) => {
    const filterValue = e.target.value.toLowerCase();
    
    imageCards.forEach(card => {
        const title = card.dataset.title;
        const prompt = card.dataset.prompt;
        
        if (filterValue === 'all') {
            card.style.display = '';
        } else if (filterValue === 'recent') {
            // You'll need to add a data-date attribute to cards in the template
            // For now, just show all
            card.style.display = '';
        } else {
            // Filter by keyword in title or prompt
            if (title.includes(filterValue) || prompt.includes(filterValue)) {
                card.style.display = '';
            } else {
                card.style.display = 'none';
            }
        }
    });
});

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

// Make closeResultModal globally available
window.closeResultModal = closeResultModal;