// BookGPT Frontend JavaScript - Modern SaaS Theme

// Global state
let currentProjects = [];
let currentProject = null;
let currentProgressProjectId = null;
let refreshInterval = null;
let progressInterval = null;
let isChatMode = false;

// DOM elements
const createProjectBtn = document.getElementById('createProjectBtn');
const createProjectBtnSmall = document.getElementById('createProjectBtnSmall');
const createFirstProjectBtn = document.getElementById('createFirstProjectBtn');
const createProjectModal = document.getElementById('createProjectModal');
const createProjectForm = document.getElementById('createProjectForm');
const cancelBtn = document.getElementById('cancelBtn');
const closeProjectModal = document.getElementById('closeProjectModal');
const projectsList = document.getElementById('projectsList');
const projectDetailsModal = document.getElementById('projectDetailsModal');
const projectTitle = document.getElementById('projectTitle');
const projectContent = document.getElementById('projectContent');

// Progress Interface elements
const progressInterface = document.getElementById('progressInterface');
const progressProjectTitle = document.getElementById('progressProjectTitle');
const progressProjectStatus = document.getElementById('progressProjectStatus');
const overallProgress = document.getElementById('overallProgress');
const mainProgressBar = document.getElementById('mainProgressBar');
const activityFeed = document.getElementById('activityFeed');
let commandInput = document.getElementById('commandInput');
const commandSendButton = document.getElementById('commandSendButton');
const projectSidebar = document.getElementById('projectSidebar');
let activityLoadingCard = null;

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    loadProjects();
    setupEventListeners();
    checkLLMStatus();
    checkMonitorPage();
    
    // Auto-refresh for active projects
    refreshInterval = setInterval(autoRefresh, 30000); // Every 30 seconds
});

function checkMonitorPage() {
    const params = new URLSearchParams(window.location.search);
    const projectId = params.get('id');
    if (window.location.pathname === '/monitor' && projectId) {
        currentProgressProjectId = projectId;
        loadMonitorProject(projectId);
        startProgressTracking(projectId);
    }
}

async function loadMonitorProject(projectId) {
    try {
        const response = await fetch(`/api/projects/${projectId}`);
        const data = await response.json();
        
        if (data.success) {
            const project = data.project;
            const titleEl = document.getElementById('monitorProjectTitle');
            const genreEl = document.getElementById('monitorGenre');
            const wordsEl = document.getElementById('monitorWords');
            
            if (titleEl) titleEl.textContent = project.title;
            if (genreEl) genreEl.textContent = project.genre;
            if (wordsEl) wordsEl.textContent = `${(project.progress?.words || 0).toLocaleString()} words`;
            
            // Update initial progress
            if (project.progress) {
                updateProgressUI({
                    progress_percentage: project.progress.percent,
                    phase: project.progress.phase,
                    status: project.status,
                    recent_activities: []
                });
            }
        }
    } catch (error) {
        console.error('Error loading project for monitor:', error);
    }
}

// Setup event listeners
function setupEventListeners() {
    if (createProjectBtn) createProjectBtn.addEventListener('click', showCreateProjectModal);
    if (createProjectBtnSmall) createProjectBtnSmall.addEventListener('click', showCreateProjectModal);
    if (createFirstProjectBtn) createFirstProjectBtn.addEventListener('click', showCreateProjectModal);
    
    if (cancelBtn) cancelBtn.addEventListener('click', hideCreateProjectModal);
    if (closeProjectModal) closeProjectModal.addEventListener('click', hideProjectDetailsModal);
    if (createProjectForm) createProjectForm.addEventListener('submit', handleCreateProject);
    
    // Command input Enter key
    const cmdInput = document.getElementById('commandInput');
    if (cmdInput) {
        cmdInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendCommand();
            }
        });
    }

    // Close modals when clicking outside
    if (createProjectModal) {
        createProjectModal.addEventListener('click', function(e) {
            if (e.target === createProjectModal) hideCreateProjectModal();
        });
    }

    if (projectDetailsModal) {
        projectDetailsModal.addEventListener('click', function(e) {
            if (e.target === projectDetailsModal) hideProjectDetailsModal();
        });
    }

    // Story arc modal close when clicking outside
    const storyArcModal = document.getElementById('storyArcModal');
    if (storyArcModal) {
        storyArcModal.addEventListener('click', function(e) {
            if (e.target === storyArcModal) closeStoryArcModal();
        });
    }

    // Version diff modal close when clicking outside
    const versionDiffModal = document.getElementById('versionDiffModal');
    if (versionDiffModal) {
        versionDiffModal.addEventListener('click', function(e) {
            if (e.target === versionDiffModal) closeVersionDiffModal();
        });
    }
    
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            hideCreateProjectModal();
            hideProjectDetailsModal();
            hideProgressInterface();
        }
    });
}

// Load projects from API
async function loadProjects() {
    try {
        showLoading(true, 'Syncing Library...');
        const response = await fetch('/api/projects');
        const data = await response.json();
        
        if (data.success) {
            currentProjects = data.projects;
            displayProjects();
            updateStats();
        } else {
            showNotification('Failed to load projects: ' + data.error, 'error');
        }
    } catch (error) {
        console.error('Error loading projects:', error);
        showNotification('Error loading projects', 'error');
    } finally {
        showLoading(false);
    }
}

// Update dashboard statistics
function updateStats() {
    const totalProjects = currentProjects.length;
    const totalChapters = currentProjects.reduce((sum, p) => sum + (p.chapters_completed || 0), 0);
    const totalWords = currentProjects.reduce((sum, p) => sum + (p.total_words || 0), 0);
    
    animateNumber('totalProjects', totalProjects);
    animateNumber('totalChapters', totalChapters);
    animateNumber('totalWords', totalWords, true);
}

function animateNumber(elementId, targetValue, format = false) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    const startValue = parseInt(element.textContent.replace(/,/g, '')) || 0;
    const duration = 1000;
    const startTime = performance.now();
    
    function updateNumber(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easedProgress = 1 - Math.pow(1 - progress, 3);
        
        const currentValue = Math.floor(startValue + (targetValue - startValue) * easedProgress);
        element.textContent = format ? currentValue.toLocaleString() : currentValue;
        
        if (progress < 1) requestAnimationFrame(updateNumber);
    }
    requestAnimationFrame(updateNumber);
}

// Display projects in the grid
function displayProjects() {
    if (!projectsList) return;
    projectsList.innerHTML = '';
    
    if (currentProjects.length === 0) {
        document.getElementById('emptyState').classList.remove('hidden');
        return;
    }
    
    document.getElementById('emptyState').classList.add('hidden');
    
    currentProjects.forEach((project, index) => {
        const projectCard = createProjectCard(project);
        projectsList.appendChild(projectCard);
    });
}

function createProjectCard(project) {
    const card = document.createElement('div');
    card.className = 'project-card bg-surface-50 dark:bg-surface-900/50 rounded-2xl border border-surface-200 dark:border-white/5 p-6 hover:shadow-soft transition-all duration-300';
    
    const targetLength = project.target_length || 50000;
    const totalWords = project.total_words || 0;
    const progress = targetLength > 0 ? Math.min(100, (totalWords / targetLength) * 100) : 0;
    
    const statusConfig = {
        'created': { bg: 'bg-surface-200 dark:bg-white/10', text: 'text-slate-500 dark:text-slate-400', label: 'Created' },
        'writing': { bg: 'bg-accent/10', text: 'text-accent', label: 'Writing' },
        'completed': { bg: 'bg-editorial-teal/10', text: 'text-editorial-teal', label: 'Completed' },
        'failed': { bg: 'bg-red-500/10', text: 'text-red-500', label: 'Failed' }
    };
    
    const status = project.status || 'created';
    const config = statusConfig[status] || statusConfig['created'];
    
    const genreEmojis = {
        'fiction': '📖',
        'non_fiction': '📚',
        'fantasy': '🏰',
        'mystery': '🔍',
        'sci-fi': '🚀'
    };
    
    card.innerHTML = `
        <div class="flex justify-between items-start mb-5">
            <div class="w-10 h-10 bg-surface-100 dark:bg-white/5 rounded-xl flex items-center justify-center text-lg group-hover:scale-110 transition-transform">
                ${genreEmojis[project.genre] || '📄'}
            </div>
            <span class="px-2.5 py-0.5 rounded-full text-xs font-medium uppercase tracking-wide ${config.bg} ${config.text}">
                ${config.label}
            </span>
        </div>
        
        <h3 class="font-display text-lg font-medium text-slate-900 dark:text-white mb-1.5 truncate">${project.title || 'Untitled'}</h3>
        <p class="text-slate-500 text-xs font-medium mb-6 capitalize">${project.genre || 'General'} • ${targetLength.toLocaleString()} words</p>
        
        <div class="space-y-2 mb-6">
            <div class="flex justify-between text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                <span>Progress</span>
                <span>${progress.toFixed(0)}%</span>
            </div>
            <div class="h-1.5 bg-surface-200 dark:bg-white/10 rounded-full overflow-hidden">
                <div class="h-full bg-accent rounded-full transition-all duration-1000 ease-out" style="width: ${progress}%"></div>
            </div>
        </div>
        
        <div class="grid grid-cols-2 gap-3">
            <button onclick="viewProject('${project.id}')" class="py-2.5 px-4 bg-slate-900 dark:bg-white text-white dark:text-slate-900 rounded-lg font-medium text-sm hover:opacity-90 transition-all">
                Details
            </button>
            ${status === 'created' ?
                `<button onclick="startWriting('${project.id}')" class="py-2.5 px-4 bg-accent hover:bg-accent-muted text-white rounded-lg font-medium text-sm transition-all">Start</button>` :
            (status === 'failed' || status === 'stopped') ?
                `<button onclick="resumeWriting('${project.id}')" class="py-2.5 px-4 bg-amber-500 hover:bg-amber-600 text-white rounded-lg font-medium text-sm transition-all">Resume</button>` :
                `<button onclick="showProgressInterface('${project.id}')" class="py-2.5 px-4 bg-editorial-teal hover:bg-editorial-teal/80 text-white rounded-lg font-medium text-sm transition-all">Monitor</button>`
            }
        </div>
    `;
    return card;
}

