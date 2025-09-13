class QuickAction {
  constructor(containerId, quickActions) {
    this.container = document.getElementById(containerId);
    if (!this.container) {
      console.error(`Container with ID ${containerId} not found.`);
      return;
    }

    this.actions = quickActions || [];
    this.recentActions = JSON.parse(localStorage.getItem('recent_actions')) || [];
    this.init();
  }

  getTemplate() {
    const quickActionsHTML = this.actions.map(item => `
      <button class="selection-item w-full text-left p-4 rounded-lg border border-gray-200 dark:border-gray-600
        hover:border-${item.statusColor || 'blue'}-300 dark:hover:border-${item.statusColor || 'blue'}-500
        hover:bg-${item.statusColor || 'blue'}-50 dark:hover:bg-${item.statusColor || 'blue'}-900/20 transition-all"
        data-content="${item.action}">
        <div class="flex items-center space-x-3 rtl:space-x-reverse">
          <div class="w-10 h-10 ${item.iconBg} rounded-lg flex items-center justify-center">
            <i data-lucide="${item.icon}" class="w-5 h-5 ${item.iconColor}"></i>
          </div>
          <div>
            <h4 class="font-medium text-gray-800 dark:text-white">${item.title}</h4>
            <p class="text-sm text-gray-500 dark:text-gray-400">${item.summery || item.description}</p>
          </div>
        </div>
      </button>
    `).join('');

    return `
      <button id="open-modal-dash" class="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 w-full flex justify-center m-auto mt-[2.5rem] ${this.isPanelOpen() ? 'hidden' : ''}">
        <i data-lucide="arrow-big-${document.dir === 'rtl' ? 'left' : 'right'}-dash" class="w-5 h-5"></i>
      </button>

      <div class="quick-actions-section mb-6 ${this.isPanelOpen() ? '' : 'hidden'}">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-medium text-gray-800 dark:text-white">Quick Actions</h3>
          <button id="close-quick-actions" class="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200">
            <i data-lucide="arrow-big-${document.dir === 'rtl' ? 'right' : 'left'}-dash" class="w-5 h-5 "></i>
          </button>
        </div>
        <div class="space-y-3">${quickActionsHTML}</div>
      </div>

      <div class="mb-6 recent-log-section ${this.isPanelOpen() ? '' : 'hidden'}">
        <div class="flex items-center justify-between mb-4">
          <button id="download-actions" class="px-3 py-1 bg-blue-600 text-white rounded-lg hover:bg-blue-700 w-full h-10 text-sm">Download Log</button>
        </div>
        <div id="recent-actions-log" class="space-y-2"></div>
      </div>
    `;
  }

  isPanelOpen() {
    return localStorage.getItem('quick_actions_panel_state') !== 'closed';
  }

  setPanelState(open) {
    localStorage.setItem('quick_actions_panel_state', open ? 'open' : 'closed');
  }

  logAction(action, summery) {
    const timestamp = new Date().toISOString();
    this.recentActions.push({ action, summery, timestamp });
    localStorage.setItem('recent_actions', JSON.stringify(this.recentActions));
    this.updateRecentActionsLog();
  }

  clearRecentActions() {
    this.recentActions = [];
    localStorage.setItem('recent_actions', JSON.stringify(this.recentActions));
    this.updateRecentActionsLog();
    this.showToast('Recent actions cleared', 'info');
  }

  updateRecentActionsLog() {
    const logContainer = this.container.querySelector('#recent-actions-log');
    logContainer.innerHTML = this.recentActions.length > 0
      ? this.recentActions.map(action => `
        <div class="p-3 rounded-lg bg-gray-50 dark:bg-gray-700">
          <p class="text-sm text-gray-800 dark:text-white">Action: ${action.action}</p>
          <p class="text-sm text-gray-800 dark:text-white">Summary: ${action.summery}</p>
          <p class="text-xs text-gray-500 dark:text-gray-400">Timestamp: ${action.timestamp}</p>
        </div>
      `).join('')
      : '<p class="text-sm text-gray-500">No recent actions.</p>';
  }

  downloadRecentActions() {
    const data = JSON.stringify(this.recentActions, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'recent_actions.json';
    a.click();
    URL.revokeObjectURL(url);
  }

  showToast(message, type) {
    const toast = document.createElement('div');
    toast.className = `fixed bottom-4 ${document.dir === 'rtl' ? 'left-4' : 'right-4'} p-4 rounded-lg text-white ${type === 'info' ? 'bg-blue-600' : 'bg-gray-600'}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }

  bindEvents() {
    const selectionItems = this.container.querySelectorAll('.selection-item');
    selectionItems.forEach((item) => {
      item.addEventListener('mouseenter', () => {
        item.style.transform = 'translateY(-2px)';
        item.style.transition = 'transform 0.2s ease';
      });
      item.addEventListener('mouseleave', () => {
        item.style.transform = 'translateY(0)';
      });
      item.addEventListener('click', () => {
        const contentType = item.dataset.content;
        const actionData = this.actions.find(action => action.action === contentType);
        if (actionData) {
          try {
            if (typeof actionData.function === 'string') {
              eval(actionData.function);
            } else if (typeof actionData.function === 'function') {
              actionData.function(this);
            }
            this.logAction(actionData.action, actionData.summery);
          } catch (error) {
            console.error(`Error executing action ${actionData.action}:`, error);
            this.showToast(`Error executing ${actionData.action}`, 'error');
          }
        }
        item.style.transform = 'scale(0.98)';
        setTimeout(() => item.style.transform = 'scale(1)', 150);
      });
    });

    const closeButton = this.container.querySelector('#close-quick-actions');
    if (closeButton) {
      closeButton.addEventListener('click', () => {
        this.container.classList.add('w-[3rem]');
        this.container.classList.remove('p-6');
        this.setPanelState(false);
        this.container.querySelector('#open-modal-dash').classList.remove('hidden');
        this.container.querySelector('.quick-actions-section').classList.add('hidden');
        this.container.querySelector('.recent-log-section').classList.add('hidden');
      });
    }

    const openButton = this.container.querySelector('#open-modal-dash');
    if (openButton) {
      openButton.addEventListener('click', () => {
        this.container.classList.remove('w-[3rem]');
        this.container.classList.add('p-6');
        this.setPanelState(true);
        this.container.querySelector('#open-modal-dash').classList.add('hidden');
        this.container.querySelector('.quick-actions-section').classList.remove('hidden');
        this.container.querySelector('.recent-log-section').classList.remove('hidden');
      });
    }

    const downloadButton = this.container.querySelector('#download-actions');
    if (downloadButton) {
      downloadButton.addEventListener('click', () => {
        this.downloadRecentActions();
      });
    }
  }

  init() {
    // Set initial panel state if not set
    if (localStorage.getItem('quick_actions_panel_state') === null) {
      this.setPanelState(true);
    }
    
    this.container.innerHTML = this.getTemplate();
    this.bindEvents();
    this.updateRecentActionsLog();
    lucide.createIcons();
    
    // Apply initial state
    if (this.isPanelOpen()) {
      this.container.classList.remove('w-[3rem]');
      this.container.classList.add('p-6');
    } else {
      this.container.classList.add('w-[3rem]');
      this.container.classList.remove('p-6');
    }
  }
}