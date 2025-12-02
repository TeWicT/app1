from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from django.contrib.sessions.models import Session
from webd_core.models import Year, Group, Enrollment, Topic, TopicRequest


def _increment_group_name(name: str) -> str:
    if not name:
        return name
    try:
        digits = int(name)
        width = len(name)
        return f"{digits + 100:0{width}d}"
    except ValueError:
        return name


def _increment_course(value: str) -> str:
    try:
        num = int(value)
        return str(num + 1)
    except (TypeError, ValueError):
        return value or ""


class Command(BaseCommand):
    help = "Переводит систему на новый учебный год: создаёт год, группы и переносит студентов."

    def add_arguments(self, parser):
        parser.add_argument(
            '--from-year',
            type=int,
            help='Год обучения, который считается завершённым (по умолчанию максимальный).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, что будет сделано, без сохранения изменений.',
        )

    def handle(self, *args, **options):
        from_year_val = options.get('from_year') or Year.objects.order_by('-year').values_list('year', flat=True).first()
        if not from_year_val:
            raise CommandError("В базе нет ни одного учебного года.")
        try:
            from_year = Year.objects.get(year=from_year_val)
        except Year.DoesNotExist:
            raise CommandError(f"Учебный год {from_year_val} не найден.")

        to_year_val = from_year_val + 1
        if Year.objects.filter(year=to_year_val).exists() and not options['dry_run']:
            raise CommandError(f"Учебный год {to_year_val} уже существует. Укажите --from-year явно или удалите год.")

        self.stdout.write(f"Перенос с {from_year_val} на {to_year_val}")
        if options['dry_run']:
            self.stdout.write("Режим dry-run: изменения не сохраняются.")

        if options['dry_run']:
            self._plan_rollover(from_year)
        else:
            self._execute_rollover(from_year, to_year_val)

    def _plan_rollover(self, from_year):
        to_year_val = from_year.year + 1
        groups = Group.objects.filter(year=from_year, is_latest=False).count()
        enrollments = Enrollment.objects.filter(year=from_year, group__is_latest=False).count()
        self.stdout.write(f"Будет создан год {to_year_val}")
        self.stdout.write(f"Будет создано групп: {groups}")
        self.stdout.write(f"Будет перенесено записей студентов: {enrollments}")

    def _execute_rollover(self, from_year, to_year_val):
        with transaction.atomic():
            to_year, created = Year.objects.get_or_create(year=to_year_val)
            if created:
                self.stdout.write(f"Создан учебный год {to_year_val}")
            else:
                self.stdout.write(f"Используется существующий учебный год {to_year_val}")

            group_map = {}
            for group in Group.objects.filter(year=from_year):
                if group.is_latest:
                    continue
                new_name = _increment_group_name(group.name)
                new_group, _ = Group.objects.get_or_create(
                    year=to_year,
                    name=new_name,
                    defaults={'is_latest': False},
                )
                group_map[group.id] = new_group

            for suffix in range(1, 7):
                name = f"221{suffix:02d}"
                Group.objects.get_or_create(year=to_year, name=name, defaults={'is_latest': False})

            moved = 0
            skipped = 0
            for enrollment in Enrollment.objects.select_related('group').filter(year=from_year):
                if enrollment.group.is_latest:
                    skipped += 1
                    continue
                new_group = group_map.get(enrollment.group_id)
                if not new_group:
                    skipped += 1
                    continue
                Enrollment.objects.update_or_create(
                    student=enrollment.student,
                    year=to_year,
                    defaults={
                        'group': new_group,
                        'courses': _increment_course(enrollment.courses),
                        'adviser_status': '',
                        'adviser_position': '',
                        'title': '',
                        'adviser_name': '',
                        'adviser_rank': '',
                        'department': '',
                    },
                )
                moved += 1

            TopicRequest.objects.all().delete()
            Topic.objects.all().delete()
            Session.objects.all().delete()

            self.stdout.write(self.style.SUCCESS(
                f"Перенос завершён. Создано групп: {len(group_map)}, перенесено записей: {moved}, пропущено: {skipped}"
            ))

