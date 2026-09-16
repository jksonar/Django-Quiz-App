import csv
import random

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Avg, Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, FormView, ListView

from .forms import QuestionImportForm
from .imports import commit_questions, parse_questions_csv
from .models import Attempt, AttemptAnswer, Category, Question, Quiz
from .services import grade_and_complete, ordered_questions, time_remaining_seconds


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


@login_required
def take_quiz(request, pk):
    attempt = get_object_or_404(Attempt, pk=pk, user=request.user)

    if attempt.status != Attempt.Status.IN_PROGRESS:
        return redirect('quizzes:result', pk=attempt.pk)

    remaining = time_remaining_seconds(attempt)
    if remaining <= 0 and request.method == 'GET':
        grade_and_complete(attempt, {}, timed_out=True)
        return redirect('quizzes:result', pk=attempt.pk)

    quiz = attempt.quiz
    questions = ordered_questions(quiz, attempt.question_order)

    if quiz.shuffle_choices:
        for question in questions:
            question.display_choices = sorted(question.choices.all(), key=lambda c: random.random())
    else:
        for question in questions:
            question.display_choices = list(question.choices.all())

    if request.method == 'POST':
        timed_out = time_remaining_seconds(attempt) <= 0
        grade_and_complete(attempt, request.POST, timed_out=timed_out)
        return redirect('quizzes:result', pk=attempt.pk)

    context = {
        'attempt': attempt,
        'quiz': quiz,
        'questions': questions,
        'remaining_seconds': max(int(remaining), 0),
    }
    return render(request, 'quizzes/take.html', context)


class ResultView(LoginRequiredMixin, DetailView):
    model = Attempt
    template_name = 'quizzes/result.html'
    context_object_name = 'attempt'

    def get_queryset(self):
        return Attempt.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        attempt = self.object
        questions = ordered_questions(attempt.quiz, attempt.question_order)
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

        trend = list(reversed(attempts))
        context['trend_labels'] = [a.start_time.strftime('%b %d') for a in trend]
        context['trend_scores'] = [a.score_percent for a in trend]

        weak_areas = (
            self.get_queryset()
            .values('quiz__category__name')
            .annotate(avg_score=Avg('score_percent'), attempt_count=Count('id'))
            .order_by('avg_score')
        )
        context['weak_areas'] = list(weak_areas)
        return context


class InstructorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_instructor


class ManageDashboardView(InstructorRequiredMixin, ListView):
    model = Quiz
    template_name = 'quizzes/manage/dashboard.html'
    context_object_name = 'quizzes'

    def get_queryset(self):
        return Quiz.objects.select_related('category').annotate(
            attempt_count=Count('attempts'),
            finished_count=Count('attempts', filter=Q(attempts__status__in=[
                Attempt.Status.COMPLETED, Attempt.Status.TIMED_OUT,
            ])),
            avg_score=Avg('attempts__score_percent'),
        )


class QuizAnalyticsView(InstructorRequiredMixin, DetailView):
    model = Quiz
    template_name = 'quizzes/manage/quiz_analytics.html'
    context_object_name = 'quiz'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        quiz = self.object
        all_attempts = quiz.attempts.all()
        finished = all_attempts.filter(status__in=[Attempt.Status.COMPLETED, Attempt.Status.TIMED_OUT])

        started_count = all_attempts.count()
        finished_count = finished.count()
        context['started_count'] = started_count
        context['finished_count'] = finished_count
        context['completion_rate'] = round(finished_count / started_count * 100, 1) if started_count else None
        context['average_score'] = round(
            finished.aggregate(avg=Avg('score_percent'))['avg'] or 0, 2
        ) if finished_count else None
        context['pass_count'] = finished.filter(score_percent__gte=quiz.pass_score_percent).count()

        question_stats = []
        for question in quiz.questions.all():
            answers = AttemptAnswer.objects.filter(attempt__in=finished, question=question)
            answered_count = answers.count()
            missed_count = answers.filter(is_correct=False).count()
            miss_rate = round(missed_count / answered_count * 100, 1) if answered_count else 0
            question_stats.append({
                'question': question,
                'answered_count': answered_count,
                'missed_count': missed_count,
                'miss_rate': miss_rate,
            })
        question_stats.sort(key=lambda s: s['miss_rate'], reverse=True)
        context['question_stats'] = question_stats
        return context


@login_required
def export_quiz_csv(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    if not request.user.is_instructor:
        messages.error(request, 'You do not have permission to export this data.')
        return redirect('quizzes:catalog')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{quiz.title}-results.csv"'
    writer = csv.writer(response)
    writer.writerow(['username', 'email', 'score_percent', 'correct_count', 'total_questions', 'status', 'start_time', 'end_time'])
    for attempt in quiz.attempts.select_related('user').all():
        writer.writerow([
            attempt.user.username,
            attempt.user.email,
            attempt.score_percent,
            attempt.correct_count,
            len(attempt.question_order),
            attempt.status,
            attempt.start_time.isoformat(),
            attempt.end_time.isoformat() if attempt.end_time else '',
        ])
    return response


class QuestionImportView(InstructorRequiredMixin, FormView):
    template_name = 'quizzes/manage/import_questions.html'
    form_class = QuestionImportForm

    def get_success_url(self):
        return self.request.path

    def form_valid(self, form):
        rows, errors = parse_questions_csv(form.cleaned_data['csv_file'])
        if errors:
            return self.render_to_response(self.get_context_data(form=form, errors=errors))
        created = commit_questions(rows, created_by=self.request.user)
        messages.success(self.request, f'Imported {len(created)} question(s) successfully.')
        return redirect('quizzes:import_questions')


@login_required
def download_import_template(request):
    if not request.user.is_instructor:
        messages.error(request, 'You do not have permission to do that.')
        return redirect('quizzes:catalog')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="question_import_template.csv"'
    writer = csv.writer(response)
    writer.writerow(['category', 'question_text', 'question_type', 'difficulty', 'explanation', 'choices', 'correct_answers'])
    writer.writerow([
        'General Science', 'What is the boiling point of water at sea level (Celsius)?',
        'single', 'easy', 'Water boils at 100C at standard atmospheric pressure.',
        '100|90|80|120', '100',
    ])
    writer.writerow([
        'General Science', 'Which of these are noble gases?',
        'multi', 'medium', 'Noble gases include helium, neon, and argon.',
        'Helium|Neon|Nitrogen|Oxygen', 'Helium|Neon',
    ])
    return response
