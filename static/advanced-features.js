// Advanced Features Module for BookGPT
// Enhanced UI interactions, real-time updates, and advanced functionality

class AdvancedFeatures {
    constructor() {
        this.isOnline = navigator.onLine;
        this.performanceObserver = null;
        this.visibilityChangeCallbacks = new Map();
        this.setupAdvancedFeatures();
    }

    setupAdvancedFeatures() {
        this.setupPerformanceMonitoring();
        this.setupVisibilityChangeHandling();
        this.setupNetworkStatusMonitoring();
        this.setupAdvancedKeyboardShortcuts();
        this.setupGestureSupport();
        this.setupAdvancedNotifications();
    }

    // Performance monitoring and optimization
    setupPerformanceMonitoring() {
        if ('PerformanceObserver' in window) {
            this.performanceObserver = new PerformanceObserver((list) => {
                const entries = list.getEntries();
                entries.forEach(entry => {
                    if (entry.entryType === 'measure') {
                        console.log(`Performance: ${entry.name} took ${entry.duration}ms`);
                    }
                });
            });
            this.performanceObserver.observe({ entryTypes: ['measure', 'navigation'] });
        }
    }

    // Handle page visibility changes
    setupVisibilityChangeHandling() {
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.handlePageHidden();
            } else {
                this.handlePageVisible();
            }
        });

        // Add callbacks for visibility changes
        this.addVisibilityChangeCallback('page-hidden', this.handlePageHidden.bind(this));
        this.addVisibilityChangeCallback('page-visible', this.handlePageVisible.bind(this));
    }

    addVisibilityChangeCallback(event, callback) {
        this.visibilityChangeCallbacks.set(event, callback);
    }

    handlePageHidden() {
        // Pause any ongoing animations or intervals
        this.pauseNonEssentialActivities();
        
        // Save any pending changes
        this.savePendingChanges();
        
        console.log('Page hidden - paused non-essential activities');
    }

    handlePageVisible() {
        // Resume paused activities
        this.resumePausedActivities();
        
        // Refresh data if needed
        this.refreshDataIfNeeded();
        
        console.log('Page visible - resumed activities');
    }

    pauseNonEssentialActivities() {
        // Pause progress updates
        if (window.progressInterval) {
            clearInterval(window.progressInterval);
        }
        
        // Pause auto-refresh
        if (window.refreshInterval) {
            clearInterval(window.refreshInterval);
        }
    }

    resumePausedActivities() {
        // Resume progress tracking if needed
        if (currentProgressProjectId) {
            window.progressInterval = setInterval(async () => {
                const shouldStop = await checkProgress(currentProgressProjectId);
                if (shouldStop) {
                    clearInterval(window.progressInterval);
                }
            }, 3000);
        }
        
        // Resume auto-refresh
        const autoRefreshInterval = localStorage.getItem('autoRefreshInterval') || '30';
        if (autoRefreshInterval !== '0') {
            window.refreshInterval = setInterval(autoRefresh, parseInt(autoRefreshInterval) * 1000);
        }
    }

    savePendingChanges() {
        // Save form data to localStorage as backup
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            const formData = new FormData(form);
            const data = Object.fromEntries(formData.entries());
            localStorage.setItem(`form_backup_${form.id}`, JSON.stringify(data));
        });
    }

    refreshDataIfNeeded() {
        // Refresh projects if last update was more than 5 minutes ago
        const lastUpdate = localStorage.getItem('lastProjectUpdate');
        const now = Date.now();
        
        if (!lastUpdate || (now - parseInt(lastUpdate)) > 300000) { // 5 minutes
            loadProjects();
            localStorage.setItem('lastProjectUpdate', now.toString());
        }
    }

    // Network status monitoring
    setupNetworkStatusMonitoring() {
        window.addEventListener('online', () => {
            this.isOnline = true;
            this.handleConnectionChange(true);
        });

        window.addEventListener('offline', () => {
            this.isOnline = false;
            this.handleConnectionChange(false);
        });
    }

    handleConnectionChange(isOnline) {
        if (isOnline) {
            showNotification('🌐 Connection restored', 'success', 3000);
            this.resumeOnlineActivities();
        } else {
            showNotification('📡 Connection lost - working offline', 'warning', 5000);
            this.handleOfflineMode();
        }
    }

    resumeOnlineActivities() {
        // Retry failed requests
        this.retryFailedRequests();
        
        // Sync pending changes
        this.syncPendingChanges();
    }

    handleOfflineMode() {
        // Enable offline functionality
        this.enableOfflineMode();
        
        // Queue requests for later
        this.queueRequestsForLater();
    }

    retryFailedRequests() {
        // Implementation for retry logic
        console.log('Retrying failed requests...');
    }

    syncPendingChanges() {
        // Implementation for syncing data
        console.log('Syncing pending changes...');
    }

    enableOfflineMode() {
        // Implementation for offline functionality
        console.log('Enabled offline mode');
    }

    queueRequestsForLater() {
        // Implementation for request queuing
        console.log('Queued requests for later');
    }

    // Advanced keyboard shortcuts
    setupAdvancedKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Only handle shortcuts when not in input fields
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }

            // Global shortcuts
            if (e.ctrlKey || e.metaKey) {
                switch (e.key) {
                    case 'k':
                        e.preventDefault();
                        this.showCommandPalette();
                        break;
                    case 'n':
                        e.preventDefault();
                        showCreateProjectModal();
                        break;
                    case '1':
                        e.preventDefault();
                        this.navigateToSection('dashboard');
                        break;
                    case '2':
                        e.preventDefault();
                        this.navigateToSection('projects');
                        break;
                    case '3':
                        e.preventDefault();
                        showSettingsPage();
                        break;
                }
            }

            // Arrow key navigation
            if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
                this.handleArrowNavigation(e);
            }
        });
    }

    showCommandPalette() {
        // Simple command palette implementation
        const command = prompt('Command palette:\n- new: Create new project\n- settings: Open settings\n- help: Show help\n\nEnter command:');
        
        switch (command?.toLowerCase()) {
            case 'new':
                showCreateProjectModal();
                break;
            case 'settings':
                showSettingsPage();
                break;
            case 'help':
                showNotification('Available commands: new, settings, help', 'info');
                break;
        }
    }

    navigateToSection(section) {
        // Implementation for section navigation
        console.log(`Navigating to ${section}`);
    }

    handleArrowNavigation(e) {
        // Handle arrow key navigation between projects
        const projects = Array.from(document.querySelectorAll('.project-card'));
        const activeIndex = projects.findIndex(card => card.classList.contains('ring-2'));
        
        if (e.key === 'ArrowDown' && activeIndex < projects.length - 1) {
            projects[activeIndex + 1]?.focus();
        } else if (e.key === 'ArrowUp' && activeIndex > 0) {
            projects[activeIndex - 1]?.focus();
        }
    }

    // Gesture support for touch devices
    setupGestureSupport() {
        let startX = 0;
        let startY = 0;
        let startTime = 0;

        document.addEventListener('touchstart', (e) => {
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
            startTime = Date.now();
        });

        document.addEventListener('touchend', (e) => {
            const endX = e.changedTouches[0].clientX;
            const endY = e.changedTouches[0].clientY;
            const endTime = Date.now();
            
            const deltaX = endX - startX;
            const deltaY = endY - startY;
            const deltaTime = endTime - startTime;
            
            // Swipe detection
            if (deltaTime < 300 && Math.abs(deltaX) > 50) {
                if (deltaX > 0) {
                    this.handleSwipeRight();
                } else {
                    this.handleSwipeLeft();
                }
            }
        });
    }

    handleSwipeRight() {
        // Handle right swipe gesture
        console.log('Swipe right detected');
    }

    handleSwipeLeft() {
        // Handle left swipe gesture
        console.log('Swipe left detected');
    }

    // Advanced notifications
    setupAdvancedNotifications() {
        // Request notification permission
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
    }

    showAdvancedNotification(title, body, options = {}) {
        const defaultOptions = {
            icon: '/static/favicon.ico',
            badge: '/static/badge-icon.png',
            ...options
        };

        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification(title, {
                body,
                ...defaultOptions
            });
        } else {
            // Fallback to in-app notification
            showNotification(`${title}: ${body}`, options.type || 'info');
        }
    }

    // Utility methods
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    // Progressive Web App features
    setupPWAFeatures() {
        // Service worker registration
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/static/sw.js')
                .then(registration => {
                    console.log('SW registered: ', registration);
                })
                .catch(registrationError => {
                    console.log('SW registration failed: ', registrationError);
                });
        }

        // Install prompt
        let deferredPrompt;
        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            deferredPrompt = e;
            this.showInstallPrompt(deferredPrompt);
        });
    }

    showInstallPrompt(deferredPrompt) {
        // Show custom install prompt
        const installBanner = document.createElement('div');
        installBanner.className = 'fixed bottom-4 right-4 bg-black text-white p-4 rounded-lg shadow-lg z-50';
        installBanner.innerHTML = `
            <div class="flex items-center space-x-4">
                <span>📱 Install BookGPT app?</span>
                <button onclick="this.parentElement.parentElement.remove()" class="bg-white text-black px-3 py-1 rounded text-sm">Later</button>
                <button onclick="installPWA()" class="bg-blue-600 text-white px-3 py-1 rounded text-sm">Install</button>
            </div>
        `;
        
        document.body.appendChild(installBanner);
        
        // Auto-remove after 10 seconds
        setTimeout(() => {
            if (installBanner.parentNode) {
                installBanner.remove();
            }
        }, 10000);
    }

    // Advanced project management
    async createProjectWithTemplate(template) {
        const projectData = {
            title: template.title,
            genre: template.genre,
            target_length: template.target_length,
            writing_style: template.writing_style,
            description: template.description,
            template: template.id
        };

        try {
            const response = await fetch('/api/projects', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(projectData)
            });

            const data = await response.json();
            
            if (data.success) {
                showNotification(`✅ Project created from ${template.name} template!`, 'success');
                await loadProjects();
                return data.project;
            } else {
                throw new Error(data.error);
            }
        } catch (error) {
            showNotification('❌ Failed to create project from template', 'error');
            throw error;
        }
    }

    // Bulk operations
    async bulkDeleteProjects(projectIds) {
        const results = [];
        
        for (const projectId of projectIds) {
            try {
                const response = await fetch(`/api/projects/${projectId}`, {
                    method: 'DELETE'
                });
                
                const data = await response.json();
                results.push({ projectId, success: data.success, error: data.error });
            } catch (error) {
                results.push({ projectId, success: false, error: error.message });
            }
        }

        const successCount = results.filter(r => r.success).length;
        const failCount = results.filter(r => !r.success).length;
        
        showNotification(`Bulk delete: ${successCount} succeeded, ${failCount} failed`, 
                        failCount > 0 ? 'warning' : 'success');
        
        return results;
    }

    // Export/Import functionality
    exportData() {
        const data = {
            projects: currentProjects,
            settings: this.getUserSettings(),
            exportDate: new Date().toISOString()
        };

        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `bookgpt-backup-${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        showNotification('📁 Data exported successfully!', 'success');
    }

    importData(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const data = JSON.parse(e.target.result);
                
                // Validate data structure
                if (!data.projects || !Array.isArray(data.projects)) {
                    throw new Error('Invalid backup file format');
                }
                
                // Import projects
                this.importProjects(data.projects);
                
                // Import settings
                if (data.settings) {
                    this.importSettings(data.settings);
                }
                
                showNotification('📥 Data imported successfully!', 'success');
                loadProjects();
            } catch (error) {
                showNotification('❌ Failed to import data: ' + error.message, 'error');
            }
        };
        reader.readAsText(file);
    }

    async importProjects(projects) {
        for (const project of projects) {
            // Remove ID to create new project
            delete project.id;
            
            try {
                await fetch('/api/projects', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(project)
                });
            } catch (error) {
                console.error('Failed to import project:', project.title, error);
            }
        }
    }

    importSettings(settings) {
        Object.keys(settings).forEach(key => {
            localStorage.setItem(key, settings[key]);
        });
    }

    getUserSettings() {
        const settings = {};
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            settings[key] = localStorage.getItem(key);
        }
        return settings;
    }
}

// Initialize advanced features
let advancedFeatures;
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        advancedFeatures = new AdvancedFeatures();
    });
} else {
    advancedFeatures = new AdvancedFeatures();
}

// Global functions for templates
window.installPWA = function() {
    if (window.deferredPrompt) {
        window.deferredPrompt.prompt();
        window.deferredPrompt.userChoice.then((choiceResult) => {
            if (choiceResult.outcome === 'accepted') {
                showNotification('📱 App installed successfully!', 'success');
            }
            window.deferredPrompt = null;
        });
    }
};

window.exportData = () => advancedFeatures?.exportData();
window.importData = (file) => advancedFeatures?.importData(file);

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AdvancedFeatures;
}