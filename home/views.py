from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import re
import logging
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from collections import Counter
import spacy
from datetime import datetime

# PDF Generation imports
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from io import BytesIO

logger = logging.getLogger(__name__)

# Initialize spaCy model (install with: python -m spacy download en_core_web_sm)
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    nlp = None
    logger.warning("spaCy model not found. Install with: python -m spacy download en_core_web_sm")

class JobMatcher:
    """Handles job description parsing and candidate matching"""
    
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2),
            min_df=1
        )
        self.skill_keywords = [
            'python', 'java', 'javascript', 'react', 'nodejs', 'django', 'flask',
            'sql', 'mongodb', 'postgresql', 'mysql', 'aws', 'azure', 'docker',
            'kubernetes', 'git', 'machine learning', 'ai', 'data science',
            'agile', 'scrum', 'devops', 'ci/cd', 'html', 'css', 'angular',
            'vue', 'tensorflow', 'pytorch', 'pandas', 'numpy', 'api', 'rest',
            'microservices', 'cloud computing', 'blockchain', 'cybersecurity'
        ]
    
    def extract_skills_from_text(self, text):
        """Extract skills from job description or resume text"""
        text_lower = text.lower()
        found_skills = []
        
        # Basic keyword matching
        for skill in self.skill_keywords:
            if skill.lower() in text_lower:
                found_skills.append(skill)
        
        # Use spaCy for entity extraction if available
        if nlp:
            doc = nlp(text)
            for ent in doc.ents:
                if ent.label_ in ['ORG', 'PRODUCT', 'SKILL']:  # Custom skill entities
                    found_skills.append(ent.text.lower())
        
        return list(set(found_skills))
    
    def extract_experience_years(self, text):
        """Extract years of experience from text"""
        patterns = [
            r'(\d+)\s*(?:\+)?\s*years?\s*(?:of\s*)?(?:experience|exp)',
            r'(\d+)\s*(?:\+)?\s*yrs?\s*(?:experience|exp)',
            r'(\d+)\s*(?:\+)?\s*years?\s*in',
        ]
        
        years = []
        for pattern in patterns:
            matches = re.findall(pattern, text.lower())
            years.extend([int(match) for match in matches])
        
        return max(years) if years else 0
    
    def compute_similarity_score(self, job_description, candidate_data):
        """Compute similarity score between job and candidate"""
        # Combine candidate text
        candidate_text = f"""
        {candidate_data.get('about', '')} 
        {' '.join(candidate_data.get('skills', []))}
        {' '.join([exp.get('description', '') for exp in candidate_data.get('experience', [])])}
        {' '.join([proj.get('description', '') for proj in candidate_data.get('projects', [])])}
        """
        
        # Vectorize texts
        try:
            texts = [job_description, candidate_text]
            tfidf_matrix = self.vectorizer.fit_transform(texts)
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return float(similarity)
        except:
            return 0.0
    
    def rank_candidates(self, job_description, candidates_list):
        """Rank candidates based on job requirements"""
        job_skills = self.extract_skills_from_text(job_description)
        job_experience_req = self.extract_experience_years(job_description)
        
        scored_candidates = []
        
        for candidate in candidates_list:
            # Similarity score (40% weight)
            similarity_score = self.compute_similarity_score(job_description, candidate)
            
            # Skill match score (30% weight)
            candidate_skills = candidate.get('skills', [])
            skill_matches = len(set(job_skills) & set([s.lower() for s in candidate_skills]))
            skill_score = skill_matches / max(len(job_skills), 1)
            
            # Experience score (20% weight)
            candidate_exp = len([exp for exp in candidate.get('experience', []) if exp.get('company')])
            experience_score = min(candidate_exp / max(job_experience_req, 1), 1.0)
            
            # Education score (10% weight)
            education_score = len([edu for edu in candidate.get('education', []) if edu.get('degree')]) * 0.2
            education_score = min(education_score, 1.0)
            
            # Composite score
            final_score = (
                similarity_score * 0.4 +
                skill_score * 0.3 +
                experience_score * 0.2 +
                education_score * 0.1
            )
            
            scored_candidates.append({
                'candidate': candidate,
                'score': final_score,
                'similarity_score': similarity_score,
                'skill_score': skill_score,
                'experience_score': experience_score,
                'education_score': education_score,
                'matched_skills': [s for s in job_skills if s.lower() in [cs.lower() for cs in candidate_skills]]
            })
        
        return sorted(scored_candidates, key=lambda x: x['score'], reverse=True)