// Modal controls
function showCreateProjectModal() {
    createProjectModal.classList.remove('hidden');
    document.getElementById('title').focus();
}

function hideCreateProjectModal() {
    createProjectModal.classList.add('hidden');
    createProjectForm.reset();
}

async function handleCreateProject(e) {
    e.preventDefault();
    const formData = new FormData(createProjectForm);
    const projectData = Object.fromEntries(formData.entries());

    // Handle checkbox: FormData doesn't include unchecked checkboxes
    const selfCritiqueEl = createProjectForm.querySelector('#self_critique');
    if (selfCritiqueEl) projectData.self_critique = selfCritiqueEl.checked;
    // Ensure draft_passes is a number
    if (projectData.draft_passes) projectData.draft_passes = parseInt(projectData.draft_passes);
    // Remove empty style_voice so it doesn't override defaults
    if (!projectData.style_voice) delete projectData.style_voice;
    
    try {
        showLoading(true, 'Creating Manuscript...');
        const response = await fetch('/api/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(projectData)
        });
        const data = await response.json();
        if (data.success) {
            hideCreateProjectModal();
            await loadProjects();
            showNotification('Project created successfully', 'success');
        }
    } catch (error) {
        showNotification('Error creating project', 'error');
    } finally {
        showLoading(false);
    }
}

// Project Details
async function viewProject(projectId) {
    try {
        showLoading(true, 'Loading Details...');
        const response = await fetch(`/api/projects/${projectId}`);
        const data = await response.json();
        if (data.success) {
            currentProject = data.project;
            renderProjectDetails();
            projectDetailsModal.classList.remove('hidden');
        }
    } catch (error) {
        showNotification('Error loading project', 'error');
    } finally {
        showLoading(false);
    }
}

