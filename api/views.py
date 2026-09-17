from rest_framework import generics, permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

from quizzes.models import Attempt, Category, Quiz
from quizzes.services import (
    grade_and_complete_answers,
    select_adaptive_questions,
    select_fixed_questions,
    time_remaining_seconds,
)

from .serializers import (
    AttemptHistorySerializer,
    AttemptResultSerializer,
    AttemptStateSerializer,
    CategorySerializer,
    QuizListSerializer,
    RegisterSerializer,
    SubmitAttemptSerializer,
)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, 'username': user.username}, status=status.HTTP_201_CREATED)


class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]


class QuizListView(generics.ListAPIView):
    serializer_class = QuizListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = Quiz.objects.filter(is_active=True).select_related('category')
        params = self.request.query_params
        category = params.get('category')
        difficulty = params.get('difficulty')
        duration = params.get('duration')
        if category:
            qs = qs.filter(category_id=category)
        if difficulty:
            qs = qs.filter(difficulty=difficulty)
        if duration == 'short':
            qs = qs.filter(time_limit_minutes__lte=10)
        elif duration == 'medium':
            qs = qs.filter(time_limit_minutes__gt=10, time_limit_minutes__lte=30)
        elif duration == 'long':
            qs = qs.filter(time_limit_minutes__gt=30)
        return qs


class QuizDetailView(generics.RetrieveAPIView):
    queryset = Quiz.objects.filter(is_active=True)
    serializer_class = QuizListSerializer
    permission_classes = [permissions.AllowAny]


class StartAttemptView(APIView):
    def post(self, request, pk):
        try:
            quiz = Quiz.objects.get(pk=pk, is_active=True)
        except Quiz.DoesNotExist:
            return Response({'detail': 'Quiz not found.'}, status=status.HTTP_404_NOT_FOUND)

        existing = Attempt.objects.filter(
            user=request.user, quiz=quiz, status=Attempt.Status.IN_PROGRESS
        ).first()
        if existing:
            return Response(AttemptStateSerializer(existing).data)

        if quiz.selection_mode == Quiz.SelectionMode.ADAPTIVE:
            question_ids = select_adaptive_questions(request.user, quiz)
        else:
            question_ids = select_fixed_questions(quiz)

        if not question_ids:
            return Response({'detail': 'This quiz has no questions yet.'}, status=status.HTTP_400_BAD_REQUEST)

        attempt = Attempt.objects.create(user=request.user, quiz=quiz, question_order=question_ids)
        return Response(AttemptStateSerializer(attempt).data, status=status.HTTP_201_CREATED)


class AttemptStateView(generics.RetrieveAPIView):
    serializer_class = AttemptStateSerializer

    def get_queryset(self):
        return Attempt.objects.filter(user=self.request.user)


class SubmitAttemptView(APIView):
    def post(self, request, pk):
        try:
            attempt = Attempt.objects.get(pk=pk, user=request.user)
        except Attempt.DoesNotExist:
            return Response({'detail': 'Attempt not found.'}, status=status.HTTP_404_NOT_FOUND)

        if attempt.status != Attempt.Status.IN_PROGRESS:
            return Response(AttemptResultSerializer(attempt).data)

        serializer = SubmitAttemptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        answers = {
            item['question_id']: item['choice_ids']
            for item in serializer.validated_data['answers']
        }

        timed_out = time_remaining_seconds(attempt) <= 0
        grade_and_complete_answers(attempt, answers, timed_out=timed_out)
        return Response(AttemptResultSerializer(attempt).data)


class AttemptResultView(generics.RetrieveAPIView):
    serializer_class = AttemptResultSerializer

    def get_queryset(self):
        return Attempt.objects.filter(user=self.request.user)


class HistoryView(generics.ListAPIView):
    serializer_class = AttemptHistorySerializer

    def get_queryset(self):
        return Attempt.objects.filter(
            user=self.request.user,
            status__in=[Attempt.Status.COMPLETED, Attempt.Status.TIMED_OUT],
        ).select_related('quiz', 'quiz__category')
