class NavigationMain {
  constructor(containerId, navItems, contentSections) {
    this.container = document.getElementById(containerId);
    console.log('here');
    
    if (!this.container) {
      console.error(`Container with ID ${containerId} not found.`);
      return;
    }
    this.navItems = navItems || [];
    this.contentSections = contentSections || {};
    this.init();
  }

  getTemplate() {
    const navItemsHTML = this.navItems.map(item => `
      <li>
        <button class="nav-item w-full text-left px-4 py-3 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors flex items-center space-x-3 rtl:space-x-reverse
          ${item.active ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300' : 'text-gray-700 dark:text-gray-300'}"
          data-section="${item.section}">
          <i data-lucide="${item.icon}" class="w-5 h-5"></i>
          <span>${item.label}</span>
        </button>
      </li>
    `).join('');

    return `
      <div class="p-6 border-b border-gray-200 dark:border-gray-700">
        <h1 class="text-xl font-bold text-gray-800 dark:text-white">Workflow UI</h1>
      </div>
      <div class="p-4">
        <ul class="space-y-2">
          ${navItemsHTML}
        </ul>
      </div>
    `;
  }

  showToast(message, type) {
    const toast = document.createElement('div');
    toast.className = `fixed bottom-4 ${document.dir === 'rtl' ? 'left-4' : 'right-4'} p-4 rounded-lg text-white ${type === 'info' ? 'bg-blue-600' : 'bg-gray-600'}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
  }

  loadWorkflowsTable() {
    const workflowsTable = document.getElementById('workflows-table');
    if (workflowsTable) {
      workflowsTable.innerHTML = `
        <table class="w-full text-left border border-gray-200 dark:border-gray-600">
          <thead>
            <tr class="bg-gray-50 dark:bg-gray-700">
              <th class="p-2">Workflow</th>
              <th class="p-2">Status</th>
              <th class="p-2">Last Modified</th>
            </tr>
          </thead>
          <tbody>
            <tr class="hover:bg-gray-100 dark:hover:bg-gray-600">
              <td class="p-2">Customer Onboarding</td>
              <td class="p-2">Active</td>
              <td class="p-2">2 hours ago</td>
            </tr>
            <tr class="hover:bg-gray-100 dark:hover:bg-gray-600">
              <td class="p-2">Data Processing</td>
              <td class="p-2">Paused</td>
              <td class="p-2">1 day ago</td>
            </tr>
          </tbody>
        </table>
      `;
      this.showToast('Workflows table loaded', 'info');
    }
  }

  switchToSection(section) {
    console.log('switchToSection firing')
    const navItems = this.container.querySelectorAll('.nav-item');
    const pageTitle = document.getElementById('page-title');
    const dynamicContent = document.getElementById('dynamic-content');

    navItems.forEach(nav => {
      nav.classList.remove('bg-blue-50', 'dark:bg-blue-900/30', 'text-blue-700', 'dark:text-blue-300');
      nav.classList.add('text-gray-700', 'dark:text-gray-300');
      if (nav.dataset.section === section) {
        nav.classList.add('bg-blue-50', 'dark:bg-blue-900/30', 'text-blue-700', 'dark:text-blue-300');
        nav.classList.remove('text-gray-700', 'dark:text-gray-300');
      }
    });

    if (pageTitle) {
      pageTitle.textContent = section.charAt(0).toUpperCase() + section.slice(1);
    }

    Object.values(this.contentSections).forEach(content => {
      if (content) content.classList.add('hidden');
    });
    if (dynamicContent) dynamicContent.classList.add('hidden');

    if (this.contentSections[section]) {
      this.contentSections[section].classList.remove('hidden');
      this.showToast(`Navigated to ${section}`, 'info');
      if (section === 'workflows') {
        this.loadWorkflowsTable();
      }
    }
  }

  bindEvents() {
    const navItems = this.container.querySelectorAll('.nav-item');

    navItems.forEach(item => {
      item.addEventListener('click', () => {
        const section = item.dataset.section;
        this.switchToSection(section);
        lucide.createIcons();
      });
    });

    document.addEventListener('keydown', (e) => {
      if (e.ctrlKey && e.shiftKey) {
        const keyMap = { '!': '1', '@': '2', '#': '3', '$': '4', '%': '5', '^': '6', '&': '7', '*': '8', '(': '9', ')': '0' };
        let keyValue = keyMap[e.key] || e.key;
        const binding = this.navItems.find(b => b.key === keyValue);
        if (binding && this.contentSections[binding.section]) {
          e.preventDefault();
          this.switchToSection(binding.section);
          lucide.createIcons();
        }
      }
    });
  }

  init() {
    this.container.innerHTML = this.getTemplate();
    this.bindEvents();
    lucide.createIcons();
  }
}