function renderProjectDetails() {
    const p = currentProject;
    projectTitle.textContent = p.title;
    
    // Extract description from metadata if it exists
    const description = p.metadata?.description || 'No description provided.';
    const writingStyle = p.writing_style || 'Standard';
    
    // Status configuration
    const statusConfig = {
        'created': { bg: 'bg-surface-200 dark:bg-white/10', text: 'text-slate-600 dark:text-slate-400', label: 'Created' },
        'writing': { bg: 'bg-accent/10', text: 'text-accent', label: 'Writing' },
        'completed': { bg: 'bg-editorial-teal/10', text: 'text-editorial-teal', label: 'Completed' },
        'failed': { bg: 'bg-red-500/10', text: 'text-red-500', label: 'Failed' }
    };
    const status = p.status || 'created';
    const config = statusConfig[status] || statusConfig['created'];
    
    projectContent.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-3 gap-5 mb-8">
            <div class="p-5 rounded-2xl bg-surface-100 dark:bg-white/5 border border-surface-200 dark:border-white/5">
                <div class="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">Status</div>
                <div class="text-lg font-display font-medium text-slate-900 dark:text-white capitalize">${config.label}</div>
            </div>
            <div class="p-5 rounded-2xl bg-surface-100 dark:bg-white/5 border border-surface-200 dark:border-white/5">
                <div class="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">Word Count</div>
                <div class="text-lg font-display font-medium text-slate-900 dark:text-white">${(p.total_words || 0).toLocaleString()} / ${p.target_length.toLocaleString()}</div>
            </div>
            <div class="p-5 rounded-2xl bg-surface-100 dark:bg-white/5 border border-surface-200 dark:border-white/5">
                <div class="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">Chapters</div>
                <div class="text-lg font-display font-medium text-slate-900 dark:text-white">${p.chapters_completed || 0}</div>
            </div>
        </div>

        <!-- User Provided Details -->
        <div class="mb-8 p-8 rounded-2xl bg-accent/5 dark:bg-accent/10 border border-accent/20">
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                <h4 class="text-xs font-semibold uppercase tracking-wider text-accent">Project Brief</h4>
                <div class="flex gap-2">
                    <span class="px-3 py-1.5 rounded-lg bg-surface-50 dark:bg-white/5 text-xs font-medium text-slate-600 dark:text-slate-300 border border-surface-200 dark:border-white/5 capitalize">${p.genre}</span>
                    <span class="px-3 py-1.5 rounded-lg bg-surface-50 dark:bg-white/5 text-xs font-medium text-slate-600 dark:text-slate-300 border border-surface-200 dark:border-white/5 capitalize">${writingStyle}</span>
                </div>
            </div>
            
            <div>
                <div class="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-2">Detailed Description</div>
                <div class="max-h-64 overflow-y-auto pr-4">
                    <p class="text-base font-medium text-slate-600 dark:text-slate-300 leading-relaxed whitespace-pre-wrap">${description}</p>
                </div>
            </div>
        </div>
        
        <div class="space-y-5">
            <h4 class="font-display text-lg font-medium text-slate-900 dark:text-white">Manuscript Content</h4>
            <div id="chaptersList" class="grid gap-4">
                <div class="animate-pulse flex space-x-4">
                    <div class="flex-1 space-y-4 py-1">
                        <div class="h-4 bg-surface-200 dark:bg-white/10 rounded w-3/4"></div>
                        <div class="h-4 bg-surface-200 dark:bg-white/10 rounded"></div>
                    </div>
                </div>
            </div>
        </div>

        <div class="mt-10 flex flex-col sm:flex-row gap-3">
            <button onclick="deleteProject('${p.id}')" class="px-6 py-3 border border-red-200 dark:border-red-900/30 text-red-600 dark:text-red-400 rounded-xl font-medium text-sm hover:bg-red-50 dark:hover:bg-red-900/20 transition-all">Delete Project</button>
            <button onclick="openStoryArcModal('${p.id}')" class="px-6 py-3 bg-editorial-teal/10 text-editorial-teal border border-editorial-teal/20 rounded-xl font-medium text-sm hover:bg-editorial-teal/20 transition-all ml-auto sm:ml-0">Story Arc Timeline</button>
            <button onclick="downloadBook('${p.id}')" class="px-6 py-3 bg-slate-900 dark:bg-white text-white dark:text-slate-900 rounded-xl font-medium text-sm hover:opacity-90 transition-all ml-auto sm:ml-3">Download TXT</button>
        </div>
    `;
    loadChapters(p.id);
}

async function loadChapters(projectId) {
    const list = document.getElementById('chaptersList');
    try {
        const response = await fetch(`/api/projects/${projectId}/chapters`);
        const data = await response.json();
        if (data.success && data.chapters.length > 0) {
            list.innerHTML = data.chapters.map(c => `
                <div class="p-6 rounded-2xl bg-surface-50 dark:bg-surface-900/50 border border-surface-200 dark:border-white/5 flex flex-col gap-5 group hover:border-accent/30 transition-all duration-300">
                    <div class="flex items-center justify-between">
                        <div>
                            <div class="font-display text-base font-medium text-slate-900 dark:text-white">${c.title}</div>
                            <div class="text-xs text-slate-400 font-medium mt-0.5">${c.words.toLocaleString()} words</div>
                        </div>
                        <button onclick="viewChapter('${c.file_path}')" class="w-10 h-10 rounded-xl bg-accent/10 text-accent flex items-center justify-center hover:bg-accent hover:text-white transition-all">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                            </svg>
                        </button>
                    </div>
                    
                    ${c.preview ? `
                    <div class="relative h-40 rounded-xl bg-surface-100 dark:bg-white/5 border border-surface-200 dark:border-white/5 group/ch">
                        <div class="absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-surface-50 dark:from-surface-900 to-transparent z-10 pointer-events-none rounded-b-xl opacity-100 group-hover/ch:opacity-0 transition-opacity duration-300"></div>
                        <div class="h-full overflow-y-auto p-5">
                            <div class="prose prose-slate dark:prose-invert prose-sm max-w-none font-serif italic opacity-70">
                                ${marked.parse(c.preview)}
                            </div>
                        </div>
                    </div>
                    ` : ''}
                </div>
            `).join('');
        } else {
            list.innerHTML = '<div class="text-center py-10 text-slate-400 text-sm font-medium">No chapters generated yet.</div>';
        }
    } catch (e) {
        list.innerHTML = '<div class="text-red-500 text-sm font-medium">Error loading chapters.</div>';
    }
}

function hideProjectDetailsModal() {
    projectDetailsModal.classList.add('hidden');
}

// Progress Interface
async function showProgressInterface(projectId) {
    window.location.href = `/monitor?id=${projectId}`;
}

function hideProgressInterface() {
    window.location.href = '/';
}

async function loadProjectForProgress(projectId) {
    try {
        const response = await fetch(`/api/projects/${projectId}`);
        const data = await response.json();
        
        if (data.success) {
            const project = data.project;
            const titleEl = document.getElementById('progressProjectTitle');
            const statusEl = document.getElementById('progressProjectStatus');
            if (titleEl) titleEl.textContent = project.title;
            if (statusEl) statusEl.textContent = `Status: ${project.status}`;
        }
    } catch (error) {
        console.error('Error loading project for progress:', error);
    }
}

function startProgressTracking(projectId) {
    if (progressInterval) clearInterval(progressInterval);
    checkProgress(projectId);
    progressInterval = setInterval(() => checkProgress(projectId), 3000);
}

async function checkProgress(projectId) {
    try {
        const response = await fetch(`/api/projects/${projectId}/progress`);
        const data = await response.json();
        if (data.success) {
            updateProgressUI(data);
            if (data.completed || data.status === 'completed') {
                clearInterval(progressInterval);
                showNotification('Manuscript completed!', 'success');
            }
        }
    } catch (e) { console.error(e); }
}

function updateProgressUI(data) {
    const percentage = data.progress_percentage || 0;
    
    // Core Progress Elements
    const overallProgressEl = document.getElementById('overallProgress');
    const mainProgressBarEl = document.getElementById('mainProgressBar');
    const monitorProgressBar = document.getElementById('monitorProgressBar');
    const monitorProgressPercent = document.getElementById('monitorProgressPercent');
    
    if (overallProgressEl) overallProgressEl.textContent = `${percentage.toFixed(0)}%`;
    if (mainProgressBarEl) mainProgressBarEl.style.width = `${percentage}%`;
    if (monitorProgressBar) monitorProgressBar.style.width = `${percentage}%`;
    if (monitorProgressPercent) monitorProgressPercent.textContent = `${percentage.toFixed(0)}%`;

    // Status & Phase Messages
    const statusEl = document.getElementById('progressProjectStatus');
    const monitorStatusBadge = document.getElementById('monitorStatusBadge');
    if (statusEl) statusEl.textContent = data.phase || 'Active';
    if (monitorStatusBadge) {
        monitorStatusBadge.textContent = data.phase || 'Active';
        if (data.status === 'refining' || data.status === 'completed') {
            monitorStatusBadge.className = 'px-3 py-1 rounded-full bg-accent/10 text-accent border border-accent/20';
        } else {
            monitorStatusBadge.className = 'px-3 py-1 rounded-full bg-editorial-teal/10 text-editorial-teal border border-editorial-teal/20';
        }
    }

    // Activity Feed (Chat drawer)
    const feedEl = document.getElementById('activityFeed');
    
    // Activity Log (Dashboard view)
    const logEl = document.getElementById('monitorActivityLog');

    if (data.recent_activities) {
        if (logEl) {
            logEl.innerHTML = data.recent_activities.slice(-5).reverse().map(a => `
                <div class="flex items-center gap-3 text-sm font-medium text-slate-600 dark:text-slate-300 animate-slide-in">
                    <div class="w-1.5 h-1.5 rounded-full bg-accent"></div>
                    <span class="opacity-50 text-[10px] w-12">${new Date(a.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                    <span class="truncate">${a.message}</span>
                </div>
            `).join('');
        }
    }
    
    // Agent Welcome Logic
    const inviteEl = document.getElementById('agentWelcomeInvite');
    if (inviteEl) {
        if (data.status === 'refining' || data.status === 'completed') {
            inviteEl.classList.remove('hidden');
        } else {
            inviteEl.classList.add('hidden');
        }
    }

    // Resume button visibility (for failed/stopped projects)
    const resumeButton = document.getElementById('resumeButton');
    if (resumeButton) {
        if (data.status === 'failed' || data.status === 'stopped') {
            resumeButton.classList.remove('hidden');
        } else {
            resumeButton.classList.add('hidden');
        }
    }
    
    // Update phases - aligned with app.py _get_phase_order
    // 0: initializing, 1: planning, 2: research, 3: writing, 4: editing, 5: refining
    const phases = ['initializing', 'planning', 'research', 'writing', 'editing', 'refining'];
    const currentIdx = data.phase_order || 0;
    
    // Special handling for completed status
    const effectiveIdx = (data.status === 'completed' || data.status === 'refining') ? 5 : currentIdx;

    // We only show Planning, Research, Writing, Agent Mode in the UI
    // Map them to the indices: Planning(1), Research(2), Writing(3), Agent Mode(5)
    const uiPhases = [
        { id: 'phasePlanning', idx: 1 },
        { id: 'phaseResearch', idx: 2 },
        { id: 'phaseWriting', idx: 3 },
        { id: 'phaseRefining', idx: 5 }
    ];

    uiPhases.forEach((p) => {
        const el = document.getElementById(p.id);
        if (el) {
            if (p.idx < effectiveIdx) { 
                el.textContent = 'Done'; 
                el.className = 'text-xs font-medium text-editorial-teal';
                el.parentElement.classList.add('border-editorial-teal/30');
                el.parentElement.classList.remove('border-accent/30', 'bg-accent/5');
            }
            else if (p.idx === effectiveIdx) { 
                el.textContent = 'Active'; 
                el.className = 'text-xs font-medium text-accent';
                el.parentElement.classList.add('border-accent/30', 'bg-accent/5');
                el.parentElement.classList.remove('border-editorial-teal/30');
            }
            else { 
                el.textContent = 'Pending'; 
                el.className = 'text-xs font-medium text-slate-400';
                el.parentElement.classList.remove('border-accent/30', 'bg-accent/5', 'border-editorial-teal/30');
            }
        }
    });

    // Load documents periodically if on monitor page
    if (currentProgressProjectId && !window.lastDocLoad || (Date.now() - window.lastDocLoad > 10000)) {
        loadMonitorDocuments(currentProgressProjectId);
        window.lastDocLoad = Date.now();
    }

    // If completed, ensure the command input is prominent
    if (data.status === 'completed') {
        const input = document.getElementById('commandInput');
        if (input && input.placeholder !== "Ask Agent to edit or improve...") {
            input.placeholder = "Ask Agent to edit or improve...";
            
            // Add a welcome message if the feed is empty or just has writing activities
            if (feedEl && !feedEl.querySelector('.agent-welcome')) {
                const welcome = document.createElement('div');
                welcome.className = 'agent-welcome p-6 rounded-2xl bg-editorial-teal/10 border border-editorial-teal/20 animate-slide-in';
                welcome.innerHTML = `
                    <div class="flex items-center gap-3 mb-3">
                        <div class="w-8 h-8 bg-editorial-teal text-white rounded-lg flex items-center justify-center">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                            </svg>
                        </div>
                        <h4 class="font-display font-medium text-slate-900 dark:text-white">Manuscript Draft Complete</h4>
                    </div>
                    <p class="text-sm text-slate-600 dark:text-slate-300 leading-relaxed mb-4">
                        I've finished the initial draft of your book. We are now in <strong>Agent Mode</strong>. 
                        You can ask me to rewrite sections, add more detail to chapters, fix consistency issues, 
                        or even change the ending.
                    </p>
                    <div class="flex flex-wrap gap-2">
                        <button onclick="fillCommand('Rewrite the first chapter to be more suspenseful')" class="text-[10px] px-3 py-1.5 rounded-lg bg-white dark:bg-white/5 border border-slate-200 dark:border-white/10 hover:border-accent/50 transition-all font-semibold uppercase tracking-wider text-slate-500">Suspenseful Intro</button>
                        <button onclick="fillCommand('Check for character consistency across all chapters')" class="text-[10px] px-3 py-1.5 rounded-lg bg-white dark:bg-white/5 border border-slate-200 dark:border-white/10 hover:border-accent/50 transition-all font-semibold uppercase tracking-wider text-slate-500">Consistency Check</button>
                        <button onclick="fillCommand('Add more sensory details to the climax')" class="text-[10px] px-3 py-1.5 rounded-lg bg-white dark:bg-white/5 border border-slate-200 dark:border-white/10 hover:border-accent/50 transition-all font-semibold uppercase tracking-wider text-slate-500">Enhance Climax</button>
                    </div>
                `;
                feedEl.appendChild(welcome);
                feedEl.scrollTop = feedEl.scrollHeight;
            }
        }
    }
}

// Actions
async function loadMonitorDocuments(projectId) {
    const list = document.getElementById('monitorDocumentsList');
    if (!list) return;
    
    try {
        const response = await fetch(`/api/projects/${projectId}/documents`);
        const data = await response.json();
        
        if (data.success && data.documents.length > 0) {
            list.innerHTML = data.documents.map(doc => `
                <button onclick="viewChapter('${doc.file_path}')" class="w-full flex items-center gap-3 p-3 rounded-xl hover:bg-surface-100 dark:hover:bg-white/5 transition-all text-left group">
                    <div class="w-8 h-8 rounded-lg bg-surface-200 dark:bg-white/10 flex items-center justify-center group-hover:bg-accent/10 transition-all">
                        <svg class="w-4 h-4 text-slate-500 group-hover:text-accent transition-all" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="text-xs font-semibold text-slate-700 dark:text-slate-300 truncate">${doc.title}</div>
                        <div class="text-[10px] text-slate-400 font-medium">${doc.words.toLocaleString()} words</div>
                    </div>
                </button>
            `).join('');
        }
    } catch (e) {
        console.error('Error loading documents for monitor:', e);
    }
}

async function startWriting(projectId) {
    try {
        showLoading(true, 'Initializing Agent...');
        const response = await fetch(`/api/projects/${projectId}/start`, { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            showProgressInterface(projectId);
            loadProjects();
        }
    } catch (e) { showNotification('Error starting agent', 'error'); }
    finally { showLoading(false); }
}

async function resumeWriting(projectId) {
    try {
        showLoading(true, 'Resuming writing process...');
        const response = await fetch(`/api/projects/${projectId}/resume`, { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            showProgressInterface(projectId);
            loadProjects();
            showNotification('Writing resumed', 'success');
        } else {
            showNotification(data.error || 'Error resuming', 'error');
        }
    } catch (e) {
        showNotification('Error resuming project', 'error');
    }
    finally { showLoading(false); }
}

// Resume from monitor page - resumes and continues monitoring
async function resumeProject() {
    if (!currentProgressProjectId) return;
    try {
        showLoading(true, 'Resuming writing process...');
        const response = await fetch(`/api/projects/${currentProgressProjectId}/resume`, { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            showNotification('Writing resumed', 'success');
            // Re-enable progress tracking
            startProgressTracking(currentProgressProjectId);
        } else {
            showNotification(data.error || 'Error resuming', 'error');
        }
    } catch (e) {
        showNotification('Error resuming project', 'error');
    }
    finally { showLoading(false); }
}

async function stopWriting(projectId) {
    try {
        showLoading(true, 'Stopping...');
        const response = await fetch(`/api/projects/${projectId}/stop`, { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            loadProjects();
            showNotification('Writing stopped', 'success');
        }
    } catch (e) { showNotification('Error stopping project', 'error'); }
    finally { showLoading(false); }
}

async function deleteProject(projectId) {
    if (!confirm('Delete this manuscript permanently?')) return;
    try {
        showLoading(true, 'Deleting...');
        const response = await fetch(`/api/projects/${projectId}`, { method: 'DELETE' });
        const data = await response.json();
        if (data.success) {
            hideProjectDetailsModal();
            loadProjects();
            showNotification('Project deleted', 'success');
        }
    } catch (e) { showNotification('Error deleting project', 'error'); }
    finally { showLoading(false); }
}

async function downloadBook(projectId) {
    window.location.href = `/api/projects/${projectId}/download?download=true`;
}

async function viewChapter(filePath) {
    try {
        showLoading(true, 'Opening Chapter...');
        const response = await fetch(`/api/files/content?path=${encodeURIComponent(filePath)}`);
        const data = await response.json();
        
        if (data.success) {
            openMarkdownModal('Chapter Content', data.content);
        } else {
            showNotification('Failed to load chapter content', 'error');
        }
    } catch (error) {
        console.error('Error viewing chapter:', error);
        showNotification('Error loading chapter content', 'error');
    } finally {
        showLoading(false);
    }
}

function openMarkdownModal(title, content) {
    const modal = document.createElement('div');
    // Elegant dark backdrop with subtle grain
    modal.className = 'fixed inset-0 bg-canvas-dark/95 backdrop-blur-xl flex items-center justify-center z-[200] p-4 md:p-8 overflow-hidden';
    
    // Add noise overlay
    const noiseOverlay = document.createElement('div');
    noiseOverlay.className = 'fixed inset-0 pointer-events-none opacity-[0.025]';
    noiseOverlay.style.backgroundImage = `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`;
    modal.appendChild(noiseOverlay);
    
    // Split content into "pages" based on paragraph count or length
    const paragraphs = content.split('\n\n');
    const pages = [];
    let currentPage = [];
    let currentLength = 0;
    const MAX_PAGE_CHARS = 1800;
    
    paragraphs.forEach(p => {
        if (currentLength + p.length > MAX_PAGE_CHARS && currentPage.length > 0) {
            pages.push(`<article class="prose prose-slate dark:prose-invert prose-headings:font-display prose-headings:text-2xl prose-headings:font-medium prose-headings:mb-6 prose-p:font-serif prose-p:text-[1.125rem] prose-p:leading-[1.85] prose-p:mb-5 prose-p:text-slate-700 dark:prose-p:text-slate-300 max-w-none">${marked.parse(currentPage.join('\n\n'))}</article>`);
            currentPage = [];
            currentLength = 0;
        }
        currentPage.push(p);
        currentLength += p.length;
    });
    
    if (currentPage.length > 0) {
        pages.push(`<article class="prose prose-slate dark:prose-invert prose-headings:font-display prose-headings:text-2xl prose-headings:font-medium prose-headings:mb-6 prose-p:font-serif prose-p:text-[1.125rem] prose-p:leading-[1.85] prose-p:mb-5 prose-p:text-slate-700 dark:prose-p:text-slate-300 max-w-none">${marked.parse(currentPage.join('\n\n'))}</article>`);
    }

    let pageIdx = 0;
    let isAnimating = false;

    const renderPage = (idx, direction = 1) => {
        if (isAnimating || idx === pageIdx) return;
        isAnimating = true;
        
        const container = modal.querySelector('#book-container');
        const pageNum = modal.querySelector('#page-number');
        if (!container) {
            isAnimating = false;
            return;
        }
        
        // Elegant page turn animation
        container.style.transition = 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)';
        container.style.opacity = '0';
        container.style.transform = direction > 0 ? 'translateX(-30px) rotateY(-5deg)' : 'translateX(30px) rotateY(5deg)';
        
        setTimeout(() => {
            container.innerHTML = pages[idx];
            container.scrollTop = 0;
            container.style.transition = 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)';
            container.style.opacity = '1';
            container.style.transform = 'translateX(0) rotateY(0)';
            pageNum.textContent = `${idx + 1} / ${pages.length}`;
            
            // Update button states
            const prevBtn = modal.querySelector('#prev-page');
            const nextBtn = modal.querySelector('#next-page');
            prevBtn.style.opacity = idx === 0 ? '0.2' : '1';
            prevBtn.style.pointerEvents = idx === 0 ? 'none' : 'auto';
            nextBtn.style.opacity = idx === pages.length - 1 ? '0.2' : '1';
            nextBtn.style.pointerEvents = idx === pages.length - 1 ? 'none' : 'auto';
            
            isAnimating = false;
        }, 200);
        
        pageIdx = idx;
    };

    // Main container
    const container = document.createElement('div');
    container.className = 'relative z-10 flex flex-col items-center w-full max-w-5xl h-full max-h-[90vh]';
    container.innerHTML = `
        <!-- Header -->
        <div class="w-full flex justify-between items-center mb-6 px-2">
            <div class="flex flex-col">
                <span class="text-[10px] font-semibold uppercase tracking-[0.5em] text-accent/60 mb-1">Manuscript</span>
                <h3 class="font-display text-xl lg:text-2xl font-medium text-white/90">${title}</h3>
            </div>
            <button onclick="this.closest('.fixed').remove()" class="w-10 h-10 rounded-xl bg-white/5 hover:bg-white/10 flex items-center justify-center text-white/60 hover:text-white transition-all">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M6 18L18 6M6 6l12 12" />
                </svg>
            </button>
        </div>

        <!-- Book Area -->
        <div class="relative flex-1 w-full max-w-4xl mx-auto perspective-[2000px]">
            <!-- Prev Button - Fixed position -->
            <button id="prev-page" class="hidden sm:flex absolute left-[-80px] top-1/2 -translate-y-1/2 w-12 h-12 lg:w-14 lg:h-14 rounded-full bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-all duration-300 items-center justify-center z-20">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 19l-7-7 7-7" />
                </svg>
            </button>

            <!-- The Book -->
            <div class="relative w-full bg-[#faf9f5] dark:bg-[#1c1c1c] shadow-2xl rounded-r-sm border-l-[10px] border-slate-800 flex flex-col overflow-hidden transition-all duration-500 mx-auto" style="max-height: calc(90vh - 100px);">
                <!-- Spine -->
                <div class="absolute left-0 top-0 bottom-0 w-4 bg-gradient-to-r from-slate-900/40 to-transparent z-10"></div>
                
                <!-- Header with Title -->
                <div class="px-6 py-4 border-b border-slate-200/40 dark:border-white/5 flex items-center justify-between shrink-0">
                    <span class="text-[10px] font-semibold uppercase tracking-[0.5em] text-accent/60">Manuscript</span>
                    <span id="page-number" class="font-display text-sm text-slate-400 dark:text-slate-500 italic tracking-widest">${1} / ${pages.length}</span>
                </div>
                
                <!-- Content -->
                <div id="book-container" class="flex-1 py-10 px-12 lg:px-16 overflow-y-auto transition-all duration-400">
                    ${pages[0]}
                </div>
            </div>

            <!-- Next Button - Fixed position -->
            <button id="next-page" class="hidden sm:flex absolute right-[-80px] top-1/2 -translate-y-1/2 w-12 h-12 lg:w-14 lg:h-14 rounded-full bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-all duration-300 items-center justify-center z-20">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5l7 7-7 7" />
                </svg>
            </button>
        </div>

        <!-- Mobile Navigation -->
        <div class="flex sm:hidden gap-4 mt-4">
            <button id="prev-page-mobile" class="w-12 h-12 rounded-full bg-white/5 hover:bg-white/10 text-white/60 hover:text-white flex items-center justify-center transition-all">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 19l-7-7 7-7" />
                </svg>
            </button>
            <span class="flex items-center text-sm font-medium text-white/50 px-4">${1} / ${pages.length}</span>
            <button id="next-page-mobile" class="w-12 h-12 rounded-full bg-white/5 hover:bg-white/10 text-white/60 hover:text-white flex items-center justify-center transition-all">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5l7 7-7 7" />
                </svg>
            </button>
        </div>
    `;

    modal.appendChild(container);

    // Event handlers
    modal.querySelector('#prev-page').onclick = (e) => { 
        e.stopPropagation(); 
        renderPage(Math.max(0, pageIdx - 1), -1); 
    };
    modal.querySelector('#next-page').onclick = (e) => { 
        e.stopPropagation(); 
        renderPage(Math.min(pages.length - 1, pageIdx + 1), 1); 
    };
    
    const prevMobile = modal.querySelector('#prev-page-mobile');
    const nextMobile = modal.querySelector('#next-page-mobile');
    if (prevMobile) prevMobile.onclick = (e) => { e.stopPropagation(); renderPage(Math.max(0, pageIdx - 1), -1); };
    if (nextMobile) nextMobile.onclick = (e) => { e.stopPropagation(); renderPage(Math.min(pages.length - 1, pageIdx + 1), 1); };
    
    modal.addEventListener('click', (e) => {
        if (e.target === modal || e.target === noiseOverlay) modal.remove();
    });
    
    document.body.appendChild(modal);
}

async function sendCommand() {
    const input = document.getElementById('commandInput');
    const feed = document.getElementById('activityFeed');
    const sendBtn = document.getElementById('commandSendButton');
    
    if (!input || !input.value.trim() || !currentProgressProjectId) return;
    
    const message = input.value.trim();
    input.value = '';
    input.style.height = ''; // Reset height
    
    // Disable input while processing
    input.disabled = true;
    sendBtn.disabled = true;
    sendBtn.classList.add('opacity-50', 'cursor-not-allowed');

    // 1. Append User Message
    appendChatMessage('user', message);

    // 2. Prepare AI Message Container
    const aiMessageId = 'ai-' + Date.now();
    const aiContainer = appendChatMessage('assistant', '', aiMessageId);
    const contentEl = aiContainer.querySelector('.message-content');
    const toolContainer = aiContainer.querySelector('.tool-calls');
    
    let accumulatedContent = '';
    let currentToolCall = null;
    let sseBuffer = '';

    try {
        const response = await fetch(`/api/projects/${currentProgressProjectId}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, stream: true })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            sseBuffer += decoder.decode(value, { stream: true });
            const lines = sseBuffer.split('\n\n');
            sseBuffer = lines.pop(); // Keep partial line in buffer

            for (const line of lines) {
                if (line.trim().startsWith('data: ')) {
                    try {
                        const dataStr = line.trim().substring(6);
                        if (dataStr === '[DONE]') continue;
                        
                        const update = JSON.parse(dataStr);
                        
                        if (update.type === 'turn_start') {
                            accumulatedContent = '';
                        }
                        else if (update.type === 'content') {
                            accumulatedContent += update.data;
                            contentEl.innerHTML = marked.parse(accumulatedContent);
                            feed.scrollTop = feed.scrollHeight;
                        } 
                        else if (update.type === 'tool_call_start') {
                            const tc = update.data;
                            if (tc.id) {
                                addToolCallUI(toolContainer, { id: tc.id, function: { name: tc.name, arguments: '' } });
                                feed.scrollTop = feed.scrollHeight;
                            }
                        }
                        else if (update.type === 'tool_call') {
                            const tc = update.data;
                            if (tc.id) {
                                updateToolCallArgsUI(tc);
                                feed.scrollTop = feed.scrollHeight;
                            }
                        }
                        else if (update.type === 'tool_result') {
                            const result = update.data;
                            updateToolResultUI(toolContainer, result);
                            feed.scrollTop = feed.scrollHeight;
                        }
                        else if (update.type === 'suggestions') {
                            // Update proactive suggestions panel
                            updateAgentSuggestions(update.data);
                        }
                    } catch (e) {
                        console.error('Error parsing SSE line', e, line);
                    }
                }
            }
        }
    } catch (e) {
        console.error('Chat failed', e);
        showNotification('Communication lost with Supervisor AI', 'error');
    } finally {
        input.disabled = false;
        sendBtn.disabled = false;
        sendBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        input.focus();
    }
}

