import random

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from quizzes.models import Attempt, Category, Choice, Question, Quiz
from quizzes.services import ordered_questions, time_remaining_seconds

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('That username is already taken.')
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=User.Role.STUDENT,
        )
        return user


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']


class QuizListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    question_count = serializers.ReadOnlyField()

    class Meta:
        model = Quiz
        fields = [
            'id', 'title', 'description', 'category', 'difficulty', 'selection_mode',
            'question_count', 'time_limit_minutes', 'pass_score_percent',
        ]


class ChoiceSerializer(serializers.ModelSerializer):
    """Choices as shown while taking a quiz - never reveals is_correct."""

    class Meta:
        model = Choice
        fields = ['id', 'text']


class QuestionSerializer(serializers.ModelSerializer):
    choices = serializers.SerializerMethodField()
    image = serializers.ImageField(read_only=True, use_url=True)

    class Meta:
        model = Question
        fields = ['id', 'text', 'question_type', 'image', 'image_alt_text', 'choices']

    def get_choices(self, question):
        choices = list(question.choices.all())
        if self.context.get('shuffle_choices'):
            random.shuffle(choices)
        return ChoiceSerializer(choices, many=True).data


class AttemptStateSerializer(serializers.ModelSerializer):
    quiz = QuizListSerializer(read_only=True)
    questions = serializers.SerializerMethodField()
    remaining_seconds = serializers.SerializerMethodField()

    class Meta:
        model = Attempt
        fields = ['id', 'quiz', 'status', 'start_time', 'questions', 'remaining_seconds']

    def get_questions(self, attempt):
        questions = ordered_questions(attempt.question_order)
        return QuestionSerializer(
            questions, many=True, context={'shuffle_choices': attempt.quiz.shuffle_choices}
        ).data

    def get_remaining_seconds(self, attempt):
        return max(int(time_remaining_seconds(attempt)), 0)


class AnswerInSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    choice_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)


class SubmitAttemptSerializer(serializers.Serializer):
    answers = AnswerInSerializer(many=True)


class ChoiceResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ['id', 'text', 'is_correct']


class QuestionResultSerializer(serializers.ModelSerializer):
    choices = ChoiceResultSerializer(many=True, read_only=True)
    selected_choice_ids = serializers.SerializerMethodField()
    is_correct = serializers.SerializerMethodField()
    image = serializers.ImageField(read_only=True, use_url=True)

    class Meta:
        model = Question
        fields = [
            'id', 'text', 'question_type', 'image', 'image_alt_text', 'explanation', 'choices',
            'selected_choice_ids', 'is_correct',
        ]

    def get_selected_choice_ids(self, question):
        answer = self.context['answers_by_question'].get(question.id)
        return list(answer.selected_choices.values_list('id', flat=True)) if answer else []

    def get_is_correct(self, question):
        answer = self.context['answers_by_question'].get(question.id)
        return answer.is_correct if answer else False


class AttemptResultSerializer(serializers.ModelSerializer):
    quiz = QuizListSerializer(read_only=True)
    passed = serializers.ReadOnlyField()
    questions = serializers.SerializerMethodField()

    class Meta:
        model = Attempt
        fields = [
            'id', 'quiz', 'status', 'score_percent', 'correct_count', 'passed',
            'start_time', 'end_time', 'questions',
        ]

    def get_questions(self, attempt):
        questions = ordered_questions(attempt.question_order)
        answers_by_question = {a.question_id: a for a in attempt.answers.prefetch_related('selected_choices')}
        return QuestionResultSerializer(
            questions, many=True, context={'answers_by_question': answers_by_question}
        ).data


class AttemptHistorySerializer(serializers.ModelSerializer):
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)
    category = serializers.CharField(source='quiz.category.name', read_only=True)
    passed = serializers.ReadOnlyField()

    class Meta:
        model = Attempt
        fields = ['id', 'quiz_title', 'category', 'score_percent', 'status', 'passed', 'start_time', 'end_time']
