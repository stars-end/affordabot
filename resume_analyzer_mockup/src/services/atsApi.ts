// ATS API Service - TypeScript Implementation
interface PersonalInfo {
  name: string;
  email: string;
  phone: string;
  location: string;
}

interface Section {
  name: string;
  score: number;
  status: string;
  found: boolean;
}

interface Skill {
  name: string;
  confidence: number;
  category: string;
}

interface Experience {
  totalYears: number;
  positions: Array<{
    title: string;
    company: string;
    duration: string;
    skills: string[];
  }>;
}

interface Education {
  degree: string;
  institution: string;
  year: string;
}

interface JobMatch {
  title: string;
  matchPercentage: number;
  missingSkills: string[];
  strengths: string[];
  recommendations: string[];
}

interface Keywords {
  found: string[];
  missing: string[];
  density: number;
}

interface Formatting {
  score: number;
  issues: string[];
}

interface Analysis {
  overallScore: number;
  personalInfo: PersonalInfo;
  sections: Section[];
  skills: Skill[];
  experience: Experience;
  education: Education[];
  jobMatch: JobMatch;
  keywords: Keywords;
  formatting: Formatting;
  analysisDate: string;
  textLength: number;
}

interface Resume {
  id: string;
  filename: string;
  uploadDate: string;
  status: 'completed' | 'processing' | 'failed' | 'queued';
  analysis?: Analysis;
}

interface JobProfile {
  id: string;
  title: string;
  requiredSkills: string[];
  preferredSkills: string[];
  minimumExperience: number;
  description: string;
}

interface AnalysisStatus {
  status: 'processing' | 'completed' | 'failed' | 'unknown';
  progress?: number;
}

interface UploadResponse {
  jobId: string;
  resumeId: string;
}

interface BackendStatus {
  available: boolean;
  url: string;
}

interface ModeInfo {
  mode: 'backend' | 'demo';
  features: string[];
}

class ATSApiService {
  private baseUrl = 'http://localhost:5000/api';
  private isBackendAvailable = false;
  private mockResumes: Resume[] = [];
  private mockJobProfiles: JobProfile[] = [];
  private processingJobs = new Map<string, any>();

  constructor() {
    this.initializeMockData();
    console.log('🚀 ATS API Service initialized in demo mode');
    console.log('📋 All features work with realistic mock data');
  }

