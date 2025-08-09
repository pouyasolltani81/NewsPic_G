function showConfirmationModal(title, message) {
  return new Promise((resolve) => {
    document.getElementById("close_modal").classList.add('hidden')
    document.getElementById("modal-title").innerHTML = title;
    document.getElementById("modal-content").innerHTML = `
      <div class="text-gray-700 dark:text-gray-200 mb-4">${message}</div>
      <div class="flex justify-between w-full gap-4">
        <button id="modal-no" class="w-full px-4 py-2 bg-gray-300 dark:bg-gray-600 rounded hover:bg-gray-400">No</button>
        <button id="modal-yes" class="w-full px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600">Yes</button>
      </div>
    `;

    document.getElementById("modal-container").classList.remove("hidden");
    document.getElementById("modal-overlay").classList.remove("hidden");

    setTimeout(() => lucide.createIcons(), 0); // Ensure icon renders

    document.getElementById("modal-yes").onclick = () => {
      hideModal();
      resolve(true);
    };

    document.getElementById("modal-no").onclick = () => {
      hideModal();
      resolve(false);
    };
  });
}


function showMessageModal(title, formHtml) {

  document.removeEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const form = document.getElementById("custom-form");
      const fd = new FormData(form);
      fd.append('from_user_id', document.body.dataset.userId)
      fd.append('from_user', document.body.dataset.userId)
      fd.append('to_user_id', document.getElementById('to_user_message').value)



      hideModal();
      resolve(fd);
    }
  });
  return new Promise((resolve) => {
    document.getElementById("modal-title").innerHTML = title;
    document.getElementById("modal-content").innerHTML = formHtml + `
      <div class="flex justify-end gap-4 mt-4 w-full">
        <button id="modal-no" class="w-full px-4 py-2 bg-gray-300 dark:bg-gray-600 rounded hover:bg-gray-400">No</button>
        <button id="modal-yes" class="w-full px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">Yes</button>
      </div>
    `;

    document.getElementById("modal-container").classList.remove("hidden");
    document.getElementById("modal-overlay").classList.remove("hidden");
    document.getElementById("close_modal").classList.add('hidden')


    setTimeout(() => lucide.createIcons(), 0);

    document.getElementById("modal-no").onclick = () => {
      hideModal();
      resolve(null);
    };

    document.getElementById("modal-yes").onclick = () => {
      const form = document.getElementById("custom-form");
      const fd = new FormData(form);
      fd.append('from_user_id', document.body.dataset.userId)
      fd.append('from_user', document.body.dataset.userId)
      fd.append('to_user_id', document.getElementById('to_user_message').value)



      hideModal();
      resolve(fd);
    };





    document.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const form = document.getElementById("custom-form");
        const fd = new FormData(form);
        fd.append('from_user_id', document.body.dataset.userId)
        fd.append('from_user', document.body.dataset.userId)
        fd.append('to_user_id', document.getElementById('to_user_message').value)



        hideModal();
        resolve(fd);
      }
    });
  });
}


// ====== GLOBAL VARIABLES (Moved to top) ====== //
const NOTIF_API2 = "https://message.imoonex.ir/msgCore/GetUserMessagesInPage";
const READ_API2 = "https://message.imoonex.ir/msgCore/ReadUserMessages";
const DELETE_API2 = "https://message.imoonex.ir/msgCore/DeleteUserMessages";
const MESSAGE_API = 'https://message.imoonex.ir/msgCore/SendMessage';
const AUTH_TOKEN2 = "7688b6ef5255596256325511";
let notifications_all = [];
let checkboxesVisible = false;
let checkedNotifications = new Set();
let currentExpandedUuid = null;
let notifications_page = 1;
let totalPages = null

// ====== FUNCTIONS ====== //
function toggleCheckboxesVisibility() {
  checkboxesVisible = !checkboxesVisible;

  const checkboxes = document.querySelectorAll('.notification-checkbox');
  const showNotifBtn = document.getElementById('show-notif');

  checkboxes.forEach(checkbox => {
    checkbox.style.transition = 'opacity 0.3s ease';
    checkbox.style.opacity = checkboxesVisible ? '1' : '0';
    checkbox.style.pointerEvents = checkboxesVisible ? 'auto' : 'none';
  });

  if (showNotifBtn) {
    const icon = showNotifBtn.querySelector('#shownotif_btn');
    const delete_icon = document.querySelector('#delete_all');
    const message_icon = document.querySelector('#message');

    delete_icon.classList.toggle('translate-x-12')
    message_icon.classList.toggle('translate-x-12')

    if (icon) {
      icon.setAttribute('data-lucide', checkboxesVisible ? 'eye' : 'eye-off');
      lucide.createIcons();
    }
  }
}

