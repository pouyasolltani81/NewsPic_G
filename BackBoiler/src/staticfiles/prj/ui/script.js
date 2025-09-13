
// Initialize Lucide icons
lucide.createIcons()

// Theme management
const themeToggle = document.getElementById("theme-toggle")
const html = document.documentElement

// Check for saved theme preference or default to light mode
const currentTheme = localStorage.getItem("theme") || "light"
html.classList.toggle("dark", currentTheme === "dark")

themeToggle.addEventListener("click", () => {
  const isDark = html.classList.contains("dark")
  html.classList.toggle("dark", !isDark)
  localStorage.setItem("theme", !isDark ? "dark" : "light")

  // Show toast notification
  showToast(!isDark ? "Dark mode enabled" : "Light mode enabled", "success")
})













// Toast notification system
function showToast(message, type = "info") {
  const toastContainer = document.getElementById("toast-container")
  const toast = document.createElement("div")

  const colors = {
    success: "bg-green-500",
    error: "bg-red-500",
    warning: "bg-yellow-500",
    info: "bg-blue-500",
  }

  toast.className = `${colors[type]} text-white px-4 py-3 rounded-lg shadow-lg transform translate-x-full transition-transform duration-300`
  toast.innerHTML = `
        <div class="flex items-center space-x-2">
            <i data-lucide="${type === "success" ? "check" : type === "error" ? "x" : type === "warning" ? "alert-triangle" : "info"}" class="w-4 h-4"></i>
            <span>${message}</span>
        </div>
    `

  toastContainer.appendChild(toast)
  lucide.createIcons()

  // Animate in
  setTimeout(() => {
    toast.classList.remove("translate-x-full")
  }, 100)

  // Remove after 3 seconds
  setTimeout(() => {
    toast.classList.add("translate-x-full")
    setTimeout(() => {
      toastContainer.removeChild(toast)
    }, 300)
  }, 3000)
}







// Header button functionality
document.getElementById("search-btn").addEventListener("click", () => {
  showToast("Search functionality coming soon!", "info")
})

document.getElementById("user-menu-btn").addEventListener("click", () => {
  const content = `
        <div class="space-y-2">
            <div class="flex items-center space-x-3 p-3 border-b border-gray-200 dark:border-gray-600">
                <div class="w-10 h-10 bg-blue-100 dark:bg-blue-900/50 rounded-full flex items-center justify-center">
                    <i data-lucide="user" class="w-5 h-5 text-blue-600 dark:text-blue-400"></i>
                </div>
                <div>
                    <p class="font-medium text-gray-800 dark:text-white">John Doe</p>
                    <p class="text-sm text-gray-500 dark:text-gray-400">john@example.com</p>
                </div>
            </div>
            <button class="w-full text-left p-3 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg transition-colors">
                <div class="flex items-center space-x-3">
                    <i data-lucide="user" class="w-4 h-4 text-gray-600 dark:text-gray-400"></i>
                    <span class="text-gray-800 dark:text-white">Profile</span>
                </div>
            </button>
            <button class="w-full text-left p-3 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg transition-colors" onclick="document.querySelector('[data-section=settings]').click(); hideModal();">
                <div class="flex items-center space-x-3">
                    <i data-lucide="settings" class="w-4 h-4 text-gray-600 dark:text-gray-400"></i>
                    <span class="text-gray-800 dark:text-white">Settings</span>
                </div>
            </button>
            <button class="w-full text-left p-3 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-lg transition-colors text-red-600 dark:text-red-400">
                <div class="flex items-center space-x-3">
                    <i data-lucide="log-out" class="w-4 h-4"></i>
                    <span>Sign Out</span>
                </div>
            </button>
        </div>
    `
  showModal("User Menu", content)
})


// Add entrance animations
document.addEventListener("DOMContentLoaded", () => {
  const cards = document.querySelectorAll(".bg-white, .dark\\:bg-gray-800") 
  cards.forEach((card, index) => {
    card.style.opacity = "0"
    card.style.transform = "translateY(20px)"

    setTimeout(() => {
      card.style.transition = "all 0.5s ease"
      card.style.opacity = "1"
      card.style.transform = "translateY(0)"
    }, index * 50)
  })
})


// Initialize the app
lucide.createIcons()
