import React, { useState, useRef } from 'react';
import { 
  Upload, 
  FileText, 
  X, 
  CheckCircle, 
  AlertCircle, 
  Clock,
  Star,
  Download,
  Eye,
  RotateCcw,
  Zap,
  Info,
  FileSearch
} from 'lucide-react';
import { atsApi } from '../services/atsApi';

export function ResumeAnalyzer() {
  const [dragActive, setDragActive] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResults, setAnalysisResults] = useState([]);
  const [jobProfiles, setJobProfiles] = useState([]);
  const [selectedJobProfile, setSelectedJobProfile] = useState('fullstack');
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);

  React.useEffect(() => {
    loadJobProfiles();
  }, []);

  const loadJobProfiles = async () => {
    try {
      const profiles = await atsApi.getJobProfiles();
      setJobProfiles(profiles);
    } catch (error) {
      console.error('Failed to load job profiles:', error);
    }
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFiles(Array.from(e.target.files));
    }
  };

  const handleFiles = async (files) => {
    const validFiles = files.filter(file => {
      const fileType = file.type;
      const fileName = file.name.toLowerCase();
      return fileType === 'application/pdf' || 
             fileName.endsWith('.pdf') || 
             fileName.endsWith('.doc') || 
             fileName.endsWith('.docx') ||
             fileType === 'application/msword' ||
             fileType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
    });

    if (validFiles.length !== files.length) {
      setError('Please upload only PDF, DOC, or DOCX files.');
      return;
    }

    setError('');
    setUploadedFiles(prev => [...prev, ...validFiles]);

    // Auto-analyze uploaded files
    await analyzeFiles(validFiles);
  };

  const analyzeFiles = async (files) => {
    setIsAnalyzing(true);
    
    try {
      for (const file of files) {
        const { jobId, resumeId } = await atsApi.uploadResume(file, selectedJobProfile);
        
        // Poll for completion
        await pollAnalysisStatus(jobId, resumeId, file.name);
      }
    } catch (error) {
      console.error('Analysis failed:', error);
      setError('Analysis failed. Please try again.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const pollAnalysisStatus = async (jobId, resumeId, fileName) => {
    const maxAttempts = 30; // 30 seconds timeout
    let attempts = 0;

    const poll = async () => {
      try {
        const status = await atsApi.getAnalysisStatus(jobId);
        
        if (status.status === 'completed') {
          const result = await atsApi.getAnalysisResult(resumeId);
          setAnalysisResults(prev => [...prev, {
            id: resumeId,
            fileName: fileName,
            analysis: result,
            status: 'completed'
          }]);
          return;
        } else if (status.status === 'failed') {
          setError(`Analysis failed for ${fileName}`);
          return;
        }

        attempts++;
        if (attempts < maxAttempts) {
          setTimeout(poll, 1000);
        } else {
          setError(`Analysis timeout for ${fileName}`);
        }
      } catch (error) {
        console.error('Polling error:', error);
        setError(`Failed to get analysis status for ${fileName}`);
      }
    };

    poll();
  };

  const removeFile = (index) => {
    setUploadedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const removeResult = (id) => {
    setAnalysisResults(prev => prev.filter(result => result.id !== id));
  };

  const getScoreColor = (score) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getScoreLabel = (score) => {
    if (score >= 80) return 'Excellent';
    if (score >= 60) return 'Good';
    if (score >= 40) return 'Average';
    return 'Poor';
  };

  // Glassmorphism styles
  const glassStyle = {
    backdropFilter: 'blur(16px)',
    background: 'rgba(255, 255, 255, 0.1)',
    border: '1px solid rgba(255, 255, 255, 0.2)',
    boxShadow: '0 8px 32px rgba(31, 38, 135, 0.15)'
  };

  const fileUploadAreaStyle = {
    background: dragActive 
      ? 'linear-gradient(145deg, rgba(139, 92, 246, 0.15), rgba(20, 184, 166, 0.15))'
      : 'linear-gradient(145deg, rgba(139, 92, 246, 0.1), rgba(20, 184, 166, 0.1))',
    border: `2px dashed ${dragActive ? 'rgba(139, 92, 246, 0.6)' : 'rgba(139, 92, 246, 0.3)'}`,
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    transform: dragActive ? 'scale(1.02)' : 'scale(1)',
    boxShadow: dragActive ? '0 16px 48px rgba(139, 92, 246, 0.2)' : '0 8px 24px rgba(139, 92, 246, 0.1)'
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:justify-between lg:items-center gap-4">
        <div>
          <h1 className="text-3xl bg-gradient-to-r from-purple-600 to-teal-600 bg-clip-text text-transparent">
            Resume Analyzer
          </h1>
          <p className="text-gray-600 mt-1">Upload and analyze resumes with AI-powered insights.</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm bg-blue-100 text-blue-700 border border-blue-200">
            <Info className="w-4 h-4" />
            <span>Demo Mode</span>
          </div>
          <select 
            value={selectedJobProfile}
            onChange={(e) => setSelectedJobProfile(e.target.value)}
            className="px-4 py-2 rounded-xl border border-white/30 text-gray-700 focus:outline-none focus:ring-2 focus:ring-purple-500"
            style={glassStyle}
          >
            {jobProfiles.map(profile => (
              <option key={profile.id} value={profile.id}>
                {profile.title}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* File Upload Area */}
      <div 
        className={`rounded-2xl p-8 text-center cursor-pointer relative overflow-hidden ${
          dragActive ? 'scale-102' : ''
        }`}
        style={fileUploadAreaStyle}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.doc,.docx"
          onChange={handleFileInput}
          className="hidden"
        />
        
        <div className="flex flex-col items-center gap-4">
          <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-teal-500 rounded-2xl flex items-center justify-center shadow-lg">
            <Upload className="w-8 h-8 text-white" />
          </div>
          
          <div>
            <h3 className="text-xl text-gray-800 mb-2">
              {dragActive ? 'Drop files here' : 'Upload Resume Files'}
            </h3>
            <p className="text-gray-600 mb-4">
              Drag & drop your resume files here, or click to browse
            </p>
            <p className="text-sm text-gray-500">
              Supports PDF, DOC, and DOCX files • Max 10MB per file
            </p>
          </div>
          
          <button className="px-6 py-3 bg-gradient-to-r from-purple-500 to-teal-500 text-white rounded-xl hover:shadow-lg transition-all duration-200 hover:-translate-y-1">
            Choose Files
          </button>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
          <button 
            onClick={() => setError('')}
            className="ml-auto p-1 hover:bg-red-100 rounded"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Uploaded Files */}
      {uploadedFiles.length > 0 && (
        <div className="rounded-2xl p-6 shadow-xl" style={glassStyle}>
          <h3 className="text-lg text-gray-800 mb-4">Uploaded Files</h3>
          <div className="space-y-3">
            {uploadedFiles.map((file, index) => (
              <div key={index} className="flex items-center justify-between p-3 bg-white/5 border border-white/10 rounded-xl">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-500 rounded-lg flex items-center justify-center">
                    <FileText className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <p className="text-gray-800 truncate max-w-48">{file.name}</p>
                    <p className="text-sm text-gray-600">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {isAnalyzing ? (
                    <div className="flex items-center gap-2 text-blue-600">
                      <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                      <span className="text-sm">Analyzing...</span>
                    </div>
                  ) : (
                    <span className="px-3 py-1 bg-yellow-100 text-yellow-700 rounded-full text-sm">
                      Pending
                    </span>
                  )}
                  <button 
                    onClick={() => removeFile(index)}
                    className="p-1 hover:bg-red-100 rounded text-red-500"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Analysis Results */}
      {analysisResults.length > 0 && (
        <div className="space-y-6">
          <h2 className="text-2xl text-gray-800">Analysis Results</h2>
          
          {analysisResults.map((result) => (
            <div key={result.id} className="rounded-2xl p-6 shadow-xl" style={glassStyle}>
              <div className="flex justify-between items-start mb-6">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-gradient-to-br from-green-500 to-blue-500 rounded-xl flex items-center justify-center">
                    <FileText className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h3 className="text-lg text-gray-800">{result.fileName}</h3>
                    <p className="text-sm text-gray-600">
                      Analyzed on {new Date(result.analysis.analysisDate).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-center">
                    <div className={`text-3xl ${getScoreColor(result.analysis.overallScore)}`}>
                      {result.analysis.overallScore}%
                    </div>
                    <div className={`text-sm ${getScoreColor(result.analysis.overallScore)}`}>
                      {getScoreLabel(result.analysis.overallScore)}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button className="p-2 hover:bg-white/10 rounded-lg transition-colors">
                      <Eye className="w-4 h-4 text-gray-600" />
                    </button>
                    <button className="p-2 hover:bg-white/10 rounded-lg transition-colors">
                      <Download className="w-4 h-4 text-gray-600" />
                    </button>
                    <button 
                      onClick={() => removeResult(result.id)}
                      className="p-2 hover:bg-red-100 rounded-lg transition-colors text-red-500"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>

              {/* Personal Information */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                  <h4 className="text-sm text-gray-600 mb-2">Name</h4>
                  <p className="text-gray-800">{result.analysis.personalInfo.name}</p>
                </div>
                <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                  <h4 className="text-sm text-gray-600 mb-2">Email</h4>
                  <p className="text-gray-800 truncate">{result.analysis.personalInfo.email}</p>
                </div>
                <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                  <h4 className="text-sm text-gray-600 mb-2">Phone</h4>
                  <p className="text-gray-800">{result.analysis.personalInfo.phone}</p>
                </div>
                <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                  <h4 className="text-sm text-gray-600 mb-2">Location</h4>
                  <p className="text-gray-800">{result.analysis.personalInfo.location}</p>
                </div>
              </div>

              {/* Section Scores */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                {result.analysis.sections.map((section, index) => (
                  <div key={index} className="bg-white/5 border border-white/10 rounded-xl p-4">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="text-sm text-gray-600">{section.name}</h4>
                      <CheckCircle className="w-4 h-4 text-green-500" />
                    </div>
                    <div className={`text-xl ${getScoreColor(section.score)}`}>
                      {section.score}%
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
                      <div 
                        className="bg-gradient-to-r from-purple-500 to-teal-500 h-2 rounded-full transition-all duration-300"
                        style={{ width: `${section.score}%` }}
                      ></div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Skills */}
              <div className="mb-6">
                <h4 className="text-lg text-gray-800 mb-4">Detected Skills</h4>
                <div className="flex flex-wrap gap-2">
                  {result.analysis.skills.map((skill, index) => (
                    <span 
                      key={index}
                      className="px-3 py-1 bg-white/10 border border-white/20 rounded-full text-sm text-gray-700 hover:bg-white/20 transition-colors"
                      title={`Confidence: ${Math.round(skill.confidence * 100)}%`}
                    >
                      {skill.name}
                      <span className="ml-1 text-xs text-gray-500">
                        {Math.round(skill.confidence * 100)}%
                      </span>
                    </span>
                  ))}
                </div>
              </div>

              {/* Job Match */}
              <div className="bg-gradient-to-r from-purple-50 to-teal-50 border border-purple-200 rounded-xl p-4">
                <h4 className="text-lg text-gray-800 mb-3">Job Match Analysis</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <h5 className="text-sm text-gray-600 mb-2">Match Percentage</h5>
                    <div className={`text-2xl ${getScoreColor(result.analysis.jobMatch.matchPercentage)}`}>
                      {result.analysis.jobMatch.matchPercentage}%
                    </div>
                  </div>
                  <div>
                    <h5 className="text-sm text-gray-600 mb-2">Recommendations</h5>
                    <ul className="text-sm text-gray-700 space-y-1">
                      {result.analysis.jobMatch.recommendations.slice(0, 2).map((rec, index) => (
                        <li key={index} className="flex items-start gap-2">
                          <span className="text-purple-500 mt-1">•</span>
                          {rec}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {uploadedFiles.length === 0 && analysisResults.length === 0 && (
        <div className="text-center py-12">
          <div className="w-24 h-24 bg-gradient-to-br from-purple-100 to-teal-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <FileSearch className="w-12 h-12 text-purple-500" />
          </div>
          <h3 className="text-xl text-gray-800 mb-2">No Resumes Uploaded</h3>
          <p className="text-gray-600">Upload your first resume to get started with AI-powered analysis.</p>
        </div>
      )}
    </div>
  );
}