// Dashboard Module
window.Dashboard = {
    stats: {
        totalApplications: 0,
        activeCandidates: 0,
        avgMatchScore: 0,
        avgTimeToHire: 12
    },
    
    charts: {},
    
    async load() {
        await this.loadDashboardData();
        this.render();
    },

    async loadDashboardData() {
        try {
            // Load recent resumes
            const resumes = await window.atsApi.getAllResumes();
            
            // Calculate statistics from real data
            const completedResumes = resumes.filter(r => r.status === 'completed' && r.analysis);
            const processingResumes = resumes.filter(r => r.status === 'processing');
            
            // Calculate average score
            let totalScore = 0;
            let scoreCount = 0;
            const scores = [];
            
            for (const resume of completedResumes) {
                if (resume.analysis) {
                    totalScore += resume.analysis.overallScore;
                    scoreCount++;
                    scores.push(resume.analysis.overallScore);
                }
            }

            const avgScore = scoreCount > 0 ? Math.round(totalScore / scoreCount) : 0;

            this.stats = {
                totalApplications: resumes.length,
                activeCandidates: completedResumes.length,
                avgMatchScore: avgScore,
                avgTimeToHire: 12
            };

            this.recentResumes = resumes.slice(0, 4);
            this.processingQueue = processingResumes.slice(0, 4);
            this.chartData = this.generateChartData(resumes, completedResumes, scores);
            
        } catch (error) {
            console.error('Failed to load dashboard data:', error);
        }
    },

    generateChartData(resumes, completedResumes, scores) {
        // Monthly applications data
        const monthlyData = this.generateMonthlyData(resumes);
        
        // Skills distribution
        const skillsData = this.generateSkillsDistribution(completedResumes);
        
        // Score distribution
        const scoreDistData = this.generateScoreDistribution(scores);

        return {
            monthly: monthlyData,
            skills: skillsData,
            scores: scoreDistData
        };
    },

    generateMonthlyData(resumes) {
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'];
        const data = months.map(month => ({
            month,
            applications: Math.floor(Math.random() * 30) + 10
        }));
        
        // Add some resumes to current month
        if (resumes.length > 0) {
            data[data.length - 1].applications += resumes.length;
        }
        
        return data;
    },

    generateSkillsDistribution(resumes) {
        const skillCount = {};
        
        resumes.forEach(resume => {
            if (resume.analysis?.skills) {
                resume.analysis.skills.forEach(skill => {
                    skillCount[skill.name] = (skillCount[skill.name] || 0) + 1;
                });
            }
        });

        const sortedSkills = Object.entries(skillCount)
            .sort(([,a], [,b]) => b - a)
            .slice(0, 5);

        if (sortedSkills.length === 0) {
            return [
                { label: 'JavaScript', value: 15 },
                { label: 'Python', value: 12 },
                { label: 'React', value: 10 },
                { label: 'Node.js', value: 8 },
                { label: 'SQL', value: 6 }
            ];
        }

        return sortedSkills.map(([label, value]) => ({ label, value }));
    },

    generateScoreDistribution(scores) {
        const ranges = [
            { range: '0-40', count: 0 },
            { range: '41-60', count: 0 },
            { range: '61-80', count: 0 },
            { range: '81-100', count: 0 }
        ];

        scores.forEach(score => {
            if (score <= 40) ranges[0].count++;
            else if (score <= 60) ranges[1].count++;
            else if (score <= 80) ranges[2].count++;
            else ranges[3].count++;
        });

        return ranges;
    },

    render() {
        const tabElement = document.getElementById('dashboard-tab');
        tabElement.innerHTML = `
            <div class="space-y-6">
                <!-- Header -->
                <div class="flex flex-col lg:flex-row lg:justify-between lg:items-center gap-4">
                    <div>
                        <h1 class="text-3xl bg-gradient-to-r from-purple-600 to-teal-600 bg-clip-text text-transparent">
                            ATS Resume Analyzer
                        </h1>
                        <p class="text-gray-600 mt-1">AI-powered recruitment insights and candidate analysis.</p>
                    </div>
                    <div class="flex items-center gap-4">
                        <div class="flex items-center gap-2 px-4 py-2 rounded-xl text-sm bg-blue-100 text-blue-700 border border-blue-200">
                            <i data-lucide="info" class="w-4 h-4"></i>
                            <span>Demo Mode</span>
                        </div>
                        <button onclick="Dashboard.refresh()" class="p-2 glass border border-white/30 rounded-xl hover:bg-white/30 transition-colors">
                            <i data-lucide="refresh-cw" class="w-4 h-4 text-gray-700"></i>
                        </button>
                        <div class="glass border border-white/30 rounded-xl px-6 py-3 shadow-lg">
                            <span class="text-sm text-gray-700">
                                Updated: ${new Date().toLocaleTimeString()}
                            </span>
                        </div>
                    </div>
                </div>

                <!-- Mode Information Banner -->
                <div class="glass border-blue-200 rounded-2xl p-6 shadow-xl bg-blue-50/50">
                    <div class="flex items-start gap-4">
                        <i data-lucide="info" class="w-6 h-6 text-blue-600 flex-shrink-0 mt-1"></i>
                        <div class="flex-1">
                            <h3 class="text-lg text-blue-800 mb-2">Demo Mode Active</h3>
                            <p class="text-sm text-blue-700 mb-3">
                                You're experiencing the full ATS interface with realistic demo data. All features are functional for testing and exploration.
                            </p>
                            <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                                <div class="flex items-center gap-2 text-xs text-blue-700">
                                    <i data-lucide="check-circle" class="w-3 h-3"></i>
                                    <span>Interactive UI demonstration</span>
                                </div>
                                <div class="flex items-center gap-2 text-xs text-blue-700">
                                    <i data-lucide="check-circle" class="w-3 h-3"></i>
                                    <span>Realistic analysis results</span>
                                </div>
                                <div class="flex items-center gap-2 text-xs text-blue-700">
                                    <i data-lucide="check-circle" class="w-3 h-3"></i>
                                    <span>Chart visualizations</span>
                                </div>
                                <div class="flex items-center gap-2 text-xs text-blue-700">
                                    <i data-lucide="check-circle" class="w-3 h-3"></i>
                                    <span>Export functionality</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Stats Grid -->
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    <div class="glass rounded-2xl p-6 shadow-xl hover:shadow-2xl transition-all duration-300 hover:scale-105">
                        <div class="flex items-center justify-between">
                            <div class="w-12 h-12 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl flex items-center justify-center shadow-lg">
                                <i data-lucide="file-text" class="w-6 h-6 text-white"></i>
                            </div>
                            <div class="flex items-center text-green-600">
                                <i data-lucide="trending-up" class="w-4 h-4 mr-1"></i>
                                <span class="text-sm">+12%</span>
                            </div>
                        </div>
                        <div class="mt-4">
                            <h3 class="text-2xl text-gray-800">${this.stats.totalApplications.toLocaleString()}</h3>
                            <p class="text-sm text-gray-600 mt-1">Total Resumes</p>
                        </div>
                    </div>

                    <div class="glass rounded-2xl p-6 shadow-xl hover:shadow-2xl transition-all duration-300 hover:scale-105">
                        <div class="flex items-center justify-between">
                            <div class="w-12 h-12 bg-gradient-to-br from-blue-500 to-teal-500 rounded-xl flex items-center justify-center shadow-lg">
                                <i data-lucide="users" class="w-6 h-6 text-white"></i>
                            </div>
                            <div class="flex items-center text-green-600">
                                <i data-lucide="trending-up" class="w-4 h-4 mr-1"></i>
                                <span class="text-sm">+8%</span>
                            </div>
                        </div>
                        <div class="mt-4">
                            <h3 class="text-2xl text-gray-800">${this.stats.activeCandidates}</h3>
                            <p class="text-sm text-gray-600 mt-1">Analyzed Candidates</p>
                        </div>
                    </div>

                    <div class="glass rounded-2xl p-6 shadow-xl hover:shadow-2xl transition-all duration-300 hover:scale-105">
                        <div class="flex items-center justify-between">
                            <div class="w-12 h-12 bg-gradient-to-br from-teal-500 to-green-500 rounded-xl flex items-center justify-center shadow-lg">
                                <i data-lucide="star" class="w-6 h-6 text-white"></i>
                            </div>
                            <div class="flex items-center text-green-600">
                                <i data-lucide="trending-up" class="w-4 h-4 mr-1"></i>
                                <span class="text-sm">+5%</span>
                            </div>
                        </div>
                        <div class="mt-4">
                            <h3 class="text-2xl text-gray-800">${this.stats.avgMatchScore}%</h3>
                            <p class="text-sm text-gray-600 mt-1">Avg. Match Score</p>
                        </div>
                    </div>

                    <div class="glass rounded-2xl p-6 shadow-xl hover:shadow-2xl transition-all duration-300 hover:scale-105">
                        <div class="flex items-center justify-between">
                            <div class="w-12 h-12 bg-gradient-to-br from-orange-500 to-red-500 rounded-xl flex items-center justify-center shadow-lg">
                                <i data-lucide="clock" class="w-6 h-6 text-white"></i>
                            </div>
                            <div class="flex items-center text-red-600">
                                <i data-lucide="activity" class="w-4 h-4 mr-1"></i>
                                <span class="text-sm">-2 days</span>
                            </div>
                        </div>
                        <div class="mt-4">
                            <h3 class="text-2xl text-gray-800">${this.stats.avgTimeToHire} days</h3>
                            <p class="text-sm text-gray-600 mt-1">Avg. Processing Time</p>
                        </div>
                    </div>
                </div>

                <!-- Charts Section -->
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <!-- Monthly Applications Chart -->
                    <div class="glass rounded-2xl p-6 shadow-xl">
                        <div class="flex justify-between items-center mb-6">
                            <h3 class="text-lg text-gray-800">Monthly Applications</h3>
                            <button class="p-2 hover:bg-white/10 rounded-lg transition-colors">
                                <i data-lucide="more-vertical" class="w-4 h-4 text-gray-600"></i>
                            </button>
                        </div>
                        <div class="chart-container">
                            <canvas id="monthlyChart"></canvas>
                        </div>
                    </div>

                    <!-- Skills Distribution Chart -->
                    <div class="glass rounded-2xl p-6 shadow-xl">
                        <div class="flex justify-between items-center mb-6">
                            <h3 class="text-lg text-gray-800">Top Skills Detected</h3>
                            <button class="p-2 hover:bg-white/10 rounded-lg transition-colors">
                                <i data-lucide="more-vertical" class="w-4 h-4 text-gray-600"></i>
                            </button>
                        </div>
                        <div class="chart-container">
                            <canvas id="skillsChart"></canvas>
                        </div>
                    </div>
                </div>

                <!-- Processing Queue & Recent Resumes -->
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <!-- Processing Queue -->
                    <div class="glass rounded-2xl p-6 shadow-xl">
                        <div class="flex justify-between items-center mb-6">
                            <h3 class="text-lg text-gray-800">Processing Queue</h3>
                            <span class="text-sm text-gray-600">${this.processingQueue.length} active</span>
                        </div>
                        ${this.renderProcessingQueue()}
                    </div>

                    <!-- Recent Resumes -->
                    <div class="glass rounded-2xl p-6 shadow-xl">
                        <div class="flex justify-between items-center mb-6">
                            <h3 class="text-lg text-gray-800">Recent Resumes</h3>
                            <button class="text-sm text-purple-600 hover:text-purple-700 transition-colors">
                                View All
                            </button>
                        </div>
                        ${this.renderRecentResumes()}
                    </div>
                </div>

                <!-- Score Distribution -->
                <div class="glass rounded-2xl p-6 shadow-xl">
                    <h3 class="text-lg text-gray-800 mb-6">Score Distribution</h3>
                    <div class="chart-container">
                        <canvas id="scoresChart"></canvas>
                    </div>
                </div>
            </div>
        `;

        // Recreate icons and initialize charts
        lucide.createIcons();
        this.initializeCharts();
    },

    renderProcessingQueue() {
        if (this.processingQueue.length === 0) {
            return `
                <div class="text-center py-8 text-gray-500">
                    <i data-lucide="clock" class="w-12 h-12 mx-auto mb-2 opacity-50"></i>
                    <p>No resumes processing</p>
                </div>
            `;
        }

        return `
            <div class="space-y-4">
                ${this.processingQueue.map((item, index) => `
                    <div class="flex items-center justify-between p-3 glass bg-white/5 border border-white/10 rounded-xl">
                        <div class="flex items-center gap-3">
                            <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                            <span class="text-sm text-gray-700 truncate max-w-48">${item.filename}</span>
                        </div>
                        <div class="flex items-center gap-2">
                            <div class="w-16 h-2 bg-gray-200 rounded-full">
                                <div class="h-2 bg-gradient-to-r from-blue-500 to-teal-500 rounded-full transition-all duration-300" style="width: ${20 + Math.random() * 60}%"></div>
                            </div>
                            <span class="text-xs text-gray-600">${Math.round(20 + Math.random() * 60)}%</span>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    },

    renderRecentResumes() {
        return `
            <div class="space-y-4">
                ${this.recentResumes.map((resume, index) => `
                    <div class="flex items-center justify-between p-4 glass bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition-colors">
                        <div class="flex items-center gap-4">
                            <div class="w-12 h-12 bg-gradient-to-br from-purple-400 to-pink-400 rounded-xl flex items-center justify-center">
                                <span class="text-white text-sm">
                                    ${resume.filename?.substring(0, 2).toUpperCase() || 'R'}
                                </span>
                            </div>
                            <div>
                                <h4 class="text-gray-800 truncate max-w-32">${resume.filename}</h4>
                                <p class="text-sm text-gray-600">
                                    ${window.utils.formatDate(resume.uploadDate)}
                                </p>
                            </div>
                        </div>
                        <div class="flex items-center gap-4">
                            ${resume.analysis ? `
                                <div class="flex items-center gap-2">
                                    <i data-lucide="star" class="w-4 h-4 text-yellow-500"></i>
                                    <span class="text-sm ${this.getScoreColor(resume.analysis.overallScore)}">
                                        ${resume.analysis.overallScore}%
                                    </span>
                                </div>
                            ` : ''}
                            <span class="px-3 py-1 rounded-full text-xs ${this.getStatusColor(resume.status)}">
                                ${resume.status}
                            </span>
                            <div class="flex gap-2">
                                <button class="p-2 hover:bg-white/10 rounded-lg transition-colors">
                                    <i data-lucide="eye" class="w-4 h-4 text-gray-600"></i>
                                </button>
                                <button class="p-2 hover:bg-white/10 rounded-lg transition-colors">
                                    <i data-lucide="download" class="w-4 h-4 text-gray-600"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    },

    getScoreColor(score) {
        if (score >= 80) return 'text-green-600';
        if (score >= 60) return 'text-yellow-600';
        return 'text-red-600';
    },

    getStatusColor(status) {
        switch (status) {
            case 'completed': return 'bg-green-100 text-green-700';
            case 'processing': return 'bg-blue-100 text-blue-700';
            case 'failed': return 'bg-red-100 text-red-700';
            default: return 'bg-yellow-100 text-yellow-700';
        }
    },

    initializeCharts() {
        // Monthly Applications Chart
        const monthlyCtx = document.getElementById('monthlyChart');
        if (monthlyCtx) {
            this.charts.monthly = new Chart(monthlyCtx, {
                type: 'line',
                data: {
                    labels: this.chartData.monthly.map(d => d.month),
                    datasets: [{
                        label: 'Applications',
                        data: this.chartData.monthly.map(d => d.applications),
                        borderColor: '#8B5CF6',
                        backgroundColor: 'rgba(139, 92, 246, 0.1)',
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            }
                        },
                        x: {
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            }
                        }
                    }
                }
            });
        }

        // Skills Distribution Chart
        const skillsCtx = document.getElementById('skillsChart');
        if (skillsCtx) {
            this.charts.skills = new Chart(skillsCtx, {
                type: 'doughnut',
                data: {
                    labels: this.chartData.skills.map(d => d.label),
                    datasets: [{
                        data: this.chartData.skills.map(d => d.value),
                        backgroundColor: [
                            '#8B5CF6',
                            '#14B8A6',
                            '#3B82F6',
                            '#F59E0B',
                            '#EF4444'
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom'
                        }
                    }
                }
            });
        }

        // Score Distribution Chart
        const scoresCtx = document.getElementById('scoresChart');
        if (scoresCtx) {
            this.charts.scores = new Chart(scoresCtx, {
                type: 'bar',
                data: {
                    labels: this.chartData.scores.map(d => d.range),
                    datasets: [{
                        label: 'Count',
                        data: this.chartData.scores.map(d => d.count),
                        backgroundColor: 'rgba(139, 92, 246, 0.8)',
                        borderColor: '#8B5CF6',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            }
                        },
                        x: {
                            grid: {
                                color: 'rgba(0, 0, 0, 0.1)'
                            }
                        }
                    }
                }
            });
        }
    },

    async refresh() {
        window.utils.showLoading();
        await this.loadDashboardData();
        this.render();
        window.utils.hideLoading();
        window.utils.showNotification('Dashboard refreshed successfully', 'success');
    }
};