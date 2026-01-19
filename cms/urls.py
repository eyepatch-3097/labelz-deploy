from django.urls import path
from . import views

urlpatterns = [
    path("content/", views.content_list, name="cms_content_list"),   # paginated list (all or filtered)
    path("post/<slug:slug>/", views.post_detail, name="cms_post_detail"),  # blog/video detail
]
