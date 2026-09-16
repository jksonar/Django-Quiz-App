from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import email_verification_token


def send_verification_email(user, request=None):
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    path = reverse('accounts:verify_email', kwargs={'uidb64': uidb64, 'token': token})

    base_url = request.build_absolute_uri('/').rstrip('/') if request else settings.SITE_URL
    verify_url = f'{base_url}{path}'

    send_mail(
        subject='Verify your Quiz App email address',
        message=(
            f'Hi {user.first_name or user.username},\n\n'
            f'Please confirm your email address by visiting the link below:\n\n'
            f'{verify_url}\n\n'
            f'If you did not create this account, you can ignore this email.'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )
