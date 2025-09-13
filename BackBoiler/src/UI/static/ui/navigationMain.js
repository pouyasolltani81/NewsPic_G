class NavigationMain {
  constructor(containerId, navItems, contentSections) {
    this.container = document.getElementById(containerId);
    
    if (!this.container) {
      console.error(`Container with ID ${containerId} not found.`);
      return;
    }
    this.navItems = navItems || [];
    this.contentSections = contentSections || {};

    // Default auth (guest); will be updated by probeAuth()
    this.auth = {
      isAuthenticated: false,
      isStaff: false,
      isSuperuser: false,
      isAdmin: false,
      isUser: false,
      allowAny: true
    };

    this.csrfToken = this.getCookie('csrftoken');
    this.init();
  }

  getCookie(name) {
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

  hasAccess(access) {
    const rule = access || 'allowAny';
    if (rule === 'allowAny') return true;
    if (rule === 'user') return !!this.auth.isAuthenticated;
    if (rule === 'staff') return !!this.auth.isStaff;
    if (rule === 'admin') return !!this.auth.isAdmin;
    if (rule === 'superuser') return !!this.auth.isSuperuser;
    return false;
  }

  getTemplate() {
    const navItemsHTML = this.navItems.map(item => {
      // Backward compat: requiresAuth true implies access 'user'
      const access = item.access || (item.requiresAuth ? 'user' : 'allowAny');
      const isLocked = !this.hasAccess(access);
      const statusIcon = access !== 'allowAny'
        ? (isLocked
            ? '<i data-lucide="lock" class="w-4 h-4 text-gray-500 dark:text-gray-400"></i>'
            : '<i data-lucide="lock-open" class="w-4 h-4 text-green-500 dark:text-green-400"></i>')
        : '';
      
      return `
        <li>
          <button class="nav-item w-full text-left px-4 py-3 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors flex items-center justify-between 
            ${item.active && !isLocked ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300' : 'text-gray-700 dark:text-gray-300'}
            ${isLocked ? 'cursor-pointer opacity-75' : ''}"
            data-section="${item.section}"
            data-access="${access}"
            data-locked="${isLocked}">
            <div class="flex items-center space-x-3 rtl:space-x-reverse">
              <i data-lucide="${item.icon}" class="w-5 h-5"></i>
              <span>${item.label}</span>
            </div>
            ${statusIcon}
          </button>
        </li>
      `;
    }).join('');

    return `
      <div class="p-6 border-b border-gray-200 dark:border-gray-700">
        <h1 class="text-xl text-center font-bold text-gray-800 dark:text-white">UI</h1>
      </div>
      <div class="p-4">
        <ul class="space-y-2">
          ${navItemsHTML}
        </ul>
      </div>
    `;
  }

  async probeAuth() {
    try {
      const res = await fetch('/User/CheckAuthStatus/', { credentials: 'same-origin' });
      const data = await res.json();
      if (data && data.return) {
        const u = data.user || {};
        this.auth = {
          isAuthenticated: !!data.authenticated,
          isStaff: !!u.is_staff,
          isSuperuser: !!u.is_superuser,
          isAdmin: !!u.is_superuser,
          isUser: !!data.authenticated,
          allowAny: true,
        };
        this.redraw();
      }
    } catch (e) {
      // stay guest on failure
    }
  }

  redraw() {
    this.container.innerHTML = this.getTemplate();
    this.bindEvents();
    if (window.lucide && typeof window.lucide.createIcons === 'function') window.lucide.createIcons();
  }

  createLoginModal() {
    if (document.getElementById('login-modal')) return;

    const t = (window.loginTranslations || {});
    const TT = (key, fallback) => (t[key] ? t[key] : fallback);

    const modal = document.createElement('div');
    modal.id = 'login-modal';
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 hidden';
    modal.innerHTML = `
      <div class="bg-white dark:bg-gray-800 rounded-lg p-6 w-full max-w-md mx-4">
        <div class="flex justify-between items-center mb-4">
          <h2 class="text-xl font-bold text-gray-800 dark:text-white">${TT('account','Account')}</h2>
          <button id="close-login-modal" class="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200">
            <i data-lucide="x" class="w-5 h-5"></i>
          </button>
        </div>

        <div class="flex mb-4 border-b border-gray-200 dark:border-gray-700">
          <button id="tab-login" class="flex-1 py-2 text-sm font-medium border-b-2 border-blue-600 text-blue-600">${TT('login','Login')}</button>
          <button id="tab-register" class="flex-1 py-2 text-sm font-medium border-b-2 border-transparent text-gray-500">${TT('register','Register')}</button>
        </div>
        
        <div id="login-pane">
          <form id="login-form" class="space-y-4">
            <div id="login-error" class="hidden bg-red-100 border border-red-400 text-red-700 px-4 py-2 rounded text-sm"></div>
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">${TT('email_or_phone','Email or Phone')}</label>
              <input type="text" name="email_or_phone" required class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white" placeholder="${TT('email_or_phone','Email or Phone')}">
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">${TT('password','Password')}</label>
              <input type="password" name="password" required class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white" placeholder="${TT('password','Password')}">
            </div>
            <button type="submit" id="login-submit" class="w-full bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors">${TT('login','Login')}</button>
          </form>
        </div>

        <div id="register-pane" class="hidden">
          <form id="register-form" class="space-y-4">
            <div id="register-error" class="hidden bg-red-100 border border-red-400 text-red-700 px-4 py-2 rounded text-sm"></div>
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">${TT('email','Email')} (${TT('optional','Optional')})</label>
              <input type="email" name="email" class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white" placeholder="${TT('email','Email')}">
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">${TT('phone_number','Phone Number')} (${TT('optional','Optional')})</label>
              <input type="text" name="phone_number" class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white" placeholder="${TT('phone_number','Phone Number')}">
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">${TT('password','Password')}</label>
              <input type="password" name="password" required class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white" placeholder="${TT('password','Password')}">
            </div>
            <div class="grid grid-cols-2 gap-2">
              <div>
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">${TT('first_name','First Name')}</label>
                <input type="text" name="first_name" class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white">
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">${TT('last_name','Last Name')}</label>
                <input type="text" name="last_name" class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:text-white">
              </div>
            </div>
            <button type="submit" id="register-submit" class="w-full bg-green-600 text-white py-2 px-4 rounded-lg hover:bg-green-700 transition-colors">${TT('create_account','Create Account')}</button>
          </form>
        </div>
      </div>
    `;
    
    document.body.appendChild(modal);
    
    // Bind events
    document.getElementById('close-login-modal').addEventListener('click', () => {
      this.hideLoginModal();
    });
    
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        this.hideLoginModal();
      }
    });

    // Tabs
    const tabLogin = document.getElementById('tab-login');
    const tabRegister = document.getElementById('tab-register');
    const loginPane = document.getElementById('login-pane');
    const registerPane = document.getElementById('register-pane');

    tabLogin.addEventListener('click', () => {
      tabLogin.classList.add('border-blue-600','text-blue-600');
      tabRegister.classList.remove('border-blue-600','text-blue-600');
      tabRegister.classList.add('text-gray-500');
      loginPane.classList.remove('hidden');
      registerPane.classList.add('hidden');
    });
    tabRegister.addEventListener('click', () => {
      tabRegister.classList.add('border-blue-600','text-blue-600');
      tabLogin.classList.remove('border-blue-600','text-blue-600');
      tabLogin.classList.add('text-gray-500');
      registerPane.classList.remove('hidden');
      loginPane.classList.add('hidden');
    });
    
    // Bind form submissions
    document.getElementById('login-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const form = e.target;
      const emailOrPhone = form.email_or_phone.value.trim();
      const password = form.password.value;
      const errorDiv = document.getElementById('login-error');
      errorDiv.classList.add('hidden');
      try {
        const payload = emailOrPhone.includes('@') ? { email: emailOrPhone, password } : { phone_number: emailOrPhone, password };
        const res = await fetch('/User/LoginUser/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
          body: JSON.stringify(payload),
          credentials: 'same-origin'
        });
        const data = await res.json();
        if (data.return) {
          this.showToast((window.loginTranslations?.login_success)||'Login successful!', 'success');
          setTimeout(() => window.location.reload(), 800);
        } else {
          errorDiv.textContent = data.error || ((window.loginTranslations?.login)||'Login') + ' failed';
          errorDiv.classList.remove('hidden');
        }
      } catch (err) {
        errorDiv.textContent = err.message || (((window.loginTranslations?.login)||'Login') + ' failed');
        errorDiv.classList.remove('hidden');
      }
    });

    document.getElementById('register-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const form = e.target;
      const payload = {
        email: form.email.value || undefined,
        phone_number: form.phone_number.value || undefined,
        password: form.password.value,
        first_name: form.first_name.value || '',
        last_name: form.last_name.value || ''
      };
      const errorDiv = document.getElementById('register-error');
      errorDiv.classList.add('hidden');
      try {
        const res = await fetch('/User/RegisterUser/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.csrfToken },
          body: JSON.stringify(payload),
          credentials: 'same-origin'
        });
        const data = await res.json();
        if (data.return) {
          this.showToast((window.loginTranslations?.register_success)||'Account created successfully', 'success');
          setTimeout(() => window.location.reload(), 800);
        } else {
          errorDiv.textContent = data.error || ((window.loginTranslations?.register)||'Register') + ' failed';
          errorDiv.classList.remove('hidden');
        }
      } catch (err) {
        errorDiv.textContent = err.message || (((window.loginTranslations?.register)||'Register') + ' failed');
        errorDiv.classList.remove('hidden');
      }
    });
    
    if (window.lucide && typeof window.lucide.createIcons === 'function') window.lucide.createIcons();
  }

  async handleLogin() {
    this.showLoginModal();
  }

  showLoginModal() {
    const modal = document.getElementById('login-modal');
    if (modal) {
      modal.classList.remove('hidden');
      setTimeout(() => {
        const input = document.querySelector('#login-form input[name="email_or_phone"]');
        if (input) input.focus();
      }, 100);
    }
  }

  hideLoginModal() {
    const modal = document.getElementById('login-modal');
    if (modal) {
      modal.classList.add('hidden');
    }
  }

  showToast(message, type) {
    const toast = document.createElement('div');
    toast.className = `fixed bottom-4 ${document.dir === 'rtl' ? 'left-4' : 'right-4'} p-4 rounded-lg text-white ${type === 'info' ? 'bg-blue-600' : 'bg-green-600'} z-50`;
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
      if (nav.dataset.section === section && nav.dataset.locked !== 'true') {
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
        const access = item.dataset.access || 'allowAny';
        const isLocked = !this.hasAccess(access);
        
        if (isLocked) {
          this.showLoginModal();
          return;
        }
        
        this.switchToSection(section);
        if (window.lucide && typeof window.lucide.createIcons === 'function') window.lucide.createIcons();
      });
    });

    document.addEventListener('keydown', (e) => {
      if (e.ctrlKey && e.shiftKey) {
        const keyMap = { '!': '1', '@': '2', '#': '3', '$': '4', '%': '5', '^': '6', '&': '7', '*': '8', '(': '9', ')': '0' };
        let keyValue = keyMap[e.key] || e.key;
        const binding = this.navItems.find(b => b.key === keyValue);
        if (binding && this.contentSections[binding.section]) {
          e.preventDefault();
          
          const navItem = this.container.querySelector(`[data-section="${binding.section}"]`);
          if (navItem) {
            const access = navItem.dataset.access || 'allowAny';
            const isLocked = !this.hasAccess(access);
            if (isLocked) {
              this.showLoginModal();
              return;
            }
          }
          
          this.switchToSection(binding.section);
          if (window.lucide && typeof window.lucide.createIcons === 'function') window.lucide.createIcons();
        }
      }
    });
  }

  init() {
    // Initial render (guest until proven otherwise)
    this.container.innerHTML = this.getTemplate();
    this.createLoginModal();
    this.bindEvents();
    if (window.lucide && typeof window.lucide.createIcons === 'function') window.lucide.createIcons();
    // Auto-detect auth
    this.probeAuth();
  }
}