from django.conf import settings
from django.db import models
from django.urls import reverse


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Question(models.Model):
    class Type(models.TextChoices):
        SINGLE = 'single', 'Single choice'
        MULTI = 'multi', 'Multi-select'
        TRUE_FALSE = 'true_false', 'True/False'

    class Difficulty(models.TextChoices):
        EASY = 'easy', 'Easy'
        MEDIUM = 'medium', 'Medium'
        HARD = 'hard', 'Hard'

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    question_type = models.CharField(max_length=20, choices=Type.choices, default=Type.SINGLE)
    difficulty = models.CharField(max_length=20, choices=Difficulty.choices, default=Difficulty.MEDIUM)
    explanation = models.TextField(blank=True, help_text='Shown to students after they answer.')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='questions_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.text[:60]

    @property
    def correct_choices(self):
        return self.choices.filter(is_correct=True)


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text[:60]


class Quiz(models.Model):
    title = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='quizzes')
    description = models.TextField(blank=True)
    difficulty = models.CharField(
        max_length=20, choices=Question.Difficulty.choices, default=Question.Difficulty.MEDIUM
    )
    questions = models.ManyToManyField(Question, through='QuizQuestion', related_name='quizzes')
    time_limit_minutes = models.PositiveIntegerField(default=10)
    pass_score_percent = models.PositiveIntegerField(default=60)
    shuffle_questions = models.BooleanField(default=True)
    shuffle_choices = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='quizzes_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'quizzes'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('quizzes:detail', args=[self.pk])

    @property
    def question_count(self):
        return self.questions.count()


class QuizQuestion(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='quiz_questions')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='quiz_links')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = ('quiz', 'question')

    def __str__(self):
        return f'{self.quiz} - {self.question}'


class Attempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'In progress'
        COMPLETED = 'completed', 'Completed'
        TIMED_OUT = 'timed_out', 'Timed out'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    question_order = models.JSONField(default=list, blank=True)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    score_percent = models.FloatField(null=True, blank=True)
    correct_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)

    class Meta:
        ordering = ['-start_time']

    def __str__(self):
        return f'{self.user} - {self.quiz} ({self.status})'

    @property
    def passed(self):
        if self.score_percent is None:
            return None
        return self.score_percent >= self.quiz.pass_score_percent

    @property
    def duration_seconds(self):
        if not self.end_time:
            return None
        return (self.end_time - self.start_time).total_seconds()


class AttemptAnswer(models.Model):
    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='attempt_answers')
    selected_choices = models.ManyToManyField(Choice, blank=True, related_name='selected_in_answers')
    is_correct = models.BooleanField(default=False)
    answered_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('attempt', 'question')

    def __str__(self):
        return f'{self.attempt} - {self.question}'
