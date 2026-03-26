from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
import os
User = get_user_model()

DEPARTMENTS = ['ПМиК','ИМО','ГиТ','МА','ТВиАД','ТМОМИ']
DEPARTMENT_CHOICES = [(d, d) for d in DEPARTMENTS]
ADVISER_POSITION_CHOICES = [
    ('преподаватель', 'преподаватель'),
    ('ст. преподаватель', 'ст. преподаватель'),
    ('доцент', 'доцент'),
    ('профессор', 'профессор'),
    ('зав. кафедрой', 'зав. кафедрой'),
    ('другая', 'другая'),
]
COURSE_CHOICES = [(i, f"{i}") for i in range(1, 7)]
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
    is_latest = models.BooleanField(default=False, verbose_name="Выпускной год")
    is_master_latest = models.BooleanField(default=False, verbose_name="Магистратура Выпускной Год")

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


    courses = models.CharField("Курс",blank=True, max_length=10)

    adviser_status = models.CharField("Ученая степень руководителя",blank=True, max_length=100)
    adviser_position = models.CharField("Должность руководителя",blank=True, max_length=100)
    
    title = models.CharField("Тема работы", max_length=255,blank=True)
    adviser_name = models.CharField("ФИО руководителя",blank=True, max_length=200)
    adviser_rank = models.CharField("Ученое звание руководителя",blank=True, max_length=100)
    department = models.CharField("Кафедра",blank=True, max_length=100, choices=DEPARTMENT_CHOICES)
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
    PRACTICE_NIR_REPORT  = 'practice_nir_report'
    THESIS_TEXT          = 'thesis_text'
    THESIS_PRESENTATION  = 'thesis_presentation'
    PLAGIARISM_CHECK     = 'plagiarism_check'
    ADVISOR_REVIEW       = 'advisor_review'
    REVIEW               = 'review'

    _INTERIM_DOCS = [
        (INTERIM_REPORT,       'Пр. отчет'),
        (INTERIM_PRESENTATION, 'Пр. ЭП'),
    ]
    _REGULAR_FINAL_DOCS = [
        (FINAL_REPORT,         'Отчет'),
        (FINAL_PRESENTATION,   'ЭП'),
    ]
    _LATEST_EXTRA_DOCS = [
        (PRACTICE_NIR_REPORT,  'Отчет по<br>практике НИР'),
        (THESIS_TEXT,          'Текст<br>ВКР'),
        (THESIS_PRESENTATION,  'Презент.<br>ВКР'),
        (PLAGIARISM_CHECK,     'Проверка на<br>плагиат'),
        (ADVISOR_REVIEW,       'Отзыв<br>руковод.'),
    ]
    _MASTER_LATEST_EXTRA_DOCS = _LATEST_EXTRA_DOCS + [
        (REVIEW,               'Рецензия'),
    ]

    STANDARD_DOC_TYPES = _INTERIM_DOCS + _REGULAR_FINAL_DOCS
    LATEST_DOC_TYPES   = _INTERIM_DOCS + _LATEST_EXTRA_DOCS
    MASTER_LATEST_DOC_TYPES = _INTERIM_DOCS + _MASTER_LATEST_EXTRA_DOCS
    DOC_TYPES = _INTERIM_DOCS + _REGULAR_FINAL_DOCS + _MASTER_LATEST_EXTRA_DOCS

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

    @classmethod
    def get_doc_types_for_group(cls, is_latest: bool, is_master_latest: bool = False):
        if is_master_latest:
            return cls.MASTER_LATEST_DOC_TYPES
        return cls.LATEST_DOC_TYPES if is_latest else cls.STANDARD_DOC_TYPES


class TeacherProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='teacher_profile')
    full_name = models.CharField("ФИО преподавателя", max_length=200)
    department = models.CharField("Кафедра", max_length=100, choices=DEPARTMENT_CHOICES, blank=True)
    adviser_position = models.CharField("Должность руководителя", max_length=100, choices=ADVISER_POSITION_CHOICES, default='преподаватель')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Профиль преподавателя"
        verbose_name_plural = "Профили преподавателей"
        ordering = ['full_name']

    def __str__(self):
        return self.full_name


class Topic(models.Model):
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name='topics', verbose_name="Преподаватель")
    title = models.CharField("Название темы", max_length=255)
    description = models.TextField("Описание", blank=True)
    department = models.CharField("Кафедра", max_length=100, choices=DEPARTMENT_CHOICES)
    direction = models.CharField("Направление", max_length=100, blank=True)
    course = models.PositiveSmallIntegerField("Курс", choices=COURSE_CHOICES, default=1)
    capacity = models.PositiveSmallIntegerField("Количество студентов", default=1)
    is_active = models.BooleanField("Активна", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Тема"
        verbose_name_plural = "Темы"

    def __str__(self):
        return f"{self.title} ({self.teacher.full_name})"


class TopicRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Ожидает решения'),
        (STATUS_APPROVED, 'Принята'),
        (STATUS_REJECTED, 'Отклонена'),
    ]

    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='requests', verbose_name="Тема")
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='topic_requests', verbose_name="Запись обучения")
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    comment = models.TextField("Комментарий преподавателя", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Заявка на тему"
        verbose_name_plural = "Заявки на темы"
        unique_together = ('topic', 'enrollment')

    def __str__(self):
        return f"{self.enrollment.student.full_name} → {self.topic.title} ({self.get_status_display()})"
