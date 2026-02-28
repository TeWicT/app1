from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from webd_core.models import Year


class Command(BaseCommand):
    help = (
        "Создаёт новый учебный год (Year) без каких-либо переносов данных.\n"
        "Группы, студенты, темы и заявки НЕ трогаются.\n"
        "Используется для того, чтобы просто переключить систему на следующий год."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--from-year",
            type=int,
            help="Год обучения, от которого считать следующий (по умолчанию максимальный год в БД).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать, что будет сделано, без сохранения изменений.",
        )

    def handle(self, *args, **options):
        from_year_val = (
            options.get("from_year")
            or Year.objects.order_by("-year").values_list("year", flat=True).first()
        )
        if not from_year_val:
            raise CommandError("В базе нет ни одного учебного года.")

        try:
            from_year = Year.objects.get(year=from_year_val)
        except Year.DoesNotExist:
            raise CommandError(f"Учебный год {from_year_val} не найден.")

        to_year_val = from_year_val + 1
        if Year.objects.filter(year=to_year_val).exists() and not options["dry_run"]:
            raise CommandError(
                f"Учебный год {to_year_val} уже существует. Укажите --from-year явно или удалите год."
            )

        self.stdout.write(f"Создание года {to_year_val} на основе {from_year_val}")
        if options["dry_run"]:
            self._plan(from_year, to_year_val)
        else:
            self._execute(from_year, to_year_val)

    def _plan(self, from_year, to_year_val: int):
        self.stdout.write(f"Будет создан учебный год {to_year_val}")
        self.stdout.write("Группы, студенты и темы затронуты не будут.")

    def _execute(self, from_year, to_year_val: int):
        with transaction.atomic():
            to_year, created = Year.objects.get_or_create(year=to_year_val)
            if created:
                self.stdout.write(f"Создан учебный год {to_year_val}")
            else:
                self.stdout.write(f"Используется существующий учебный год {to_year_val}")

            self.stdout.write(
                self.style.SUCCESS(
                    "Создание года завершено. Другие данные (группы, студенты, темы) не изменялись."
                )
            )

