import React, { useState, useEffect } from 'react';
import { 
  Briefcase, 
  Plus, 
  Edit, 
  Trash2, 
  Users, 
  Clock, 
  MapPin,
  DollarSign,
  Search,
  Filter,
  MoreVertical,
  Eye,
  Copy
} from 'lucide-react';
import { atsApi } from '../services/atsApi';

export function JobPostings() {
  const [jobProfiles, setJobProfiles] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingJob, setEditingJob] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

  // Glassmorphism styles
  const glassStyle = {
    backdropFilter: 'blur(16px)',
    background: 'rgba(255, 255, 255, 0.1)',
    border: '1px solid rgba(255, 255, 255, 0.2)',
    boxShadow: '0 8px 32px rgba(31, 38, 135, 0.15)'
  };

  useEffect(() => {
    loadJobProfiles();
  }, []);

  const loadJobProfiles = async () => {
    try {
      setIsLoading(true);
      const profiles = await atsApi.getJobProfiles();
      setJobProfiles(profiles);
    } catch (error) {
      console.error('Failed to load job profiles:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const filteredJobs = jobProfiles.filter(job =>
    job.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    job.description.toLowerCase().includes(searchTerm.toLowerCase())
  );

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
            Job Postings
          </h1>
          <p className="text-gray-600 mt-1">Manage job profiles and requirements for resume analysis.</p>
        </div>
        <button
          onClick={() => setShowCreateForm(true)}
          className="px-6 py-3 bg-gradient-to-r from-purple-500 to-teal-500 text-white rounded-xl hover:shadow-lg transition-all duration-200 flex items-center gap-2"
        >
          <Plus className="w-5 h-5" />
          Create Job Profile
        </button>
      </div>

      {/* Search */}
      <div className="rounded-2xl p-6 shadow-xl" style={glassStyle}>
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
          <input
            type="text"
            placeholder="Search job profiles..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-xl border border-white/30 bg-white/10 text-gray-700 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
          />
        </div>
      </div>

      {/* Job Profiles Grid */}
      {filteredJobs.length > 0 ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {filteredJobs.map((job) => (
            <div key={job.id} className="rounded-2xl p-6 shadow-xl hover:shadow-2xl transition-all duration-300" style={glassStyle}>
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-teal-500 rounded-xl flex items-center justify-center">
                    <Briefcase className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h3 className="text-lg text-gray-800">{job.title}</h3>
                    <p className="text-sm text-gray-600">Job Profile</p>
                  </div>
                </div>
                <button className="p-2 hover:bg-white/10 rounded-lg">
                  <MoreVertical className="w-4 h-4 text-gray-600" />
                </button>
              </div>

              <p className="text-gray-700 mb-4 line-clamp-2">{job.description}</p>

              {/* Job Details */}
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div className="bg-white/5 border border-white/10 rounded-xl p-3">
                  <div className="flex items-center gap-2 text-sm text-gray-600 mb-1">
                    <Clock className="w-4 h-4" />
                    <span>Experience</span>
                  </div>
                  <p className="text-gray-800">{job.minimumExperience}+ years</p>
                </div>
                <div className="bg-white/5 border border-white/10 rounded-xl p-3">
                  <div className="flex items-center gap-2 text-sm text-gray-600 mb-1">
                    <Users className="w-4 h-4" />
                    <span>Active Matches</span>
                  </div>
                  <p className="text-gray-800">{Math.floor(Math.random() * 20) + 5}</p>
                </div>
              </div>

              {/* Required Skills */}
              <div className="mb-4">
                <h4 className="text-sm text-gray-600 mb-2">Required Skills</h4>
                <div className="flex flex-wrap gap-2">
                  {job.requiredSkills.slice(0, 4).map((skill, index) => (
                    <span key={index} className="px-2 py-1 bg-purple-100 text-purple-700 rounded-lg text-xs">
                      {skill}
                    </span>
                  ))}
                  {job.requiredSkills.length > 4 && (
                    <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded-lg text-xs">
                      +{job.requiredSkills.length - 4} more
                    </span>
                  )}
                </div>
              </div>

              {/* Preferred Skills */}
              <div className="mb-6">
                <h4 className="text-sm text-gray-600 mb-2">Preferred Skills</h4>
                <div className="flex flex-wrap gap-2">
                  {job.preferredSkills.slice(0, 3).map((skill, index) => (
                    <span key={index} className="px-2 py-1 bg-teal-100 text-teal-700 rounded-lg text-xs">
                      {skill}
                    </span>
                  ))}
                  {job.preferredSkills.length > 3 && (
                    <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded-lg text-xs">
                      +{job.preferredSkills.length - 3} more
                    </span>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2">
                <button className="flex-1 px-3 py-2 bg-white/10 hover:bg-white/20 text-gray-700 rounded-lg transition-colors flex items-center justify-center gap-2">
                  <Eye className="w-4 h-4" />
                  View Matches
                </button>
                <button 
                  onClick={() => setEditingJob(job)}
                  className="flex-1 px-3 py-2 bg-white/10 hover:bg-white/20 text-gray-700 rounded-lg transition-colors flex items-center justify-center gap-2"
                >
                  <Edit className="w-4 h-4" />
                  Edit
                </button>
                <button className="px-3 py-2 bg-white/10 hover:bg-red-100 text-gray-700 hover:text-red-600 rounded-lg transition-colors">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-12">
          <div className="w-24 h-24 bg-gradient-to-br from-purple-100 to-teal-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Briefcase className="w-12 h-12 text-purple-500" />
          </div>
          <h3 className="text-xl text-gray-800 mb-2">No Job Profiles Found</h3>
          <p className="text-gray-600">
            {searchTerm ? 'Try adjusting your search terms.' : 'Create your first job profile to get started.'}
          </p>
        </div>
      )}
    </div>
  );
}