# Initialize matcher
job_matcher = JobMatcher()

def resume_form(request):
    """Render the resume form (HTML)"""
    return render(request, 'resume.html')

@csrf_exempt
@require_http_methods(["POST"])
def generate_resume(request):
    """Process the resume form and generate a PDF"""
    try:
        # Extract form data
        form_data = {
            'name': request.POST.get('name', ''),
            'about': request.POST.get('about', ''),
            'age': request.POST.get('age', ''),
            'email': request.POST.get('email', ''),
            'phone': request.POST.get('phone', ''),

            # Skills
            'skills': [
                request.POST.get('skill1', ''),
                request.POST.get('skill2', ''),
                request.POST.get('skill3', ''),
                request.POST.get('skill4', ''),
                request.POST.get('skill5', ''),
            ],

            # Education
            'education': [
                {
                    'degree': request.POST.get('degree1', ''),
                    'college': request.POST.get('college1', ''),
                    'year': request.POST.get('year1', ''),
                },
                {
                    'degree': request.POST.get('degree2', ''),
                    'college': request.POST.get('college2', ''),
                    'year': request.POST.get('year2', ''),
                },
                {
                    'degree': request.POST.get('degree3', ''),
                    'college': request.POST.get('college3', ''),
                    'year': request.POST.get('year3', ''),
                }
            ],

            # Languages
            'languages': [
                request.POST.get('lang1', ''),
                request.POST.get('lang2', ''),
                request.POST.get('lang3', ''),
            ],

            # Projects
            'projects': [
                {
                    'title': request.POST.get('project1', ''),
                    'duration': request.POST.get('durat1', ''),
                    'description': request.POST.get('desc1', ''),
                },
                {
                    'title': request.POST.get('project2', ''),
                    'duration': request.POST.get('durat2', ''),
                    'description': request.POST.get('desc2', ''),
                }
            ],

            # Experience
            'experience': [
                {
                    'company': request.POST.get('company1', ''),
                    'position': request.POST.get('post1', ''),
                    'duration': request.POST.get('duration1', ''),
                    'description': request.POST.get('lin11', ''),
                },
                {
                    'company': request.POST.get('company2', ''),
                    'position': request.POST.get('post2', ''),
                    'duration': request.POST.get('duration2', ''),
                    'description': request.POST.get('lin21', ''),
                }
            ],

            # Achievements
            'achievements': [
                request.POST.get('ach1', ''),
                request.POST.get('ach2', ''),
                request.POST.get('ach3', ''),
            ]
        }

        # Generate PDF
        pdf_buffer = generate_resume_pdf(form_data)

        # Return PDF response
        response = HttpResponse(content_type='application/pdf')
        filename = (form_data["name"] or "resume").replace(" ", "_")
        response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
        response.write(pdf_buffer.getvalue())
        return response

    except Exception as e:
        logger.exception("Error generating resume")
        return HttpResponse("Error generating resume. Please try again.", status=500)