function handleCheckboxChange() {
  const checkedActions = document.getElementById('checked_actions');
  if (checkedActions) {
    checkedActions.style.transition = 'opacity 0.3s ease';
    checkedActions.style.opacity = checkedNotifications.size > 0 ? '1' : '0';
    checkedActions.style.pointerEvents = checkedNotifications.size > 0 ? 'auto' : 'none';
  }
}


function arrayToString(arr) {
  if (arr.length === 1) return String(arr[0]);
  return arr.join(",");
}


async function deleteSelected() {
  if (checkedNotifications.size === 0) return;

  const confirmed = await showConfirmationModal(
    `<div class='flex gap-2'>Delete Messages <i style='color: #E54343;' class='size-6' data-lucide="trash"></i></div>`,
    `Are you sure about deleting these messages?`
  );

  if (!confirmed) return;

  try {
    const formData = new FormData();
    formData.append("app_id", "aican");
    formData.append("to_user_id", document.body.dataset.userId);
    formData.append("message_uuids", arrayToString(Array.from(checkedNotifications)));

    const response = await axios.post(DELETE_API2, formData, {
      headers: {
        Accept: "application/json",
        Authorization: AUTH_TOKEN2,
      },
      withCredentials: true,
    });

    if (response.data?.return) {
      showToast('Deleted Successfuly', 'success')
    } else {
      showToast('Sorry we couldnt delete that', 'error')

    }

    notifications_all = notifications_all.filter(
      n => !checkedNotifications.has(n.message.uuid)
    );

    if (currentExpandedUuid && checkedNotifications.has(currentExpandedUuid)) {
      currentExpandedUuid = null;
    }

    checkedNotifications.clear();
    rendernotifications_allTable();
    handleCheckboxChange();


  } catch (err) {
    console.error("Error deleting messages:", err);
  }
}


async function fetchnotifications_all() {
  try {
    const formData = new FormData();
    formData.append("app_id", "aican");
    formData.append("to_user_id", document.body.dataset.userId);
    formData.append("message_type", "");
    formData.append("message_class", "");
    formData.append("message_device", "app");
    formData.append("unread", "false");
    formData.append("page", notifications_page);
    formData.append("page_size", 10);

    const formDataObj = Object.fromEntries(formData.entries());
    console.log("Form Data:", formDataObj);


    const response = await axios.post(NOTIF_API2, formData, {
      headers: {
        Accept: "application/json",
        Authorization: AUTH_TOKEN2,
      },
      withCredentials: true,
    });


    if (response.data?.return && Array.isArray(response.data.messages)) {
      const prevNotifications = [...notifications_all];
      notifications_all = response.data.messages;
      totalPages = response.data.total_pages;

      if (currentExpandedUuid) {
        const expandedMsgExists = notifications_all.some(
          n => n.message.uuid === currentExpandedUuid
        );
        if (!expandedMsgExists) {
          currentExpandedUuid = null;
        }
      }

      rendernotifications_allTable();
      renderPagination();

    }
  } catch (err) {
    console.error("Notification fetch failed:", err);
  }
}

function setupSearchFilter() {
  const searchInput = document.getElementById("message-search");
  if (!searchInput) return;

  searchInput.addEventListener("input", applySearchFilter);
}

function applySearchFilter() {
  const searchInput = document.getElementById("message-search");
  const table = document.getElementById("messages-table");
  if (!searchInput || !table) return;

  const filter = searchInput.value.toLowerCase();
  const rows = table.querySelectorAll("tbody tr");

  rows.forEach((row) => {
    // Skip expansion rows (they have colspan attribute)
    if (row.querySelector('td[colspan]')) return;

    const text = row.innerText.toLowerCase();
    row.style.display = text.includes(filter) ? "" : "none";
  });
}

