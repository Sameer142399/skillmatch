from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User

from .models import Job, Resume, Score, Applicant

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import io
from PyPDF2 import PdfReader
from docx import Document


# =========================
#   SIMPLE NLP UTILITIES
# =========================

SKILL_KEYWORDS = [
    "python", "java", "c++", "c", "html", "css", "javascript", "react",
    "angular", "node", "django", "flask", "spring", "sql", "mysql",
    "postgresql", "mongodb", "oracle", "git", "github", "docker", "aws",
    "azure", "gcp", "pandas", "numpy", "matplotlib", "tensorflow", "keras",
    "pytorch", "machine learning", "deep learning", "nlp", "data analysis",
    "data science", "excel", "power bi", "tableau", "linux"
]


def extract_text_from_resume(uploaded_file):
    """
    Read text from an uploaded resume file (PDF/DOCX/others).
    Returns plain text.
    """
    filename = uploaded_file.name.lower()
    file_bytes = uploaded_file.read()
    uploaded_file.seek(0)  # reset pointer so Django can save the file

    text = ""

    if filename.endswith(".pdf"):
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                page_text = page.extract_text() or ""
                text += page_text + "\n"
        except Exception:
            text = ""

    elif filename.endswith(".docx"):
        try:
            doc = Document(io.BytesIO(file_bytes))
            text = "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            text = ""

    else:
        # fallback for txt-like files
        try:
            text = file_bytes.decode(errors="ignore")
        except Exception:
            text = ""

    return text


def extract_skills_from_text(text: str) -> str:
    """
    Very simple NLP-style skill extraction:
    Looks for known skill keywords in the resume text.
    Returns comma-separated skills.
    """
    text_lower = text.lower()
    found = []
    for skill in SKILL_KEYWORDS:
        if skill in text_lower:
            found.append(skill)

    unique_sorted = sorted(set(found))
    return ", ".join(unique_sorted)


# =========================
#         PUBLIC PAGES
# =========================

def home(request):
    return render(request, "home.html")


# core/views.py

from django.db.models import Q

def job_list(request):
    jobs = Job.objects.all()
    applied_job_ids = []

    if request.user.is_authenticated:
        # Consider a job "applied" only if the score is SUBMITTED or later
        applied_job_ids = (
            Score.objects
            .filter(
                resume__user=request.user,
                status__in=["SUBMITTED", "SHORTLISTED", "REJECTED"],
            )
            .values_list("job_id", flat=True)
            .distinct()
        )

    return render(request, "job_list.html", {
        "jobs": jobs,
        "applied_job_ids": applied_job_ids,
    })

# =========================
#      APPLICANT FLOW
# =========================

@login_required
def upload_resume(request):
    """
    Step 1: Applicant uploads resume.
    → System analyses resume, auto-extracts skills
    → Creates DRAFT applications (Score) for jobs not applied yet.
    """
    if request.method == "POST" and request.FILES.get("resume"):
        file = request.FILES["resume"]

        # 1) Extract text from resume
        resume_text = extract_text_from_resume(file)
        cleaned = (resume_text or "").strip()

        # 2) Basic validation to ensure it looks like a resume
        RESUME_KEYWORDS = [
            "education", "experience", "skills", "project",
            "b.tech", "btech", "bachelor", "masters", "internship",
            "curriculum vitae", "resume"
        ]

        if len(cleaned) < 200 or not any(k in cleaned.lower() for k in RESUME_KEYWORDS):
            messages.error(
                request,
                "The uploaded file does not look like a valid resume. "
                "Please upload a proper resume (PDF/DOCX) with your details."
            )
            return redirect("upload_resume")

        # 3) Auto-extract skills from resume text
        extracted_skills = extract_skills_from_text(cleaned)

        if not extracted_skills:
            messages.error(
                request,
                "No technical skills were detected in your resume. "
                "Please clearly list your skills (e.g. 'Python, Django, SQL') "
                "in your resume and upload again."
            )
            return redirect("upload_resume")

        # 4) Extra skills typed by user (OPTIONAL, added on top)
        extra_skills = request.POST.get("skills", "").strip()

        all_skills = [extracted_skills]
        if extra_skills:
            all_skills.append(extra_skills)

        skills_text = ", ".join(all_skills)

        # 5) Save resume itself
        resume = Resume.objects.create(
            user=request.user,
            file=file,
            skills=skills_text,
        )

        # 6) Create draft scores only for jobs not already applied by this user
        jobs = Job.objects.all()
        created_any = False

        for job in jobs:
            # stop duplicate applications for same job & user
            already_exists = Score.objects.filter(
                job=job,
                resume__user=request.user,
            ).exists()

            if already_exists:
                continue

            job_text = job.required_skills or ""

            # TF-IDF + cosine similarity
            vectorizer = TfidfVectorizer(stop_words="english")
            tfidf = vectorizer.fit_transform([skills_text, job_text])
            sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
            score_value = round(float(sim) * 100, 2)

            user_skills_set = {
                s.strip().lower() for s in skills_text.split(",") if s.strip()
            }
            job_skills_set = {
                s.strip().lower() for s in (job.required_skills or "").split(",") if s.strip()
            }
            missing_skills = ", ".join(sorted(job_skills_set - user_skills_set))

            Score.objects.create(
                resume=resume,
                job=job,
                value=score_value,
                recommended_skills=missing_skills,
                status="DRAFT",          # applicant still editing
                is_shortlisted=False,
            )

            created_any = True

        if not created_any:
            messages.warning(
                request,
                "You have already created applications for all current jobs. "
                "No new applications were created."
            )
            return redirect("my_applications")

        messages.success(
            request,
            "Resume analysed. Draft applications created for new jobs. "
            "Check 'My Applications' to see scores and skill suggestions."
        )
        return redirect("my_applications")

    # GET request → show upload form
    return render(request, "upload_resume.html")


