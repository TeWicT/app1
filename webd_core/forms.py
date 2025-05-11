from django import forms
from .models import Enrollment, Document,Student



class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['doc_type', 'file']
        widgets = {
            'doc_type': forms.Select(attrs={'class': 'form-control'}),
            'file':     forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
        }
class StudentForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ['adviser_name', 'adviser_position', 'adviser_status', 'adviser_rank', 'department','title']
        labels = {
            'adviser_name': 'ФИО руководителя',
            'adviser_position': 'Должность руководителя',
            'adviser_status': 'Ученая степень руководителя',
            'adviser_rank': 'Ученое звание руководителя',
            'department': 'Кафедра',
            'title': 'Тема работы',
        }
        widgets = {
            'adviser_name': forms.TextInput(attrs={'class': 'form-control'}),
            'adviser_position': forms.Select(attrs={'class': 'form-control'}),
            'adviser_status': forms.TextInput(attrs={'class': 'form-control'}),
            'adviser_rank': forms.Select(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
        }
