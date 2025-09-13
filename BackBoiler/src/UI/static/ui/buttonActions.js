
function showModal(title, content) {
  document.getElementById("modal-title").innerHTML = title;
  document.getElementById("modal-content").innerHTML = content;
  document.getElementById("modal-container").classList.remove("hidden");
  document.getElementById("modal-overlay").classList.remove("hidden");
  lucide.createIcons(); // Re-render icons inside modal
}

function hideModal() {
  document.getElementById("close_modal").classList.remove('hidden')
  document.getElementById("modal-container").classList.add("hidden");
  document.getElementById("modal-overlay").classList.add("hidden");
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    hideModal();
  }
});


const currentLang = document.getElementById('main').lang || "en";

const rtlLanguages = ["fa", "ar"]

document.getElementById('main').dir = rtlLanguages.includes(currentLang) ? "rtl" : "ltr"


const options = [
  { code: "en", label: "English", flag: "🇺🇸" },
  { code: "fa", label: "فارسی", flag: "🇮🇷" },

];

const optionsHTML = options
  .map(({ code, label, flag }) => {
    const selected = code === currentLang ? "selected" : "";
    return `<option value="${code}" ${selected}>${flag} ${label}</option>`;
  })
  .join("");


document.getElementById("language-btn").addEventListener("click", () => {
  const content = `
      <form action="/i18n/setlang/" method="post" class="space-y-6 text-sm text-gray-800 dark:text-gray-100">
      <input type="hidden" name="csrfmiddlewaretoken" value="${getCSRFToken()}">

      <div>
        <label class="block text-base font-semibold text-gray-700 dark:text-gray-200 mb-2">
          🌍 Select Your Language
        </label>
        <div class="relative">
          <select
            name="language"
            class="appearance-none w-full bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 text-gray-900 dark:text-white rounded-lg py-3 px-4 pr-10 focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm transition-all"
          >
            ${optionsHTML}
          </select>
          <div class="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
            <i data-lucide="chevron-down" class="w-4 h-4 text-gray-400 dark:text-gray-500"></i>
          </div>
        </div>
      </div>

      <div class="flex justify-end pt-2">
        <button type="submit" class="inline-flex items-center space-x-2 px-5 py-2.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition font-medium text-sm w-full justify-center">
          <i data-lucide="globe" class="w-4 h-4"></i>
          <span>Change Language</span>
        </button>
      </div>
    </form>
    `
  document.getElementById("close_modal").classList.add('hidden')

  showModal("Change Language", content)
})

// Helper to extract CSRF token from cookie (needed since form is inserted via JS)
function getCSRFToken() {
  const name = "csrftoken"
  const cookieValue = document.cookie
    .split("; ")
    .find(row => row.startsWith(name + "="))
    ?.split("=")[1]
  return cookieValue || ""
}

//   notifications 
// ─────────────── Constants & State ───────────────
const NOTIF_API = "https://message.imoonex.ir/msgCore/GetUserMessages";
const READ_API = "https://message.imoonex.ir/msgCore/ReadUserMessages"; // adjust if different
const AUTH_TOKEN = "7688b6ef5255596256325511";
let notifications = [];
let currentNotificationIndex = null;

// ─────────────── Fetching ───────────────
async function fetchNotifications() {
  try {


    const formData = new FormData();
    formData.append("app_id", "aican");
    formData.append("to_user_id", document.body.dataset.userId);
    formData.append("message_type", "");
    formData.append("message_class", "");
    formData.append("message_device", "app");
    formData.append("unread", "true");

    const response = await axios.post(NOTIF_API, formData, {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json; charset=utf-8",
        Authorization: AUTH_TOKEN,
      },
      withCredentials: true,
      withXSRFToken: true,
    });


    if (response.data?.return && Array.isArray(response.data.messages)) {

      if (response.data.messages.length > 0) {
        document.getElementById('bell_dot').classList.remove('hidden')

      } else {
        document.getElementById('bell_dot').classList.add('hidden')

      }

      notifications = response.data.messages;
    }
  } catch (err) {
    console.error("Notification fetch failed:", err);
  }
}
fetchNotifications();
setInterval(fetchNotifications, 10000);

// ─────────────── Modal Override ───────────────
// keep original hideModal around
const _origHideModal = hideModal;
hideModal = async function () {
  _origHideModal();
  if (currentNotificationIndex !== null) {
    const formDataR = new FormData();
    formDataR.append("app_id", "aican");
    formDataR.append("to_user_id", document.body.dataset.userId);
    formDataR.append("message_uuids", notifications[currentNotificationIndex]?.message?.uuid);
    formDataR.append("read_all", "false");


    const response = await axios.post(READ_API, formDataR, {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json; charset=utf-8",
        Authorization: AUTH_TOKEN,
      },
      withCredentials: true,
      withXSRFToken: true,
    });

    // re‑render drawer if it's open
    const notifBox = document.getElementById("notif-box");
    if (!notifBox.classList.contains("hidden")) {
      showNotif();
    }
  }
};

