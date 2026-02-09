"""
URL маршруты для приложения admissions
"""
from django.urls import path
from . import views

app_name = 'admissions'

urlpatterns = [
    # Главная
    path('', views.dashboard, name='dashboard'),
    
    # Загрузка данных
    path('upload/', views.upload_csv, name='upload'),
    
    # Просмотр списков
    path('applications/', views.applications_list, name='applications_list'),
    
    # Проходные баллы
    path('passing-scores/', views.passing_scores, name='passing_scores'),
    path('passing-scores/history/', views.passing_scores_history, name='passing_scores_history'),
    path('applicant-chances/', views.applicant_chances_view, name='applicant_chances'),
    
    # Отчеты
    path('reports/', views.reports, name='reports'),
    path('reports/pdf/', views.generate_pdf_report, name='generate_pdf_report'),
    
    # API
    path('api/passing-scores/', views.passing_scores_api, name='passing_scores_api'),
]