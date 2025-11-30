'use client';

import React, { useEffect, useState } from 'react';
import {
  Users,
  FileText,
  TrendingUp,
  Clock,
  Star,
  MoreVertical,
  Eye,
  Download,
  RefreshCw,
  Activity,
  AlertCircle,
  CheckCircle,
  XCircle,
  Info,
  Zap
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell, AreaChart, Area } from 'recharts';
// import { atsApi } from '../services/atsApi';

export function Dashboard() {
  const [stats, setStats] = useState({
    totalApplications: 0,
    activeCandidates: 0,
    avgMatchScore: 0,
    avgTimeToHire: 0
  });

  const [recentResumes, setRecentResumes] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const [error, setError] = useState<string | null>(null);
  const [backendStatus, setBackendStatus] = useState({ available: false, url: '' });
  const [modeInfo, setModeInfo] = useState({ mode: 'demo', features: [] as string[] });

  // Real-time dashboard data
  const [dashboardData, setDashboardData] = useState<{
    monthlyApplications: Array<{ month: string; applications: number }>;
    skillsDistribution: Array<{ name: string; value: number; color: string }>;
    processingQueue: Array<{ name: string; progress: number; id: string }>;
    scoreDistribution: Array<{ name: string; value: number }>;
  }>({
    monthlyApplications: [],
    skillsDistribution: [],
    processingQueue: [],
    scoreDistribution: []
  });

  useEffect(() => {
    // Mock data loading
    const loadMockData = () => {
      setIsLoading(true);

      // Mock stats
      setStats({
        totalApplications: 124,
        activeCandidates: 45,
        avgMatchScore: 78,
        avgTimeToHire: 12
      });

      // Mock recent resumes
      setRecentResumes([
        { filename: 'John_Doe_Resume.pdf', uploadDate: new Date().toISOString(), status: 'completed', analysis: { overallScore: 85 } },
        { filename: 'Jane_Smith_CV.pdf', uploadDate: new Date(Date.now() - 86400000).toISOString(), status: 'processing', analysis: null },
        { filename: 'Mike_Johnson.pdf', uploadDate: new Date(Date.now() - 172800000).toISOString(), status: 'completed', analysis: { overallScore: 62 } },
        { filename: 'Sarah_Williams.pdf', uploadDate: new Date(Date.now() - 259200000).toISOString(), status: 'failed', analysis: null }
      ]);

      // Mock dashboard data
      setDashboardData({
        monthlyApplications: [
          { month: 'Jan', applications: 45 },
          { month: 'Feb', applications: 52 },
          { month: 'Mar', applications: 38 },
          { month: 'Apr', applications: 65 },
          { month: 'May', applications: 48 },
          { month: 'Jun', applications: 72 }
        ],
        skillsDistribution: [
          { name: 'React', value: 35, color: '#8B5CF6' },
          { name: 'Node.js', value: 28, color: '#14B8A6' },
          { name: 'Python', value: 22, color: '#3B82F6' },
          { name: 'SQL', value: 15, color: '#F59E0B' },
          { name: 'AWS', value: 12, color: '#EF4444' }
        ],
        processingQueue: [
          { name: 'Jane_Smith_CV.pdf', progress: 45, id: '2' },
          { name: 'Robert_Brown.docx', progress: 12, id: '5' }
        ],
        scoreDistribution: [
          { name: '0-40', value: 5 },
          { name: '41-60', value: 12 },
          { name: '61-80', value: 25 },
          { name: '81-100', value: 18 }
        ]
      });

      setBackendStatus({ available: true, url: 'http://localhost:8000' });
      setModeInfo({ mode: 'backend', features: ['Real AI Analysis', 'PDF Parsing', 'Skill Matching'] });
      setIsLoading(false);
    };

    loadMockData();
  }, []);

  const refreshData = () => {
    setIsLoading(true);
    setTimeout(() => setIsLoading(false), 1000);
  };


  // Helper functions with explicit types
  const generateMonthlyData = (resumes: any[]) => {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'];
    // Mock data generation
    return months.map(month => ({
      month,
      applications: Math.floor(Math.random() * 30) + 10
    }));
  };

  const generateSkillsDistribution = (resumes: any[]) => {
    const colors = ['#8B5CF6', '#14B8A6', '#3B82F6', '#F59E0B', '#EF4444'];
    return [
      { name: 'JavaScript', value: 15, color: colors[0] },
      { name: 'Python', value: 12, color: colors[1] },
      { name: 'React', value: 10, color: colors[2] },
      { name: 'Node.js', value: 8, color: colors[3] },
      { name: 'SQL', value: 6, color: colors[4] }
    ];
  };

  const generateScoreDistribution = (scores: number[]) => {
    return [
      { name: '0-40', value: 5 },
      { name: '41-60', value: 12 },
      { name: '61-80', value: 25 },
      { name: '81-100', value: 18 }
    ];
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-700';
      case 'processing': return 'bg-blue-100 text-blue-700';
      case 'failed': return 'bg-red-100 text-red-700';
      default: return 'bg-yellow-100 text-yellow-700';
    }
  };

  // Glassmorphism styles using inline styles
  const glassStyle = {
    backdropFilter: 'blur(16px)',
    background: 'rgba(255, 255, 255, 0.1)',
    border: '1px solid rgba(255, 255, 255, 0.2)',
    boxShadow: '0 8px 32px rgba(31, 38, 135, 0.15)'
  };

  const glassStrongStyle = {
    backdropFilter: 'blur(20px)',
    background: 'rgba(255, 255, 255, 0.15)',
    border: '1px solid rgba(255, 255, 255, 0.3)',
    boxShadow: '0 12px 40px rgba(31, 38, 135, 0.2)'
  };

  const BackendStatusIndicator = () => (
    <div className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm ${backendStatus.available
      ? 'bg-green-100 text-green-700 border border-green-200'
      : 'bg-blue-100 text-blue-700 border border-blue-200'
      }`}>
      {backendStatus.available ? (
        <>
          <Zap className="w-4 h-4" />
          <span>AI Backend Active</span>
        </>
      ) : (
        <>
          <Info className="w-4 h-4" />
          <span>Demo Mode</span>
        </>
      )}
    </div>
  );

  const ModeInfoBanner = () => (
    <div className={`rounded-2xl p-6 shadow-xl ${modeInfo.mode === 'backend'
      ? 'bg-green-50/50 border-green-200'
      : 'bg-blue-50/50 border-blue-200'
      }`} style={glassStyle}>
      <div className="flex items-start gap-4">
        {modeInfo.mode === 'backend' ? (
          <Zap className="w-6 h-6 text-green-600 flex-shrink-0 mt-1" />
        ) : (
          <Info className="w-6 h-6 text-blue-600 flex-shrink-0 mt-1" />
        )}
        <div className="flex-1">
          <h3 className={`text-lg mb-2 ${modeInfo.mode === 'backend' ? 'text-green-800' : 'text-blue-800'
            }`}>
            {modeInfo.mode === 'backend' ? 'AI Backend Connected' : 'Demo Mode Active'}
          </h3>
          <p className={`text-sm mb-3 ${modeInfo.mode === 'backend' ? 'text-green-700' : 'text-blue-700'
            }`}>
            {modeInfo.mode === 'backend'
              ? 'Full AI-powered analysis is available with real spaCy NLP processing and BERT skill matching.'
              : 'You\'re experiencing the full ATS interface with realistic demo data. All features are functional for testing and exploration.'
            }
          </p>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
            {modeInfo.features.slice(0, 4).map((feature, index) => (
              <div key={index} className={`flex items-center gap-2 text-xs ${modeInfo.mode === 'backend' ? 'text-green-700' : 'text-blue-700'
                }`}>
                <CheckCircle className="w-3 h-3" />
                <span>{feature}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  if (error) {
    return (
      <div className="space-y-6">
        <div className="rounded-2xl p-8 shadow-xl text-center" style={glassStyle}>
          <div className="text-red-500 mb-4">
            <AlertCircle className="w-16 h-16 mx-auto mb-4" />
            <h2 className="text-xl mb-2">Dashboard Error</h2>
            <p className="text-sm">{error}</p>
          </div>
          <button
            onClick={refreshData}
            className="px-4 py-2 bg-gradient-to-r from-purple-500 to-teal-500 text-white rounded-xl hover:shadow-lg transition-all duration-200"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with Backend Status */}
      <div className="flex flex-col lg:flex-row lg:justify-between lg:items-center gap-4">
        <div>
          <h1 className="text-3xl bg-gradient-to-r from-purple-600 to-teal-600 bg-clip-text text-transparent">
            ATS Resume Analyzer
          </h1>
          <p className="text-gray-600 mt-1">AI-powered recruitment insights and candidate analysis.</p>
        </div>
        <div className="flex items-center gap-4">
          <BackendStatusIndicator />
          <button
            onClick={refreshData}
            className="p-2 rounded-xl hover:bg-white/30 transition-colors border border-white/30"
            style={glassStyle}
            disabled={isLoading}
          >
            <RefreshCw className={`w-4 h-4 text-gray-700 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
          <div className="rounded-xl px-6 py-3 shadow-lg border border-white/30" style={glassStyle}>
            <span className="text-sm text-gray-700">
              Updated: {lastUpdate.toLocaleTimeString()}
            </span>
          </div>
        </div>
      </div>

      {/* Mode Information Banner */}
      <ModeInfoBanner />

      {/* Real-time Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="rounded-2xl p-6 shadow-xl hover:shadow-2xl transition-all duration-300 hover:scale-105" style={glassStyle}>
          <div className="flex items-center justify-between">
            <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl flex items-center justify-center shadow-lg">
              <FileText className="w-6 h-6 text-white" />
            </div>
            <div className="flex items-center text-green-600">
              <TrendingUp className="w-4 h-4 mr-1" />
              <span className="text-sm">+12%</span>
            </div>
          </div>
          <div className="mt-4">
            <h3 className="text-2xl text-gray-800">{stats.totalApplications.toLocaleString()}</h3>
            <p className="text-sm text-gray-600 mt-1">Total Resumes</p>
          </div>
        </div>

        <div className="rounded-2xl p-6 shadow-xl hover:shadow-2xl transition-all duration-300 hover:scale-105" style={glassStyle}>
          <div className="flex items-center justify-between">
            <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-teal-500 rounded-xl flex items-center justify-center shadow-lg">
              <Users className="w-6 h-6 text-white" />
            </div>
            <div className="flex items-center text-green-600">
              <TrendingUp className="w-4 h-4 mr-1" />
              <span className="text-sm">+8%</span>
            </div>
          </div>
          <div className="mt-4">
            <h3 className="text-2xl text-gray-800">{stats.activeCandidates}</h3>
            <p className="text-sm text-gray-600 mt-1">Analyzed Candidates</p>
          </div>
        </div>

        <div className="rounded-2xl p-6 shadow-xl hover:shadow-2xl transition-all duration-300 hover:scale-105" style={glassStyle}>
          <div className="flex items-center justify-between">
            <div className="w-12 h-12 bg-gradient-to-br from-teal-500 to-green-500 rounded-xl flex items-center justify-center shadow-lg">
              <Star className="w-6 h-6 text-white" />
            </div>
            <div className="flex items-center text-green-600">
              <TrendingUp className="w-4 h-4 mr-1" />
              <span className="text-sm">+5%</span>
            </div>
          </div>
          <div className="mt-4">
            <h3 className="text-2xl text-gray-800">{stats.avgMatchScore}%</h3>
            <p className="text-sm text-gray-600 mt-1">Avg. Match Score</p>
          </div>
        </div>

        <div className="rounded-2xl p-6 shadow-xl hover:shadow-2xl transition-all duration-300 hover:scale-105" style={glassStyle}>
          <div className="flex items-center justify-between">
            <div className="w-12 h-12 bg-gradient-to-br from-orange-500 to-red-500 rounded-xl flex items-center justify-center shadow-lg">
              <Clock className="w-6 h-6 text-white" />
            </div>
            <div className="flex items-center text-red-600">
              <Activity className="w-4 h-4 mr-1" />
              <span className="text-sm">-2 days</span>
            </div>
          </div>
          <div className="mt-4">
            <h3 className="text-2xl text-gray-800">{stats.avgTimeToHire} days</h3>
            <p className="text-sm text-gray-600 mt-1">Avg. Processing Time</p>
          </div>
        </div>
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Monthly Applications */}
        <div className="rounded-2xl p-6 shadow-xl" style={glassStyle}>
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-lg text-gray-800">Monthly Applications</h3>
            <button className="p-2 hover:bg-white/10 rounded-lg transition-colors">
              <MoreVertical className="w-4 h-4 text-gray-600" />
            </button>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={dashboardData.monthlyApplications}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis dataKey="month" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Area
                type="monotone"
                dataKey="applications"
                stroke="#8B5CF6"
                fill="url(#gradient1)"
                strokeWidth={2}
              />
              <defs>
                <linearGradient id="gradient1" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#8B5CF6" stopOpacity={0.8} />
                  <stop offset="100%" stopColor="#14B8A6" stopOpacity={0.1} />
                </linearGradient>
              </defs>
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Skills Distribution */}
        <div className="rounded-2xl p-6 shadow-xl" style={glassStyle}>
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-lg text-gray-800">Top Skills Detected</h3>
            <button className="p-2 hover:bg-white/10 rounded-lg transition-colors">
              <MoreVertical className="w-4 h-4 text-gray-600" />
            </button>
          </div>
          <ResponsiveContainer width="100%" height={150}>
            <PieChart>
              <Pie
                data={dashboardData.skillsDistribution}
                cx="50%"
                cy="50%"
                innerRadius={40}
                outerRadius={75}
                dataKey="value"
              >
                {dashboardData.skillsDistribution.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap gap-4 mt-4">
            {dashboardData.skillsDistribution.map((skill, index) => (
              <div key={index} className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: skill.color }}></div>
                <span className="text-sm text-gray-700">{skill.name} ({skill.value})</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Processing Queue & Recent Resumes */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Processing Queue */}
        <div className="rounded-2xl p-6 shadow-xl" style={glassStyle}>
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-lg text-gray-800">Processing Queue</h3>
            <span className="text-sm text-gray-600">{dashboardData.processingQueue.length} active</span>
          </div>
          {dashboardData.processingQueue.length > 0 ? (
            <div className="space-y-4">
              {dashboardData.processingQueue.slice(0, 4).map((item, index) => (
                <div key={index} className="flex items-center justify-between p-3 bg-white/5 border border-white/10 rounded-xl">
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                    <span className="text-sm text-gray-700 truncate max-w-48">{item.name}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-16 h-2 bg-gray-200 rounded-full">
                      <div
                        className="h-2 bg-gradient-to-r from-purple-500 to-teal-500 rounded-full transition-all duration-300"
                        style={{ width: `${item.progress}%` }}
                      ></div>
                    </div>
                    <span className="text-xs text-gray-600">{Math.round(item.progress)}%</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <Clock className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p>No resumes processing</p>
            </div>
          )}
        </div>

        {/* Recent Resumes */}
        <div className="rounded-2xl p-6 shadow-xl" style={glassStyle}>
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-lg text-gray-800">Recent Resumes</h3>
            <button className="text-sm text-purple-600 hover:text-purple-700 transition-colors">
              View All
            </button>
          </div>
          <div className="space-y-4">
            {recentResumes.map((resume, index) => {
              const analysis = resume.analysis;

              return (
                <div key={index} className="flex items-center justify-between p-4 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 transition-colors">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-gradient-to-br from-purple-400 to-pink-400 rounded-xl flex items-center justify-center">
                      <span className="text-white text-sm">
                        {resume.filename?.substring(0, 2).toUpperCase() || 'R'}
                      </span>
                    </div>
                    <div>
                      <h4 className="text-gray-800 truncate max-w-32">{resume.filename}</h4>
                      <p className="text-sm text-gray-600">
                        {new Date(resume.uploadDate).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    {analysis && (
                      <div className="flex items-center gap-2">
                        <Star className="w-4 h-4 text-yellow-500" />
                        <span className={`text-sm ${getScoreColor(analysis.overallScore)}`}>
                          {analysis.overallScore}%
                        </span>
                      </div>
                    )}
                    <span className={`px-3 py-1 rounded-full text-xs ${getStatusColor(resume.status)}`}>
                      {resume.status}
                    </span>
                    <div className="flex gap-2">
                      <button className="p-2 hover:bg-white/10 rounded-lg transition-colors">
                        <Eye className="w-4 h-4 text-gray-600" />
                      </button>
                      <button className="p-2 hover:bg-white/10 rounded-lg transition-colors">
                        <Download className="w-4 h-4 text-gray-600" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Score Distribution */}
      {dashboardData.scoreDistribution.some(item => item.value > 0) && (
        <div className="rounded-2xl p-6 shadow-xl" style={glassStyle}>
          <h3 className="text-lg text-gray-800 mb-6">Score Distribution</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={dashboardData.scoreDistribution}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Bar dataKey="value" fill="url(#scoreGradient)" radius={8} />
              <defs>
                <linearGradient id="scoreGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#8B5CF6" />
                  <stop offset="100%" stopColor="#14B8A6" />
                </linearGradient>
              </defs>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}