function toggleNotificationExpansion(idx) {
  const uuid = notifications_all[idx].message.uuid;
  const row = document.querySelector(`tr[data-index="${idx}"]`);

  if (!row) return;

  const expandRow = row.nextElementSibling;
  const chevron = row.querySelector('.view-btn');



  // Collapse if same message
  if (currentExpandedUuid === uuid) {


    chevron.style.transform = 'rotate(0deg)';
    expandRow.style.height = '0';
    expandRow.style.opacity = '0';

    setTimeout(() => {
      expandRow.classList.add('hidden');
    }, 300);

    currentExpandedUuid = null;
    return;
  }

  // Collapse currently expanded row
  if (currentExpandedUuid) {
    const prevIdx = notifications_all.findIndex(
      n => n.message.uuid === currentExpandedUuid
    );
    if (prevIdx !== -1) {
      const prevRow = document.querySelector(`tr[data-index="${prevIdx}"]`);
      if (prevRow) {
        const prevExpandRow = prevRow.nextElementSibling;
        const prevChevron = prevRow.querySelector('.view-btn');
        prevChevron.style.transform = 'rotate(0deg)';
        prevExpandRow.style.height = '0';
        prevExpandRow.style.opacity = '0';

        setTimeout(() => {
          prevExpandRow.classList.add('hidden');
        }, 300);
      }
    }
  }



  expandRow.classList.remove('hidden');
  chevron.style.transform = 'rotate(90deg)';
  expandRow.style.height = '0';
  expandRow.style.opacity = '0';

  setTimeout(() => {
    const contentHeight = expandRow.scrollHeight;
    expandRow.style.height = `${contentHeight}px`;
    expandRow.style.opacity = '1';
  }, 10);

  currentExpandedUuid = uuid;

  // Mark as read if unread
  if (!notifications_all[idx].read_at) {
    markAsRead(notifications_all[idx].message.uuid);
  }
}

async function markAsRead(uuid) {
  try {
    const formDataR = new FormData();
    formDataR.append("app_id", "aican");
    formDataR.append("to_user_id", document.body.dataset.userId);
    formDataR.append("message_uuids", uuid);
    formDataR.append("read_all", "false");

    await axios.post(READ_API2, formDataR, {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json; charset=utf-8",
        Authorization: AUTH_TOKEN2,
      },
      withCredentials: true,
    });

    // Update local state
    const notification = notifications_all.find(n => n.message.uuid === uuid);
    if (notification) {
      notification.read_at = new Date().toISOString();
    }

    // Update UI
    const idx = notifications_all.findIndex(n => n.message.uuid === uuid);
    if (idx !== -1) {
      const row = document.querySelector(`tr[data-index="${idx}"]`);
      if (row) {
        const readIconCell = row.querySelector('.read-status-cell');
        if (readIconCell) {
          readIconCell.innerHTML = `<i style='color: #E54343;' class='size-6' data-lucide="message-square-dot"></i>`;
          lucide.createIcons();
        }
      }
    }
  } catch (err) {
    console.error("Error marking as read:", err);
  }
}

