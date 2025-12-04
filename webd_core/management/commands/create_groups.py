from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from webd_core.models import Year, Group


class Command(BaseCommand):
    help = "Создаёт пустые группы для указанного учебного года"

    def add_arguments(self, parser):
        parser.add_argument(
            '--year',
            type=int,
            required=True,
            help='Учебный год, для которого нужно создать группы (например, 2025)',
        )
        parser.add_argument(
            '--courses',
            type=int,
            nargs='+',
            default=[1, 2, 3, 4, 5, 6],
            help='Курсы, для которых создавать группы (по умолчанию все: 1 2 3 4 5 6)',
        )
        parser.add_argument(
            '--groups-per-course',
            type=int,
            default=6,
            help='Количество групп на курс (по умолчанию 6)',
        )
        parser.add_argument(
            '--latest',
            action='store_true',
            help='Пометить группы как выпускные (is_latest=True)',
        )

    def handle(self, *args, **options):
        year_val = options['year']
        courses = options['courses']
        groups_per_course = options['groups_per_course']
        is_latest = options['latest']

        # Проверяем или создаём год
        try:
            year_obj = Year.objects.get(year=year_val)
            self.stdout.write(f"Используется существующий учебный год {year_val}")
        except Year.DoesNotExist:
            year_obj = Year.objects.create(year=year_val)
            self.stdout.write(f"Создан новый учебный год {year_val}")

        # Создаём группы
        created_count = 0
        existing_count = 0

        with transaction.atomic():
            for course in courses:
                if course < 1 or course > 6:
                    self.stdout.write(self.style.WARNING(f"Пропущен недопустимый курс: {course}"))
                    continue

                for group_num in range(1, groups_per_course + 1):
                    # Формат имени группы: 22{курс}{номер_группы:02d}
                    # Например: 22101, 22102, ..., 22106 для 1 курса
                    group_name = f"22{course}{group_num:02d}"
                    
                    group, created = Group.objects.get_or_create(
                        year=year_obj,
                        name=group_name,
                        defaults={'is_latest': is_latest}
                    )
                    
                    if created:
                        created_count += 1
                        self.stdout.write(f"  Создана группа: {group_name} (курс {course})")
                    else:
                        existing_count += 1
                        # Обновляем is_latest, если указан флаг
                        if is_latest and not group.is_latest:
                            group.is_latest = True
                            group.save()
                            self.stdout.write(f"  Обновлена группа: {group_name} (помечена как выпускная)")

        # Итоговая статистика
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS("Генерация завершена!"))
        self.stdout.write(f"Учебный год: {year_val}")
        self.stdout.write(f"Создано новых групп: {created_count}")
        self.stdout.write(f"Уже существовало групп: {existing_count}")
        self.stdout.write(f"Всего групп в году: {Group.objects.filter(year=year_obj).count()}")
        if is_latest:
            self.stdout.write(self.style.WARNING("Все группы помечены как выпускные"))
        self.stdout.write("="*50)



