from django import forms


class QuestionImportForm(forms.Form):
    csv_file = forms.FileField(
        label='CSV file',
        help_text='Columns: category, question_text, question_type, difficulty, explanation, choices, correct_answers',
    )

    def clean_csv_file(self):
        f = self.cleaned_data['csv_file']
        if not f.name.lower().endswith('.csv'):
            raise forms.ValidationError('Please upload a .csv file.')
        return f
