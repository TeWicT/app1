from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import Year, Group, Student, Enrollment

@receiver(post_migrate)
def create_enrollments(sender, **kwargs):
    # Автозапуск после миграций: создаем Year, Group и Enrollment для существующих студентов
    for stud in Student.objects.all():
        # если есть старые поля study_year и groups — используем их
        try:
            y = int(getattr(stud, 'study_year', None))
        except (TypeError, ValueError):
            continue
        year_obj, _ = Year.objects.get_or_create(year=y)
        grp_name = getattr(stud, 'groups', None)
        if grp_name:
            group_obj, _ = Group.objects.get_or_create(name=grp_name, year=year_obj)
        else:
            continue
        Enrollment.objects.get_or_create(student=stud, year=year_obj, group=group_obj)