function appendChatMessage(role, content, id = null) {
    const feed = document.getElementById('activityFeed');
    const wrapper = document.createElement('div');
    wrapper.className = `flex flex-col ${role === 'user' ? 'items-end' : 'items-start'} animate-slide-in group`;
    if (id) wrapper.id = id;

    const isUser = role === 'user';
    
    wrapper.innerHTML = `
        <div class="flex items-center gap-2 mb-2 px-1">
            ${!isUser ? `
                <div class="w-6 h-6 bg-editorial-teal text-white rounded-lg flex items-center justify-center">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                </div>
                <span class="text-[10px] font-bold uppercase tracking-widest text-slate-400">Supervisor Agent</span>
            ` : `
                <span class="text-[10px] font-bold uppercase tracking-widest text-slate-400">You</span>
                <div class="w-6 h-6 bg-accent text-white rounded-lg flex items-center justify-center">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                </div>
            `}
        </div>
        
        <div class="max-w-[85%] lg:max-w-[75%] rounded-2xl p-5 ${isUser ? 'bg-accent text-white shadow-glow' : 'bg-white dark:bg-white/5 border border-surface-200 dark:border-white/10 shadow-sm'}">
            <div class="tool-calls space-y-3 mb-3"></div>
            <div class="message-content prose prose-sm dark:prose-invert max-w-none font-medium leading-relaxed">
                ${content ? marked.parse(content) : (isUser ? '' : '<span class="animate-pulse">...</span>')}
            </div>
        </div>
    `;
    
    feed.appendChild(wrapper);
    feed.scrollTop = feed.scrollHeight;
    return wrapper;
}

