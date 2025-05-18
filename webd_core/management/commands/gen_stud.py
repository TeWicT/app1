import random
from django.core.management.base import BaseCommand
from faker import Faker
from webd_core.models import Year, Group, Student, Enrollment

class Command(BaseCommand):
    help = "Генерирует тестовые данные"

    def handle(self, *args, **opts):
        fake = Faker('ru_RU')
        # Сколько годов, групп, студентов, записей
        YEARS = [2020,2021, 2022, 2023, 2024]
        STUDENTS_PER_GROUP = 20

        # 1) Годы
        for y in YEARS:
            Year.objects.get_or_create(year=y)

        # 2) Группы
        for year in Year.objects.all():
            for grp_name in ['22201','22202','22203','22204','22205','22206','22301','22302','22303','22304','22305','22306']:
                Group.objects.get_or_create(name=grp_name, year=year)

        # 3) Студенты + их зачисления
        for group in Group.objects.all():
            for _ in range(STUDENTS_PER_GROUP):
                login = fake.user_name()
                student, _ = Student.objects.get_or_create(
                    login=login,
                    full_name=fake.name()
                )
                Enrollment.objects.get_or_create(
                    student=student,
                    year=group.year,
                    group=group,
                    courses=str(random.randint(1,6)),
                    adviser_name=fake.name(),
                    title=fake.sentence(nb_words=6)
                )

        self.stdout.write(self.style.SUCCESS("Сгенерировано данные"))