@login_required
def my_applications(request):
    """
    Show all applications (Score rows) for the logged-in applicant:
    - DRAFT (only analysed)
    - SUBMITTED (sent to recruiter)
    - SHORTLISTED / REJECTED (decisions by recruiter)
    """
    scores = (
        Score.objects
        .filter(resume__user=request.user)
        .select_related("job", "resume")
        .order_by("-id")   # ✅ FIX: we use -id instead of -created_at
    )
    return render(request, "my_applications.html", {"scores": scores})


@login_required
def submit_application(request, score_id):
    score = get_object_or_404(Score, id=score_id, resume__user=request.user)

    if score.status != "DRAFT":
        messages.info(request, "This application is already submitted.")
        return redirect("my_applications")

    score.status = "SUBMITTED"
    score.save()
    messages.success(request, f"Application for '{score.job.title}' submitted to recruiter.")
    return redirect("my_applications")



# =========================
#   RECRUITER / ADMIN
# =========================

def score_list(request):
    scores = Score.objects.select_related('resume', 'job').order_by('-value')
    return render(request, 'score_list.html', {'scores': scores})


@staff_member_required
def recruiter_dashboard(request):
    # Show all scores grouped by job, highest score first
    scores = (
        Score.objects
        .select_related('resume', 'job', 'resume__user')
        .order_by('job__title', '-value')
    )
    return render(request, 'recruiter_dashboard.html', {'scores': scores})


@staff_member_required
def toggle_shortlist(request, score_id):
    score = get_object_or_404(Score, id=score_id)
    # toggle shortlist & status
    score.is_shortlisted = not score.is_shortlisted
    score.status = "SHORTLISTED" if score.is_shortlisted else "REJECTED"
    score.save()
    return redirect('recruiter_dashboard')


# =========================
#     AUTH VIEWS
# =========================

def register_view(request):
    """
    Custom registration:
    - username = email
    - email must be unique
    - phone number must be unique in Applicant
    """
    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("phone", "").strip()
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")

        # basic checks
        if not full_name or not email or not phone or not password1 or not password2:
            messages.error(request, "All fields are required.")
            return render(request, "register.html")

        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return render(request, "register.html")

        # email uniqueness (since we use email as username)
        if User.objects.filter(username=email).exists():
            messages.error(
                request,
                "User with this email already exists. Please login with your credentials."
            )
            return redirect("login")

        # phone uniqueness
        if Applicant.objects.filter(phone=phone).exists():
            messages.error(
                request,
                "This mobile number is already registered. Please login with your credentials."
            )
            return redirect("login")

        # create user
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password1,
        )

        # create applicant profile
        Applicant.objects.create(
            user=user,
            full_name=full_name,
            phone=phone,
        )

        messages.success(
            request,
            "Registration successful. You can now login with your email and password."
        )
        return redirect("login")

    # GET
    return render(request, "register.html")


def login_view(request):
    """
    Login using email (stored as username) + password.
    """
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password")

        user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, "Logged in successfully.")
            return redirect("home")
        else:
            messages.error(request, "Invalid email or password.")
            return render(request, "login.html")

    # GET
    return render(request, "login.html")


@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("home")
