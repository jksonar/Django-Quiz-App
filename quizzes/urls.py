from django.urls import path

from . import views

app_name = 'quizzes'

urlpatterns = [
    path('', views.CatalogView.as_view(), name='catalog'),
    path('dashboard/', views.HistoryView.as_view(), name='history'),
    path('<int:pk>/', views.QuizDetailView.as_view(), name='detail'),
    path('<int:pk>/start/', views.start_quiz, name='start'),
    path('attempt/<int:pk>/', views.take_quiz, name='take'),
    path('attempt/<int:pk>/result/', views.ResultView.as_view(), name='result'),
]