def generate_resume_pdf(data):
    """Generate a professional PDF resume"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=1,  # Center
        textColor=HexColor('#667eea')
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        textColor=HexColor('#764ba2'),
        borderWidth=1,
        borderColor=HexColor('#667eea'),
        borderPadding=5,
        backColor=HexColor('#f0f8ff')
    )

    normal_style = styles['Normal']

    story = []

    # Name
    if data.get('name'):
        story.append(Paragraph(data['name'], title_style))
        story.append(Spacer(1, 12))

    # Contact info
    contact_bits = []
    if data.get('email'):
        contact_bits.append(f"Email: {data['email']}")
    if data.get('phone'):
        contact_bits.append(f"Phone: {data['phone']}")
    if data.get('age'):
        contact_bits.append(f"Age: {data['age']}")
    if contact_bits:
        story.append(Paragraph(" | ".join(contact_bits), normal_style))
        story.append(Spacer(1, 20))

    # Summary
    if data.get('about'):
        story.append(Paragraph("Professional Summary", heading_style))
        story.append(Paragraph(data['about'], normal_style))
        story.append(Spacer(1, 20))

    # Skills
    skills = [s for s in data.get('skills', []) if s.strip()]
    if skills:
        story.append(Paragraph("Skills", heading_style))
        story.append(Paragraph(" • ".join(skills), normal_style))
        story.append(Spacer(1, 20))

    # Experience
    experience = [e for e in data.get('experience', []) if e.get('company', '').strip()]
    if experience:
        story.append(Paragraph("Work Experience", heading_style))
        for exp in experience:
            title = []
            if exp.get('position'):
                title.append(f"<b>{exp['position']}</b>")
            if exp.get('company'):
                title.append(f"- {exp['company']}")
            if exp.get('duration'):
                title.append(f" ({exp['duration']})")
            story.append(Paragraph("".join(title), normal_style))
            if exp.get('description'):
                story.append(Paragraph(exp['description'], normal_style))
            story.append(Spacer(1, 10))
        story.append(Spacer(1, 10))

    # Projects
    projects = [p for p in data.get('projects', []) if p.get('title', '').strip()]
    if projects:
        story.append(Paragraph("Projects", heading_style))
        for proj in projects:
            line = f"<b>{proj.get('title','')}</b>"
            if proj.get('duration'):
                line += f" ({proj['duration']})"
            story.append(Paragraph(line, normal_style))
            if proj.get('description'):
                story.append(Paragraph(proj['description'], normal_style))
            story.append(Spacer(1, 10))
        story.append(Spacer(1, 10))

    # Education
    education = [e for e in data.get('education', []) if e.get('degree', '').strip()]
    if education:
        story.append(Paragraph("Education", heading_style))
        for edu in education:
            line = f"<b>{edu.get('degree','')}</b>"
            if edu.get('college'):
                line += f" - {edu['college']}"
            if edu.get('year'):
                line += f" ({edu['year']})"
            story.append(Paragraph(line, normal_style))
            story.append(Spacer(1, 5))
        story.append(Spacer(1, 10))

    # Languages
    langs = [l for l in data.get('languages', []) if l.strip()]
    if langs:
        story.append(Paragraph("Languages", heading_style))
        story.append(Paragraph(" • ".join(langs), normal_style))
        story.append(Spacer(1, 20))

    # Achievements
    achievements = [a for a in data.get('achievements', []) if a.strip()]
    if achievements:
        story.append(Paragraph("Achievements", heading_style))
        for a in achievements:
            story.append(Paragraph(f"• {a}", normal_style))
        story.append(Spacer(1, 10))

    doc.build(story)
    buffer.seek(0)
    return buffer

# === Enhanced AI Endpoints ===

@csrf_exempt
def ai_enhance_summary(request):
    """Enhanced summary generation with better context"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        data = json.loads(request.body)
        original_summary = data.get('summary', '')
        skills = data.get('skills', [])
        experience = data.get('experience', [])
        
        # Generate enhanced summary based on skills and experience
        enhanced_summary = generate_enhanced_summary(original_summary, skills, experience)
        
        return JsonResponse({'success': True, 'enhanced_summary': enhanced_summary})
    except Exception as e:
        logger.exception("Error enhancing summary")
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def ai_analyze_job(request):
    """Analyze job description and provide recommendations"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        data = json.loads(request.body)
        job_description = data.get('job_description', '')
        
        if not job_description.strip():
            return JsonResponse({'success': False, 'error': 'Job description is required'})
        
        # Extract skills from job description
        found_skills = job_matcher.extract_skills_from_text(job_description)
        
        # Generate recommendations
        recommendations = generate_job_recommendations(job_description, found_skills)
        
        return JsonResponse({
            'success': True,
            'key_skills': found_skills[:8],  # Top 8 skills
            'recommendations': recommendations,
            'experience_years': job_matcher.extract_experience_years(job_description)
        })
    except Exception as e:
        logger.exception("Error analyzing job")
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def ai_suggest_skills(request):
    """Suggest trending skills with better categorization"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        import random
        
        # Categorized trending skills
        skill_categories = {
            'Programming': ['Python', 'JavaScript', 'Java', 'Go', 'Rust', 'TypeScript'],
            'Web Development': ['React', 'Vue.js', 'Angular', 'Node.js', 'Next.js', 'Svelte'],
            'Data & AI': ['Machine Learning', 'Data Science', 'TensorFlow', 'PyTorch', 'Pandas', 'NumPy'],
            'Cloud & DevOps': ['AWS', 'Azure', 'Docker', 'Kubernetes', 'Terraform', 'Jenkins'],
            'Databases': ['PostgreSQL', 'MongoDB', 'Redis', 'Elasticsearch', 'GraphQL', 'MySQL']
        }
        
        # Select skills from different categories
        suggested = []
        for category, skills in skill_categories.items():
            suggested.extend(random.sample(skills, min(2, len(skills))))
        
        return JsonResponse({
            'success': True,
            'suggested_skills': random.sample(suggested, min(8, len(suggested))),
            'categories': skill_categories
        })
    except Exception as e:
        logger.exception("Error suggesting skills")
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def rank_candidates(request):
    """New endpoint: Rank candidates against job description"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        data = json.loads(request.body)
        job_description = data.get('job_description', '')
        candidates = data.get('candidates', [])
        
        if not job_description or not candidates:
            return JsonResponse({'success': False, 'error': 'Job description and candidates are required'})
        
        # Rank candidates
        ranked_results = job_matcher.rank_candidates(job_description, candidates)
        
        return JsonResponse({
            'success': True,
            'ranked_candidates': ranked_results[:10],  # Top 10
            'total_candidates': len(candidates),
            'avg_score': np.mean([r['score'] for r in ranked_results]) if ranked_results else 0
        })
    except Exception as e:
        logger.exception("Error ranking candidates")
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def match_resume_to_job(request):
    """New endpoint: Match a single resume to job requirements"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    try:
        data = json.loads(request.body)
        job_description = data.get('job_description', '')
        resume_data = data.get('resume_data', {})
        
        if not job_description or not resume_data:
            return JsonResponse({'success': False, 'error': 'Job description and resume data are required'})
        
        # Calculate match score
        similarity_score = job_matcher.compute_similarity_score(job_description, resume_data)
        job_skills = job_matcher.extract_skills_from_text(job_description)
        resume_skills = resume_data.get('skills', [])
        
        matched_skills = [s for s in job_skills if s.lower() in [rs.lower() for rs in resume_skills]]
        missing_skills = [s for s in job_skills if s.lower() not in [rs.lower() for rs in resume_skills]]
        
        return JsonResponse({
            'success': True,
            'match_score': round(similarity_score * 100, 2),
            'matched_skills': matched_skills,
            'missing_skills': missing_skills[:5],  # Top 5 missing skills
            'improvement_suggestions': generate_improvement_suggestions(job_description, resume_data)
        })
    except Exception as e:
        logger.exception("Error matching resume to job")
        return JsonResponse({'success': False, 'error': str(e)})

