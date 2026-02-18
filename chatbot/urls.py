from django.urls import path
from .views import chat_public, chat_authed, chat_api

urlpatterns = [
    path("public/", chat_public, name="chat_public"),
    path("authed/", chat_authed, name="chat_authed"),
    path("api/", chat_api, name="chat_api"),
]