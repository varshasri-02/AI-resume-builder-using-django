from django.contrib import admin
from django.urls import path
from home.views import *

urlpatterns = [
    path('', resume_form, name='resume_form'),  # Root URL for the form
    path('resume/', resume_form, name='resume_form_alt'),  # Alternative URL for the form
    path('generate-resume/', generate_resume, name='generate_resume'),  # URL for PDF generation
    
    # Optional AI enhancement endpoints (if you plan to use them)
    path('ai/enhance-summary/', ai_enhance_summary, name='ai_enhance_summary'),
    path('ai/analyze-job/', ai_analyze_job, name='ai_analyze_job'),
    path('ai/suggest-skills/', ai_suggest_skills, name='ai_suggest_skills'),
    
    path("admin/", admin.site.urls),
]