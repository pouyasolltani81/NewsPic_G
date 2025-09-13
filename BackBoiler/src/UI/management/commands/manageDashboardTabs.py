import os
import re
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = "Manage dashboard tabs - add, remove, or list tabs in existing dashboard configurations"

    def add_arguments(self, parser):
        parser.add_argument('action', type=str, choices=['add', 'remove', 'list'], help='Action to perform')
        parser.add_argument('app', type=str, help='App containing the dashboard')
        parser.add_argument('dashboard_name', type=str, help='Dashboard name (folder name)')
        parser.add_argument('--tab-name', type=str, help='Tab name (for add/remove actions)')
        parser.add_argument('--tab-label', type=str, help='Tab display label (for add action)')
        parser.add_argument('--tab-icon', type=str, help='Tab icon (lucide icon name, for add action)')
        parser.add_argument('--tab-auth', type=str, choices=['true', 'false'], default='true', help='Requires authentication (default: true)')
        parser.add_argument('--tab-position', type=int, help='Position to insert tab (1-based, default: append)')
        parser.add_argument('--force', action='store_true', help='Force operation without confirmation')

    def handle(self, *args, **options):
        action = options['action']
        app = options['app']
        dashboard_name = options['dashboard_name']
        
        app_path = os.path.join(settings.BASE_DIR, app)
        if not os.path.isdir(app_path):
            raise CommandError(f"App '{app}' does not exist at {app_path}")
        
        dashboard_path = os.path.join(app_path, 'templates', dashboard_name)
        if not os.path.isdir(dashboard_path):
            raise CommandError(f"Dashboard '{dashboard_name}' does not exist at {dashboard_path}")
        
        dashboard_html = os.path.join(dashboard_path, f"{dashboard_name}.html")
        if not os.path.exists(dashboard_html):
            raise CommandError(f"Dashboard HTML file not found at {dashboard_html}")
        
        self.stdout.write(f"✔ Found dashboard: {dashboard_html}")
        
        if action == 'list':
            self.list_tabs(dashboard_html)
        elif action == 'add':
            self.add_tab(dashboard_html, options)
        elif action == 'remove':
            self.remove_tab(dashboard_html, options)

    def list_tabs(self, dashboard_html):
        """List all tabs in the dashboard"""
        with open(dashboard_html, 'r') as f:
            content = f.read()
        
        # Extract navItems array
        nav_items_match = re.search(r'const navItems = \[(.*?)\];', content, re.DOTALL)
        if not nav_items_match:
            self.stdout.write(self.style.WARNING("⚠️ No navItems found in dashboard"))
            return
        
        nav_items_text = nav_items_match.group(1)
        
        # Find all properties separately
        sections = re.findall(r'section:\s*[\'"]([^\'"]+)[\'"]', nav_items_text)
        labels = re.findall(r'label:\s*[\'"]([^\'"]+)[\'"]', nav_items_text)
        icons = re.findall(r'icon:\s*[\'"]([^\'"]+)[\'"]', nav_items_text)
        auths = re.findall(r'requiresAuth:\s*([^,}]+)', nav_items_text)
        keys = re.findall(r'key:\s*[\'"]([^\'"]+)[\'"]', nav_items_text)
        
        if sections and labels and icons:
            self.stdout.write("\n📋 Dashboard Tabs:")
            self.stdout.write("─" * 60)
            
            for i in range(min(len(sections), len(labels), len(icons))):
                key = keys[i] if i < len(keys) else str(i+1)
                section = sections[i]
                label = labels[i]
                icon = icons[i]
                auth = auths[i] if i < len(auths) else 'true'
                
                # Clean up label (remove Django template syntax)
                # Handle {{ _('Label') }} pattern
                label = re.sub(r'{{{\s*_\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)\s*}}}', r'\1', label)
                # Remove any remaining {{ }} patterns
                label = re.sub(r'{{.*?}}', '', label).strip()
                # Clean up any extra whitespace
                label = re.sub(r'\s+', ' ', label).strip()
                
                auth_status = "🔒 Auth Required" if 'true' in auth else "🔓 Public"
                self.stdout.write(f"{key:>3}. {label:<20} ({section:<15}) | {icon:<15} | {auth_status}")
        else:
            self.stdout.write(self.style.WARNING("⚠️ Could not parse tab information"))

    def add_tab(self, dashboard_html, options):
        """Add a new tab to the dashboard"""
        tab_name = options['tab_name']
        tab_label = options['tab_label']
        tab_icon = options['tab_icon']
        tab_auth = options['tab_auth']
        tab_position = options['tab_position']
        force = options['force']
        
        if not all([tab_name, tab_label, tab_icon]):
            raise CommandError("--tab-name, --tab-label, and --tab-icon are required for add action")
        
        with open(dashboard_html, 'r') as f:
            content = f.read()
        
        # Check if tab already exists
        if f'section: "{tab_name}"' in content:
            if not force:
                raise CommandError(f"Tab '{tab_name}' already exists. Use --force to overwrite.")
            self.stdout.write(f"⚠️ Tab '{tab_name}' already exists, will update...")
        
        # Create partial template
        partials_dir = os.path.join(os.path.dirname(dashboard_html), 'partials')
        os.makedirs(partials_dir, exist_ok=True)
        
        partial_content = f'''{{% block {tab_name}_tab %}}
{{% load i18n %}}

<div id="{tab_name}-content" class="tab-content hidden">
  <!-- {tab_label} Content -->
  <div class="p-6">
    <h2 class="text-2xl font-bold text-gray-800 dark:text-white mb-4">{tab_label}</h2>
    <p class="text-gray-600 dark:text-gray-400">This is the {tab_label} tab content.</p>
    <!-- Add your custom content here -->
  </div>
</div>
{{% endblock %}}'''
        
        partial_file = os.path.join(partials_dir, f"{tab_name}_section.html")
        with open(partial_file, 'w') as f:
            f.write(partial_content)
        self.stdout.write(f"📝 Created partial template: {partial_file}")
        
        # Add include statement
        dashboard_name = os.path.basename(os.path.dirname(dashboard_html))
        include_pattern = f'{{% include "{dashboard_name}/partials/{tab_name}_section.html" %}}'
        if include_pattern not in content:
            # Find the last include statement and add after it
            last_include = content.rfind('{# ─────────────────────── ADDITIONAL TABS ─────────────────────── #}')
            if last_include != -1:
                # Find the end of the last include line
                end_line = content.find('\n', last_include)
                if end_line != -1:
                    new_include = f'\n    {{# ─────────────────────── {tab_label.upper()} TAB ─────────────────────── #}}\n    {include_pattern}'
                    content = content[:end_line] + new_include + content[end_line:]
        
        # Update navItems array
        new_tab_item = f'  {{ key: \'{self._get_next_key(content)}\', section: "{tab_name}", label: "{{{{ _(\'{tab_label}\') }}}}", icon: "{tab_icon}", requiresAuth: {tab_auth} }},'
        
        # Find where to insert the new tab
        nav_items_start = content.find('const navItems = [')
        if nav_items_start != -1:
            # Find the end of the array
            nav_items_end = content.find('];', nav_items_start)
            if nav_items_end != -1:
                if tab_position and tab_position > 1:
                    # Insert at specific position
                    lines = content[nav_items_start:nav_items_end].split('\n')
                    insert_pos = min(tab_position, len(lines))
                    lines.insert(insert_pos, new_tab_item)
                    new_nav_items = '\n'.join(lines)
                    content = content[:nav_items_start] + new_nav_items + content[nav_items_end:]
                else:
                    # Append to the end
                    content = content[:nav_items_end] + '\n' + new_tab_item + content[nav_items_end:]
        
        # Update contentSections
        new_content_section = f'      {tab_name}: document.getElementById(\'{tab_name}-content\'),'
        content_sections_start = content.find('const contentSections = {')
        if content_sections_start != -1:
            content_sections_end = content.find('};', content_sections_start)
            if content_sections_end != -1:
                content = content[:content_sections_end] + '\n' + new_content_section + content[content_sections_end:]
        
        # Write updated content
        with open(dashboard_html, 'w') as f:
            f.write(content)
        
        self.stdout.write(f"✅ Successfully added tab '{tab_name}' ({tab_label}) to dashboard")
        self.stdout.write(f"   Icon: {tab_icon}")
        self.stdout.write(f"   Auth Required: {tab_auth}")

    def remove_tab(self, dashboard_html, options):
        """Remove a tab from the dashboard"""
        tab_name = options['tab_name']
        force = options['force']
        
        if not tab_name:
            raise CommandError("--tab-name is required for remove action")
        
        with open(dashboard_html, 'r') as f:
            content = f.read()
        
        # Check if tab exists
        if f'section: "{tab_name}"' not in content:
            raise CommandError(f"Tab '{tab_name}' not found in dashboard")
        
        if not force:
            confirm = input(f"Are you sure you want to remove tab '{tab_name}'? (yes/no): ")
            if confirm.lower() != 'yes':
                self.stdout.write("Operation cancelled.")
                return
        
        # Remove from navItems
        content = re.sub(r'\s*\{[^}]*section:\s*[\'"]([^\'"]*' + re.escape(tab_name) + r')[^\'"]*[^}]*\},?\n?', '', content)
        
        # Remove from contentSections
        content = re.sub(r'\s*' + re.escape(tab_name) + r':\s*document\.getElementById\([^)]*\),?\n?', '', content)
        
        # Remove include statement
        include_pattern = f'{{% include "[^"]*{tab_name}_section\.html" %}}'
        content = re.sub(r'\s*{{# ─────────────────────── [^#]* ─────────────────────── #}}\s*\n\s*' + include_pattern + '\n?', '', content)
        
        # Remove partial file
        partials_dir = os.path.join(os.path.dirname(dashboard_html), 'partials')
        partial_file = os.path.join(partials_dir, f"{tab_name}_section.html")
        if os.path.exists(partial_file):
            os.remove(partial_file)
            self.stdout.write(f"🗑️ Removed partial template: {partial_file}")
        
        # Write updated content
        with open(dashboard_html, 'w') as f:
            f.write(content)
        
        self.stdout.write(f"✅ Successfully removed tab '{tab_name}' from dashboard")

    def _get_next_key(self, content):
        """Get the next available key for a new tab"""
        nav_items_match = re.search(r'const navItems = \[(.*?)\];', content, re.DOTALL)
        if nav_items_match:
            nav_items_text = nav_items_match.group(1)
            # Find the highest key value
            keys = re.findall(r'key:\s*[\'"]([^\'"]+)[\'"]', nav_items_text)
            if keys:
                try:
                    numeric_keys = [int(k) for k in keys if k.isdigit()]
                    if numeric_keys:
                        return str(max(numeric_keys) + 1)
                except ValueError:
                    pass
        return '999'  # Default fallback
