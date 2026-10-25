from django.urls import path
from . import views
from . import api_views

urlpatterns = [
    # Public Portal & Auth
    path('', views.landing_page_view, name='landing_page'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('register/status/', views.registration_status_check, name='registration_status'),
    path('dashboard/', views.dashboard_view, name='dashboard'),


    # 1. Residents & Households
    path('residents/', views.residents_list, name='residents_list'),
    path('residents/new/', views.resident_create, name='resident_create'),
    path('residents/<int:pk>/edit/', views.resident_edit, name='resident_edit'),
    path('residents/import/', views.census_import_view, name='census_import'),
    path('residents/import/sample/', views.census_sample_csv, name='census_sample_csv'),
    path('residents/<int:pk>/', views.resident_detail, name='resident_detail'),
    path('households/', views.households_list, name='households_list'),


    # 2. Documents & Issuance
    path('documents/', views.documents_list, name='documents_list'),
    path('documents/apply/', views.document_request_create, name='document_request_create'),
    path('documents/<int:pk>/process/', views.document_process, name='document_process'),
    path('documents/<int:pk>/print/', views.document_view, name='document_view'),
    path('verify/', views.document_verify, name='document_verify_search'),
    path('verify/<str:qr_hash>/', views.document_verify, name='document_verify'),

    # 3. Blotter & Incidents
    path('incidents/', views.incidents_list, name='incidents_list'),
    path('incidents/new/', views.incident_create, name='incident_create'),
    path('incidents/<int:pk>/', views.incident_detail, name='incident_detail'),
    path('incidents/<int:incident_id>/hearing/new/', views.hearing_create, name='hearing_create'),

    # 4. Health & Welfare
    path('assistance/', views.assistance_programs_list, name='assistance_programs_list'),
    path('assistance/<int:pk>/', views.assistance_program_detail, name='assistance_program_detail'),
    path('health/', views.health_records_list, name='health_records_list'),
    path('medicines/', views.medicines_inventory, name='medicines_inventory'),

    # 5. Announcements
    path('announcements/', views.announcements_list, name='announcements_list'),

    # 6. Admin Security & Users
    path('audit-logs/', views.audit_logs_list, name='audit_logs_list'),
    path('users/', views.users_list, name='users_list'),
    path('settings/', views.barangay_settings_view, name='barangay_settings'),
    path('profile/', views.profile_redirect_view, name='user_profile'),
    path('citizen-applications/', views.admin_registrations_list, name='admin_registrations'),
    path('citizen-applications/<int:pk>/process/', views.admin_registration_process, name='admin_registration_process'),

    # 7. Notifications
    path('notifications/<int:pk>/read/', views.notification_mark_read, name='notification_mark_read'),
    path('notifications/read-all/', views.notification_mark_all_read, name='notification_mark_all_read'),

    # 8. REST API v1 (SIA 2 System Integration Endpoints)
    path('api/v1/health/', api_views.api_health, name='api_health'),
    path('api/v1/verify/<str:qr_hash>/', api_views.api_document_verify, name='api_document_verify'),
    path('api/v1/statistics/summary/', api_views.api_statistics_summary, name='api_statistics_summary'),
    path('api/v1/document-types/', api_views.api_document_types, name='api_document_types'),
    path('api/v1/residents/search/', api_views.api_residents_search, name='api_residents_search'),
    path('api/v1/documents/request/', api_views.api_document_request_submit, name='api_document_request_submit'),
]



