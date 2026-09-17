from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.encoding import force_str
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_decode
from django.views.decorators.http import require_POST
from django.views.generic import CreateView

from .emails import send_verification_email
from .forms import StudentRegistrationForm
from .tokens import email_verification_token

User = get_user_model()


class RegisterView(CreateView):
    form_class = StudentRegistrationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('quizzes:catalog')

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        send_verification_email(self.object, request=self.request)
        messages.info(self.request, "We've sent a verification link to your email address.")
        return response


def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and email_verification_token.check_token(user, token):
        user.email_verified = True
        user.save(update_fields=['email_verified'])
        return render(request, 'accounts/verify_email_result.html', {'success': True})

    return render(request, 'accounts/verify_email_result.html', {'success': False})


@login_required
@require_POST
def resend_verification(request):
    if request.user.email_verified:
        messages.info(request, 'Your email is already verified.')
    else:
        send_verification_email(request.user, request=request)
        messages.success(request, 'Verification email sent.')

    referer = request.META.get('HTTP_REFERER')
    if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(referer)
    return redirect('quizzes:catalog')
