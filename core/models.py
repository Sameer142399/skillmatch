from django.db import models
from django.contrib.auth.models import User


class Job(models.Model):
    title = models.CharField(max_length=100)
    required_skills = models.TextField()   # comma separated: python, django, sql
    description = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.title


class Resume(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    file = models.FileField(upload_to='resumes/')
    skills = models.TextField(blank=True, null=True)  # we will auto-fill or type manually
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.user:
            return f"{self.user.username} resume"
        return f"Resume {self.id}"


class Score(models.Model):
    STATUS_CHOICES = [
        ("DRAFT", "Draft (for applicant only)"),
        ("SUBMITTED", "Submitted to recruiter"),
        ("SHORTLISTED", "Shortlisted"),
        ("REJECTED", "Rejected"),
    ]

    resume = models.ForeignKey(Resume, on_delete=models.CASCADE)
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    value = models.FloatField()
    recommended_skills = models.TextField(blank=True, null=True)
    is_shortlisted = models.BooleanField(default=False)  # you already had this

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT",            # 🔥 important: start as DRAFT
    )

    def __str__(self):
        return f"{self.resume} - {self.job} - {self.value} ({self.status})"


from django.contrib.auth.models import User
from django.db import models

class Applicant(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=150)
    education = models.CharField(max_length=255)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.full_name