function rendernotifications_allTable() {
  const tbody = document.querySelector("#messages-content tbody");
  if (!tbody) return;

  tbody.innerHTML = "";

  notifications_all.forEach((n, i) => {
    const tooltipId = `tooltip-${i}`; // assuming `i` is row index

    const tr = document.createElement("tr");
    tr.dataset.index = i;
    tr.className = "border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700";

    const tr2 = document.createElement("tr");
    tr2.className = "hidden transition-all duration-300 overflow-hidden h-0 opacity-0 rtl:right-to-left ltr:left-to-right";
    tr2.innerHTML = `
      <td colspan="8" class="p-0">
        <div class="px-[4rem] space-y-4 bg-white dark:bg-gray-800 border border-2 border-gray-900">
          <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-100">${n.message.title}</h2>
          <p class="whitespace-pre-wrap text-gray-700 dark:text-gray-300">${n.message.body || n.message.content}</p>
          <div class="text-xs text-gray-500">${new Date(n.message.created_at).toLocaleString()}</div>
        </div>
      </td>
    `;

    // Preserve expanded state
    const isExpanded = currentExpandedUuid === n.message.uuid;
    if (isExpanded) {
      tr2.classList.remove('hidden');
      tr2.style.height = 'auto';
      tr2.style.opacity = '1';
    }

    const read = n.read_at
      ? `<i style='color: #2DD71E;' class='size-6' data-lucide="mail-check"></i>`
      : `<i style='color: #E54343;' class='size-6' data-lucide="message-square-dot"></i>`;

    const title = n.message.title || "-";
    const device = n.message.mdevice;
    const id = n.message.app_id;

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

    const from = n.message.from_user;

    const mclass = n.message.mclass;
    let mclass_bg = '';
    if (mclass == 'page') {
      mclass_bg = 'text-[#5291D0] bg-[#EDF4FA]';
    } else if (mclass == 'signal') {
      mclass_bg = 'text-[#9176EA] bg-[#F7F6FE]';
    } else if (mclass == 'trade') {
      mclass_bg = 'text-[#E57C43] bg-[#FAE5D9]';
    } else if (mclass == 'admin') {
      mclass_bg = 'text-[#4C4B58] bg-[#F2F2F3]';
    } else if (mclass == 'withdraw') {
      mclass_bg = 'text-[#E54343] bg-[#FAD9D9]';
    } else if (mclass == 'deposit') {
      mclass_bg = 'text-[#2DD71E] bg-[#DCFAD9]';
    }

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

    const isChecked = checkedNotifications.has(n.message.uuid);
    const chevronRotation = isExpanded ? 'rotate(90deg)' : '';

    tr.innerHTML = `
    <td class="p-3 text-center text-base font-medium"> 
      <div class='flex gap-2 justify-center items-center'> 
        <input type="checkbox" class="notification-checkbox" data-uuid="${n.message.uuid}" 
          ${isChecked ? 'checked' : ''}
          style="opacity: ${checkboxesVisible ? '1' : '0'}; 
          pointer-events: ${checkboxesVisible ? 'auto' : 'none'}; 
          transition: opacity 0.3s ease;"> 
        ${device_icon} ${id}
      </div>
    </td>
    <td class="p-3 text-center text-base font-medium">${from}</td>
    <td class="p-3 text-center text-base font-medium">${title}</td>
    <td class="p-3 flex justify-center items-center text-base font-medium read-status-cell">${read}</td>
    <td class="p-3 text-center text-base font-medium">
      <div class="text-xs ">
        <div class="font-bold">
          ${new Date(n.message.created_at).toLocaleDateString()}
        </div>
        <div class='text-gray-500'>
          ${new Date(n.message.created_at).toLocaleTimeString()}
        </div>
      </div>
    </td>
    <td class="p-3 flex justify-center items-center text-base font-medium">${mtype_icon}</td>
    <td class="p-3 text-center text-base font-medium"><div class='p-2 ${mclass_bg} rounded-lg capitalize'>${mclass}</div></td>
    <td class="p-3 text-center text-base font-medium">
      <button class="view-btn" data-index="${i}">
        <i class='size-6 transition-transform duration-300 rtl:rotate-180' style="transform: ${chevronRotation} " data-lucide="chevron-right"></i>
      </button>
    </td>
  `;

    tbody.appendChild(tr);
    tbody.appendChild(tr2);

    // const tooltipTrigger = tr.querySelector(`[data-tooltip-target="${tooltipId}"]`);
    // const tooltipEl = tr.querySelector(`#${tooltipId}`);
    // if (tooltipTrigger && tooltipEl && window.Tooltip) {
    //   new Tooltip(tooltipEl, tooltipTrigger);
    // }


    const checkbox = tr.querySelector('.notification-checkbox');
    if (checkbox) {
      checkbox.addEventListener('change', function () {
        if (this.checked) {
          checkedNotifications.add(n.message.uuid);
        } else {
          checkedNotifications.delete(n.message.uuid);
        }
        handleCheckboxChange();
      });
    }

    const viewBtn = tr.querySelector('.view-btn');
    if (viewBtn) {
      viewBtn.addEventListener('click', () => toggleNotificationExpansion(i));
    }
  });

  applySearchFilter();
  lucide.createIcons();
}



// pagination 



const turnToPage = (pageNumber) => {

  if (pageNumber < 1 || pageNumber > totalPages) return;
  notifications_page = pageNumber;

  fetchnotifications_all();
  // Put your page fetch logic here if needed



}