// ─────────────── Open One Notification ───────────────
function openNotification(idx) {
  const { message } = notifications[idx];
  currentNotificationIndex = idx;
  // build your full-content HTML however you like:
  const content = `
    <div class="space-y-4 text-gray-800 dark:text-gray-100">
    <p class="mt-2 whitespace-pre-wrap">${message.body || message.content}</p>
    <div class="text-xs text-gray-500">${new Date(message.created_at).toLocaleString()}</div>
     
    </div>
  `;
  showModal(message.title, content);
}

// ─────────────── Drawer Rendering ───────────────
function showNotif() {
  const notifBox = document.getElementById("notif-box");
  const t = window.translations;

  if (!notifBox.classList.contains("hidden")) {
    notifBox.classList.add("hidden");
    return;
  }

  if (!notifications.length) {


    notifBox.innerHTML = `
      <div class="p-4 text-sm text-gray-500 dark:text-gray-400 flex items-center justify-center h-24">
        📭 ${t.noMessages}
      </div>`;
  } else {
    // FILTER OUT anything with read_at === null
    const toRender = notifications.filter(n => n.message.read_at !== null);

    notifBox.innerHTML = toRender.map((n, i) => {
      const msg = n.message;
      const title = (msg.title || t.newNotification).trim();
      const createdAt = new Date(msg.created_at || Date.now()).toLocaleString();
      const device = n.message.mdevice;


      const mtype = n.message.mtype;

      let mtype_icon = '';
      if (mtype == 'alert') {
        mtype_icon = `<i style='color: #1F1E2E;' class='size-6' data-lucide="triangle-alert"></i>`;
      } else if (mtype == 'message') {
        mtype_icon = `<i style='color: #1F1E2E;' class='size-6' data-lucide="message-circle-more"></i>`;
      } else if (mtype == 'notif') {
        mtype_icon = `<i style='color: #1F1E2E;' class='size-6' data-lucide="bell"></i>`;
      } else if (mtype == 'news') {
        mtype_icon = `<i style='color: #1F1E2E;' class='size-6' data-lucide="megaphone"></i>`;
      } else if (mtype == 'ads') {
        mtype_icon = `<i style='color: #1F1E2E;' class='size-6' data-lucide="file-text"></i>`;
      } else if (mtype == 'bill') {
        mtype_icon = `<i style='color: #1F1E2E;' class='size-6' data-lucide="receipt"></i>`;
      } else if (mtype == 'bugs') {
        mtype_icon = `<i style='color: #1F1E2E;' class='size-6' data-lucide="bug"></i>`;
      }



      let device_icon = '';
      if (device == 'app') {
        device_icon = `<div class='p-2 rounded-full size-9 bg-[#F7F6FE] flex justify-center items-center'><i style='color : #B4A1F1 ; fill : #B4A1F1 ;' class='size-9' data-lucide="layout-grid"></i></div>`;
      } else if (device == 'telegram') {
        device_icon = `<div class='p-2 rounded-full size-9 bg-[#F7F6FE] flex justify-center items-center'><i style='color : #B4A1F1 ; fill : #B4A1F1 ;' class='size-9' data-lucide="send"></i></div>`;
      } else if (device == 'email') {
        device_icon = `<div class='p-2 rounded-full size-9 bg-[#F7F6FE] flex justify-center items-center'><i style='color : #B4A1F1 ; fill : #B4A1F1 ;' class='size-9' data-lucide="mail"></i></div>`;
      } else if (device == 'sms') {
        device_icon = `<div class='p-2 rounded-full size-9 bg-[#F7F6FE] flex justify-center items-center'><i style='color : #B4A1F1 ; fill : #B4A1F1 ;' class='size-9' data-lucide="message-circle-more"></i></div>`;
      }


      return `
        <div 
          class="group px-4 py-3 border-b last:border-0 border-gray-200 dark:border-gray-700 
                 hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-colors"
          onclick="openNotification(${i})"
        >
        <div class='flex justify-between'>
          <div class="flex items-start gap-3">
            <div class="pt-1">
              ${mtype_icon}
            </div>
            <div class="flex-1">
              <div class="text-sm font-semibold text-gray-800 dark:text-white line-clamp-1">${title}</div>
              <div class="text-xs text-gray-400 mt-1">${createdAt}</div>
            </div>
          </div>

          <div>${device_icon}</div>
        </div>
        </div>`;
    }).join("") + `
      <button 
        id="goToMessagesBtn" 
        class="w-full text-center text-blue-600 dark:text-blue-400 hover:underline text-sm py-3"
        onclick="window.nav?.switchToSection?.('messages')"
      >
        ${t.showAll}
      </button>`;
  }

  notifBox.classList.remove("hidden");
  lucide?.createIcons?.();
}


// ─────────────── Event Hooks ───────────────
document.getElementById("notifications-btn")
  .addEventListener("click", showNotif);

document.addEventListener("click", function (e) {
  const notifBox = document.getElementById("notif-box");
  const notifBtn = document.getElementById("notifications-btn");
  if (!notifBox.contains(e.target) && !notifBtn.contains(e.target)) {
    notifBox.classList.add("hidden");
  }
});
