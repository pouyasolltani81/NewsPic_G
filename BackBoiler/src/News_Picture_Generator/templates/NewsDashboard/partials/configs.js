(function () {
  const API_BASE = "/News_Picture_Generator"; // base path
  // DOM refs
  const systemInput = document.getElementById("config-system-prompt-input");
  const userInput = document.getElementById("config-user-prompt-input");
  const styleInput = document.getElementById("config-style-input");
  const scopesList = document.getElementById("config-scopes-list");
  const newScopeInput = document.getElementById("config-new-scope-input");

  const status = id => document.getElementById(id);

  // Helpers
  function showStatus(id, msg, ok = true) {
    const el = status(id);
    el.textContent = msg;
    el.className = ok ? "text-sm text-emerald-500" : "text-sm text-rose-500";
    setTimeout(() => { if (el.textContent === msg) el.textContent = ""; }, 2500);
  }

  async function fetchJson(path, opts = {}) {
    const res = await fetch(path, Object.assign({ credentials: "same-origin" }, opts));
    const data = await res.json();
    if (!res.ok) throw data;
    return data;
  }

  // Load all configs
  async function loadAll() {
    try {
      document.querySelectorAll("#configs-content textarea, #configs-content input").forEach(i => i.disabled = true);
      // system
      const sys = await fetchJson(API_BASE + "/system_prompt/");
      systemInput.value = sys.SYSTEM_PROMPT ?? "";
      // user
      const usr = await fetchJson(API_BASE + "/user_prompt/");
      userInput.value = usr.USER_PROMPT ?? "";
      // style
      const sty = await fetchJson(API_BASE + "/style/");
      styleInput.value = sty.STYLE ?? "";
      // scopes
      const sc = await fetchJson(API_BASE + "/scopes/");
      const scopes = Array.isArray(sc.SCOPES) ? sc.SCOPES : [];
      renderScopes(scopes);
    } catch (err) {
      console.error("load error", err);
      showStatus("system-status", "Failed to load configs", false);
    } finally {
      document.querySelectorAll("#configs-content textarea, #configs-content input").forEach(i => i.disabled = false);
    }
  }

  // Render scopes list
  function renderScopes(scopes) {
    scopesList.innerHTML = "";
    if (!scopes || scopes.length === 0) {
      const p = document.createElement("div");
      p.className = "text-sm text-slate-500 dark:text-slate-400";
      p.textContent = "No scopes set.";
      scopesList.appendChild(p);
      return;
    }
    scopes.forEach((s, idx) => {
      const row = document.createElement("div");
      row.className = "flex items-center gap-2 bg-slate-50 dark:bg-slate-800 p-2 rounded-md border border-slate-100 dark:border-slate-800";
      const label = document.createElement("div");
      label.className = "flex-1 text-sm text-slate-800 dark:text-slate-100 break-words";
      label.textContent = s;
      const removeBtn = document.createElement("button");
      removeBtn.className = "inline-flex items-center gap-2 px-2 py-1 rounded-md text-sm border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200";
      removeBtn.innerHTML = '<i data-lucide="trash" class="w-4 h-4"></i> Remove';
      removeBtn.onclick = () => {
        row.remove();
      };
      row.appendChild(label);
      row.appendChild(removeBtn);
      scopesList.appendChild(row);
    });
  }

  // Collect scopes from DOM into array
  function collectScopes() {
    return Array.from(scopesList.querySelectorAll("div > .flex-1")).map(d => d.textContent.trim());
  }

  // Save helpers for each field
  async function saveField(fieldName, value, statusId) {
    try {
      const body = {};
      body[fieldName] = value;
      const res = await fetchJson(API_BASE + "/" + fieldName.toLowerCase() + "/update/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.return === true) {
        showStatus(statusId, "Saved ✓", true);
      } else {
        showStatus(statusId, "Save failed", false);
      }
    } catch (err) {
      console.error("save error", err);
      showStatus(statusId, "Save error", false);
    }
  }

  // Attach UI actions
  document.getElementById("config-refresh-configs").addEventListener("click", loadAll);

  document.getElementById("config-save-system").addEventListener("click", () => {
    saveField("SYSTEM_PROMPT", systemInput.value, "system-status");
  });
  document.getElementById("config-revert-system").addEventListener("click", loadAll);

  document.getElementById("config-save-user").addEventListener("click", () => {
    saveField("USER_PROMPT", userInput.value, "user-status");
  });
  document.getElementById("config-revert-user").addEventListener("click", loadAll);

  document.getElementById("config-save-style").addEventListener("click", () => {
    saveField("STYLE", styleInput.value, "style-status");
  });
  document.getElementById("config-revert-style").addEventListener("click", loadAll);

  // Scopes actions
  document.getElementById("config-add-scope").addEventListener("click", () => {
    const v = newScopeInput.value.trim();
    if (!v) return;
    // append visually
    const row = document.createElement("div");
    row.className = "flex items-center gap-2 bg-slate-50 dark:bg-slate-800 p-2 rounded-md border border-slate-100 dark:border-slate-800";
    const label = document.createElement("div");
    label.className = "flex-1 text-sm text-slate-800 dark:text-slate-100 break-words";
    label.textContent = v;
    const removeBtn = document.createElement("button");
    removeBtn.className = "inline-flex items-center gap-2 px-2 py-1 rounded-md text-sm border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200";
    removeBtn.innerHTML = '<i data-lucide="trash" class="w-4 h-4"></i> Remove';
    removeBtn.onclick = () => row.remove();
    row.appendChild(label);
    row.appendChild(removeBtn);
    scopesList.appendChild(row);
    newScopeInput.value = "";
  });

  document.getElementById("config-save-scopes").addEventListener("click", async () => {
    const arr = collectScopes();
    try {
      const res = await fetchJson(API_BASE + "/scopes/update/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ SCOPES: arr }),
      });
      if (res.return === true) {
        showStatus("scopes-status", "Saved ✓", true);
      } else {
        showStatus("scopes-status", "Save failed", false);
      }
    } catch (err) {
      console.error(err);
      showStatus("scopes-status", "Save error", false);
    }
  });

  // initial load
  loadAll();

  // expose utilities for debugging
  window.CONFIGS_UI = {
    reload: loadAll
  };
})();