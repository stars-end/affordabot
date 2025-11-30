// Main Application Controller
class ATSApp {
    constructor() {
        this.currentTab = 'dashboard';
        this.init();
    }

    init() {
        // Initialize Lucide icons
        lucide.createIcons();
        
        // Load initial tab
        this.showTab('dashboard');
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Initialize backend status check
        this.checkBackendStatus();
        
        console.log('🚀 ATS Resume Analyzer - Demo Mode');
        console.log('📋 All features are functional with realistic mock data');
        console.log('💡 Upload resumes, view analytics, and explore the full ATS experience');
    }

    setupEventListeners() {
        // Tab navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                const tab = e.currentTarget.dataset.tab;
                this.showTab(tab);
            });
        });

        // File upload handling (global)
        document.addEventListener('dragover', (e) => {
            e.preventDefault();
        });

        document.addEventListener('drop', (e) => {
            e.preventDefault();
        });
    }

    showTab(tabName) {
        // Update navigation active state
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active', 'bg-gradient-to-r', 'from-purple-500', 'to-teal-500', 'text-white');
            item.classList.add('text-gray-700');
        });

        const activeNavItem = document.querySelector(`[data-tab="${tabName}"]`);
        if (activeNavItem) {
            activeNavItem.classList.add('active', 'bg-gradient-to-r', 'from-purple-500', 'to-teal-500', 'text-white');
            activeNavItem.classList.remove('text-gray-700');
        }

        // Hide all tab content
        document.querySelectorAll('.tab-content').forEach(tab => {
            tab.classList.add('hidden');
        });

        // Show selected tab content
        const selectedTab = document.getElementById(`${tabName}-tab`);
        if (selectedTab) {
            selectedTab.classList.remove('hidden');
        }

        // Load tab-specific content
        this.loadTabContent(tabName);
        this.currentTab = tabName;
    }

    async loadTabContent(tabName) {
        const tabElement = document.getElementById(`${tabName}-tab`);
        if (!tabElement) return;

        // Show loading state
        if (tabElement.children.length === 0) {
            tabElement.innerHTML = `
                <div class="flex items-center justify-center h-64">
                    <div class="text-center">
                        <div class="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                        <p class="text-gray-600">Loading ${tabName}...</p>
                    </div>
                </div>
            `;
        }

        // Load content based on tab
        try {
            switch (tabName) {
                case 'dashboard':
                    await window.Dashboard.load();
                    break;
                case 'analyzer':
                    await window.ResumeAnalyzer.load();
                    break;
                case 'candidates':
                    await window.CandidateManagement.load();
                    break;
                case 'jobs':
                    await window.JobPostings.load();
                    break;
                case 'analytics':
                    await window.Analytics.load();
                    break;
                case 'settings':
                    await window.Settings.load();
                    break;
            }
        } catch (error) {
            console.error(`Error loading ${tabName}:`, error);
            tabElement.innerHTML = `
                <div class="glass rounded-2xl p-8 text-center">
                    <div class="text-red-500 mb-4">
                        <i data-lucide="alert-circle" class="w-12 h-12 mx-auto mb-4"></i>
                        <h3 class="text-lg font-semibold mb-2">Error Loading Content</h3>
                        <p class="text-sm">Failed to load ${tabName}. Please try again.</p>
                    </div>
                    <button onclick="app.loadTabContent('${tabName}')" class="px-4 py-2 bg-gradient-to-r from-purple-500 to-teal-500 text-white rounded-xl hover:shadow-lg transition-all duration-200">
                        Retry
                    </button>
                </div>
            `;
            lucide.createIcons();
        }
    }

    checkBackendStatus() {
        const statusElement = document.getElementById('backend-status');
        if (statusElement) {
            // Always show demo mode for this HTML version
            statusElement.innerHTML = `
                <i data-lucide="info" class="w-4 h-4"></i>
                <span>Demo Mode</span>
            `;
            lucide.createIcons();
        }
    }

    showLoading() {
        document.getElementById('loading-overlay').classList.remove('hidden');
    }

    hideLoading() {
        document.getElementById('loading-overlay').classList.add('hidden');
    }

    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 z-50 glass-strong rounded-xl p-4 shadow-xl transform transition-all duration-300 translate-x-full`;
        
        const iconMap = {
            success: 'check-circle',
            error: 'alert-circle',
            warning: 'alert-triangle',
            info: 'info'
        };

        const colorMap = {
            success: 'text-green-600',
            error: 'text-red-600',
            warning: 'text-yellow-600',
            info: 'text-blue-600'
        };

        notification.innerHTML = `
            <div class="flex items-center gap-3">
                <i data-lucide="${iconMap[type]}" class="w-5 h-5 ${colorMap[type]}"></i>
                <span class="text-gray-800">${message}</span>
                <button onclick="this.parentElement.parentElement.remove()" class="ml-2 text-gray-500 hover:text-gray-700">
                    <i data-lucide="x" class="w-4 h-4"></i>
                </button>
            </div>
        `;

        document.body.appendChild(notification);
        lucide.createIcons();

        // Animate in
        setTimeout(() => {
            notification.classList.remove('translate-x-full');
        }, 100);

        // Auto remove after 5 seconds
        setTimeout(() => {
            notification.classList.add('translate-x-full');
            setTimeout(() => {
                if (notification.parentElement) {
                    notification.remove();
                }
            }, 300);
        }, 5000);
    }

    formatDate(date) {
        return new Date(date).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    }

    formatTime(date) {
        return new Date(date).toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    generateId() {
        return Math.random().toString(36).substr(2, 9);
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Global navigation function
function showTab(tabName) {
    if (window.app) {
        window.app.showTab(tabName);
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new ATSApp();
});

// Utility functions
window.utils = {
    formatDate: (date) => window.app.formatDate(date),
    formatTime: (date) => window.app.formatTime(date),
    formatFileSize: (bytes) => window.app.formatFileSize(bytes),
    generateId: () => window.app.generateId(),
    delay: (ms) => window.app.delay(ms),
    showLoading: () => window.app.showLoading(),
    hideLoading: () => window.app.hideLoading(),
    showNotification: (message, type) => window.app.showNotification(message, type)
};