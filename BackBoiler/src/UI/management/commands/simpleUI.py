import os
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from UI.static.js_files import MESSAGES_JS
from UI.static.js_files import QUICKACTIONS_JS


Messages = ''' 
{% block message_tab %}
{% load i18n %}

<div id="messages-content" class="tab-content hidden bg-white w-full h-screen overflow-hidden">
 
  <!-- 🔍 Search Input -->
  <div class="mb-4 flex justify-between p-6">
    <input
      type="text"
      id="message-search"
      placeholder="{% trans 'Search messages...' %}"
      class="w-full md:w-1/2 p-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring focus:ring-blue-300 dark:bg-gray-800 dark:text-white"
    />

    <div class='flex gap-2 flex-row-reverse transition-all w-fit'>
      <div id='show-notif' class=' z-10 cursor-pointer bg-slate-200  hover:bg-emerald-100 rounded-lg'>
        <i id='shownotif_btn' class=' rounded-lg h-10 w-10 p-2' data-lucide="eye-off"></i>
      </div>

      <div id='delete_all' class='translate-x-12 z-0 transition-all cursor-pointer bg-slate-200 hover:bg-red-100 rounded-lg'>
        <i class='h-10 w-10 p-2' data-lucide="trash"></i>
      </div>
  
      <div id='message' class='translate-x-12 transition-all cursor-pointer bg-slate-200 hover:bg-blue-100 rounded-lg'>
        <i class='h-10 w-10 p-2' data-lucide="mail-plus"></i>
      </div>
    </div>
  </div>

  <table class="w-full bg-white dark:bg-gray-800 text-base shadow overflow-hidden" id="messages-table">
    <thead class="dark:bg-gray-700 border-b-2 border-gray-100 text-neutral-500 dark:text-gray-300">
      <tr>
        <th class="p-3 font-normal">
          <div class='flex gap-2 justify-center items-center'> {% trans "Device/ID" %} </div>
        </th>
        <th class="p-3 font-normal select-none">{% trans "Sender" %}</th>
        <th class="p-3 font-normal select-none">{% trans "Title" %}</th>
        <th class="p-3 font-normal select-none">{% trans "Status" %}</th>
        <th class="p-3 font-normal select-none">{% trans "sent Time" %}</th>
        <th class="p-3 font-normal select-none">{% trans "Message Type" %}</th>
        <th class="p-3 font-normal select-none">{% trans "Message Class" %}</th>
        <th class="p-3 font-normal select-none">{% trans "View" %}</th>

      </tr>
    </thead>
    <tbody>
    </tbody>
  </table>
 
  <div id='pagination' class="flex items-center justify-center space-x-2 p-4 text-sm text-gray-700 dark:text-white select-none">
  </div>
</div>

{% endblock %}
'''


TEMPLATE_HTML = '''{{% extends "ui/{template}.html" %}}
{{% load i18n %}}

{{% block title %}}{name} –  UI{{% endblock %}}
{{% block page_heading %}}{name}{{% endblock %}}


{{% block extra_css %}}
  {{{{ block.super }}}}
{{% endblock %}}

{{% block content %}}
  <div id="main-content" class='z-10'>
    {{# ─────────────────────── DASHBOARD TAB ─────────────────────── #}}
    {{% include "{name}/partials/dashboard_section.html" %}}

    {{# ─────────────────────── WORKFLOWS TAB ─────────────────────── #}}
    {{% include "{name}/partials/workflows_section.html" %}}

    {{# ─────────────────────── ANALYTICS TAB ─────────────────────── #}}
    {{% include "{name}/partials/analytics_section.html" %}}

    {{# ─────────────────────── INPUTS TAB ─────────────────────── #}}
    {{% include "{name}/partials/inputs_section.html" %}}
    
     {{# ─────────────────────── MESSAGES TAB ─────────────────────── #}}
    {{% include "{name}/partials/messages_section.html" %}}

    {{# ─────────────────────── SETTINGS TAB ─────────────────────── #}}
    {{% include "{name}/partials/setting_section.html" %}}
    
    {{# ─────────────────────── ADDITIONAL TABS ─────────────────────── #}}
     
  </div>
{{% endblock %}}

{{% block extra_js %}}
  {{{{ block.super }}}}
  <script>

  const navItems = [
  {{ key: '1', section: "dashboard", label: "{{{{ _('Dashboard') }}}}", icon: "layout-dashboard", active: true, requiresAuth: false}},
  {{ key: '2', section: "workflows", label: "{{{{ _('Workflows') }}}}", icon: "workflow", requiresAuth: true }},
  {{ key: '3', section: "analytics", label: "{{{{ _('Analytics') }}}}", icon: "bar-chart-3", requiresAuth: true}},
  {{ key: '4', section: "inputs", label: "{{{{ _('Inputs') }}}}", icon: "calendar-fold", requiresAuth: true}},
  {{ key: '5', section: "messages", label: "{{{{ _('Messages') }}}}", icon: "mails", requiresAuth: true }},
  {{ key: '6', section: "settings", label: "{{{{ _('Settings') }}}}", icon: "settings", requiresAuth: true }},
];


    const contentSections = {{
      dashboard: document.getElementById('dashboard-content'),
      workflows: document.getElementById('workflows-content'),
      analytics: document.getElementById('analytics-content'),
      inputs: document.getElementById('inputs-content'),
      messages: document.getElementById('messages-content'),
      settings: document.getElementById('settings-content'),
    }};

    
    window.addEventListener('DOMContentLoaded', () => {{
      // Pass the authentication status as the fourth parameter
      const isAuthenticated = {{{{ user.is_authenticated|yesno:"true,false" }}}};
      const nav = new NavigationMain('navigationMain', navItems, contentSections, isAuthenticated);
      window.nav = nav;
    }});
</script>


<script>
  {{% comment %}} {{% include "dashboardcli/partials/quickactions.js" %}} {{% endcomment %}}
  {{% include "{name}/partials/messages.js" %}}

</script>

{{% endblock %}}
'''