# Helper functions

def generate_enhanced_summary(original, skills, experience):
    """Generate an enhanced professional summary"""
    if not original.strip():
        base = "Dedicated professional with strong technical skills"
    else:
        base = original.strip()
    
    skill_text = ""
    if skills:
        top_skills = [s for s in skills[:3] if s.strip()]
        if top_skills:
            skill_text = f" with expertise in {', '.join(top_skills)}"
    
    exp_text = ""
    if experience:
        exp_count = len([e for e in experience if e.get('company', '').strip()])
        if exp_count > 0:
            exp_text = f" and {exp_count}+ years of industry experience"
    
    return f"{base}{skill_text}{exp_text}. Proven track record of delivering high-quality solutions and driving business growth through technology innovation."

def generate_job_recommendations(job_description, found_skills):
    """Generate recommendations based on job analysis"""
    recommendations = [
        "Highlight relevant technical skills prominently in your summary section",
        "Use action verbs and quantify achievements with specific metrics",
        "Tailor your project descriptions to match the job requirements"
    ]
    
    if found_skills:
        recommendations.append(f"Emphasize your experience with: {', '.join(found_skills[:3])}")
    
    if 'agile' in job_description.lower() or 'scrum' in job_description.lower():
        recommendations.append("Highlight your experience with Agile methodologies")
    
    if 'lead' in job_description.lower() or 'senior' in job_description.lower():
        recommendations.append("Emphasize leadership experience and mentoring capabilities")
    
    return recommendations

def generate_improvement_suggestions(job_description, resume_data):
    """Generate suggestions to improve resume match"""
    suggestions = []
    
    job_skills = job_matcher.extract_skills_from_text(job_description)
    resume_skills = [s.lower() for s in resume_data.get('skills', [])]
    
    missing_skills = [s for s in job_skills if s.lower() not in resume_skills]
    if missing_skills:
        suggestions.append(f"Consider adding these skills: {', '.join(missing_skills[:3])}")
    
    if len(resume_data.get('projects', [])) < 2:
        suggestions.append("Add more project examples to demonstrate your technical abilities")
    
    if not resume_data.get('about', '').strip():
        suggestions.append("Add a compelling professional summary highlighting your key strengths")
    
    return suggestions[:4]  # Limit to 4 suggestions