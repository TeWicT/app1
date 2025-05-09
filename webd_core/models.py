from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Student(models.Model):
    login = models.CharField("Логин студента", max_length=50, unique=True)
    study_year = models.CharField("Год", max_length=4)
    courses = models.CharField("Курс", max_length=10)
    groups = models.CharField("Группа", max_length=50)

    full_name = models.CharField("ФИО студента", max_length=200)
    title = models.CharField("Тема работы", max_length=255,blank=True)
    adviser_name = models.CharField("ФИО руководителя",blank=True, max_length=200)
    adviser_status = models.CharField("Звание руководителя",blank=True, max_length=100)
    department = models.CharField("Кафедра",null=True, max_length=100)
    class Meta:
        db_table = 'student'
    def __str__(self):
        return f"{self.login} – {self.full_name}"

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
