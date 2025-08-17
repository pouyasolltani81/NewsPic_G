document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const sourceText = document.getElementById('sourceText');
    const translatedTextDiv = document.getElementById('translatedText');
    const sourceLang = document.getElementById('sourceLang');
    const targetLang = document.getElementById('targetLang');
    const translateBtn = document.getElementById('translateBtn');
    const translateBtnText = document.getElementById('translateBtnText');
    const translateSpinner = document.getElementById('translateSpinner');
    const charCount = document.getElementById('charCount');
    const swapLangs = document.getElementById('swapLangs');
    const clearSource = document.getElementById('clearSource');
    const copyTranslation = document.getElementById('copyTranslation');
    const pasteBtn = document.getElementById('pasteBtn');
    const uploadBtn = document.getElementById('uploadBtn');
    const fileInput = document.getElementById('fileInput');
    const downloadBtn = document.getElementById('downloadBtn');
    const speakBtn = document.getElementById('speakBtn');
    const historyDiv = document.getElementById('translationHistory');

    let translationHistory = [];

    // Character counter
    sourceText.addEventListener('input', () => {
        const count = sourceText.value.length;
        charCount.textContent = `${count} / 5000`;
        translateBtn.disabled = count === 0;
    });

    // Clear source text
    clearSource.addEventListener('click', () => {
        sourceText.value = '';
        charCount.textContent = '0 / 5000';
        translateBtn.disabled = true;
    });

    // Swap languages
    swapLangs.addEventListener('click', () => {
        if (sourceLang.value !== '') {
            const temp = sourceLang.value;
            sourceLang.value = targetLang.value;
            targetLang.value = temp;
        }
    });

    // Paste text
    pasteBtn.addEventListener('click', async () => {
        try {
            const text = await navigator.clipboard.readText();
            sourceText.value = text.substring(0, 5000);
            sourceText.dispatchEvent(new Event('input'));
        } catch (err) {
            console.error('Failed to read clipboard:', err);
        }
    });

    // Upload file
    uploadBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                sourceText.value = e.target.result.substring(0, 5000);
                sourceText.dispatchEvent(new Event('input'));
            };
            reader.readAsText(file);
        }
    });

    // Copy translation
    copyTranslation.addEventListener('click', async () => {
        const text = translatedTextDiv.textContent;
        try {
            await navigator.clipboard.writeText(text);
            copyTranslation.textContent = 'Copied!';
            setTimeout(() => {
                copyTranslation.textContent = 'Copy';
            }, 2000);
        } catch (err) {
            console.error('Failed to copy:', err);
        }
    });

    // Download translation
    downloadBtn.addEventListener('click', () => {
        const text = translatedTextDiv.textContent;
                const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'translation.txt';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });

    // Speak translation
    speakBtn.addEventListener('click', () => {
        const text = translatedTextDiv.textContent;
        if ('speechSynthesis' in window) {
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = targetLang.value;
            speechSynthesis.speak(utterance);
        }
    });

    // Translate function
    async function translateText(text, target, source = '') {
        try {
            const response = await fetch('http://79.175.177.113:19800/Translate/translate/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({
                    text: text,
                    target_lang: target,
                    source_lang: source
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            if (data.return && data.data?.translated_text) return data.data.translated_text;
            if (data.return && data.translated_text) return data.translated_text;

            throw new Error('No translated text in response');

        } catch (error) {
            console.error('Translation error:', error);
            throw error;
        }
    }

    // Handle translation
    translateBtn.addEventListener('click', async () => {
        const text = sourceText.value.trim();
        if (!text) return;

        // Show loading state
        translateBtn.disabled = true;
        translateBtnText.textContent = 'Translating...';
        translateSpinner.classList.remove('hidden');
        translatedTextDiv.innerHTML = '<p class="text-gray-500 dark:text-gray-400 italic">Translating...</p>';

        try {
            const translatedText = await translateText(text, targetLang.value, sourceLang.value);
            
            // Display translation
            translatedTextDiv.textContent = translatedText;
            
            // Enable action buttons
            copyTranslation.disabled = false;
            downloadBtn.disabled = false;
            speakBtn.disabled = false;
            
            // Add to history
            addToHistory(text, translatedText, sourceLang.value || 'auto', targetLang.value);
            
        } catch (error) {
            translatedTextDiv.innerHTML = `<p class="text-red-500">Translation failed. Please try again.</p>`;
        } finally {
            // Reset button state
            translateBtn.disabled = false;
            translateBtnText.textContent = 'Translate';
            translateSpinner.classList.add('hidden');
        }
    });

    // Add to history
    function addToHistory(source, translation, sourceLang, targetLang) {
        const historyItem = {
            source,
            translation,
            sourceLang,
            targetLang,
            timestamp: new Date()
        };
        
        translationHistory.unshift(historyItem);
        if (translationHistory.length > 5) {
            translationHistory = translationHistory.slice(0, 5);
        }
        
        updateHistoryDisplay();
    }

    // Update history display
    function updateHistoryDisplay() {
        if (translationHistory.length === 0) {
            historyDiv.innerHTML = '<p class="text-gray-500 dark:text-gray-400 text-center py-4">No translation history yet</p>';
            return;
        }

        historyDiv.innerHTML = translationHistory.map((item, index) => `
            <div class="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors cursor-pointer" onclick="loadFromHistory(${index})">
                <div class="flex justify-between items-start mb-2">
                    <div class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                        <span class="font-medium">${getLanguageName(item.sourceLang)}</span>
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"></path>
                        </svg>
                        <span class="font-medium">${getLanguageName(item.targetLang)}</span>
                    </div>
                    <span class="text-xs text-gray-500">${formatTime(item.timestamp)}</span>
                </div>
                <p class="text-sm text-gray-700 dark:text-gray-300 truncate">${item.source}</p>
                <p class="text-sm text-gray-600 dark:text-gray-400 truncate mt-1">${item.translation}</p>
            </div>
        `).join('');
    }

    // Load from history
    window.loadFromHistory = function(index) {
        const item = translationHistory[index];
        sourceText.value = item.source;
        sourceLang.value = item.sourceLang;
        targetLang.value = item.targetLang;
        translatedTextDiv.textContent = item.translation;
        
        // Enable action buttons
        copyTranslation.disabled = false;
        downloadBtn.disabled = false;
        speakBtn.disabled = false;
        
        // Update character count
        sourceText.dispatchEvent(new Event('input'));
        
        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    // Helper function to get language name
    function getLanguageName(code) {
        const languages = {
            '': 'Auto',
            'en': 'English',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'it': 'Italian',
            'pt': 'Portuguese',
            'ru': 'Russian',
            'ja': 'Japanese',
            'ko': 'Korean',
            'zh': 'Chinese',
            'ar': 'Arabic',
            'hi': 'Hindi'
        };
        return languages[code] || code;
    }

    // Format time
    function formatTime(date) {
        const now = new Date();
        const diff = now - date;
        const minutes = Math.floor(diff / 60000);
        
        if (minutes < 1) return 'Just now';
        if (minutes < 60) return `${minutes}m ago`;
        
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return `${hours}h ago`;
        
        return date.toLocaleDateString();
    }

    // Get CSRF token
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

    // Enable translate on Enter key
    sourceText.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && e.ctrlKey && !translateBtn.disabled) {
            e.preventDefault();
            translateBtn.click();
        }
    });
});