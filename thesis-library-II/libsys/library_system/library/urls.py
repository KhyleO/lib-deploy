from django.urls import path
from . import views


urlpatterns = [
    # path('', views.home, name='home'),
    # path('encoding/', views.encoding_page, name='encoding'),
    # path('acquisition/', views.acquisition_page, name='acquisition'),
    # path('bibliography/', views.bibliography_page, name='bibliography'),
    # path('summary/', views.summary_page, name='summary'),
    # path('profile/', views.profile_page, name='profile'),
    # path('login/', views.login_view, name='login'),
    # path('logout/', views.logout_view, name='logout'),
    # path('export/', views.export_file, name='export_file'),
    # path('algo/', views.algo_result, name='algorithm'),
    # path('full-details/<int:entry_id>/', views.full_details_page, name='full_details'),
    # path('edit_entry/<int:entry_id>/', views.edit_entry, name='edit_entry'),
    # path('delete_entry/<int:entry_id>/', views.delete_entry, name='delete_entry'),

    
    # Core pages
    path('', views.login_view, name='login'),
    path('home/', views.home, name='home'),
    path('profile/', views.login_view, name='profile'),

    # Bibliography workflow
    path('encoding/', views.encoding_page, name='encoding'),
    path('acquisition/', views.acquisition_page, name='acquisition'),
    path('acquisition-batch/', views.acquisition_batch_page, name='acquisition_batch'),
    path('bibliography/', views.bibliography_page, name='generate_bibliography'),
    path('bibliography/<str:course_code>/', views.bibliography_page, name='bibliography_by_course'),
    path('summary/', views.summary_page, name='summary'),
    path('import/', views.import_page, name='import_page'),
    path('import/process/', views.import_books, name='import_books'),
    path("acquisition/import/", views.acquisition_import_page, name="acquisition_import"),
    # path("acquisition/import/process/", views.acquisition_import_process, name="acquisition_import_process"),
    path('export/', views.export_file, name='export_file'),

    # Algorithms
    path('algo/', views.algo_result, name='algorithm'),

    # Entry management
    path('full-details/<int:entry_id>/', views.full_details_page, name='full_details'),
    path('encoding/<int:entry_id>/', views.edit_entry, name='edit_entry'),
    path('delete_entry/<int:entry_id>/', views.delete_entry, name='delete_entry'),

    # Auth
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

]