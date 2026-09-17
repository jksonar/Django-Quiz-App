from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from . import views

app_name = 'api'

urlpatterns = [
    path('auth/token/', obtain_auth_token, name='token'),
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('categories/', views.CategoryListView.as_view(), name='categories'),
    path('quizzes/', views.QuizListView.as_view(), name='quiz-list'),
    path('quizzes/<int:pk>/', views.QuizDetailView.as_view(), name='quiz-detail'),
    path('quizzes/<int:pk>/start/', views.StartAttemptView.as_view(), name='quiz-start'),
    path('attempts/<int:pk>/', views.AttemptStateView.as_view(), name='attempt-state'),
    path('attempts/<int:pk>/submit/', views.SubmitAttemptView.as_view(), name='attempt-submit'),
    path('attempts/<int:pk>/result/', views.AttemptResultView.as_view(), name='attempt-result'),
    path('history/', views.HistoryView.as_view(), name='history'),
]