PARTIAL_TEMPLATE = '''{{% block {block_name}_tab %}}
{{% load i18n %}}

<div id="{tab_id}" class="tab-content{extra_classes}">
 {block_name}
</div>
{{% endblock %}}
'''





class Command(BaseCommand):
    help = "Generate a UI template, view, URL route, and partials"

    def add_arguments(self, parser):
        parser.add_argument('app', type=str, help='App to create the UI in')
        parser.add_argument('name', type=str, help='UI page name (used as folder and file name)')
        parser.add_argument('template', type=str, help='Base UI template to extend')

    def handle(self, *args, **options):
        app = options['app']
        name = options['name']
        template = options['template']

        app_path = os.path.join(settings.BASE_DIR, app)
        if not os.path.isdir(app_path):
            raise CommandError(f"App '{app}' does not exist at {app_path}")

        self.stdout.write(f"✔ App found: {app_path}")

        # === Step 1: Create templates folder if missing ===
        templates_dir = os.path.join(app_path, 'templates')
        if not os.path.exists(templates_dir):
            os.mkdir(templates_dir)
            self.stdout.write(f"📁 Created: {templates_dir}")

        # === Step 2: Create main template folder ===
        page_dir = os.path.join(templates_dir, name)
        os.makedirs(page_dir, exist_ok=True)
        self.stdout.write(f"📁 Ensured page folder: {page_dir}")

        # === Step 3: Create HTML file ===
        html_path = os.path.join(page_dir, f"{name}.html")
        with open(html_path, 'w') as f:
            f.write(TEMPLATE_HTML.format(name=name, template=template))
        self.stdout.write(f"📝 Created template: {html_path}")

        # === Step 4: Create partials ===
        partials_path = os.path.join(page_dir, 'partials')
        os.makedirs(partials_path, exist_ok=True)
        self.stdout.write(f"📁 Ensured partials folder: {partials_path}")

        partial_names = ['dashboard_section', 'workflows_section', 'analytics_section', 'inputs_section', 'setting_section']
        for i, part in enumerate(partial_names):
            block_name = part
            tab_id = f"{part.replace('_section', '')}-content"
            extra_classes = "" if i == 0 else " hidden"
            content = PARTIAL_TEMPLATE.format(
                block_name=block_name,
                tab_id=tab_id,
                extra_classes=extra_classes
            )
            with open(os.path.join(partials_path, f"{part}.html"), 'w') as f:
                f.write(content)
            self.stdout.write(f"🧩 Created partial: {part}.html")
            
        

        with open(os.path.join(partials_path, "messages_section.html"), 'w') as f:
            f.write(Messages)
        self.stdout.write("🧩 Created partial: messages.html")
        
        
        # === Step 5: Create  JS file ===
        with open(os.path.join(partials_path, "quickactions.js"), 'w') as f:
            f.write(QUICKACTIONS_JS)
        self.stdout.write("🧠 Created quick actions JS: quickactions.js")
        
        with open(os.path.join(partials_path, "messages.js"), 'w') as f:
            f.write(MESSAGES_JS)
        self.stdout.write("🧠 Created messages JS: messages.js")

        # === Step 6: Add view ===
        views_path = os.path.join(app_path, 'views.py')
        view_func = f"""
def {name}_view(request):
  return render(request, '{name}/{name}.html')
                """
        with open(views_path, 'a') as f:
            f.write(view_func)
        self.stdout.write(f"📄 Appended view to: {views_path}")

        # === Step 7: Add URL ===
        urls_path = os.path.join(app_path, 'urls.py')
        if not os.path.exists(urls_path):
            with open(urls_path, 'w') as f:
                f.write("from django.urls import path\nfrom . import views\n\nurlpatterns = []\n")

        with open(urls_path, 'r') as f:
            content = f.read()
        if 'urlpatterns' not in content:
            raise CommandError(f"No urlpatterns list found in {urls_path}")

        new_url = f"path('{name}/', views.{name}_view, name='{name}'),"
        if new_url not in content:
            with open(urls_path, 'a') as f:
                f.write(f"\nurlpatterns += [\n    {new_url}\n]\n")
            self.stdout.write(f"🌐 Added URL route to: {urls_path}")
        else:
            self.stdout.write(f"⚠️ URL already exists in: {urls_path}")

        self.stdout.write(self.style.SUCCESS(f"✅ simpleUI for '{name}' created successfully in app '{app}'"))

