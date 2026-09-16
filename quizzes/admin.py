from django.contrib import admin

from .models import Attempt, AttemptAnswer, Category, Choice, Question, Quiz, QuizQuestion


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 4


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'category', 'question_type', 'difficulty', 'created_by')
    list_filter = ('category', 'question_type', 'difficulty')
    search_fields = ('text',)
    exclude = ('created_by',)
    inlines = [ChoiceInline]

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class QuizQuestionInline(admin.TabularInline):
    model = QuizQuestion
    extra = 1
    autocomplete_fields = ['question']


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'category', 'difficulty', 'question_count', 'time_limit_minutes', 'pass_score_percent', 'is_active'
    )
    list_filter = ('category', 'difficulty', 'is_active')
    search_fields = ('title',)
    inlines = [QuizQuestionInline]
    exclude = ('questions', 'created_by')

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


admin.site.register(Attempt)
admin.site.register(AttemptAnswer)
