# billing/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("plans/", views.billing_select_plan, name="billing_select_plan"),
    path("super/", views.billing_super_plan, name="billing_super_plan"),
    path("checkout/start/", views.billing_checkout_start, name="billing_checkout_start"),
    path("checkout/verify/", views.billing_verify_payment, name="billing_verify_payment"),
    path("webhook/razorpay/", views.razorpay_webhook, name="razorpay_webhook"),
    path("invoices/", views.billing_invoices, name="billing_invoices"),
    path("invoices/export.csv", views.billing_invoices_csv, name="billing_invoices_csv"),
    path("invoices/<int:payment_id>/pdf/", views.billing_invoice_pdf, name="billing_invoice_pdf"),
    path("cancel/", views.billing_cancel_plan, name="billing_cancel_plan"),
]