// ---------------------------------------------------------------------------
// Tool-call card rendering for the Supervisor AI chat drawer
// ---------------------------------------------------------------------------
// Friendly metadata + colour-coding per tool so cards read like an activity
// log ("Read File · chapters/chapter_1.md · Done") instead of a raw JSON dump.
const TOOL_META = {
    read_file:      { label: 'Read File',    color: 'teal',   blurb: 'Read a project file',
        icon: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253' },
    write_file:     { label: 'Write File',   color: 'accent', blurb: 'Create or overwrite a file',
        icon: 'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z' },
    edit_file:      { label: 'Edit File',    color: 'gold',   blurb: 'Search & replace text',
        icon: 'M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z' },
    list_directory: { label: 'List Files',   color: 'teal',   blurb: 'Browse project structure',
        icon: 'M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z' },
    search_files:   { label: 'Search Files', color: 'teal',   blurb: 'Glob file search',
        icon: 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z' },
    grep_search:    { label: 'Grep Content', color: 'teal',   blurb: 'Search file contents',
        icon: 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z' },
    delete_file:    { label: 'Delete File',  color: 'red',    blurb: 'Remove a file',
        icon: 'M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16' },
};
const TOOL_FALLBACK_META = { label: 'AI Tool', color: 'slate', blurb: '', icon: 'M11.42 15.17L17.25 21A2.652 2.652 0 0021 17.25l-5.83-5.83m1.41-1.41L17.25 8.99A2.652 2.652 0 0013 4.25L7.17 10.08m1.41 1.41L13 4.25' };

const TOOL_COLORS = {
    teal:   { dot: 'bg-editorial-teal', soft: 'bg-editorial-teal/10', text: 'text-editorial-teal', border: 'border-editorial-teal/30' },
    accent: { dot: 'bg-accent',          soft: 'bg-accent/10',        text: 'text-accent',          border: 'border-accent/30' },
    gold:   { dot: 'bg-editorial-gold',  soft: 'bg-editorial-gold/10',text: 'text-editorial-gold',  border: 'border-editorial-gold/30' },
    red:    { dot: 'bg-red-500',         soft: 'bg-red-500/10',       text: 'text-red-500',         border: 'border-red-500/30' },
    slate:  { dot: 'bg-slate-400',       soft: 'bg-surface-100 dark:bg-white/10', text: 'text-slate-500 dark:text-slate-300', border: 'border-surface-200 dark:border-white/10' },
};

function toolMeta(name) {
    return TOOL_META[name] || { ...TOOL_FALLBACK_META, label: name ? name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) : 'AI Tool' };
}

function addToolCallUI(container, tc) {
    const tcId = tc.id;
    if (!tcId) return; // Skip until we have an ID (args arrive in a later event)

    const rawName = (tc.function && tc.function.name) || '';
    const meta = toolMeta(rawName);
    const c = TOOL_COLORS[meta.color] || TOOL_COLORS.slate;

    const toolDiv = document.createElement('div');
    toolDiv.id = `tc-${tcId}`;
    toolDiv.className = `tool-card rounded-xl border ${c.border} bg-surface-50 dark:bg-black/20 overflow-hidden mb-3 animate-slide-in`;
    toolDiv.dataset.toolName = rawName;
    toolDiv.innerHTML = `
        <div class="flex items-center gap-3 px-3.5 py-3 cursor-pointer hover:bg-surface-100/60 dark:hover:bg-white/5 transition-colors" onclick="toggleToolDetails('${tcId}')" title="${meta.blurb}">
            <div class="w-8 h-8 rounded-lg ${c.soft} ${c.text} flex items-center justify-center shrink-0">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="${meta.icon}"/></svg>
            </div>
            <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                    <span class="text-xs font-bold text-slate-700 dark:text-slate-200">${escapeHtml(meta.label)}</span>
                    <span class="tool-status-badge inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${c.soft} ${c.text}">
                        <span class="status-dot w-1.5 h-1.5 rounded-full ${c.dot} animate-pulse"></span>
                        <span class="status-text">Running</span>
                    </span>
                </div>
                <div class="tool-args-chips mt-1 flex flex-wrap gap-1.5"></div>
            </div>
            <svg id="icon-${tcId}" class="w-4 h-4 transition-transform text-slate-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            </svg>
        </div>
        <div id="details-${tcId}" class="px-3.5 pb-3.5 space-y-2.5 hidden border-t border-surface-200 dark:border-white/5">
            <div class="args-section hidden">
                <div class="flex items-center justify-between mb-1 mt-3">
                    <span class="text-[9px] font-bold text-slate-400 uppercase tracking-widest">Parameters</span>
                    <button class="tool-copy-btn inline-flex items-center gap-1 text-[9px] font-semibold text-slate-400 hover:text-accent transition-colors" onclick="copyToolText(this, this.closest('.args-section').querySelector('.args-pre').textContent)">
                        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>
                        Copy
                    </button>
                </div>
                <pre class="args-pre text-[11px] font-mono bg-black/30 p-2.5 rounded-lg overflow-x-auto text-editorial-teal whitespace-pre-wrap break-words"></pre>
            </div>
            <div class="tool-result-status text-[10px] font-medium text-slate-400 italic flex items-center gap-2 pt-2">
                <svg class="w-3 h-3 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.001 0 01-15.357-2m15.357 2H15"/></svg>
                <span class="status-detail">Executing tool...</span>
            </div>
        </div>
    `;
    container.appendChild(toolDiv);
}

// Fill in argument chips + the full Parameters JSON once the tool_call event
// arrives (args stream in after the tool_call_start event).
function updateToolCallArgsUI(tc) {
    const toolDiv = document.getElementById(`tc-${tc.id}`);
    if (!toolDiv) return;

    let args = {};
    try { args = JSON.parse((tc.function && tc.function.arguments) || '{}'); }
    catch (e) { return; /* partial JSON — wait for the complete event */ }
    delete args.project_id;

    const chipsEl = toolDiv.querySelector('.tool-args-chips');
    if (chipsEl) chipsEl.innerHTML = buildArgChips(toolDiv.dataset.toolName, args).join('');

    const argsStr = Object.keys(args).length > 0 ? JSON.stringify(args, null, 2) : '';
    const argsSection = toolDiv.querySelector('.args-section');
    const pre = toolDiv.querySelector('.args-pre');
    if (argsSection && pre) {
        if (argsStr) {
            pre.textContent = argsStr;
            argsSection.classList.remove('hidden');
        } else {
            argsSection.classList.add('hidden');
        }
    }
}

// Surface the most meaningful argument as a compact pill so the user can see
// what the agent is doing without expanding the card.
function buildArgChips(toolName, args) {
    const chip = (label, value, mono = true) => `<span class="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded-md bg-surface-100 dark:bg-white/10 text-slate-500 dark:text-slate-300 max-w-full"><span class="opacity-60 shrink-0">${label}</span><span class="${mono ? 'font-mono text-slate-600 dark:text-slate-200' : ''} truncate max-w-[160px]">${escapeHtml(String(value))}</span></span>`;
    const out = [];
    if (args.path) out.push(chip('path:', args.path));
    if (args.directory) out.push(chip('dir:', args.directory));
    if (args.pattern) out.push(chip('glob:', args.pattern));
    if (args.query) out.push(chip('query:', `"${args.query}"`));
    if (args.search_text) out.push(chip('for:', `"${args.search_text}"`));
    if (args.old_text != null) out.push(chip('old:', `${String(args.old_text).length} chars`, false));
    if (args.new_text != null) out.push(chip('new:', `${String(args.new_text).length} chars`, false));
    if (args.line_start != null && args.line_end != null) out.push(chip('lines:', `${args.line_start}-${args.line_end}`));
    if (args.content != null) {
        const s = String(args.content);
        const words = s.trim() ? s.trim().split(/\s+/).length : 0;
        out.push(chip('content:', `${s.length} chars · ~${words} words`, false));
    }
    return out;
}

// Turn a tool result into a one-line summary + a renderable output block.
// The point is to avoid dumping raw JSON into the chat: a 1.2k-line chapter
// reads as "Read 234 lines · 12,000 chars", with the full text available on
// expand for those who want it.
function summarizeResult(toolName, res, success, error) {
    if (!success) return { summary: `Failed: ${error || 'Unknown error'}`, ok: false };
    if (!res || typeof res !== 'object') return { summary: 'Completed', ok: true };

    switch (toolName) {
        case 'read_file': {
            const content = res.content || '';
            const lines = (res.total_lines != null ? res.total_lines : content.split('\n').length);
            return {
                summary: `Read ${lines} line${lines === 1 ? '' : 's'} · ${content.length.toLocaleString()} chars${res.truncated ? ' · truncated' : ''}`,
                ok: true, output: content, outputLabel: 'File content',
            };
        }
        case 'write_file':
            return { summary: res.path ? `Saved ${res.path}` : 'File written', ok: true };
        case 'edit_file':
            return { summary: `${res.replacements || 0} replacement${(res.replacements || 0) === 1 ? '' : 's'} made in ${res.path || 'file'}`, ok: true };
        case 'delete_file':
            return { summary: res.path ? `Deleted ${res.path}` : 'File deleted', ok: true };
        case 'list_directory': {
            const items = res.entries || [];
            const files = items.filter(i => i.type === 'file').length;
            const dirs = items.filter(i => i.type === 'directory').length;
            return { summary: `${items.length} entries · ${files} file${files===1?'':'s'}, ${dirs} dir${dirs===1?'':'s'}`, ok: true, output: items, outputLabel: 'Listing', kind: 'list-dir' };
        }
        case 'search_files': {
            const items = res.matches || [];
            return { summary: `${items.length} file${items.length === 1 ? '' : 's'} matched`, ok: true, output: items, outputLabel: 'Files', kind: 'list-paths' };
        }
        case 'grep_search': {
            const items = res.matches || [];
            return { summary: `${res.count != null ? res.count : items.length} match${(res.count || items.length) === 1 ? '' : 'es'}${res.truncated ? ' · truncated' : ''}`, ok: true, output: items, outputLabel: 'Matches', kind: 'list-grep' };
        }
        default:
            return { summary: 'Completed', ok: true, output: JSON.stringify(res, null, 2), outputLabel: 'Result', kind: 'json' };
    }
}

function updateToolResultUI(container, result) {
    const toolDiv = document.getElementById(`tc-${result.tool_call_id}`);
    if (!toolDiv) return;

    const meta = toolMeta(toolDiv.dataset.toolName);
    const c = TOOL_COLORS[meta.color] || TOOL_COLORS.slate;
    const summary = summarizeResult(toolDiv.dataset.toolName, result.result, result.success, result.error);

    // 1. Header status badge
    const statusText = toolDiv.querySelector('.status-text');
    const statusDot = toolDiv.querySelector('.status-dot');
    const badge = toolDiv.querySelector('.tool-status-badge');
    if (statusText) statusText.textContent = summary.ok ? 'Done' : 'Failed';
    if (statusDot) {
        statusDot.classList.remove('animate-pulse');
        statusDot.classList.toggle(c.dot, !!summary.ok);
        if (!summary.ok) statusDot.classList.add('bg-red-500');
    }
    if (badge && !summary.ok) {
        badge.classList.remove(c.soft, c.text);
        badge.classList.add('bg-red-500/10', 'text-red-500');
    }

    // 2. Status detail line (inside details) + output block
    const detailsEl = toolDiv.querySelector(`#details-${result.tool_call_id}`);
    const statusEl = toolDiv.querySelector('.tool-result-status');
    if (statusEl) {
        statusEl.classList.remove('italic');
        statusEl.innerHTML = summary.ok
            ? `<svg class="w-3 h-3 text-editorial-teal shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/></svg><span class="not-italic text-slate-500 dark:text-slate-300">${escapeHtml(summary.summary)}</span>`
            : `<svg class="w-3 h-3 text-red-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/></svg><span class="not-italic text-red-500">${escapeHtml(summary.summary)}</span>`;
    }

    if (detailsEl && summary.output != null && summary.output !== '') {
        detailsEl.appendChild(buildOutputBlock(summary, meta, c));
    }

    // 3. Auto-expand only on failure (success stays collapsed — the header
    // summary already tells the story, and read_file output can be huge).
    if (!summary.ok) {
        toggleToolDetails(result.tool_call_id, true);
    }
}

// Render the output area according to the tool kind: pretty lists for
// list/search/grep, truncated text for file reads, JSON fallback otherwise.
function buildOutputBlock(summary, meta, c) {
    const wrap = document.createElement('div');
    wrap.className = 'output-section pt-2';

    const headerHtml = `
        <div class="flex items-center justify-between mb-1">
            <span class="text-[9px] font-bold text-slate-400 uppercase tracking-widest">${summary.outputLabel}</span>
            <button class="tool-copy-btn inline-flex items-center gap-1 text-[9px] font-semibold text-slate-400 hover:text-accent transition-colors" onclick="copyToolText(this, this.closest('.output-section').querySelector('pre').textContent)">
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>
                Copy
            </button>
        </div>`;

    if (summary.kind === 'list-dir') {
        const rows = summary.output.map(i => `<div class="flex items-center gap-2 py-0.5 text-[11px]"><span class="${i.type === 'directory' ? 'text-editorial-gold' : 'text-editorial-teal'}">${i.type === 'directory' ? '📁' : '📄'}</span><span class="font-mono text-slate-600 dark:text-slate-300 truncate">${escapeHtml(i.path)}</span>${i.size != null ? `<span class="text-slate-400 ml-auto shrink-0">${humanSize(i.size)}</span>` : ''}</div>`).join('');
        wrap.innerHTML = headerHtml + `<div class="bg-black/20 rounded-lg p-2 max-h-48 overflow-y-auto">${rows}</div>`;
        return wrap;
    }
    if (summary.kind === 'list-paths') {
        const rows = summary.output.map(p => `<div class="flex items-center gap-2 py-0.5 text-[11px]"><span class="text-editorial-teal">📄</span><span class="font-mono text-slate-600 dark:text-slate-300 truncate">${escapeHtml(p)}</span></div>`).join('') || '<div class="text-[11px] text-slate-400 italic">No files found</div>';
        wrap.innerHTML = headerHtml + `<div class="bg-black/20 rounded-lg p-2 max-h-48 overflow-y-auto">${rows}</div>`;
        return wrap;
    }
    if (summary.kind === 'list-grep') {
        const rows = summary.output.map(m => `<div class="py-1 text-[11px] border-b border-white/5 last:border-0"><div class="flex items-center gap-2"><span class="text-editorial-teal">·</span><span class="font-mono text-slate-600 dark:text-slate-300 truncate">${escapeHtml(m.file)}:${m.line}</span></div><div class="font-mono text-slate-500 dark:text-slate-400 truncate pl-4">${escapeHtml(m.match)}</div></div>`).join('') || '<div class="text-[11px] text-slate-400 italic">No matches</div>';
        wrap.innerHTML = headerHtml + `<div class="bg-black/20 rounded-lg p-2 max-h-48 overflow-y-auto">${rows}</div>`;
        return wrap;
    }

    // Text / JSON output — truncate big payloads so the chat stays readable.
    let text = typeof summary.output === 'string' ? summary.output : JSON.stringify(summary.output, null, 2);
    const MAX = 1500;
    let truncated = false;
    if (text.length > MAX) { text = text.substring(0, MAX); truncated = true; }
    wrap.innerHTML = headerHtml + `<pre class="text-[11px] font-mono bg-black/30 p-2.5 rounded-lg overflow-x-auto text-slate-300 dark:text-slate-200 max-h-56 overflow-y-auto whitespace-pre-wrap break-words">${escapeHtml(text)}${truncated ? '\n\n<span class="text-slate-500">… output truncated (use the tool to view full file)</span>' : ''}</pre>`;
    return wrap;
}

function humanSize(bytes) {
    if (bytes == null) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function copyToolText(btn, text) {
    const done = () => {
        const label = btn.querySelector('span') || btn.lastChild;
        const orig = btn.innerHTML;
        btn.innerHTML = '<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg> Copied';
        setTimeout(() => { btn.innerHTML = orig; }, 1200);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done).catch(() => {});
    } else {
        const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); done(); } catch (e) {}
        ta.remove();
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
}

function toggleToolDetails(tcId, forceOpen = false) {
    const details = document.getElementById(`details-${tcId}`);
    const icon = document.getElementById(`icon-${tcId}`);
    if (details && icon) {
        if (forceOpen) {
            details.classList.remove('hidden');
            icon.classList.add('rotate-180');
        } else {
            details.classList.toggle('hidden');
            icon.classList.toggle('rotate-180');
        }
    }
}

function fillCommand(text) {
    const input = document.getElementById('commandInput');
    if (input) {
        input.value = text;
        input.focus();
    }
}

async function applyPreset(presetName) {
    try {
        showLoading(true, 'Applying Preset...');
        const response = await fetch(`/api/llm/preset/${presetName}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        if (data.success) {
            showNotification(`Applied ${presetName} preset`, 'success');
            loadSettingsIntoForm();
        }
    } catch (e) {
        showNotification('Failed to apply preset', 'error');
    } finally {
        showLoading(false);
    }
}

async function loadSettingsIntoForm() {
    try {
        const response = await fetch('/api/llm/config');
        const data = await response.json();
        if (data.success) {
            const config = data.config;
            const modelEl = document.getElementById('llmModel');
            const tempEl = document.getElementById('llmTemperature');
            const tokensEl = document.getElementById('llmMaxTokens');
            const tempValEl = document.getElementById('temperatureValue');
            
            if (modelEl) modelEl.value = config.model || '';
            if (tempEl) tempEl.value = config.temperature || 0.7;
            if (tokensEl) tokensEl.value = config.max_tokens || 4096;
            if (tempValEl) tempValEl.textContent = config.temperature || 0.7;
        }
    } catch (e) { console.error('Error loading settings:', e); }
}

async function setupSettingsEventListeners() {
    const testBtn = document.getElementById('testConnectionBtn');
    const saveLLMBtn = document.getElementById('saveLLMBtn');
    const saveWritingBtn = document.getElementById('saveWritingBtn');
    const clearBtn = document.getElementById('clearProjectsBtn');
    const tempEl = document.getElementById('llmTemperature');
    const tempValEl = document.getElementById('temperatureValue');

    if (tempEl && tempValEl) {
        tempEl.addEventListener('input', (e) => {
            tempValEl.textContent = e.target.value;
        });
    }

    if (testBtn) testBtn.onclick = async () => {
        try {
            showLoading(true, 'Testing Connection...');
            const response = await fetch('/api/llm/test', { method: 'POST' });
            const data = await response.json();
            if (data.success) showNotification('Connection successful!', 'success');
            else showNotification('Connection failed: ' + data.error, 'error');
        } catch (e) { showNotification('Test failed', 'error'); }
        finally { showLoading(false); }
    };

    if (saveLLMBtn) saveLLMBtn.onclick = async () => {
        const config = {
            model: document.getElementById('llmModel').value,
            api_key: document.getElementById('llmApiKey').value,
            base_url: document.getElementById('llmBaseUrl').value,
            temperature: parseFloat(document.getElementById('llmTemperature').value),
            max_tokens: parseInt(document.getElementById('llmMaxTokens').value)
        };
        try {
            showLoading(true, 'Saving Config...');
            const response = await fetch('/api/llm/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            const data = await response.json();
            if (data.success) showNotification('Configuration saved', 'success');
            else showNotification('Save failed: ' + data.error, 'error');
        } catch (e) { showNotification('Save failed', 'error'); }
        finally { showLoading(false); }
    };

    if (saveWritingBtn) saveWritingBtn.onclick = async () => {
        const writingConfig = {
            defaultTargetLength: document.getElementById('defaultTargetLength').value,
            defaultGenre: document.getElementById('defaultGenre').value,
            expertMode: document.getElementById('expertMode').checked
        };
        try {
            showLoading(true, 'Saving Writing Settings...');
            const response = await fetch('/api/writing/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(writingConfig)
            });
            const data = await response.json();
            if (data.success) showNotification('Writing settings saved', 'success');
            else showNotification('Save failed: ' + data.error, 'error');
        } catch (e) { showNotification('Save failed', 'error'); }
        finally { showLoading(false); }
    };

    if (clearBtn) clearBtn.onclick = async () => {
        if (!confirm('Clear ALL projects? This is permanent.')) return;
        try {
            showLoading(true, 'Clearing Library...');
            // This would need a backend endpoint for bulk delete, 
            // but for now we'll just notify or implement if endpoint exists
            showNotification('Bulk clear not implemented in backend yet', 'error');
        } finally { showLoading(false); }
    };
}

// Utils
function showLoading(show, text) {
    const overlay = document.getElementById('loadingOverlay');
    const label = document.getElementById('loadingText');
    if (!overlay || !label) return;
    if (show) {
        label.textContent = text;
        overlay.classList.remove('hidden');
    } else {
        setTimeout(() => {
            overlay.classList.add('hidden');
        }, 300);
    }
}

function showNotification(msg, type) {
    const div = document.createElement('div');
    div.className = `fixed bottom-6 right-6 px-6 py-3.5 rounded-xl shadow-lg font-medium text-sm z-[200] animate-slide-in ${
        type === 'success' ? 'bg-editorial-teal text-white' : 'bg-red-500 text-white'
    }`;
    div.textContent = msg;
    document.body.appendChild(div);
    setTimeout(() => div.remove(), 3000);
}

async function checkLLMStatus() {
    try {
        const response = await fetch('/api/llm/config');
        const data = await response.json();
        if (data.success) {
            document.getElementById('llmStatus').classList.remove('hidden');
        }
    } catch (e) {}
}

// Story Arc Visualization Functions
function openStoryArcModal(projectId) {
    const modal = document.getElementById('storyArcModal');
    const content = document.getElementById('storyArcContent');
    
    modal.classList.remove('hidden');
    
    // Fetch story arc data
    fetch(`/api/projects/${projectId}/story-arc`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                content.innerHTML = data.html_visualization || '<div class="text-center text-slate-500 dark:text-slate-400 py-12">No story arc data available yet.</div>';
            } else {
                content.innerHTML = `<div class="text-center text-red-500 py-12">Error loading story arc: ${data.error || 'Unknown error'}</div>`;
            }
        })
        .catch(error => {
            console.error('Error loading story arc:', error);
            content.innerHTML = '<div class="text-center text-red-500 py-12">Error loading story arc visualization.</div>';
        });
}

function closeStoryArcModal() {
    const modal = document.getElementById('storyArcModal');
    modal.classList.add('hidden');
}

// Version Diff View Functions
function openVersionDiffModal(projectId, chapterNum, v1, v2) {
    const modal = document.getElementById('versionDiffModal');
    const title = document.getElementById('diffTitle');
    const content = document.getElementById('diffContent');
    
    title.textContent = `Chapter ${chapterNum}: Version ${v1} → Version ${v2}`;
    modal.classList.remove('hidden');
    
    // Fetch version diff data
    fetch(`/api/projects/${projectId}/chapters/${chapterNum}/diff?v1=${v1}&v2=${v2}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                content.innerHTML = `
                    <div class="mb-4">
                        <h4 class="text-sm font-bold text-slate-900 dark:text-white mb-2">Version Comparison Summary</h4>
                        <p class="text-sm text-slate-600 dark:text-slate-300">${data.changes_summary || 'No changes summary available'}</p>
                    </div>
                ` + (data.diff_html || '<div class="text-center text-slate-500 dark:text-slate-400 py-12">No diff data available.</div>');
            } else {
                content.innerHTML = `<div class="text-center text-red-500 py-12">Error loading version diff: ${data.error || 'Unknown error'}</div>`;
            }
        })
        .catch(error => {
            console.error('Error loading version diff:', error);
            content.innerHTML = '<div class="text-center text-red-500 py-12">Error loading version comparison.</div>';
        });
}

