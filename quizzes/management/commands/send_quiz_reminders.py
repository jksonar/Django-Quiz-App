from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from quizzes.models import Attempt
from quizzes.services import grade_and_complete, time_remaining_seconds


class Command(BaseCommand):
    help = (
        'Auto-submits quiz attempts whose time limit has expired, and emails a reminder '
        'to students whose in-progress attempt is about to run out of time. '
        'Intended to be run periodically (e.g. every 5 minutes via cron).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--reminder-minutes', type=int, default=5,
            help='Send a reminder when this many minutes (or less) remain on an attempt (default: 5).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Show what would happen without sending emails or changing attempt status.',
        )

    def handle(self, *args, **options):
        reminder_seconds = options['reminder_minutes'] * 60
        dry_run = options['dry_run']

        in_progress = Attempt.objects.filter(status=Attempt.Status.IN_PROGRESS).select_related('user', 'quiz')

        finalized_count = 0
        reminded_count = 0

        for attempt in in_progress:
            remaining = time_remaining_seconds(attempt)

            if remaining <= 0:
                self.stdout.write(f'Auto-submitting expired attempt #{attempt.pk} ({attempt.user} - {attempt.quiz})')
                if not dry_run:
                    grade_and_complete(attempt, {}, timed_out=True)
                    self._send_email(
                        attempt.user.email,
                        subject=f'Time\'s up: "{attempt.quiz.title}" was auto-submitted',
                        message=(
                            f'Hi {attempt.user.first_name or attempt.user.username},\n\n'
                            f'Your time ran out on "{attempt.quiz.title}", so it was automatically submitted. '
                            f'You can review your results any time from your dashboard.\n\n'
                            f'{settings.SITE_URL}'
                        ),
                    )
                finalized_count += 1
                continue

            if remaining <= reminder_seconds and attempt.reminder_sent_at is None:
                minutes_left = max(int(remaining // 60), 1)
                self.stdout.write(f'Reminding attempt #{attempt.pk} ({attempt.user} - {attempt.quiz})')
                if not dry_run:
                    self._send_email(
                        attempt.user.email,
                        subject=f'Hurry! "{attempt.quiz.title}" is about to time out',
                        message=(
                            f'Hi {attempt.user.first_name or attempt.user.username},\n\n'
                            f'You have about {minutes_left} minute(s) left on "{attempt.quiz.title}". '
                            f'Finish up before time runs out!\n\n'
                            f'{settings.SITE_URL}'
                        ),
                    )
                    attempt.reminder_sent_at = timezone.now()
                    attempt.save(update_fields=['reminder_sent_at'])
                reminded_count += 1

        prefix = '[dry run] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Auto-submitted {finalized_count} expired attempt(s); sent {reminded_count} reminder(s).'
        ))

    @staticmethod
    def _send_email(recipient, subject, message):
        if not recipient:
            return
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
        )
