import random
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DetailView, ListView

from .models import Attempt, AttemptAnswer, Category, Choice, Question, Quiz


class CatalogView(ListView):
    model = Quiz
    template_name = 'quizzes/catalog.html'
    context_object_name = 'quizzes'
    paginate_by = 12

    def get_queryset(self):
        qs = Quiz.objects.filter(is_active=True).select_related('category')
        category = self.request.GET.get('category')
        difficulty = self.request.GET.get('difficulty')
        duration = self.request.GET.get('duration')
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['difficulties'] = Question.Difficulty.choices
        context['selected_category'] = self.request.GET.get('category', '')
        context['selected_difficulty'] = self.request.GET.get('difficulty', '')
        context['selected_duration'] = self.request.GET.get('duration', '')
        return context


class QuizDetailView(DetailView):
    model = Quiz
    template_name = 'quizzes/detail.html'
    context_object_name = 'quiz'

    def get_queryset(self):
        return Quiz.objects.filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context['active_attempt'] = Attempt.objects.filter(
                user=self.request.user, quiz=self.object, status=Attempt.Status.IN_PROGRESS
            ).first()
        return context


def _ordered_questions(quiz, question_order):
    questions_by_id = {q.id: q for q in quiz.questions.prefetch_related('choices').all()}
    return [questions_by_id[qid] for qid in question_order if qid in questions_by_id]


@login_required
def start_quiz(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk, is_active=True)

    existing = Attempt.objects.filter(
        user=request.user, quiz=quiz, status=Attempt.Status.IN_PROGRESS
    ).first()
    if existing:
        return redirect('quizzes:take', pk=existing.pk)

    question_ids = list(quiz.questions.values_list('id', flat=True))
    if not question_ids:
        messages.error(request, 'This quiz has no questions yet.')
        return redirect('quizzes:detail', pk=quiz.pk)

    if quiz.shuffle_questions:
        random.shuffle(question_ids)

    attempt = Attempt.objects.create(user=request.user, quiz=quiz, question_order=question_ids)
    return redirect('quizzes:take', pk=attempt.pk)


def _time_remaining_seconds(attempt):
    deadline = attempt.start_time + timedelta(minutes=attempt.quiz.time_limit_minutes)
    return (deadline - timezone.now()).total_seconds()


@login_required
def take_quiz(request, pk):
    attempt = get_object_or_404(Attempt, pk=pk, user=request.user)

    if attempt.status != Attempt.Status.IN_PROGRESS:
        return redirect('quizzes:result', pk=attempt.pk)

    remaining = _time_remaining_seconds(attempt)
    if remaining <= 0 and request.method == 'GET':
        _grade_and_complete(attempt, {}, timed_out=True)
        return redirect('quizzes:result', pk=attempt.pk)

    quiz = attempt.quiz
    questions = _ordered_questions(quiz, attempt.question_order)

    if quiz.shuffle_choices:
        for question in questions:
            question.display_choices = sorted(question.choices.all(), key=lambda c: random.random())
    else:
        for question in questions:
            question.display_choices = list(question.choices.all())

    if request.method == 'POST':
        timed_out = _time_remaining_seconds(attempt) <= 0
        _grade_and_complete(attempt, request.POST, timed_out=timed_out)
        return redirect('quizzes:result', pk=attempt.pk)

    context = {
        'attempt': attempt,
        'quiz': quiz,
        'questions': questions,
        'remaining_seconds': max(int(remaining), 0),
    }
    return render(request, 'quizzes/take.html', context)


def _grade_and_complete(attempt, post_data, timed_out=False):
    quiz = attempt.quiz
    questions = _ordered_questions(quiz, attempt.question_order)
    correct_count = 0

    for question in questions:
        field_name = f'question_{question.id}'
        selected_ids = {int(v) for v in post_data.getlist(field_name)} if hasattr(post_data, 'getlist') else set()
        correct_ids = set(question.choices.filter(is_correct=True).values_list('id', flat=True))
        is_correct = bool(selected_ids) and selected_ids == correct_ids

        answer, _ = AttemptAnswer.objects.update_or_create(
            attempt=attempt, question=question, defaults={'is_correct': is_correct}
        )
        answer.selected_choices.set(Choice.objects.filter(id__in=selected_ids))
        if is_correct:
            correct_count += 1

    total = len(questions) or 1
    attempt.correct_count = correct_count
    attempt.score_percent = round((correct_count / total) * 100, 2)
    attempt.status = Attempt.Status.TIMED_OUT if timed_out else Attempt.Status.COMPLETED
    attempt.end_time = timezone.now()
    attempt.save()


class ResultView(LoginRequiredMixin, DetailView):
    model = Attempt
    template_name = 'quizzes/result.html'
    context_object_name = 'attempt'

    def get_queryset(self):
        return Attempt.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        attempt = self.object
        questions = _ordered_questions(attempt.quiz, attempt.question_order)
        answers_by_question = {a.question_id: a for a in attempt.answers.prefetch_related('selected_choices')}

        review = []
        for question in questions:
            answer = answers_by_question.get(question.id)
            selected_ids = set(answer.selected_choices.values_list('id', flat=True)) if answer else set()
            review.append({
                'question': question,
                'choices': question.choices.all(),
                'selected_ids': selected_ids,
                'is_correct': answer.is_correct if answer else False,
            })
        context['review'] = review
        return context


class HistoryView(LoginRequiredMixin, ListView):
    model = Attempt
    template_name = 'quizzes/history.html'
    context_object_name = 'attempts'
    paginate_by = 20

    def get_queryset(self):
        return Attempt.objects.filter(
            user=self.request.user, status__in=[Attempt.Status.COMPLETED, Attempt.Status.TIMED_OUT]
        ).select_related('quiz')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        attempts = list(self.get_queryset())
        if attempts:
            context['average_score'] = round(sum(a.score_percent or 0 for a in attempts) / len(attempts), 2)
        else:
            context['average_score'] = None
        return context
