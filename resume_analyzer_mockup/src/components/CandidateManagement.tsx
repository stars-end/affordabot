import React, { useState, useEffect } from 'react';
import { 
  Users, 
  Search, 
  Filter, 
  Download, 
  Eye, 
  Trash2, 
  Star,
  Calendar,
  MapPin,
  Mail,
  Phone,
  ExternalLink,
  MoreVertical,
  Plus,
  SortAsc,
  SortDesc
} from 'lucide-react';
import { atsApi } from '../services/atsApi';

export function CandidateManagement() {
  const [candidates, setCandidates] = useState([]);
  const [filteredCandidates, setFilteredCandidates] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('date');
  const [sortOrder, setSortOrder] = useState('desc');
  const [filterScore, setFilterScore] = useState('all');
  const [isLoading, setIsLoading] = useState(true);
  const [selectedCandidates, setSelectedCandidates] = useState(new Set());

  // Glassmorphism styles
  const glassStyle = {
    backdropFilter: 'blur(16px)',
    background: 'rgba(255, 255, 255, 0.1)',
    border: '1px solid rgba(255, 255, 255, 0.2)',
    boxShadow: '0 8px 32px rgba(31, 38, 135, 0.15)'
  };

  useEffect(() => {
    loadCandidates();
  }, []);

  useEffect(() => {
    filterAndSortCandidates();
  }, [candidates, searchTerm, sortBy, sortOrder, filterScore]);

  const loadCandidates = async () => {
    try {
      setIsLoading(true);
      const resumes = await atsApi.getAllResumes();
      const completedCandidates = resumes.filter(r => r.status === 'completed' && r.analysis);
      setCandidates(completedCandidates);
    } catch (error) {
      console.error('Failed to load candidates:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const filterAndSortCandidates = () => {
    let filtered = [...candidates];

    // Search filter
    if (searchTerm) {
      filtered = filtered.filter(candidate => 
        candidate.filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
        candidate.analysis?.personalInfo?.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        candidate.analysis?.personalInfo?.email?.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    // Score filter
    if (filterScore !== 'all') {
      filtered = filtered.filter(candidate => {
        const score = candidate.analysis?.overallScore || 0;
        switch (filterScore) {
          case 'excellent': return score >= 80;
          case 'good': return score >= 60 && score < 80;
          case 'average': return score >= 40 && score < 60;
          case 'poor': return score < 40;
          default: return true;
        }
      });
    }

    // Sort
    filtered.sort((a, b) => {
      let aVal, bVal;
      
      switch (sortBy) {
        case 'name':
          aVal = a.analysis?.personalInfo?.name || a.filename;
          bVal = b.analysis?.personalInfo?.name || b.filename;
          break;
        case 'score':
          aVal = a.analysis?.overallScore || 0;
          bVal = b.analysis?.overallScore || 0;
          break;
        case 'date':
        default:
          aVal = new Date(a.uploadDate).getTime();
          bVal = new Date(b.uploadDate).getTime();
          break;
      }

      if (sortOrder === 'asc') {
        return aVal > bVal ? 1 : -1;
      } else {
        return aVal < bVal ? 1 : -1;
      }
    });

    setFilteredCandidates(filtered);
  };

  const getScoreColor = (score) => {
    if (score >= 80) return 'text-green-600 bg-green-100';
    if (score >= 60) return 'text-yellow-600 bg-yellow-100';
    if (score >= 40) return 'text-orange-600 bg-orange-100';
    return 'text-red-600 bg-red-100';
  };

  const getScoreLabel = (score) => {
    if (score >= 80) return 'Excellent';
    if (score >= 60) return 'Good';
    if (score >= 40) return 'Average';
    return 'Poor';
  };

  const toggleCandidateSelection = (candidateId) => {
    const newSelected = new Set(selectedCandidates);
    if (newSelected.has(candidateId)) {
      newSelected.delete(candidateId);
    } else {
      newSelected.add(candidateId);
    }
    setSelectedCandidates(newSelected);
  };

  const selectAllCandidates = () => {
    if (selectedCandidates.size === filteredCandidates.length) {
      setSelectedCandidates(new Set());
    } else {
      setSelectedCandidates(new Set(filteredCandidates.map(c => c.id)));
    }
  };

  const deleteSelected = async () => {
    try {
      for (const candidateId of selectedCandidates) {
        await atsApi.deleteResume(candidateId);
      }
      setSelectedCandidates(new Set());
      await loadCandidates();
    } catch (error) {
      console.error('Failed to delete candidates:', error);
    }
  };

  const exportSelected = async () => {
    try {
      const ids = selectedCandidates.size > 0 
        ? Array.from(selectedCandidates) 
        : filteredCandidates.map(c => c.id);
      
      const blob = await atsApi.exportAnalysis(ids, 'csv');
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'candidates_export.csv';
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to export candidates:', error);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex justify-center items-center h-64">
          <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:justify-between lg:items-center gap-4">
        <div>
          <h1 className="text-3xl bg-gradient-to-r from-purple-600 to-teal-600 bg-clip-text text-transparent">
            Candidate Management
          </h1>
          <p className="text-gray-600 mt-1">
            Manage and review analyzed candidates ({filteredCandidates.length} of {candidates.length})
          </p>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={exportSelected}
            className="px-4 py-2 bg-gradient-to-r from-purple-500 to-teal-500 text-white rounded-xl hover:shadow-lg transition-all duration-200 flex items-center gap-2"
          >
            <Download className="w-4 h-4" />
            Export
          </button>
          {selectedCandidates.size > 0 && (
            <button
              onClick={deleteSelected}
              className="px-4 py-2 bg-red-500 text-white rounded-xl hover:bg-red-600 transition-colors flex items-center gap-2"
            >
              <Trash2 className="w-4 h-4" />
              Delete ({selectedCandidates.size})
            </button>
          )}
        </div>
      </div>

      {/* Filters and Search */}
      <div className="rounded-2xl p-6 shadow-xl" style={glassStyle}>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <input
              type="text"
              placeholder="Search candidates..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-xl border border-white/30 bg-white/10 text-gray-700 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>

          {/* Score Filter */}
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <select
              value={filterScore}
              onChange={(e) => setFilterScore(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-xl border border-white/30 bg-white/10 text-gray-700 focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="all">All Scores</option>
              <option value="excellent">Excellent (80+)</option>
              <option value="good">Good (60-79)</option>
              <option value="average">Average (40-59)</option>
              <option value="poor">Poor (&lt;40)</option>
            </select>
          </div>

          {/* Sort By */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="px-4 py-2 rounded-xl border border-white/30 bg-white/10 text-gray-700 focus:outline-none focus:ring-2 focus:ring-purple-500"
          >
            <option value="date">Sort by Date</option>
            <option value="name">Sort by Name</option>
            <option value="score">Sort by Score</option>
          </select>

          {/* Sort Order */}
          <button
            onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
            className="px-4 py-2 rounded-xl border border-white/30 bg-white/10 text-gray-700 hover:bg-white/20 transition-colors flex items-center gap-2"
          >
            {sortOrder === 'asc' ? <SortAsc className="w-4 h-4" /> : <SortDesc className="w-4 h-4" />}
            {sortOrder === 'asc' ? 'Ascending' : 'Descending'}
          </button>
        </div>
      </div>

      {/* Candidates List */}
      {filteredCandidates.length > 0 ? (
        <div className="space-y-4">
          {/* Select All */}
          <div className="flex items-center gap-3 px-4">
            <input
              type="checkbox"
              checked={selectedCandidates.size === filteredCandidates.length && filteredCandidates.length > 0}
              onChange={selectAllCandidates}
              className="rounded focus:ring-purple-500"
            />
            <span className="text-sm text-gray-600">
              Select All ({filteredCandidates.length} candidates)
            </span>
          </div>

          {/* Candidates Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {filteredCandidates.map((candidate) => (
              <div key={candidate.id} className="rounded-2xl p-6 shadow-xl hover:shadow-2xl transition-all duration-300" style={glassStyle}>
                <div className="flex items-start gap-4">
                  <input
                    type="checkbox"
                    checked={selectedCandidates.has(candidate.id)}
                    onChange={() => toggleCandidateSelection(candidate.id)}
                    className="mt-1 rounded focus:ring-purple-500"
                  />
                  
                  <div className="flex-1 min-w-0">
                    {/* Header */}
                    <div className="flex justify-between items-start mb-4">
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-teal-500 rounded-xl flex items-center justify-center">
                          <span className="text-white text-sm">
                            {candidate.analysis?.personalInfo?.name?.substring(0, 2).toUpperCase() || 
                             candidate.filename.substring(0, 2).toUpperCase()}
                          </span>
                        </div>
                        <div>
                          <h3 className="text-lg text-gray-800 truncate">
                            {candidate.analysis?.personalInfo?.name || candidate.filename}
                          </h3>
                          <p className="text-sm text-gray-600">
                            {new Date(candidate.uploadDate).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-2">
                        <div className={`px-3 py-1 rounded-full text-sm ${getScoreColor(candidate.analysis?.overallScore || 0)}`}>
                          {candidate.analysis?.overallScore || 0}%
                        </div>
                        <button className="p-2 hover:bg-white/10 rounded-lg">
                          <MoreVertical className="w-4 h-4 text-gray-600" />
                        </button>
                      </div>
                    </div>

                    {/* Contact Info */}
                    {candidate.analysis?.personalInfo && (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
                        <div className="flex items-center gap-2 text-sm text-gray-600">
                          <Mail className="w-4 h-4" />
                          <span className="truncate">{candidate.analysis.personalInfo.email}</span>
                        </div>
                        <div className="flex items-center gap-2 text-sm text-gray-600">
                          <Phone className="w-4 h-4" />
                          <span>{candidate.analysis.personalInfo.phone}</span>
                        </div>
                        <div className="flex items-center gap-2 text-sm text-gray-600">
                          <MapPin className="w-4 h-4" />
                          <span>{candidate.analysis.personalInfo.location}</span>
                        </div>
                        <div className="flex items-center gap-2 text-sm text-gray-600">
                          <Calendar className="w-4 h-4" />
                          <span>{candidate.analysis.experience?.totalYears || 0} years exp.</span>
                        </div>
                      </div>
                    )}

                    {/* Skills */}
                    {candidate.analysis?.skills && (
                      <div className="mb-4">
                        <h4 className="text-sm text-gray-600 mb-2">Top Skills</h4>
                        <div className="flex flex-wrap gap-2">
                          {candidate.analysis.skills.slice(0, 4).map((skill, index) => (
                            <span 
                              key={index}
                              className="px-2 py-1 bg-white/10 border border-white/20 rounded-lg text-xs text-gray-700"
                            >
                              {skill.name}
                            </span>
                          ))}
                          {candidate.analysis.skills.length > 4 && (
                            <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded-lg text-xs">
                              +{candidate.analysis.skills.length - 4} more
                            </span>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Action Buttons */}
                    <div className="flex gap-2 pt-3 border-t border-white/20">
                      <button className="flex-1 px-3 py-2 bg-white/10 hover:bg-white/20 text-gray-700 rounded-lg transition-colors flex items-center justify-center gap-2">
                        <Eye className="w-4 h-4" />
                        View Details
                      </button>
                      <button className="flex-1 px-3 py-2 bg-white/10 hover:bg-white/20 text-gray-700 rounded-lg transition-colors flex items-center justify-center gap-2">
                        <Download className="w-4 h-4" />
                        Download
                      </button>
                      <button className="px-3 py-2 bg-white/10 hover:bg-red-100 text-gray-700 hover:text-red-600 rounded-lg transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="text-center py-12">
          <div className="w-24 h-24 bg-gradient-to-br from-purple-100 to-teal-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Users className="w-12 h-12 text-purple-500" />
          </div>
          <h3 className="text-xl text-gray-800 mb-2">
            {candidates.length === 0 ? 'No Candidates Yet' : 'No Matching Candidates'}
          </h3>
          <p className="text-gray-600">
            {candidates.length === 0 
              ? 'Upload and analyze resumes to see candidates here.'
              : 'Try adjusting your search filters to find candidates.'
            }
          </p>
        </div>
      )}
    </div>
  );
}