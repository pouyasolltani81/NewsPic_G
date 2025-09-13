document.addEventListener('DOMContentLoaded', function() {
    // Theme Toggle
    const themeToggle = document.getElementById('theme-toggle-setting');
    const darkModeDiv = document.getElementById('theme-toggle');
    
    themeToggle.addEventListener('change', function() {
        if (this.checked) {
            darkModeDiv.classList.remove('hidden');
            
        } else {
            darkModeDiv.classList.add('hidden');
            
        }
        localStorage.setItem('darkMode', this.checked);
    });

    // Direction Toggle
    const directionToggle = document.getElementById('direction-toggle-setting');
    const directionDiv = document.getElementById('dir-toggle');
    
    directionToggle.addEventListener('change', function() {
        if (this.checked) {
            directionDiv.classList.remove('hidden');
            
        } else {
            directionDiv.classList.add('hidden');
            
        }
        localStorage.setItem('direction', this.checked ? 'rtl' : 'ltr');
    });

    // Profile Toggle
    const profileToggle = document.getElementById('profile-toggle-setting');
    const profileDiv = document.getElementById('user-menu-btn');
    
    profileToggle.addEventListener('change', function() {
        if (this.checked) {
            profileDiv.classList.remove('hidden');
        } else {
            profileDiv.classList.add('hidden');
        }
        localStorage.setItem('showProfile', this.checked);
    });

    // Notification Toggle
    const notificationToggle = document.getElementById('notification-toggle-setting');
    const notificationDiv = document.getElementById('notifications-btn');
    
    notificationToggle.addEventListener('change', function() {
        if (this.checked) {
            notificationDiv.classList.remove('hidden');
        } else {
            notificationDiv.classList.add('hidden');
        }
        localStorage.setItem('showNotifications', this.checked);
    });

    // Language Toggle
    const languageToggle = document.getElementById('language-toggle-setting');
    const languageDiv = document.getElementById('language-btn');
    
    languageToggle.addEventListener('change', function() {
        if (this.checked) {
            languageDiv.classList.remove('hidden');
        } else {
            languageDiv.classList.add('hidden');
        }
        localStorage.setItem('showLanguageSelector', this.checked);
    });

    // Load saved preferences
    if (localStorage.getItem('darkMode') === 'true') {
        themeToggle.checked = true;
        themeToggle.dispatchEvent(new Event('change'));
    }

    if (localStorage.getItem('direction') === 'rtl') {
        directionToggle.checked = true;
        directionToggle.dispatchEvent(new Event('change'));
    }

    if (localStorage.getItem('showProfile') === 'true') {
        profileToggle.checked = true;
        profileToggle.dispatchEvent(new Event('change'));
    }

    if (localStorage.getItem('showNotifications') === 'true') {
        notificationToggle.checked = true;
        notificationToggle.dispatchEvent(new Event('change'));
    }

    if (localStorage.getItem('showLanguageSelector') === 'true') {
        languageToggle.checked = true;
        languageToggle.dispatchEvent(new Event('change'));
    }
});