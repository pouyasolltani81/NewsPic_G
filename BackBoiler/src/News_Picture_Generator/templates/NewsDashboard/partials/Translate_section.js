// Translation Service JavaScript
(function() {
    'use strict';

    // API Base URL
    const API_BASE = '/Translate';
    
    // State Management
    const state = {
        supportedLanguages: [],
        currentMode: 'single',
        translationHistory: [],
        glossaryTerms: {},
        config: null,
        memoryStatus: null,
        serviceHealthy: false
    };

    // CSRF Token Helper
    function getCSRFToken() {
        const token = document.querySelector('[name=csrfmiddlewaretoken]');
        return token ? token.value : document.cookie.split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
    }

    // API Helper
    async function apiCall(endpoint, method = 'GET', data = null) {
        const url = `${API_BASE}${endpoint}`;
        const options = {
            method,
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'Content-Type': 'application/json',
            },
            credentials: 'include'
        };

        if (data && method !== 'GET') {
            options.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, options);
            const result = await response.json();
            
            if (!response.ok) {
                throw new Error(result.error || `HTTP ${response.status}`);
            }
            
            return result;
        } catch (error) {
            console.error(`API Error (${endpoint}):`, error);
            throw error;
        }
    }

    // Initialize the application
    async function init() {
        await checkServiceHealth();
        await loadSupportedLanguages();
        await loadConfiguration();
        await loadGlossary();
        await updateMemoryStatus();
        setupEventListeners();
        loadHistoryFromStorage();
        
        // Set up periodic health checks
        setInterval(checkServiceHealth, 30000); // Check every 30 seconds
        setInterval(updateMemoryStatus, 10000); // Update memory every 10 seconds
    }

    // Check service health
    async function checkServiceHealth() {
        const statusIndicator = document.getElementById('statusIndicator');
        const statusText = document.getElementById('statusText');
        
        try {
            const health = await apiCall('/health/');
            state.serviceHealthy = health.status === 'healthy' && health.model_service;
            
            if (state.serviceHealthy && health.model_service_details?.model_loaded) {
                statusIndicator.className = 'w-3 h-3 bg-green-500 rounded-full';
                statusText.textContent = 'Ready';
                document.getElementById('modelStatus').textContent = 'Loaded';
                document.getElementById('translateBtn').disabled = false;
            } else if (state.serviceHealthy) {
                statusIndicator.className = 'w-3 h-3 bg-yellow-500 rounded-full animate-pulse';
                statusText.textContent = 'Model Loading...';
                document.getElementById('modelStatus').textContent = 'Not Loaded';
                document.getElementById('translateBtn').disabled = true;
            } else {
                statusIndicator.className = 'w-3 h-3 bg-red-500 rounded-full';
                statusText.textContent = 'Service Unavailable';
                document.getElementById('modelStatus').textContent = 'Error';
                document.getElementById('translateBtn').disabled = true;
            }
        } catch (error) {
            statusIndicator.className = 'w-3 h-3 bg-red-500 rounded-full';
            statusText.textContent = 'Connection Error';
            document.getElementById('modelStatus').textContent = 'Offline';
            document.getElementById('translateBtn').disabled = true;
        }
    }

    // Load supported languages
    async function loadSupportedLanguages() {
        try {
            const response = await apiCall('/languages/');
            state.supportedLanguages = response.languages;
            
            const sourceLang = document.getElementById('sourceLang');
            const targetLang = document.getElementById('targetLang');
            
            // Clear existing options except auto-detect
            sourceLang.innerHTML = '<option value="auto">Auto-detect</option>';
            targetLang.innerHTML = '';
            
            // Populate language options
            state.supportedLanguages.forEach(lang => {
                const option1 = new Option(lang, lang);
                const option2 = new Option(lang, lang);
                sourceLang.add(option1);
                targetLang.add(option2);
            });
            
            // Set default target language to Persian
            targetLang.value = 'Persian';
            sourceLang.value = 'English';
            
        } catch (error) {
            showNotification('Failed to load languages', 'error');
        }
    }

    // Load configuration
    async function loadConfiguration() {
        try {
            state.config = await apiCall('/config/');
            
            // Update UI with current config
            if (state.config?.translation?.generation_params) {
                const params = state.config.translation.generation_params;
                document.getElementById('maxTokens').value = params.max_new_tokens || 128;
                document.getElementById('temperature').value = params.temperature || 0.7;
                document.getElementById('topP').value = params.top_p || 0.9;
                document.getElementById('topK').value = params.top_k || 50;
            }
            
            if (state.config?.model?.max_memory) {
                document.getElementById('gpuMemoryConfig').value = state.config.model.max_memory.gpu || '20GB';
                document.getElementById('cpuMemoryConfig').value = state.config.model.max_memory.cpu || '30GB';
            }
        } catch (error) {
            console.error('Failed to load configuration:', error);
        }
    }

    // Load glossary
    async function loadGlossary() {
        try {
            const config = await apiCall('/config/');
            state.glossaryTerms = config.glossary || {};
            updateGlossaryDisplay();
        } catch (error) {
            console.error('Failed to load glossary:', error);
        }
    }

    // Update memory status
    async function updateMemoryStatus() {
        try {
            const memory = await apiCall('/memory/');
            state.memoryStatus = memory;
            
            const gpuMemory = document.getElementById('gpuMemory');
            const cpuMemory = document.getElementById('cpuMemory');
            
            if (memory.gpu_allocated_gb !== undefined) {
                gpuMemory.textContent = `${memory.gpu_allocated_gb.toFixed(2)} / ${memory.gpu_total_gb.toFixed(2)} GB`;
            } else {
                gpuMemory.textContent = 'N/A';
            }
            
            if (memory.cpu_memory_gb !== undefined) {
                cpuMemory.textContent = `${memory.cpu_memory_gb.toFixed(2)} GB (${memory.cpu_percent.toFixed(1)}%)`;
            } else {
                cpuMemory.textContent = 'N/A';
            }
        } catch (error) {
            console.error('Failed to update memory status:', error);
        }
    }

    // Setup event listeners
    function setupEventListeners() {
        // Translation mode tabs
        document.querySelectorAll('.translation-mode-tab').forEach(tab => {
            tab.addEventListener('click', (e) => switchMode(e.target.dataset.mode));
        });

        // Main translate button
        document.getElementById('translateBtn').addEventListener('click', handleTranslate);

        // Language swap
        document.getElementById('swapLangs').addEventListener('click', swapLanguages);

        // Text area management
        const sourceText = document.getElementById('sourceText');
        sourceText.addEventListener('input', updateCharCount);
        document.getElementById('clearSource').addEventListener('click', clearSource);
        document.getElementById('copyTranslation').addEventListener('click', copyTranslation);

        // File upload
        document.getElementById('uploadBtn').addEventListener('click', () => {
            document.getElementById('fileInput').click();
        });
        document.getElementById('fileInput').addEventListener('change', handleFileUpload);

        // Paste button
        document.getElementById('pasteBtn').addEventListener('click', pasteFromClipboard);

        // Download button
        document.getElementById('downloadBtn').addEventListener('click', downloadTranslation);

        // Settings modal
        document.getElementById('settingsBtn').addEventListener('click', openSettings);
        document.getElementById('closeSettingsBtn').addEventListener('click', closeSettings);
        document.getElementById('cancelSettingsBtn').addEventListener('click', closeSettings);
        document.getElementById('saveSettingsBtn').addEventListener('click', saveSettings);

        // Glossary modal
        document.getElementById('addGlossaryBtn').addEventListener('click', openGlossaryModal);
        document.getElementById('cancelGlossaryBtn').addEventListener('click', closeGlossaryModal);
        document.getElementById('saveGlossaryBtn').addEventListener('click', saveGlossaryTerm);

        // Model management
        document.getElementById('reloadModelBtn').addEventListener('click', reloadModel);
        document.getElementById('freeMemoryBtn').addEventListener('click', freeMemory);
    }

    // Switch translation mode
    function switchMode(mode) {
        state.currentMode = mode;
        
        // Update tab styles
        document.querySelectorAll('.translation-mode-tab').forEach(tab => {
            if (tab.dataset.mode === mode) {
                tab.classList.add('bg-blue-100', 'dark:bg-blue-900', 'text-blue-700', 'dark:text-blue-300');
                tab.classList.remove('text-gray-600', 'dark:text-gray-400');
            } else {
                tab.classList.remove('bg-blue-100', 'dark:bg-blue-900', 'text-blue-700', 'dark:text-blue-300');
                tab.classList.add('text-gray-600', 'dark:text-gray-400');
            }
        });
        
        // Show/hide modes
        document.querySelectorAll('.translation-mode').forEach(el => {
            el.classList.add('hidden');
        });
        
        document.getElementById(`${mode}Mode`)?.classList.remove('hidden');
    }

    // Handle translation
    async function handleTranslate() {
        const targetLang = document.getElementById('targetLang').value;
        
        if (!targetLang) {
            showNotification('Please select a target language', 'warning');
            return;
        }

        const translateBtn = document.getElementById('translateBtn');
        const translateBtnText = document.getElementById('translateBtnText');
        const translateSpinner = document.getElementById('translateSpinner');
        
        // Disable button and show spinner
        translateBtn.disabled = true;
        translateBtnText.textContent = 'Translating...';
        translateSpinner.classList.remove('hidden');

        try {
            let result;
            
            if (state.currentMode === 'single') {
                const text = document.getElementById('sourceText').value.trim();
                if (!text) {
                    showNotification('Please enter text to translate', 'warning');
                    return;
                }
                
                result = await apiCall('/translate/', 'POST', {
                    text: text,
                    target_language: targetLang,
                    is_json: false
                });
                
                // Display translation
                const translatedDiv = document.getElementById('translatedText');
                translatedDiv.innerHTML = `<p class="text-gray-900 dark:text-white">${result.translation}</p>`;
                
                // Enable copy and download buttons
                document.getElementById('copyTranslation').disabled = false;
                document.getElementById('downloadBtn').disabled = false;
                
                // Add to history
                addToHistory(text, result.translation, targetLang);
                
            } else if (state.currentMode === 'batch') {
                const texts = document.getElementById('batchSourceText').value
                    .split('\n')
                    .map(t => t.trim())
                    .filter(t => t.length > 0);
                
                if (texts.length === 0) {
                    showNotification('Please enter texts to translate', 'warning');
                    return;
                }
                
                result = await apiCall('/translate/batch/', 'POST', {
                    texts: texts,
                    target_language: targetLang,
                    is_json: false
                });
                
                // Display batch results
                displayBatchResults(result.translations);
                
            } else if (state.currentMode === 'json') {
                const jsonText = document.getElementById('jsonSourceText').value.trim();
                if (!jsonText) {
                    showNotification('Please enter JSON to translate', 'warning');
                    return;
                }
                
                // Validate JSON
                try {
                    JSON.parse(jsonText);
                } catch {
                    showNotification('Invalid JSON format', 'error');
                    return;
                }
                
                result = await apiCall('/translate/', 'POST', {
                    text: jsonText,
                    target_language: targetLang,
                    is_json: true
                });
                
                // Display JSON translation
                const jsonDiv = document.getElementById('jsonTranslatedText');
                jsonDiv.innerHTML = `<pre class="text-gray-900 dark:text-white">${JSON.stringify(result.translation, null, 2)}</pre>`;
            }
            
            showNotification('Translation completed successfully', 'success');
            
        } catch (error) {
            showNotification(`Translation failed: ${error.message}`, 'error');
        } finally {
            translateBtn.disabled = false;
            translateBtnText.textContent = 'Translate';
            translateSpinner.classList.add('hidden');
        }
    }

    // Display batch results
    function displayBatchResults(translations) {
        const resultsDiv = document.getElementById('batchResults');
        resultsDiv.innerHTML = '';
        resultsDiv.classList.remove('hidden');
        
        translations.forEach((item, index) => {
            const resultItem = document.createElement('div');
            resultItem.className = 'bg-gray-50 dark:bg-gray-700 rounded-lg p-4';
            resultItem.innerHTML = `
                <div class="mb-2">
                    <span class="text-xs text-gray-500 dark:text-gray-400">Original ${index + 1}</span>
                    <p class="text-sm text-gray-700 dark:text-gray-300">${item.original}</p>
                </div>
                <div>
                    <span class="text-xs text-gray-500 dark:text-gray-400">Translation</span>
                    <p class="text-sm font-medium text-gray-900 dark:text-white">${item.translation}</p>
                </div>
            `;
            resultsDiv.appendChild(resultItem);
        });
    }

    // Add to translation history
    function addToHistory(original, translation, language) {
        const historyItem = {
            original,
            translation,
            language,
            timestamp: new Date().toISOString()
        };
        
        state.translationHistory.unshift(historyItem);
        
        // Keep only last 20 items
        if (state.translationHistory.length > 20) {
            state.translationHistory = state.translationHistory.slice(0, 20);
        }
        
        // Save to localStorage
        localStorage.setItem('translationHistory', JSON.stringify(state.translationHistory));
        
        // Update display
        updateHistoryDisplay();
    }

    // Update history display
    function updateHistoryDisplay() {
        const historyDiv = document.getElementById('translationHistory');
        
        if (state.translationHistory.length === 0) {
            historyDiv.innerHTML = '<p class="text-gray-500 dark:text-gray-400 text-center py-4">No translation history yet</p>';
            return;
        }
        
        historyDiv.innerHTML = '';
        state.translationHistory.slice(0, 5).forEach(item => {
            const historyItem = document.createElement('div');
            historyItem.className = 'bg-gray-50 dark:bg-gray-700 rounded p-3 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors';
            historyItem.innerHTML = `
                <div class="text-xs text-gray-500 dark:text-gray-400 mb-1">
                    ${new Date(item.timestamp).toLocaleString()} → ${item.language}
                </div>
                <div class="text-sm text-gray-700 dark:text-gray-300 truncate">${item.original}</div>
                <div class="text-sm font-medium text-gray-900 dark:text-white truncate">${item.translation}</div>
            `;
            
            historyItem.addEventListener('click', () => {
                document.getElementById('sourceText').value = item.original;
                document.getElementById('targetLang').value = item.language;
                updateCharCount();
            });
            
            historyDiv.appendChild(historyItem);
        });
    }

    // Load history from storage
    function loadHistoryFromStorage() {
        const saved = localStorage.getItem('translationHistory');
        if (saved) {
            try {
                state.translationHistory = JSON.parse(saved);
                updateHistoryDisplay();
            } catch (error) {
                console.error('Failed to load history:', error);
            }
        }
    }

    // Update glossary display
    function updateGlossaryDisplay() {
        const glossaryDiv = document.getElementById('glossaryList');
        const terms = Object.entries(state.glossaryTerms);
        
        if (terms.length === 0) {
            glossaryDiv.innerHTML = '<p class="text-gray-500 dark:text-gray-400 text-center py-4">No glossary terms</p>';
            return;
        }
        
        glossaryDiv.innerHTML = '';
        terms.forEach(([term, translation]) => {
            const termDiv = document.createElement('div');
            termDiv.className = 'flex justify-between items-center bg-gray-50 dark:bg-gray-700 rounded p-2';
            termDiv.innerHTML = `
                <div>
                    <span class="text-sm font-medium text-gray-900 dark:text-white">${term}</span>
                    <span class="text-sm text-gray-500 dark:text-gray-400 mx-2">→</span>
                    <span class="text-sm text-gray-700 dark:text-gray-300">${translation}</span>
                </div>
                <button class="delete-glossary-term text-red-500 hover:text-red-700" data-term="${term}">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </button>
            `;
            glossaryDiv.appendChild(termDiv);
        });
        
        // Add delete handlers
        document.querySelectorAll('.delete-glossary-term').forEach(btn => {
            btn.addEventListener('click', (e) => deleteGlossaryTerm(e.target.closest('button').dataset.term));
        });
    }

    // Utility functions
    function swapLanguages() {
        const sourceLang = document.getElementById('sourceLang');
        const targetLang = document.getElementById('targetLang');
        
        if (sourceLang.value !== 'auto') {
            const temp = sourceLang.value;
            sourceLang.value = targetLang.value;
            targetLang.value = temp;
        }
    }

    function updateCharCount() {
        const text = document.getElementById('sourceText').value;
        document.getElementById('charCount').textContent = `${text.length} / 5000`;
    }

    function clearSource() {
        document.getElementById('sourceText').value = '';
        updateCharCount();
    }

    function copyTranslation() {
        const translatedDiv = document.getElementById('translatedText');
        const text = translatedDiv.textContent;
        
        navigator.clipboard.writeText(text).then(() => {
            showNotification('Translation copied to clipboard', 'success');
        });
    }

    async function pasteFromClipboard() {
        try {
            const text = await navigator.clipboard.readText();
            document.getElementById('sourceText').value = text;
            updateCharCount();
        } catch (error) {
            showNotification('Failed to paste from clipboard', 'error');
        }
    }

    function downloadTranslation() {
        const translatedDiv = document.getElementById('translatedText');
        const text = translatedDiv.textContent;
        
        const blob = new Blob([text], { type: 'text/plain' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `translation_${Date.now()}.txt`;
        a.click();
        window.URL.revokeObjectURL(url);
    }

    async function handleFileUpload(e) {
        const file = e.target.files[0];
        if (!file) return;
        
        const reader = new FileReader();
        reader.onload = (event) => {
            const content = event.target.result;
            
            if (file.name.endsWith('.json')) {
                document.getElementById('jsonSourceText').value = content;
                switchMode('json');
            } else {
                document.getElementById('sourceText').value = content;
                updateCharCount();
            }
        };
        reader.readAsText(file);
    }

    // Settings modal functions
    function openSettings() {
        document.getElementById('settingsModal').classList.remove('hidden');
    }

    function closeSettings() {
        document.getElementById('settingsModal').classList.add('hidden');
    }

    async function saveSettings() {
        const params = {
            max_new_tokens: parseInt(document.getElementById('maxTokens').value),
            temperature: parseFloat(document.getElementById('temperature').value),
            top_p: parseFloat(document.getElementById('topP').value),
            top_k: parseInt(document.getElementById('topK').value),
            do_sample: true
        };
        
        const memory = {
            gpu_memory: document.getElementById('gpuMemoryConfig').value,
            cpu_memory: document.getElementById('cpuMemoryConfig').value
        };
        
        try {
            // Update generation parameters
            await apiCall('/config/generation/', 'PATCH', params);
            
            // Update memory configuration
            await apiCall('/config/memory/', 'PATCH', memory);
            
            showNotification('Settings saved successfully', 'success');
            closeSettings();
            
            // Reload configuration
            await loadConfiguration();
        } catch (error) {
            showNotification(`Failed to save settings: ${error.message}`, 'error');
        }
    }

    // Glossary modal functions
    function openGlossaryModal() {
        document.getElementById('glossaryModal').classList.remove('hidden');
    }

    function closeGlossaryModal() {
        document.getElementById('glossaryModal').classList.add('hidden');
        document.getElementById('glossaryTerm').value = '';
        document.getElementById('glossaryTranslation').value = '';
    }

    async function saveGlossaryTerm() {
        const term = document.getElementById('glossaryTerm').value.trim();
        const translation = document.getElementById('glossaryTranslation').value.trim();
        
        if (!term || !translation) {
            showNotification('Please fill in both fields', 'warning');
            return;
        }
        
        state.glossaryTerms[term] = translation;
        
        try {
            await apiCall('/config/glossary/', 'PATCH', { terms: state.glossaryTerms });
            showNotification('Glossary term added successfully', 'success');
            closeGlossaryModal();
            updateGlossaryDisplay();
        } catch (error) {
            showNotification(`Failed to save glossary: ${error.message}`, 'error');
        }
    }

    async function deleteGlossaryTerm(term) {
        delete state.glossaryTerms[term];
        
        try {
            if (Object.keys(state.glossaryTerms).length === 0) {
                await apiCall('/config/glossary/delete/', 'DELETE');
            } else {
                await apiCall('/config/glossary/', 'PATCH', { terms: state.glossaryTerms });
            }
            updateGlossaryDisplay();
            showNotification('Term deleted successfully', 'success');
        } catch (error) {
            showNotification(`Failed to delete term: ${error.message}`, 'error');
        }
    }

    // Model management functions
    async function reloadModel() {
        if (!confirm('This will reload the model. It may take a few minutes. Continue?')) {
            return;
        }
        
        showNotification('Reloading model...', 'info');
        
        try {
            await apiCall('/reload/', 'POST');
            showNotification('Model reloaded successfully', 'success');
            await checkServiceHealth();
        } catch (error) {
            showNotification(`Failed to reload model: ${error.message}`, 'error');
        }
    }

    async function freeMemory() {
        if (!confirm('This will unload the model and free GPU memory. Continue?')) {
            return;
        }
        
        try {
            const result = await apiCall('/free-memory/', 'POST');
            showNotification('Memory freed successfully', 'success');
            await checkServiceHealth();
            await updateMemoryStatus();
        } catch (error) {
            showNotification(`Failed to free memory: ${error.message}`, 'error');
        }
    }

    // Notification system
    function showNotification(message, type = 'info') {
        const toast = document.getElementById('notificationToast');
        const toastMessage = document.getElementById('toastMessage');
        const toastIcon = document.getElementById('toastIcon');
        
        // Set message
        toastMessage.textContent = message;
        
        // Set icon based on type
        const icons = {
            success: '<svg class="w-5 h-5 text-green-500" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path></svg>',
            error: '<svg class="w-5 h-5 text-red-500" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path></svg>',
            warning: '<svg class="w-5 h-5 text-yellow-500" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path></svg>',
            info: '<svg class="w-5 h-5 text-blue-500" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path></svg>'
        };
        
        toastIcon.innerHTML = icons[type] || icons.info;
        
        // Show toast
        toast.classList.remove('hidden', 'translate-y-full');
        toast.classList.add('translate-y-0');
        
        // Hide after 3 seconds
        setTimeout(() => {
            toast.classList.remove('translate-y-0');
            toast.classList.add('translate-y-full');
            setTimeout(() => {
                toast.classList.add('hidden');
            }, 300);
        }, 3000);
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();