function closeVersionDiffModal() {
    const modal = document.getElementById('versionDiffModal');
    modal.classList.add('hidden');
}

// Update agent suggestions based on project state
function updateAgentSuggestions(suggestions) {
    const content = document.getElementById('suggestionsContent');
    const noSuggestions = document.getElementById('noSuggestions');
    
    if (!suggestions || suggestions.length === 0) {
        if (noSuggestions) noSuggestions.classList.remove('hidden');
        // Remove any existing suggestion cards
        if (content) {
            const cards = content.querySelectorAll('.suggestion-card');
            cards.forEach(card => card.remove());
        }
        return;
    }
    
    if (noSuggestions) noSuggestions.classList.add('hidden');
    
    if (content) {
        // Clear existing suggestions
        const cards = content.querySelectorAll('.suggestion-card');
        cards.forEach(card => card.remove());
        
        // Add new suggestion cards
        suggestions.forEach(sugg => {
            const card = document.createElement('div');
            card.className = 'suggestion-card bg-white dark:bg-white/5 border border-surface-200 dark:border-white/10 rounded-xl p-3 cursor-pointer hover:border-editorial-teal/30 transition-all animate-slide-in';
            card.onclick = () => handleSuggestionClick(sugg);
            
            let iconSvg = '';
            if (sugg.type === 'editing_suggestion') {
                iconSvg = '<svg class="w-4 h-4 text-editorial-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9l-2.828-2.828z" /></svg>';
            } else if (sugg.type === 'consistency_check' || sugg.type === 'consistency_review') {
                iconSvg = '<svg class="w-4 h-4 text-editorial-teal" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>';
            } else if (sugg.type === 'export_suggestion') {
                iconSvg = '<svg class="w-4 h-4 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>';
            } else if (sugg.type === 'outline_review') {
                iconSvg = '<svg class="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>';
            }
            
            card.innerHTML = `
                <div class="flex items-start gap-3">
                    ${iconSvg}
                    <div>
                        <div class="text-xs font-bold text-slate-900 dark:text-white mb-1">${sugg.title}</div>
                        <div class="text-[12px] text-slate-600 dark:text-slate-300 leading-relaxed">${sugg.description}</div>
                    </div>
                </div>
            `;
            
            content.appendChild(card);
        });
    }
}

function handleSuggestionClick(suggestion) {
    // Generate a command based on the suggestion
    let command = '';
    if (suggestion.type === 'editing_suggestion') {
        command = 'Please start the editing phase to review and improve all chapters.';
    } else if (suggestion.type === 'consistency_check' || suggestion.type === 'consistency_review') {
        command = 'Please check character and location consistency across all chapters using grep_search.';
    } else if (suggestion.type === 'export_suggestion') {
        command = 'How can I export my book? What formats are available?';
    } else if (suggestion.type === 'outline_review') {
        command = 'Let me review the chapter outline and make any necessary adjustments.';
    }
    
    // Open chat drawer and set the command
    const input = document.getElementById('commandInput');
    if (input) {
        input.value = command;
        toggleChat(true);
        setTimeout(() => input.focus(), 600);
    }
}

function autoRefresh() {
    if (!currentProgressProjectId) loadProjects();
}
