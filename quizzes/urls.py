from django.urls import path

from . import views

app_name = 'quizzes'

urlpatterns = [
    path('', views.CatalogView.as_view(), name='catalog'),
    path('dashboard/', views.HistoryView.as_view(), name='history'),
    path('manage/', views.ManageDashboardView.as_view(), name='manage_dashboard'),
    path('manage/quiz/<int:pk>/analytics/', views.QuizAnalyticsView.as_view(), name='quiz_analytics'),
    path('manage/quiz/<int:pk>/export/', views.export_quiz_csv, name='export_quiz_csv'),
    path('manage/questions/import/', views.QuestionImportView.as_view(), name='import_questions'),
    path('manage/questions/import/template/', views.download_import_template, name='import_template'),
    path('<int:pk>/', views.QuizDetailView.as_view(), name='detail'),
    path('<int:pk>/start/', views.start_quiz, name='start'),
    path('attempt/<int:pk>/', views.take_quiz, name='take'),
    path('attempt/<int:pk>/result/', views.ResultView.as_view(), name='result'),
]