  private initializeMockData(): void {
    this.mockResumes = [
      {
        id: '1',
        filename: 'john_doe_resume.pdf',
        uploadDate: '2024-01-20T10:30:00Z',
        status: 'completed',
        analysis: {
          overallScore: 87,
          personalInfo: {
            name: 'John Doe',
            email: 'john.doe@email.com',
            phone: '+1 (555) 123-4567',
            location: 'San Francisco, CA'
          },
          sections: [
            { name: 'Skills Match', score: 92, status: 'excellent', found: true },
            { name: 'Experience', score: 85, status: 'good', found: true },
            { name: 'Education', score: 78, status: 'average', found: true },
            { name: 'Keywords', score: 90, status: 'excellent', found: true }
          ],
          skills: [
            { name: 'JavaScript', confidence: 0.95, category: 'programming' },
            { name: 'React', confidence: 0.92, category: 'web_frontend' },
            { name: 'Python', confidence: 0.88, category: 'programming' },
            { name: 'SQL', confidence: 0.85, category: 'databases' }
          ],
          experience: {
            totalYears: 5,
            positions: [
              {
                title: 'Senior Developer',
                company: 'Tech Corp',
                duration: '2021-Present',
                skills: ['React', 'Node.js', 'PostgreSQL']
              }
            ]
          },
          education: [
            {
              degree: 'Bachelor of Science in Computer Science',
              institution: 'University of California',
              year: '2019'
            }
          ],
          jobMatch: {
            title: 'Full Stack Developer',
            matchPercentage: 87,
            missingSkills: ['GraphQL', 'Docker'],
            strengths: ['React expertise', 'Full-stack experience'],
            recommendations: [
              'Add GraphQL experience to improve backend skills',
              'Include more quantified achievements in your experience section',
              'Consider adding Docker container knowledge'
            ]
          },
          keywords: {
            found: ['JavaScript', 'React', 'Python', 'SQL'],
            missing: ['GraphQL', 'Docker'],
            density: 6
          },
          formatting: {
            score: 85,
            issues: ['Consider using more bullet points', 'Add consistent formatting for dates']
          },
          analysisDate: '2024-01-20T10:35:00Z',
          textLength: 1850
        }
      },
      {
        id: '2',
        filename: 'jane_smith_resume.pdf',
        uploadDate: '2024-01-19T14:20:00Z',
        status: 'completed',
        analysis: {
          overallScore: 92,
          personalInfo: {
            name: 'Jane Smith',
            email: 'jane.smith@email.com',
            phone: '+1 (555) 987-6543',
            location: 'New York, NY'
          },
          sections: [
            { name: 'Skills Match', score: 95, status: 'excellent', found: true },
            { name: 'Experience', score: 90, status: 'excellent', found: true },
            { name: 'Education', score: 88, status: 'good', found: true },
            { name: 'Keywords', score: 93, status: 'excellent', found: true }
          ],
          skills: [
            { name: 'Python', confidence: 0.98, category: 'programming' },
            { name: 'Django', confidence: 0.94, category: 'web_backend' },
            { name: 'PostgreSQL', confidence: 0.91, category: 'databases' },
            { name: 'Docker', confidence: 0.89, category: 'cloud' }
          ],
          experience: {
            totalYears: 6,
            positions: [
              {
                title: 'Lead Backend Developer',
                company: 'DataTech Inc',
                duration: '2022-Present',
                skills: ['Python', 'Django', 'PostgreSQL', 'AWS']
              }
            ]
          },
          education: [
            {
              degree: 'Master of Science in Computer Science',
              institution: 'MIT',
              year: '2020'
            }
          ],
          jobMatch: {
            title: 'Backend Developer',
            matchPercentage: 92,
            missingSkills: ['Kubernetes'],
            strengths: ['Python expertise', 'Database design', 'Cloud architecture'],
            recommendations: [
              'Excellent match for senior backend positions',
              'Consider adding Kubernetes for container orchestration'
            ]
          },
          keywords: {
            found: ['Python', 'Django', 'PostgreSQL', 'Docker', 'AWS'],
            missing: ['Kubernetes', 'Microservices'],
            density: 7
          },
          formatting: {
            score: 92,
            issues: []
          },
          analysisDate: '2024-01-19T14:25:00Z',
          textLength: 2100
        }
      }
    ];

    this.mockJobProfiles = [
      {
        id: 'fullstack',
        title: 'Full Stack Developer',
        requiredSkills: ['JavaScript', 'React', 'Node.js', 'HTML', 'CSS'],
        preferredSkills: ['Python', 'TypeScript', 'PostgreSQL', 'AWS'],
        minimumExperience: 3,
        description: 'Full stack web developer with modern JavaScript technologies'
      },
      {
        id: 'frontend',
        title: 'Frontend Developer',
        requiredSkills: ['JavaScript', 'React', 'HTML', 'CSS'],
        preferredSkills: ['TypeScript', 'Vue.js', 'Sass', 'Webpack'],
        minimumExperience: 2,
        description: 'Frontend developer focused on user interface development'
      },
      {
        id: 'backend',
        title: 'Backend Developer',
        requiredSkills: ['Python', 'Node.js', 'SQL', 'API Development'],
        preferredSkills: ['Django', 'Flask', 'PostgreSQL', 'Redis'],
        minimumExperience: 3,
        description: 'Backend developer for server-side applications'
      },
      {
        id: 'datascientist',
        title: 'Data Scientist',
        requiredSkills: ['Python', 'Machine Learning', 'SQL', 'Statistics'],
        preferredSkills: ['TensorFlow', 'PyTorch', 'R', 'Spark'],
        minimumExperience: 2,
        description: 'Data scientist with machine learning expertise'
      }
    ];
  }

  async uploadResume(file: File, jobProfileId: string): Promise<UploadResponse> {
    await this.delay(1000);
    const resumeId = this.generateId();
    const jobId = this.generateId();
    
    console.log(`📄 Demo upload: ${file.name} (${this.formatFileSize(file.size)})`);
    
    // Add to demo data
    this.mockResumes.unshift({
      id: resumeId,
      filename: file.name,
      uploadDate: new Date().toISOString(),
      status: 'processing'
    });
    
    // Store processing job
    this.processingJobs.set(jobId, {
      status: 'processing',
      progress: 0,
      resumeId: resumeId
    });
    
    // Simulate processing completion after 3 seconds
    setTimeout(() => {
      this.completeProcessing(resumeId, jobId, jobProfileId);
    }, 3000);
    
    return { jobId, resumeId };
  }

