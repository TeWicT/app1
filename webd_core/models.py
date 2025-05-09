from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Student(models.Model):
    login = models.CharField("Логин студента", max_length=50, unique=True)
    year = models.CharField("Год", max_length=4)
    course = models.CharField("Курс", max_length=10)
    group = models.CharField("Группа", max_length=50)

    name = models.CharField("ФИО студента", max_length=200)
    title = models.CharField("Тема работы", max_length=255)
    adviser_name = models.CharField("ФИО руководителя", max_length=200)
    adviser_status = models.CharField("Звание руководителя", max_length=100)
    department = models.CharField("Кафедра", max_length=100)

    def __str__(self):
        return f"{self.login} – {self.name}"

class Document(models.Model):
    INDEX = 'index'
    PREVIEW = 'preview'
    FINAL = 'final'
    DOC_TYPES = [
        (INDEX, 'Индексный файл'),
        (PREVIEW, 'Предварительный документ'),
        (FINAL, 'Финальный документ'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='documents')
    doc_type = models.CharField('Тип документа', max_length=20, choices=DOC_TYPES)
    file = models.FileField('Файл', upload_to='students/%Y/%m/%d/')
    uploaded_at = models.DateTimeField('Дата загрузки', auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.student.login} – {self.doc_type} @ {self.uploaded_at:%Y-%m-%d}"
