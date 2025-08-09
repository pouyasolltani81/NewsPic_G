
const quickActions = [

    {
        tabId: 'messages-content',
        action: 'create-dashboard',
        icon: 'plus',
        iconBg: 'bg-blue-100 dark:bg-blue-900/50',
        iconColor: 'text-blue-600 dark:text-blue-400',
        statusColor: 'blue',
        title: "{{ _('quick.dashboard.title') }}",
        description: "{{ _('quick.dashboard.description') }}",
        summery: "{{ _('quick.dashboard.summery') }}",
        function: () => console.log("Dashboard item created")
      },
    {
      tabId: 'dashboard-content',
      action: 'create-dashboard',
      icon: 'plus',
      iconBg: 'bg-blue-100 dark:bg-blue-900/50',
      iconColor: 'text-blue-600 dark:text-blue-400',
      statusColor: 'blue',
      title: "{{ _('quick.dashboard.title') }}",
      description: "{{ _('quick.dashboard.description') }}",
      summery: "{{ _('quick.dashboard.summery') }}",
      function: () => console.log("Dashboard item created")
    },
    {
      tabId: 'workflows-content',
      action: 'create-workflow',
      icon: 'plus',
      iconBg: 'bg-blue-100 dark:bg-blue-900/50',
      iconColor: 'text-blue-600 dark:text-blue-400',
      statusColor: 'blue',
      title: "{{ _('quick.workflow.title') }}",
      description: "{{ _('quick.workflow.description') }}",
      summery: "{{ _('quick.workflow.summery') }}",
      function: () => console.log("Create workflow executed")
    },
    {
      tabId: 'analytics-content',
      action: 'view-reports',
      icon: 'file-text',
      iconBg: 'bg-purple-100 dark:bg-purple-900/50',
      iconColor: 'text-purple-600 dark:text-purple-400',
      statusColor: 'purple',
      title: "{{ _('quick.analytics.title') }}",
      description: "{{ _('quick.analytics.description') }}",
      summery: "{{ _('quick.analytics.summery') }}",
      function: () => console.log("View Reports executed")
    },
    {
      tabId: 'inputs-content',
      action: 'import-data',
      icon: 'upload',
      iconBg: 'bg-green-100 dark:bg-green-900/50',
      iconColor: 'text-green-600 dark:text-green-400',
      statusColor: 'green',
      title: "{{ _('quick.inputs.title') }}",
      description: "{{ _('quick.inputs.description') }}",
      summery: "{{ _('quick.inputs.summery') }}",
      function: () => console.log("Import Data executed")
    },
    {
      tabId: 'settings-content',
      action: 'clear-actions',
      icon: 'trash-2',
      iconBg: 'bg-red-100 dark:bg-red-900/50',
      iconColor: 'text-red-600 dark:text-red-400',
      statusColor: 'red',
      title: "{{ _('quick.settings.title') }}",
      description: "{{ _('quick.settings.description') }}",
      summery: "{{ _('quick.settings.summery') }}",
      function: (component) => component.clearRecentActions()
    }
  ];
  

function getActiveTabId() {
    const tabIds = quickActions.map(q => q.tabId);
    for (const id of tabIds) {
        const tab = document.getElementById(id);
        if (tab && !tab.classList.contains('hidden') && window.getComputedStyle(tab).display !== 'none') {
            return id;
        }
    }
    return null;
}

function reInitQuickActions() {
    const activeTabId = getActiveTabId();
    const filteredActions = quickActions.filter(q => q.tabId === activeTabId);

    const container = document.getElementById('quickAction');
    if (!container) return;

    container.innerHTML = ""; 
    window.qa = new QuickAction('quickAction', filteredActions);

    console.log("✅ QuickAction reloaded for:", activeTabId);
}

function observeTabSwitches() {
    const uniqueTabIds = [...new Set(quickActions.map(q => q.tabId))];
    const observer = new MutationObserver(() => {
        reInitQuickActions();
    });

    for (const id of uniqueTabIds) {
        const el = document.getElementById(id);
        if (el) {
            observer.observe(el, {
                attributes: true,
                attributeFilter: ['class'],
                attributeOldValue: true
            });
        }
    }
}

// Initial render on load
document.addEventListener('DOMContentLoaded', () => {
    reInitQuickActions();
    observeTabSwitches();

    // Optional: fallback for tab buttons if any
    document.querySelectorAll('[data-tab-target]').forEach(btn => {
        btn.addEventListener('click', () => {
            setTimeout(() => {
                reInitQuickActions();
            }, 50);
        });
    });

    document.getElementById('qa-toggle')?.addEventListener('click', () => {
        document.getElementById('quickAction')?.classList.toggle('hidden');
    });
});