  async getAnalysisStatus(jobId: string): Promise<AnalysisStatus> {
    await this.delay(500);
    
    const job = this.processingJobs.get(jobId);
    if (!job) {
      return { status: 'unknown' };
    }
    
    return {
      status: job.status,
      progress: job.progress
    };
  }

  async getAnalysisResult(resumeId: string): Promise<Analysis> {
    await this.delay(800);
    
    const resume = this.mockResumes.find(r => r.id === resumeId);
    if (!resume?.analysis) {
      throw new Error('Analysis not found or not completed yet');
    }
    
    return resume.analysis;
  }

  async getAllResumes(): Promise<Resume[]> {
    await this.delay(600);
    return [...this.mockResumes].reverse(); // Most recent first
  }

  async deleteResume(resumeId: string): Promise<void> {
    await this.delay(400);
    
    const index = this.mockResumes.findIndex(r => r.id === resumeId);
    if (index !== -1) {
      this.mockResumes.splice(index, 1);
      console.log(`🗑️ Demo delete: Resume ${resumeId}`);
    }
  }

  async getJobProfiles(): Promise<JobProfile[]> {
    await this.delay(400);
    return [...this.mockJobProfiles];
  }

  async createJobProfile(profile: Omit<JobProfile, 'id'>): Promise<JobProfile> {
    await this.delay(500);
    
    const newProfile: JobProfile = {
      ...profile,
      id: this.generateId()
    };
    
    this.mockJobProfiles.push(newProfile);
    return newProfile;
  }

  async exportAnalysis(resumeIds: string[], format: 'csv' | 'json'): Promise<Blob> {
    await this.delay(1500);
    
    const exportData = resumeIds.map(id => {
      const resume = this.mockResumes.find(r => r.id === id);
      return {
        filename: resume?.filename || 'Unknown',
        score: resume?.analysis?.overallScore || 0,
        status: resume?.status || 'unknown'
      };
    });
    
    const content = format === 'csv' 
      ? exportData.map(r => `${r.filename},${r.score},${r.status}`).join('\n')
      : JSON.stringify(exportData, null, 2);
    
    return new Blob([content], { 
      type: format === 'csv' ? 'text/csv' : 'application/json' 
    });
  }

  async batchUpload(files: File[], jobProfileId: string): Promise<{ jobId: string; resumeIds: string[] }> {
    await this.delay(2000);
    
    const jobId = this.generateId();
    const resumeIds = files.map(() => this.generateId());
    
    console.log(`📄 Demo batch upload: ${files.length} files`);
    files.forEach(file => console.log(`  - ${file.name}`));
    
    return { jobId, resumeIds };
  }

  async retryConnection(): Promise<boolean> {
    await this.delay(2000);
    // Simulate backend connection attempt
    console.log('🔄 Attempting to connect to backend...');
    console.log('❌ Backend not available - staying in demo mode');
    return false;
  }

  private completeProcessing(resumeId: string, jobId: string, jobProfileId: string): void {
    // Update resume with mock analysis
    const resumeIndex = this.mockResumes.findIndex(r => r.id === resumeId);
    if (resumeIndex !== -1) {
      this.mockResumes[resumeIndex] = {
        ...this.mockResumes[resumeIndex],
        status: 'completed',
        analysis: this.generateRandomAnalysis(jobProfileId)
      };
    }
    
    // Update job progress
    this.processingJobs.set(jobId, {
      status: 'completed',
      progress: 100,
      resumeId: resumeId
    });
  }