function renderPagination() {
  const container = document.getElementById("pagination");
  container.innerHTML = "";

  const createButton = (label, page, isActive = false, isDisabled = false) => {
    const btn = document.createElement("button");
    btn.className = `px-3 py-1 rounded-md ${isActive ? "bg-gray-100 text-gray-900 font-medium" : "hover:bg-gray-100"
      } ${isDisabled ? "opacity-30 cursor-not-allowed" : ""}`;
    btn.innerText = label;
    if (!isDisabled && !isActive) {
      btn.onclick = () => turnToPage(page);
    }
    return btn;
  };

  // Prev Button
  const prevBtn = document.createElement("button");
  prevBtn.innerHTML = `<i data-lucide="chevron-left" class="w-4 h-4"></i>`;
  prevBtn.className = "p-2 rounded-md hover:bg-gray-100";
  prevBtn.disabled = notifications_page === 1;
  if (!prevBtn.disabled) prevBtn.onclick = () => turnToPage(notifications_page - 1);
  container.appendChild(prevBtn);

  // Pages (1 ... current ... last)
  if (notifications_page > 2) container.appendChild(createButton("1", 1));
  if (notifications_page > 3) {
    const dots = document.createElement("span");
    dots.className = "px-2 text-gray-400";
    dots.innerText = "...";
    container.appendChild(dots);
  }

  for (let i = Math.max(1, notifications_page - 1); i <= Math.min(totalPages, notifications_page + 1); i++) {
    container.appendChild(createButton(i, i, i === notifications_page));
  }

  if (notifications_page < totalPages - 2) {
    const dots = document.createElement("span");
    dots.className = "px-2 text-gray-400";
    dots.innerText = "...";
    container.appendChild(dots);
  }
  if (notifications_page < totalPages - 1) container.appendChild(createButton(totalPages, totalPages));

  // Next Button
  const nextBtn = document.createElement("button");
  nextBtn.innerHTML = `<i data-lucide="chevron-right" class="w-4 h-4"></i>`;
  nextBtn.className = "p-2 rounded-md hover:bg-gray-100";
  nextBtn.disabled = notifications_page === totalPages;
  if (!nextBtn.disabled) nextBtn.onclick = () => turnToPage(notifications_page + 1);
  container.appendChild(nextBtn);

  // Re-render Lucide icons
  lucide.createIcons();
}

function dropdownOption(icon, label, id) {
  return `
    <div class="dropdown-option px-3 py-2 hover:bg-gray-100 flex items-center gap-2 cursor-pointer" 
         data-value="${label.toLowerCase()}" data-icon="${icon}" data-id="${id}">
      <i data-lucide="${icon}" class="size-4 text-gray-700"></i>
      <span>${label}</span>
    </div>
  `;
}

document.querySelectorAll(".dropdown-option").forEach(opt => {

  opt.addEventListener("click", () => {
    const value = opt.dataset.value;
    const icon = opt.dataset.icon;
    const id = opt.dataset.id;

    const button = document.getElementById(`${id}-button`);
    const hidden = document.getElementById(`${id}-hidden`);
    const menu = document.getElementById(`${id}-menu`);

    // Set value
    hidden.value = value;

    // Update button display
    button.innerHTML = `
      <span class="flex items-center gap-2 text-gray-600">
        <i data-lucide="${icon}" class="size-4"></i>
        <span>${capitalize(value)}</span>
      </span>
      <i data-lucide="chevron-down" class="size-4"></i>
    `;
    menu.classList.add("hidden");
    setTimeout(() => lucide.createIcons(), 0);
  });
});

function capitalize(str) {
  return str.charAt(0).toUpperCase() + str.slice(1);
}



