from django.contrib import admin
from .models import Applicant, Job, Resume, Score


# ----------------- APPLICANT ADMIN -----------------

@admin.register(Applicant)
class ApplicantAdmin(admin.ModelAdmin):
    list_display = ("user", "full_name", "phone")
    search_fields = ("full_name", "user__username", "user__email")


# ----------------- JOB ADMIN -----------------

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    # Use only fields that definitely exist on your Job model
    # You already use job.title and job.required_skills in views/templates.
    list_display = ("id", "title", "required_skills")
    search_fields = ("title", "required_skills")


# ----------------- RESUME ADMIN -----------------

@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    # Use only fields that exist on your Resume model
    # We know you have: user, file, skills
    list_display = ("id", "user", "file", "skills")
    search_fields = ("user__username", "user__email", "skills")
    # Remove uploaded_at from list_filter because it doesn't exist
    # list_filter = ("uploaded_at",)  # ❌ causing error
    # If you later add created_at field in Resume, you can enable:
    # list_filter = ("created_at",)


# ----------------- SCORE ADMIN + ACTIONS -----------------

@admin.action(description="Mark selected scores as SHORTLISTED")
def make_shortlisted(modeladmin, request, queryset):
    queryset.update(is_shortlisted=True, status="SHORTLISTED")


@admin.action(description="Mark selected scores as REJECTED")
def make_rejected(modeladmin, request, queryset):
    queryset.update(is_shortlisted=False, status="REJECTED")


@admin.register(Score)
class ScoreAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "job",
        "resume",
        "value",
        "status",
        "is_shortlisted",
        "recommended_skills",
    )
    list_filter = ("job", "status", "is_shortlisted")
    search_fields = (
        "job__title",
        "resume__user__username",
        "resume__user__email",
    )
    actions = [make_shortlisted, make_rejected]
