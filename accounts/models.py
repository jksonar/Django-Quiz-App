from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        INSTRUCTOR = 'instructor', 'Instructor'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    email_verified = models.BooleanField(default=False)

    @property
    def is_instructor(self):
        return self.role == self.Role.INSTRUCTOR or self.is_staff or self.is_superuser
