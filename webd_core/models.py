from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
import os
User = get_user_model()
class Year(models.Model):
    year = models.PositiveIntegerField(unique=True, verbose_name="Учебный год")

    class Meta:
        ordering = ['year']
        verbose_name = "Год обучения"
        verbose_name_plural = "Годы обучения"

    def __str__(self):
        return str(self.year)

class Group(models.Model):
    name = models.CharField(max_length=50, verbose_name="Группа")
    year = models.ForeignKey(Year, on_delete=models.CASCADE,
                             related_name='groups', verbose_name="Год обучения")

    class Meta:
        unique_together = ('name', 'year')
        ordering = ['year__year', 'name']
        verbose_name = "Группа студентов"
        verbose_name_plural = "Группы студентов"

    def __str__(self):
        return f"{self.name} ({self.year.year})"


class Student(models.Model):
    
    login = models.CharField("Логин студента", max_length=50, unique=True)
    full_name = models.CharField("ФИО студента", max_length=200)
    class Meta:
        ordering = [ 'full_name']
        verbose_name = "Студент"
        verbose_name_plural = "Студенты"

    def __str__(self):
        return f"{self.full_name} ({self.login})"

class Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE,
                                related_name='enrollments', verbose_name="Студент")
    year = models.ForeignKey(Year, on_delete=models.CASCADE,
                             related_name='enrollments', verbose_name="Год обучения")
    group = models.ForeignKey(Group, on_delete=models.PROTECT,
                              related_name='enrollments', verbose_name="Группа")


    courses = models.CharField("Курс", max_length=10)

    adviser_status = models.CharField("Ученая степень руководителя",blank=True, max_length=100)
    adviser_position = models.CharField("Должность руководителя",blank=True, max_length=100)
    
    title = models.CharField("Тема работы", max_length=255,blank=True)
    adviser_name = models.CharField("ФИО руководителя",blank=True, max_length=200)
    adviser_rank = models.CharField("Ученое звание руководителя",blank=True, max_length=100)
    department = models.CharField("Кафедра",blank=True, max_length=100)
    class Meta:
        unique_together = ('student', 'year')
        ordering = ['year__year']
        verbose_name = "Запись обучения"
        verbose_name_plural = "Записи обучения"

    def __str__(self):
        return f"{self.student.full_name} – {self.year.year} год, группа {self.group.name}"

def upload_to_enrollment_path(instance, filename):
    year_value = instance.enrollment.year
    group_value = instance.enrollment.group
    student_value = instance.enrollment.student
    return os.path.join('students', str(year_value),str(group_value),str(student_value), filename)

class Document(models.Model):
    INTERIM_REPORT       = 'interim_report'
    INTERIM_PRESENTATION = 'interim_presentation'
    FINAL_REPORT         = 'final_report'
    FINAL_PRESENTATION   = 'final_presentation'

    DOC_TYPES = [
        (INTERIM_REPORT,       'Промежуточный отчет'),
        (INTERIM_PRESENTATION, 'Промежуточная презентация'),
        (FINAL_REPORT,         'Окончательный отчет'),
        (FINAL_PRESENTATION,   'Окончательная презентация'),
    ]

    enrollment  = models.ForeignKey(Enrollment, on_delete=models.CASCADE,
                                    related_name='documents', verbose_name="Запись обучения")
    doc_type    = models.CharField("Тип документа", max_length=30, choices=DOC_TYPES)
    file        = models.FileField("Файл", upload_to=upload_to_enrollment_path)
    uploaded_at = models.DateTimeField("Дата загрузки", auto_now_add=True)

    class Meta:
        unique_together = ('enrollment', 'doc_type')
        ordering = ['doc_type']
        verbose_name = "Документ"
        verbose_name_plural = "Документы"

    def __str__(self):
        return f"{self.enrollment.student.login} – {self.get_doc_type_display()} @ {self.uploaded_at:%Y-%m-%d}"
