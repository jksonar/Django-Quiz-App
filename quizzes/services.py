from datetime import timedelta

from django.utils import timezone

from .models import AttemptAnswer, Attempt, Choice


def ordered_questions(quiz, question_order):
    questions_by_id = {q.id: q for q in quiz.questions.prefetch_related('choices').all()}
    return [questions_by_id[qid] for qid in question_order if qid in questions_by_id]


def time_remaining_seconds(attempt):
    deadline = attempt.start_time + timedelta(minutes=attempt.quiz.time_limit_minutes)
    return (deadline - timezone.now()).total_seconds()


def grade_and_complete(attempt, post_data, timed_out=False):
    quiz = attempt.quiz
    questions = ordered_questions(quiz, attempt.question_order)
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
