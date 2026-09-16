from django.contrib.auth import login
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import StudentRegistrationForm


class RegisterView(CreateView):
    form_class = StudentRegistrationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('quizzes:catalog')

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response
