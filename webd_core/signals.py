from django.db import connection
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import Year, Group, Student, Enrollment


@receiver(post_migrate)
def create_enrollments(sender, app_config=None, **kwargs):
    """
    Автозапуск после миграций: создаем Year, Group и Enrollment для существующих студентов.

    Важно: на чистой БД таблиц приложения webd_core еще может не быть,
    поэтому сначала проверяем, что:
      1) сигнал относится к нашему приложению,
      2) таблица Student уже создана миграциями.
    """
    # 1. Срабатываем только для нашего приложения
    if app_config is None or app_config.label != "webd_core":
        return

    # 2. Проверяем, что таблица студентов уже существует
    existing_tables = connection.introspection.table_names()
    if "webd_core_student" not in existing_tables:
        return

    # 3. Основная логика заполнения Enrollment из старых полей
    for stud in Student.objects.all():
        # если есть старые поля study_year и groups — используем их
        try:
            y = int(getattr(stud, 'study_year', None))
        except (TypeError, ValueError):
            continue
        year_obj, _ = Year.objects.get_or_create(year=y)
        grp_name = getattr(stud, 'groups', None)
        if not grp_name:
            continue
        group_obj, _ = Group.objects.get_or_create(name=grp_name, year=year_obj)
        Enrollment.objects.get_or_create(student=stud, year=year_obj, group=group_obj)