const message = async () => {


  const formHtml = `
 <form id="custom-form" class="space-y-4 text-gray-800 dark:text-gray-100">
  <!-- Row 1: input1 + input2 + input3 -->
  <div class="flex gap-4">
    <input name="app_id" class="flex-1 px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500" placeholder="app id" />
    <input name="to_user" id='to_user_message' class="flex-1 px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500" placeholder="to user" />
  </div>

  <!-- Row 2: three selects with icons -->
  <div class="flex gap-4">
    <!-- Select 1 with icon -->
    <div class="relative flex-1">
      <div class="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-file-type-icon lucide-file-type"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M9 13v-1h6v1"/><path d="M12 12v6"/><path d="M11 18h2"/></svg>
      </div>
      <select name="message_type" class="block w-full pl-10 pr-3 py-2 text-base border border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 rounded-md shadow-sm">
        <option value="message">message</option>
        <option value="notif">notif</option>
        <option value="news">news</option>
        <option value="alert">alert</option>
        <option value="ads">ads</option>
        <option value="bill">bill</option>
        <option value="bugs">bugs</option>

      </select>
    </div>

    <!-- Select 2 with icon -->
    <div class="relative flex-1">
      <div class="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-cassette-tape-icon lucide-cassette-tape"><rect width="20" height="16" x="2" y="4" rx="2"/><circle cx="8" cy="10" r="2"/><path d="M8 12h8"/><circle cx="16" cy="10" r="2"/><path d="m6 20 .7-2.9A1.4 1.4 0 0 1 8.1 16h7.8a1.4 1.4 0 0 1 1.4 1l.7 3"/></svg>
      </div>
      <select name="message_class" class="block w-full pl-10 pr-3 py-2 text-base border border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 rounded-md shadow-sm">
        <option value="signal">signal</option>
        <option value="trade">trade</option>
        <option value="page">page</option>
        <option value="deposit">deposit</option>
        <option value="withdraw">withdraw</option>
        <option value="admin">admin</option>

      </select>
    </div>

    <!-- Select 3 with icon -->
    <div class="relative flex-1">
      <div class="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-send-icon lucide-send"><path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/><path d="m21.854 2.147-10.94 10.939"/></svg>
      </div>
      <select name="message_device" class="block w-full pl-10 pr-3 py-2 text-base border border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 rounded-md shadow-sm">
      <option value="app">App</option>
        <option value="telegram">Telegram</option>
        <option value="email">Email</option>
        <option value="sms">SMS</option>
      </select>
    </div>
  </div>

  <!-- Row 3: title input -->
  <input name="title" class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500" placeholder="title" />

  <!-- Row 4: body textarea -->
  <textarea name="body" class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500" placeholder="body" rows="4"></textarea>

  <!-- Row 5: checkbox + input + tag -->
  <div class="flex items-center gap-4">
    <label class="inline-flex items-center">
      <input type="checkbox" value="true" name="is_html" class="w-4 h-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded" />
      <span class="ml-2 text-gray-700 dark:text-gray-300">Is HTML?</span>
    </label>
    
    <input name="tag" class="flex-1 px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500" placeholder="tag" />
  </div>
</form>
`;




  const title = `<div class='flex gap-2'>Message <i style='color: #42a4ff ;' class='size-6' data-lucide="message-square-dot"></div>`;

  const formData = await showMessageModal(title, formHtml);

  const response = await axios.post(MESSAGE_API, formData, {
    headers: {
      Accept: "application/json",
      Authorization: AUTH_TOKEN2,
    },
    withCredentials: true,
  });

  if (response.data?.return) {
    showToast('Sent Successfuly', 'success')
  } else {
    showToast('Sorry we couldnt send that', 'error')

  }

}


// ====== INITIALIZATION ====== //
document.addEventListener("DOMContentLoaded", () => {
  setupSearchFilter();
  fetchnotifications_all();
  setInterval(fetchnotifications_all, 10000);

  // Initialize checkboxes as hidden
  document.querySelectorAll('.notification-checkbox').forEach(checkbox => {
    checkbox.style.opacity = '0';
    checkbox.style.pointerEvents = 'none';
  });

  // Initialize actions panel as hidden
  const checkedActions = document.getElementById('checked_actions');
  if (checkedActions) {
    checkedActions.style.opacity = '0';
    checkedActions.style.pointerEvents = 'none';
  }

  // Setup event listeners
  const showNotifBtn = document.getElementById('show-notif');
  if (showNotifBtn) {
    showNotifBtn.addEventListener('click', toggleCheckboxesVisibility);
  }

  const deleteAllBtn = document.getElementById('delete_all');
  if (deleteAllBtn) {
    deleteAllBtn.addEventListener('click', deleteSelected);
  }

  const messageBtn = document.getElementById('message');
  if (messageBtn) {
    messageBtn.addEventListener('click', message);
  }
});



// new 