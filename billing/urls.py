# billing/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("plans/", views.billing_select_plan, name="billing_select_plan"),
    path("super/", views.billing_super_plan, name="billing_super_plan"),
]
