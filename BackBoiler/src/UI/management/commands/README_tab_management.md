# 📊 Dashboard Tab Management Guide

This guide covers how to use the `manageDashboardTabs` command to dynamically add, remove, and manage tabs in your Django dashboard applications.

---

## 🚀 Quick Start

### Basic Usage
```bash
# List all tabs in a dashboard
python src/manage.py manageDashboardTabs list <app> <dashboard_name>

# Add a new tab
python src/manage.py manageDashboardTabs add <app> <dashboard_name> --tab-name "reports" --tab-label "Reports" --tab-icon "file-text"

# Remove a tab
python src/manage.py manageDashboardTabs remove <app> <dashboard_name> --tab-name "reports" --force
```

---

## 📋 Command Reference

### Command Structure
```bash
python src/manage.py manageDashboardTabs <action> <app> <dashboard_name> [options]
```

### Actions
- **`list`** - Show all tabs in a dashboard
- **`add`** - Add new tabs with custom properties
- **`remove`** - Remove existing tabs

### Required Parameters
- **`<app>`** - The Django app containing the dashboard (e.g., `UI`)
- **`<dashboard_name>`** - The name of the dashboard folder (e.g., `Dashboard`)

---

## ➕ Adding New Tabs

### Basic Tab Addition
```bash
python src/manage.py manageDashboardTabs add UI Dashboard \
  --tab-name "reports" \
  --tab-label "Reports" \
  --tab-icon "file-text" \
  --tab-auth true
```

### Advanced Tab Addition with Positioning
```bash
python src/manage.py manageDashboardTabs add UI Dashboard \
  --tab-name "analytics" \
  --tab-label "Analytics" \
  --tab-icon "bar-chart-3" \
  --tab-auth true \
  --tab-position 3
```

### Tab Properties

| Property | Description | Example Values |
|----------|-------------|----------------|
| `--tab-name` | Internal identifier (no spaces) | `reports`, `analytics`, `users` |
| `--tab-label` | Display name (can have spaces) | `Reports`, `User Analytics`, `System Logs` |
| `--tab-icon` | Lucide icon name | `file-text`, `bar-chart-3`, `users`, `settings` |
| `--tab-auth` | Authentication required | `true` or `false` |
| `--tab-position` | Position in navigation (optional) | `1`, `2`, `3`, etc. |

### Available Icons
- `layout-dashboard` - Dashboard
- `workflow` - Workflows
- `bar-chart-3` - Analytics/Charts
- `scroll-text` - Logs/Documents
- `mails` - Messages/Email
- `settings` - Settings
- `file-text` - Reports/Documents
- `users` - Users/People
- `database` - Database
- `calendar` - Calendar
- `star` - Custom/Featured
- `plus` - Add/Create
- `edit` - Edit/Modify
- `trash` - Delete/Remove

---

## ➖ Removing Tabs

### Remove with Confirmation
```bash
python src/manage.py manageDashboardTabs remove UI Dashboard --tab-name "reports"
```

### Force Remove (No Confirmation)
```bash
python src/manage.py manageDashboardTabs remove UI Dashboard --tab-name "reports" --force
```

### What Gets Removed
- ✅ Partial template file (`reports_section.html`)
- ✅ Include statement in main template
- ✅ Navigation item in `navItems` array
- ✅ Content section in `contentSections` object

---

## 📋 Listing and Inspecting Tabs

### List All Tabs
```bash
python src/manage.py manageDashboardTabs list UI Dashboard
```

### Show Tab Details
```bash
python src/manage.py manageDashboardTabs list UI Dashboard --verbose
```

---

## 🏗 How It Works

### 1. File Structure Created
```
Dashboard/
├── Dashboard.html              # Main dashboard template
├── partials/
│   ├── dashboard_section.html  # Dashboard tab content
│   ├── workflows_section.html  # Workflows tab content
│   ├── analytics_section.html  # Analytics tab content
│   ├── reports_section.html    # ← New tab (when added)
│   ├── logs_section.html       # Logs tab content
│   ├── messages_section.html   # Messages tab content
│   └── setting_section.html    # Settings tab content
```

### 2. Template Updates
The command automatically updates:

#### **Main Template (`Dashboard.html`)**
```html
{# ─────────────────────── REPORTS TAB ─────────────────────── #}
{% include "Dashboard/partials/reports_section.html" %}
```

#### **JavaScript Navigation (`navItems`)**
```javascript
const navItems = [
  { key: '1', section: "dashboard", label: "{{ _('Dashboard') }}", icon: "layout-dashboard", active: true, requiresAuth: false},
  { key: '2', section: "workflows", label: "{{ _('Workflows') }}", icon: "workflow", requiresAuth: true },
  { key: '3', section: "analytics", label: "{{ _('Analytics') }}", icon: "bar-chart-3", requiresAuth: true},
  { key: '4', section: "logs", label: "{{ _('logs') }}", icon: "scroll-text", requiresAuth: true},
  { key: '5', section: "messages", label: "{{ _('Messages') }}", icon: "mails", requiresAuth: true },
  { key: '6', section: "settings", label: "{{ _('Settings') }}", icon: "settings", requiresAuth: true },
  { key: '7', section: "reports", label: "{{ _('Reports') }}", icon: "file-text", requiresAuth: true }  // ← New tab
];
```

#### **Content Sections (`contentSections`)**
```javascript
const contentSections = {
  dashboard: document.getElementById('dashboard-content'),
  workflows: document.getElementById('workflows-content'),
  analytics: document.getElementById('apiAnalysis-content'),
  logs: document.getElementById('logs-content'),
  messages: document.getElementById('messages-content'),
  settings: document.getElementById('settings-content'),
  reports: document.getElementById('reports-content')  // ← New section
};
```

### 3. Partial Template Creation
Creates `reports_section.html` with:
```html
{% block reports_tab %}
{% load i18n %}

<div id="reports-content" class="tab-content hidden">
  <!-- Reports Content -->
  <div class="p-6">
    <h2 class="text-2xl font-bold text-gray-800 dark:text-white mb-4">Reports</h2>
    <p class="text-gray-600 dark:text-gray-400">This is the Reports tab content.</p>
    <!-- Add your custom content here -->
  </div>
</div>
{% endblock %}
```

---

## 🐛 Troubleshooting

### Common Issues

#### **1. Navigation Stops Working**
**Symptoms:** Tabs don't switch, JavaScript errors in console

**Causes:**
- Missing commas in JavaScript arrays/objects
- Missing closing brackets `]` or `}`
- Syntax errors in generated JavaScript

**Solutions:**
```bash
# Check the generated JavaScript in Dashboard.html
# Look for missing commas and brackets

# Example of CORRECT syntax:
const navItems = [
  { key: '1', section: "dashboard", label: "Dashboard", icon: "layout-dashboard", requiresAuth: false},  // ← Comma
  { key: '2', section: "workflows", label: "Workflows", icon: "workflow", requiresAuth: true },        // ← Comma
  { key: '3', section: "reports", label: "Reports", icon: "file-text", requiresAuth: true }            // ← NO comma on last item
]; // ← Closing bracket

const contentSections = {
  dashboard: document.getElementById('dashboard-content'),  // ← Comma
  workflows: document.getElementById('workflows-content'),  // ← Comma
  reports: document.getElementById('reports-content')       // ← NO comma on last item
}; // ← Closing bracket
```

#### **2. Template Not Found Errors**
**Symptoms:** `TemplateDoesNotExist` errors

**Causes:**
- Partial template file wasn't created
- Include path is incorrect
- File permissions issues

**Solutions:**
```bash
# Check if partial exists
ls src/UI/templates/Dashboard/partials/

# Verify include path in Dashboard.html
# Should be: {% include "Dashboard/partials/reports_section.html" %}

# Check file permissions
chmod 644 src/UI/templates/Dashboard/partials/reports_section.html
```

#### **3. Tab Not Showing in Navigation**
**Symptoms:** Tab exists but doesn't appear in UI

**Causes:**
- JavaScript arrays not updated
- CSS classes missing
- Template not included

**Solutions:**
```bash
# Verify JavaScript arrays are updated
# Check navItems and contentSections in Dashboard.html

# Ensure template is included
# Look for: {% include "Dashboard/partials/reports_section.html" %}

# Check CSS classes
# Tab content should have: class="tab-content hidden"
```

### Debug Steps

