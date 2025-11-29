from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from core import views

urlpatterns = [
    path("admin/", admin.site.urls),

    path("", views.home, name="home"),
    path("jobs/", views.job_list, name="job_list"),

    # applicant flow
    path("upload/", views.upload_resume, name="upload_resume"),
    path("my-applications/", views.my_applications, name="my_applications"),
    path("applications/<int:score_id>/submit/",views.submit_application,name="submit_application",),

    # scores (global view – mostly for demo)
    path("scores/", views.score_list, name="score_list"),

    # auth
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # recruiter
    path(
        "recruiter/dashboard/",
        views.recruiter_dashboard,
        name="recruiter_dashboard",
    ),
    path(
        "recruiter/shortlist/<int:score_id>/",
        views.toggle_shortlist,
        name="toggle_shortlist",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
