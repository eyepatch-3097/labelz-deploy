from django.urls import path
from . import views

urlpatterns = [
    path('', views.workspace_list, name='workspace_list'),
    path('create/', views.workspace_create_step1, name='workspace_create_step1'),
    path('create/map-fields/', views.workspace_map_fields, name='workspace_map_fields'),
    path('create/manual-fields/', views.workspace_manual_fields, name='workspace_manual_fields'),
    path('create/sample/', views.workspace_sample_canvas, name='workspace_sample_canvas'),
    path('manage-access/', views.manage_access, name='workspace_manage_access'),
    path('my/', views.my_workspaces, name='my_workspaces'),
    path('my/<int:workspace_id>/', views.my_workspace_detail, name='my_workspace_detail'),
    # Label Designer routes
    path('<int:workspace_id>/designer/', views.label_template_list, name='label_template_list'),
    path("<int:workspace_id>/designer/", views.label_template_list, name="label_template_list"),
    path("<int:workspace_id>/designer/new/", views.label_template_create, name="label_template_create"),
    path("template/<int:template_id>/canvas/", views.label_template_canvas, name="label_template_canvas"),
    path("template/<int:template_id>/preview/", views.label_template_preview, name="label_template_preview"),
    path(
        "template/<int:template_id>/edit/",
        views.label_template_edit,
        name="label_template_edit",
    ),
    path(
        "template/<int:template_id>/duplicate/",
        views.label_template_duplicate,
        name="label_template_duplicate",
    ),
    path(
        "template/<int:template_id>/delete/",
        views.label_template_delete,
        name="label_template_delete",
    ),
    # super templates (superadmin only)
    path(
        "super-templates/",
        views.global_template_list,
        name="global_template_list",
    ),
    path(
        "super-templates/new/",
        views.global_template_create_meta,
        name="global_template_create",
    ),
    path(
        "super-templates/<int:template_id>/canvas/",
        views.global_template_canvas,
        name="global_template_canvas",
    ),
    path(
        "super-templates/<int:template_id>/preview/",
        views.global_template_preview,
        name="global_template_preview",
    ),
    path(
        "<int:workspace_id>/templates/use-global/<int:global_id>/",
        views.use_global_template,
        name="use_global_template",
    ),
    path(
        "<int:workspace_id>/labels/",
        views.label_generate_start,
        name="label_generate_start",
    ),
    path(
        "<int:workspace_id>/labels/single/<int:template_id>/",
        views.label_generate_single,
        name="label_generate_single",
    ),
    path(
        "<int:workspace_id>/labels/single/batch/<int:batch_id>/preview/",
        views.label_generate_single_preview,
        name="label_generate_single_preview",
    ),
    path(
        "<int:workspace_id>/labels/history/",
        views.label_batch_history,
        name="label_batch_history",
    ),
    path(
        "<int:workspace_id>/labels/batch/<int:batch_id>/print/",
        views.label_batch_print,
        name="label_batch_print",
    ),
    path(
        "workspaces/<int:workspace_id>/labels/batch/<int:batch_id>/export/",
        views.label_batch_export_csv,
        name="label_batch_export_csv",
    ),
    path(
        "workspaces/<int:workspace_id>/templates/<int:template_id>/generate/multi/",
        views.label_generate_multi,
        name="label_generate_multi",
    ),
    path(
        "workspaces/<int:workspace_id>/templates/<int:template_id>/generate/multi/export/",
        views.label_generate_multi_export_template,
        name="label_generate_multi_export_template",
    ),
    path("labels/history/", views.org_label_history, name="org_label_history"),
]