#### **1. Check Browser Console**
```javascript
// Open browser dev tools and check for JavaScript errors
// Look for syntax errors in the generated JavaScript
```

#### **2. Verify Template Structure**
```bash
# Check if all required files exist
ls -la src/UI/templates/Dashboard/partials/

# Verify template includes
grep -n "include.*partials" src/UI/templates/Dashboard/Dashboard.html
```

#### **3. Validate JavaScript Syntax**
```bash
# Check for proper comma placement and brackets
grep -A 20 "navItems" src/UI/templates/Dashboard/Dashboard.html
grep -A 20 "contentSections" src/UI/templates/Dashboard/Dashboard.html
```

---

## 💡 Best Practices

### **1. Tab Naming**
- Use lowercase, no spaces for `--tab-name`
- Use descriptive, user-friendly names for `--tab-label`
- Choose appropriate icons that match the tab's purpose

### **2. Authentication**
- Set `--tab-auth true` for sensitive operations
- Set `--tab-auth false` for public information
- Consider user roles and permissions

### **3. Positioning**
- Use `--tab-position` to control tab order
- Place most important tabs first
- Group related tabs together

### **4. Content Organization**
- Keep tab content focused and specific
- Use consistent styling and layout
- Include helpful placeholder content

### **5. Testing**
- Test tab switching after adding/removing
- Verify JavaScript console for errors
- Check mobile responsiveness

---

## 🔄 Advanced Usage

### **Batch Tab Operations**
```bash
# Add multiple tabs at once
python src/manage.py manageDashboardTabs add UI Dashboard --tab-name "users" --tab-label "Users" --tab-icon "users" --tab-auth true
python src/manage.py manageDashboardTabs add UI Dashboard --tab-name "settings" --tab-label "Settings" --tab-icon "settings" --tab-auth true
python src/manage.py manageDashboardTabs add UI Dashboard --tab-name "help" --tab-label "Help" --tab-icon "help-circle" --tab-auth false
```

### **Custom Tab Content**
After creating a tab, edit the partial template:
```html
<!-- src/UI/templates/Dashboard/partials/reports_section.html -->
{% block reports_tab %}
{% load i18n %}

<div id="reports-content" class="tab-content hidden">
  <div class="p-6">
    <h2 class="text-2xl font-bold text-gray-800 dark:text-white mb-4">Reports</h2>
    
    <!-- Add your custom content here -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <div class="bg-white dark:bg-gray-800 p-6 rounded-lg shadow">
        <h3 class="text-lg font-semibold mb-2">Monthly Report</h3>
        <p class="text-gray-600 dark:text-gray-400">Generate monthly analytics report</p>
        <button class="mt-4 bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600">
          Generate Report
        </button>
      </div>
      
      <div class="bg-white dark:bg-gray-800 p-6 rounded-lg shadow">
        <h3 class="text-lg font-semibold mb-2">User Activity</h3>
        <p class="text-gray-600 dark:text-gray-400">View user activity statistics</p>
        <button class="mt-4 bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600">
          View Stats
        </button>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

---

## 📚 Related Commands

- **`simpleUI`** - Generate complete UI dashboards
- **`editConfig`** - Manage project configuration
- **`TempBoilerInit`** - Initialize the entire project

---

## 🆘 Getting Help

### **Command Help**
```bash
python src/manage.py manageDashboardTabs --help
```

### **Verbose Output**
```bash
python src/manage.py manageDashboardTabs list UI Dashboard --verbosity 2
```

### **Common Error Messages**
- **"Tab already exists"** - Use `--force` to overwrite
- **"Dashboard not found"** - Check app and dashboard names
- **"Invalid icon name"** - Use valid Lucide icon names

---

## 🎯 Quick Reference

| Action | Command |
|--------|---------|
| List tabs | `python src/manage.py manageDashboardTabs list <app> <dashboard>` |
| Add tab | `python src/manage.py manageDashboardTabs add <app> <dashboard> --tab-name "name" --tab-label "Label" --tab-icon "icon"` |
| Remove tab | `python src/manage.py manageDashboardTabs remove <app> <dashboard> --tab-name "name" --force` |
| Get help | `python src/manage.py manageDashboardTabs --help` |

---

**Happy Tab Management! 🎉**
