"""
ATS Resume Processor - Core analysis engine
Handles PDF/DOCX parsing, NLP analysis, and skill matching
"""

import os
import re
import fitz  # PyMuPDF
import pdfplumber
import docx2txt
import spacy
from keybert import KeyBERT
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np
from datetime import datetime
import json

class ATSProcessor:
    def __init__(self):
        # Load spaCy model
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("spaCy model 'en_core_web_sm' not found. Install with: python -m spacy download en_core_web_sm")
            self.nlp = None
        
        # Initialize KeyBERT
        self.kw_model = KeyBERT()
        
        # Initialize BERT model for embeddings
        self.tokenizer = AutoTokenizer.from_pretrained('sentence-transformers/all-MiniLM-L6-v2')
        self.model = AutoModel.from_pretrained('sentence-transformers/all-MiniLM-L6-v2')
        
        # Predefined skill categories and patterns
        self.skill_patterns = {
            'programming': [
                'python', 'javascript', 'java', 'c++', 'c#', 'php', 'ruby', 'go', 'rust',
                'typescript', 'kotlin', 'swift', 'scala', 'r', 'matlab'
            ],
            'web_frontend': [
                'html', 'css', 'react', 'angular', 'vue', 'jquery', 'bootstrap',
                'sass', 'less', 'webpack', 'babel', 'redux', 'vuex'
            ],
            'web_backend': [
                'node.js', 'express', 'django', 'flask', 'spring', 'asp.net',
                'laravel', 'rails', 'fastapi', 'rest api', 'graphql'
            ],
            'databases': [
                'mysql', 'postgresql', 'mongodb', 'redis', 'sqlite', 'oracle',
                'sql server', 'elasticsearch', 'cassandra', 'dynamodb'
            ],
            'cloud': [
                'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform',
                'ansible', 'jenkins', 'gitlab ci', 'github actions'
            ],
            'data_science': [
                'pandas', 'numpy', 'scikit-learn', 'tensorflow', 'pytorch',
                'jupyter', 'matplotlib', 'seaborn', 'plotly', 'spark'
            ]
        }
        
        # Common section headers
        self.section_patterns = {
            'experience': r'(?i)(work\s+experience|professional\s+experience|employment|experience)',
            'education': r'(?i)(education|academic|qualifications|degrees)',
            'skills': r'(?i)(skills|technical\s+skills|competencies|expertise)',
            'projects': r'(?i)(projects|portfolio|work\s+samples)',
            'certifications': r'(?i)(certifications|certificates|licenses)',
            'contact': r'(?i)(contact|personal\s+information|details)'
        }
    
    def extract_text_from_pdf(self, file_path):
        """Extract text from PDF using multiple methods for better accuracy"""
        text = ""
        
        # Try pdfplumber first (better for complex layouts)
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            print(f"pdfplumber failed: {e}")
        
        # If pdfplumber fails or returns little text, try PyMuPDF
        if len(text.strip()) < 100:
            try:
                doc = fitz.open(file_path)
                text = ""
                for page in doc:
                    text += page.get_text() + "\n"
                doc.close()
            except Exception as e:
                print(f"PyMuPDF failed: {e}")
        
        return text.strip()
    
    def extract_text_from_docx(self, file_path):
        """Extract text from DOCX file"""
        try:
            return docx2txt.process(file_path)
        except Exception as e:
            print(f"DOCX extraction failed: {e}")
            return ""
    
    def extract_text(self, file_path):
        """Extract text based on file extension"""
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == '.pdf':
            return self.extract_text_from_pdf(file_path)
        elif file_ext in ['.docx', '.doc']:
            return self.extract_text_from_docx(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
    
    def extract_personal_info(self, text):
        """Extract personal information using regex patterns"""
        personal_info = {}
        
        # Email extraction
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        if emails:
            personal_info['email'] = emails[0]
        
        # Phone extraction
        phone_pattern = r'(\+?\d{1,4}[-.\s]?)?\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})'
        phones = re.findall(phone_pattern, text)
        if phones:
            personal_info['phone'] = ''.join(phones[0])
        
        # Name extraction (first line or after "Name:" pattern)
        lines = text.split('\n')
        name_patterns = [
            r'name[:\s]+(.+)',
            r'(.+?)(?:\s*\n|\s*email|\s*phone|\s*address)',
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                potential_name = match.group(1).strip()
                if len(potential_name.split()) >= 2 and len(potential_name) < 50:
                    personal_info['name'] = potential_name
                    break
        
        # Location extraction
        location_pattern = r'(?i)(location|address)[:\s]+(.+?)(?:\n|$)'
        location_match = re.search(location_pattern, text)
        if location_match:
            personal_info['location'] = location_match.group(2).strip()
        
        return personal_info
    
    def detect_sections(self, text):
        """Detect resume sections and their content"""
        sections = {}
        
        for section_name, pattern in self.section_patterns.items():
            matches = list(re.finditer(pattern, text, re.MULTILINE))
            if matches:
                sections[section_name] = {
                    'found': True,
                    'positions': [match.start() for match in matches]
                }
            else:
                sections[section_name] = {'found': False, 'positions': []}
        
        return sections
    
    def extract_skills(self, text):
        """Extract skills using multiple methods"""
        skills = {}
        text_lower = text.lower()
        
        # Pattern-based skill extraction
        for category, skill_list in self.skill_patterns.items():
            found_skills = []
            for skill in skill_list:
                # Create flexible pattern for skill matching
                pattern = r'\b' + re.escape(skill.lower()) + r'\b'
                if re.search(pattern, text_lower):
                    found_skills.append({
                        'name': skill,
                        'confidence': 0.9,  # High confidence for pattern matches
                        'category': category
                    })
            skills[category] = found_skills
        
        # KeyBERT keyword extraction for additional skills
        try:
            keywords = self.kw_model.extract_keywords(text, keyphrase_ngram_range=(1, 2), 
                                                    stop_words='english', top_k=20)
            
            for keyword, score in keywords:
                if score > 0.3:  # Confidence threshold
                    # Categorize extracted keywords
                    category = self.categorize_skill(keyword)
                    if category not in skills:
                        skills[category] = []
                    
                    skills[category].append({
                        'name': keyword,
                        'confidence': score,
                        'category': category
                    })
        except Exception as e:
            print(f"KeyBERT extraction failed: {e}")
        
        # Flatten skills list
        all_skills = []
        for category_skills in skills.values():
            all_skills.extend(category_skills)
        
        return all_skills
    
    def categorize_skill(self, skill):
        """Categorize a skill based on predefined patterns"""
        skill_lower = skill.lower()
        
        for category, patterns in self.skill_patterns.items():
            if any(pattern in skill_lower for pattern in patterns):
                return category
        
        return 'other'
    
    def extract_experience(self, text):
        """Extract work experience information"""
        experience = {
            'totalYears': 0,
            'positions': []
        }
        
        # Look for year patterns to estimate total experience
        year_pattern = r'\b(19|20)\d{2}\b'
        years = [int(year) for year in re.findall(year_pattern, text)]
        
        if years:
            current_year = datetime.now().year
            min_year = min(years)
            max_year = max(years)
            
            # Estimate total years of experience
            if min_year < current_year:
                experience['totalYears'] = current_year - min_year
        
        # Extract position titles (simplified)
        position_patterns = [
            r'(?i)(developer|engineer|manager|analyst|specialist|coordinator|director|lead)',
            r'(?i)(software|web|frontend|backend|full.?stack|data|systems)',
        ]
        
        positions = []
        for pattern in position_patterns:
            matches = re.findall(f'.{{0,20}}{pattern}.{{0,20}}', text, re.IGNORECASE)
            positions.extend(matches[:3])  # Limit to prevent noise
        
        experience['positions'] = [{'title': pos.strip(), 'company': 'Unknown', 'duration': 'Unknown', 'skills': []} 
                                 for pos in positions[:5]]
        
        return experience
    
    def extract_education(self, text):
        """Extract education information"""
        education = []
        
        # Degree patterns
        degree_patterns = [
            r'(?i)(bachelor|master|phd|doctorate|diploma|certificate).{0,50}(computer|software|engineering|science|technology)',
            r'(?i)(b\.?s\.?|m\.?s\.?|m\.?a\.?|b\.?a\.?|ph\.?d\.?)',
        ]
        
        for pattern in degree_patterns:
            matches = re.findall(pattern, text)
            for match in matches[:3]:  # Limit results
                education.append({
                    'degree': ' '.join(match) if isinstance(match, tuple) else match,
                    'institution': 'Unknown',
                    'year': 'Unknown'
                })
        
        return education
    
    def calculate_job_match(self, resume_skills, job_profile_id=None):
        """Calculate job matching score"""
        # Default job profiles
        job_profiles = {
            'fullstack': {
                'title': 'Full Stack Developer',
                'required_skills': ['javascript', 'react', 'node.js', 'html', 'css'],
                'preferred_skills': ['python', 'typescript', 'postgresql', 'aws'],
                'weights': {'required': 0.7, 'preferred': 0.3}
            },
            'frontend': {
                'title': 'Frontend Developer',
                'required_skills': ['javascript', 'react', 'html', 'css'],
                'preferred_skills': ['typescript', 'vue.js', 'sass', 'webpack'],
                'weights': {'required': 0.8, 'preferred': 0.2}
            },
            'backend': {
                'title': 'Backend Developer',
                'required_skills': ['python', 'node.js', 'sql', 'api development'],
                'preferred_skills': ['django', 'flask', 'postgresql', 'redis'],
                'weights': {'required': 0.8, 'preferred': 0.2}
            }
        }
        
        # Use default profile if none specified
        if not job_profile_id or job_profile_id not in job_profiles:
            job_profile_id = 'fullstack'
        
        profile = job_profiles[job_profile_id]
        resume_skill_names = [skill['name'].lower() for skill in resume_skills]
        
        # Calculate required skills match
        required_matches = sum(1 for skill in profile['required_skills'] 
                             if skill.lower() in resume_skill_names)
        required_score = (required_matches / len(profile['required_skills'])) * 100
        
        # Calculate preferred skills match
        preferred_matches = sum(1 for skill in profile['preferred_skills'] 
                              if skill.lower() in resume_skill_names)
        preferred_score = (preferred_matches / len(profile['preferred_skills'])) * 100 if profile['preferred_skills'] else 0
        
        # Weighted final score
        weights = profile['weights']
        final_score = (required_score * weights['required'] + 
                      preferred_score * weights['preferred'])
        
        # Find missing skills
        missing_skills = [skill for skill in profile['required_skills'] + profile['preferred_skills']
                         if skill.lower() not in resume_skill_names]
        
        # Find strengths
        strengths = [skill['name'] for skill in resume_skills 
                    if skill['name'].lower() in [s.lower() for s in profile['required_skills'] + profile['preferred_skills']]]
        
        # Generate recommendations
        recommendations = []
        if required_matches < len(profile['required_skills']):
            recommendations.append("Focus on acquiring missing required skills")
        if preferred_matches < len(profile['preferred_skills']) / 2:
            recommendations.append("Consider learning preferred skills to stand out")
        if len(resume_skills) < 10:
            recommendations.append("Add more technical skills to your resume")
        
        return {
            'title': profile['title'],
            'matchPercentage': int(final_score),
            'missingSkills': missing_skills[:5],  # Top 5 missing
            'strengths': strengths[:5],  # Top 5 strengths
            'recommendations': recommendations
        }
    
    def calculate_section_scores(self, sections, text):
        """Calculate scores for different resume sections"""
        section_scores = []
        
        section_weights = {
            'experience': 30,
            'education': 20,
            'skills': 25,
            'projects': 15,
            'certifications': 10
        }
        
        for section_name, weight in section_weights.items():
            found = sections.get(section_name, {}).get('found', False)
            
            # Base score for having the section
            score = 70 if found else 0
            
            # Additional scoring based on content quality
            if found and section_name in ['experience', 'education', 'skills']:
                # Simple content length check
                section_content_length = len(text) // 10  # Rough estimate
                if section_content_length > 100:
                    score += 20
                elif section_content_length > 50:
                    score += 10
            
            status = 'excellent' if score >= 90 else 'good' if score >= 70 else 'average' if score >= 50 else 'poor'
            
            section_scores.append({
                'name': section_name.title(),
                'score': min(100, score),
                'status': status,
                'found': found
            })
        
        return section_scores
    
    def calculate_overall_score(self, section_scores, job_match_score, skills_count):
        """Calculate overall ATS score"""
        # Weighted average of different components
        weights = {
            'sections': 0.3,
            'job_match': 0.4,
            'skills_density': 0.2,
            'formatting': 0.1
        }
        
        # Average section score
        avg_section_score = sum(s['score'] for s in section_scores) / len(section_scores)
        
        # Skills density score (more skills = better, up to a point)
        skills_density_score = min(100, (skills_count / 15) * 100)
        
        # Formatting score (simplified)
        formatting_score = 85  # Assume good formatting for now
        
        overall = (
            avg_section_score * weights['sections'] +
            job_match_score * weights['job_match'] +
            skills_density_score * weights['skills_density'] +
            formatting_score * weights['formatting']
        )
        
        return int(overall)
    
    def analyze_resume(self, file_path, job_profile_id=None):
        """Main analysis function"""
        try:
            # Extract text
            text = self.extract_text(file_path)
            
            if not text or len(text.strip()) < 50:
                raise ValueError("Could not extract sufficient text from resume")
            
            # Extract information
            personal_info = self.extract_personal_info(text)
            sections = self.detect_sections(text)
            skills = self.extract_skills(text)
            experience = self.extract_experience(text)
            education = self.extract_education(text)
            
            # Calculate scores
            section_scores = self.calculate_section_scores(sections, text)
            job_match = self.calculate_job_match(skills, job_profile_id)
            overall_score = self.calculate_overall_score(section_scores, job_match['matchPercentage'], len(skills))
            
            # Build analysis result
            analysis_result = {
                'overallScore': overall_score,
                'personalInfo': personal_info,
                'sections': section_scores,
                'skills': skills,
                'experience': experience,
                'education': education,
                'jobMatch': job_match,
                'keywords': {
                    'found': [skill['name'] for skill in skills],
                    'missing': job_match['missingSkills'],
                    'density': len(skills)
                },
                'formatting': {
                    'score': 85,
                    'issues': []
                },
                'analysisDate': datetime.now().isoformat(),
                'textLength': len(text)
            }
            
            return analysis_result
            
        except Exception as e:
            raise Exception(f"Analysis failed: {str(e)}")