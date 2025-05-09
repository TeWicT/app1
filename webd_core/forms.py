from django import forms
from .models import Document

class UploadForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['doc_type', 'file']
        labels = {
            'doc_type': 'Тип документа',
            'file': 'Файл',
        }
        widgets = {
            'doc_type': forms.Select(attrs={'class': 'form-control'}),
            'file': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
        }
