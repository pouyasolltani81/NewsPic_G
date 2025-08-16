document.addEventListener('DOMContentLoaded', function() {
    const targetLang = '{{ current_lang }}';
    const overlay = document.getElementById('translation-overlay');
    const progressBar = document.getElementById('progress-bar');
    const progressCurrent = document.getElementById('progress-current');
    const progressTotal = document.getElementById('progress-total');
    
    const items = [];
    document.querySelectorAll('.news-item').forEach(item => {
        const titleElement = item.querySelector('.news-title');
        const summaryElement = item.querySelector('.summary-en-text');
        
        const originalTitle = titleElement?.dataset?.originalTitle;
        const originalSummary = summaryElement?.dataset?.originalSummary;

        console.log(`Checking item ID=${item.dataset.itemId}, title=`, originalTitle, ', summary=', originalSummary);

        if (originalTitle || originalSummary) {
            items.push({
                id: item.dataset.itemId,
                title: originalTitle || '',
                summary: originalSummary || '',
                titleElement,
                summaryElement
            });
        } else {
            console.warn(`Item ID=${item.dataset.itemId} skipped — no original text found`);
        }
    });

    console.log(`Collected ${items.length} items for translation`);
    progressTotal.textContent = items.length;

    async function translateText(text) {
        if (!text) return '';
        try {
            const response = await fetch('http://79.175.177.113:19800/Translate/translate/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': '{{ csrf_token }}'
                },
                body: JSON.stringify({
                    text,
                    target_lang: targetLang,
                    source_lang: ''
                })
            });

            if (!response.ok) {
                console.error(`[ERR] HTTP ${response.status} for "${text}"`);
                return text;
            }

            const data = await response.json();
            if (data.return && data.data?.translated_text) return data.data.translated_text;
            if (data.return && data.translated_text) return data.translated_text;

            console.warn(`[WARN] No translated_text in response for "${text}"`);
            return text;

        } catch (error) {
            console.error(`[ERR] Translation error:`, error);
            return text;
        }
    }

    async function translateSingle(item) {
        console.log(`[REQ] Translating ID=${item.id} to ${targetLang}`);
        const [translatedTitle, translatedSummary] = await Promise.all([
            translateText(item.title),
            translateText(item.summary)
        ]);
        return { id: item.id, translatedTitle, translatedSummary };
    }

    async function translateBatch(batch) {
        console.log(`Processing batch of ${batch.length} items:`, batch.map(i => i.id));
        return Promise.all(batch.map(translateSingle));
    }

    async function translateAll() {
        const batchSize = 1;
        let translated = 0;

        for (let i = 0; i < items.length; i += batchSize) {
            const batch = items.slice(i, i + batchSize);
            batch.forEach(item => item.titleElement?.classList.add('translating'));

            const translations = await translateBatch(batch);
            console.log(`[INFO] Batch translations:`, translations);

            translations.forEach(trans => {
                const item = items.find(it => it.id === trans.id);
                if (item) {
                    if (item.titleElement && trans.translatedTitle) {
                        item.titleElement.textContent = trans.translatedTitle;
                    }
                    if (item.summaryElement && trans.translatedSummary) {
                        item.summaryElement.textContent = trans.translatedSummary;
                    }
                }
                item?.titleElement?.classList.remove('translating');
                translated++;
                progressCurrent.textContent = translated;
                progressBar.style.width = (translated / items.length * 100) + '%';
            });

            if (i + batchSize < items.length) {
                await new Promise(resolve => setTimeout(resolve, 200));
            }
        }
        setTimeout(() => { overlay.style.display = 'none'; }, 500);
    }

    if (items.length > 0) {
        translateAll();
    } else {
        console.warn("No items to translate — hiding overlay");
        overlay.style.display = 'none';
    }
});