  private generateRandomAnalysis(jobProfileId: string): Analysis {
    const baseScore = 60 + Math.random() * 35; // Score between 60-95
    
    return {
      overallScore: Math.round(baseScore),
      personalInfo: {
        name: this.generateRandomName(),
        email: 'candidate@email.com',
        phone: '+1 (555) 123-4567',
        location: this.getRandomLocation()
      },
      sections: [
        { name: 'Skills Match', score: Math.round(baseScore + Math.random() * 10 - 5), status: 'good', found: true },
        { name: 'Experience', score: Math.round(baseScore + Math.random() * 10 - 5), status: 'good', found: true },
        { name: 'Education', score: Math.round(baseScore + Math.random() * 10 - 5), status: 'average', found: true },
        { name: 'Keywords', score: Math.round(baseScore + Math.random() * 10 - 5), status: 'good', found: true }
      ],
      skills: this.generateRandomSkills(),
      experience: {
        totalYears: Math.floor(Math.random() * 8) + 2,
        positions: [
          {
            title: 'Software Developer',
            company: 'Tech Company',
            duration: '2021-Present',
            skills: ['JavaScript', 'React', 'Node.js']
          }
        ]
      },
      education: [
        {
          degree: 'Bachelor of Science in Computer Science',
          institution: 'University',
          year: '2020'
        }
      ],
      jobMatch: {
        title: this.getJobTitle(jobProfileId),
        matchPercentage: Math.round(baseScore),
        missingSkills: ['GraphQL', 'Docker'],
        strengths: ['Technical skills', 'Experience'],
        recommendations: [
          'Add more technical projects',
          'Improve keyword optimization',
          'Include quantified achievements'
        ]
      },
      keywords: {
        found: ['JavaScript', 'React', 'Python'],
        missing: ['TypeScript', 'AWS'],
        density: 6
      },
      formatting: {
        score: Math.round(80 + Math.random() * 15),
        issues: []
      },
      analysisDate: new Date().toISOString(),
      textLength: 1500 + Math.floor(Math.random() * 1000)
    };
  }

  private generateRandomName(): string {
    const firstNames = ['John', 'Jane', 'Mike', 'Sarah', 'David', 'Emily', 'Chris', 'Lisa', 'Alex', 'Maria'];
    const lastNames = ['Smith', 'Johnson', 'Brown', 'Davis', 'Wilson', 'Miller', 'Taylor', 'Anderson', 'Garcia', 'Martinez'];
    
    const firstName = firstNames[Math.floor(Math.random() * firstNames.length)];
    const lastName = lastNames[Math.floor(Math.random() * lastNames.length)];
    
    return `${firstName} ${lastName}`;
  }

  private getRandomLocation(): string {
    const locations = ['San Francisco, CA', 'New York, NY', 'Austin, TX', 'Seattle, WA', 'Boston, MA', 'Denver, CO', 'Chicago, IL', 'Los Angeles, CA'];
    return locations[Math.floor(Math.random() * locations.length)];
  }

  private generateRandomSkills(): Skill[] {
    const allSkills = [
      { name: 'JavaScript', confidence: 0.85 + Math.random() * 0.1, category: 'programming' },
      { name: 'React', confidence: 0.8 + Math.random() * 0.15, category: 'web_frontend' },
      { name: 'Node.js', confidence: 0.75 + Math.random() * 0.2, category: 'web_backend' },
      { name: 'Python', confidence: 0.7 + Math.random() * 0.25, category: 'programming' },
      { name: 'HTML', confidence: 0.9 + Math.random() * 0.1, category: 'web_frontend' },
      { name: 'CSS', confidence: 0.85 + Math.random() * 0.1, category: 'web_frontend' },
      { name: 'SQL', confidence: 0.7 + Math.random() * 0.2, category: 'databases' },
      { name: 'AWS', confidence: 0.6 + Math.random() * 0.3, category: 'cloud' },
      { name: 'TypeScript', confidence: 0.65 + Math.random() * 0.25, category: 'programming' },
      { name: 'Vue.js', confidence: 0.6 + Math.random() * 0.3, category: 'web_frontend' }
    ];
    
    const numSkills = 4 + Math.floor(Math.random() * 5);
    return allSkills.slice(0, numSkills);
  }

  private getJobTitle(jobProfileId: string): string {
    const profile = this.mockJobProfiles.find(p => p.id === jobProfileId);
    return profile?.title || 'Full Stack Developer';
  }

  private formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  private generateId(): string {
    return Math.random().toString(36).substr(2, 9);
  }

  getBackendStatus(): BackendStatus {
    return {
      available: this.isBackendAvailable,
      url: this.baseUrl
    };
  }

  getModeInfo(): ModeInfo {
    return {
      mode: 'demo',
      features: [
        'Interactive UI demonstration',
        'Realistic mock analysis results',
        'File upload simulation',
        'Chart visualizations',
        'Export functionality',
        'All frontend features',
        'No backend required'
      ]
    };
  }
}

// Export singleton instance
export const atsApi = new ATSApiService();