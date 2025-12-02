import random
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from faker import Faker
from webd_core.models import (
    Year, Group, Student, Enrollment, TeacherProfile, Topic, TopicRequest,
    DEPARTMENTS, ADVISER_POSITION_CHOICES
)

User = get_user_model()

# Направления для разных кафедр
DIRECTIONS_BY_DEPARTMENT = {
    'ПМиК': ['Прикладная математика', 'Кибернетика', 'Математическое моделирование'],
    'ИМО': ['Информатика', 'Математическое обеспечение', 'Программирование'],
    'ГиТ': ['Геометрия', 'Топология', 'Дифференциальная геометрия'],
    'МА': ['Математический анализ', 'Функциональный анализ', 'Дифференциальные уравнения'],
    'ТВиАД': ['Теория вероятностей', 'Математическая статистика', 'Анализ данных'],
    'ТМОМИ': ['Методика преподавания', 'Образовательные технологии', 'Педагогика'],
}

# Примеры тем для разных кафедр
TOPIC_TEMPLATES = {
    'ПМиК': [
        'Математическое моделирование {subject}',
        'Алгоритмы {subject}',
        'Оптимизация {subject}',
        'Численные методы {subject}',
        'Применение {subject} в {field}',
    ],
    'ИМО': [
        'Разработка системы {subject}',
        'Алгоритмы обработки {subject}',
        'База данных для {subject}',
        'Веб-приложение {subject}',
        'Мобильное приложение {subject}',
    ],
    'ГиТ': [
        'Геометрические свойства {subject}',
        'Топологические инварианты {subject}',
        'Дифференциальная геометрия {subject}',
        'Алгебраическая топология {subject}',
    ],
    'МА': [
        'Анализ {subject}',
        'Функциональный анализ {subject}',
        'Дифференциальные уравнения {subject}',
        'Интегральные уравнения {subject}',
    ],
    'ТВиАД': [
        'Статистический анализ {subject}',
        'Вероятностные модели {subject}',
        'Обработка данных {subject}',
        'Машинное обучение для {subject}',
    ],
    'ТМОМИ': [
        'Методика преподавания {subject}',
        'Образовательные технологии {subject}',
        'Разработка учебных материалов {subject}',
    ],
}

SUBJECTS = [
    'математики', 'информатики', 'алгебры', 'геометрии', 'анализа',
    'программирования', 'баз данных', 'веб-технологий', 'машинного обучения',
    'статистики', 'оптимизации', 'алгоритмов', 'структур данных',
]

FIELDS = [
    'экономике', 'физике', 'биологии', 'химии', 'медицине',
    'инженерии', 'образовании', 'бизнесе', 'науке',
]


class Command(BaseCommand):
    help = "Генерирует тестовые данные: 500 студентов, 20 преподавателей, темы и заявки"

    def add_arguments(self, parser):
        parser.add_argument(
            '--year',
            type=int,
            default=None,
            help='Учебный год для генерации данных (по умолчанию - текущий максимальный год)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Очистить существующие данные перед генерацией',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        fake = Faker('ru_RU')
        
        # Определяем год
        if options['year']:
            year_obj, _ = Year.objects.get_or_create(year=options['year'])
        else:
            year_obj = Year.objects.order_by('-year').first()
            if not year_obj:
                year_obj = Year.objects.create(year=2025)
        
        self.stdout.write(f"Используется год: {year_obj.year}")
        
        # Очистка данных если нужно
        if options['clear']:
            self.stdout.write("Очистка существующих данных...")
            TopicRequest.objects.all().delete()
            Topic.objects.all().delete()
            Enrollment.objects.filter(year=year_obj).delete()
            Student.objects.all().delete()
            TeacherProfile.objects.all().delete()
            User.objects.filter(is_staff=True).exclude(is_superuser=True).delete()
            Group.objects.filter(year=year_obj).delete()
            self.stdout.write(self.style.SUCCESS("Данные очищены"))
        
        # 1. Создаем группы для текущего года
        self.stdout.write("Создание групп...")
        group_names = []
        for course in range(1, 7):  # Курсы 1-6
            for group_num in range(1, 7):  # Группы 01-06
                group_name = f"{22}{course}{group_num:02d}"
                group_names.append(group_name)
                Group.objects.get_or_create(name=group_name, year=year_obj)
        
        groups = list(Group.objects.filter(year=year_obj))
        self.stdout.write(self.style.SUCCESS(f"Создано/найдено {len(groups)} групп"))
        
        # 2. Создаем 20 преподавателей
        self.stdout.write("Создание преподавателей...")
        teachers = []
        departments_list = list(DEPARTMENTS)
        
        for i in range(20):
            # Распределяем преподавателей по кафедрам
            department = departments_list[i % len(departments_list)]
            position = random.choice(ADVISER_POSITION_CHOICES)[0]
            
            # Создаем пользователя
            username = f"teacher_{i+1:02d}"
            email = f"{username}@example.com"
            
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'is_staff': True,
                    'is_active': True,
                }
            )
            
            if created:
                user.set_password('teacher123')
                user.save()
            
            # Создаем профиль преподавателя
            full_name = fake.name()
            teacher_profile, _ = TeacherProfile.objects.get_or_create(
                user=user,
                defaults={
                    'full_name': full_name,
                    'department': department,
                    'adviser_position': position,
                }
            )
            teachers.append(teacher_profile)
        
        self.stdout.write(self.style.SUCCESS(f"Создано {len(teachers)} преподавателей"))
        
        # 3. Создаем 500 студентов
        self.stdout.write("Создание студентов...")
        students = []
        used_logins = set()
        
        # Распределяем студентов по группам
        students_per_group = 500 // len(groups)
        remaining_students = 500 % len(groups)
        
        for idx, group in enumerate(groups):
            count = students_per_group + (1 if idx < remaining_students else 0)
            
            for _ in range(count):
                # Генерируем уникальный логин
                while True:
                    login = fake.user_name()
                    if login not in used_logins:
                        used_logins.add(login)
                        break
                
                student, _ = Student.objects.get_or_create(
                    login=login,
                    defaults={'full_name': fake.name()}
                )
                students.append(student)
        
        self.stdout.write(self.style.SUCCESS(f"Создано {len(students)} студентов"))
        
        # 4. Создаем Enrollment для студентов
        self.stdout.write("Создание записей обучения...")
        enrollments = []
        student_idx = 0
        
        for group in groups:
            # Определяем курс по номеру группы
            course_num = int(group.name[3]) if len(group.name) >= 4 else random.randint(1, 6)
            
            # Количество студентов в этой группе
            count = students_per_group + (1 if groups.index(group) < remaining_students else 0)
            
            for _ in range(count):
                if student_idx >= len(students):
                    break
                
                student = students[student_idx]
                enrollment, _ = Enrollment.objects.get_or_create(
                    student=student,
                    year=year_obj,
                    defaults={
                        'group': group,
                        'courses': str(course_num),
                    }
                )
                enrollments.append(enrollment)
                student_idx += 1
        
        self.stdout.write(self.style.SUCCESS(f"Создано {len(enrollments)} записей обучения"))
        
        # 5. Создаем темы для преподавателей
        self.stdout.write("Создание тем...")
        topics = []
        
        for teacher in teachers:
            # Количество тем на преподавателя (от 3 до 8)
            num_topics = random.randint(3, 8)
            department = teacher.department or random.choice(DEPARTMENTS)
            directions = DIRECTIONS_BY_DEPARTMENT.get(department, ['Общее направление'])
            topic_templates = TOPIC_TEMPLATES.get(department, ['Исследование {subject}'])
            
            for _ in range(num_topics):
                # Выбираем шаблон темы
                template = random.choice(topic_templates)
                subject = random.choice(SUBJECTS)
                field = random.choice(FIELDS)
                
                title = template.format(subject=subject, field=field)
                description = f"Курсовая работа по теме '{title}'. {fake.text(max_nb_chars=200)}"
                
                # Распределяем по курсам (больше тем для старших курсов)
                course = random.choices(
                    [1, 2, 3, 4, 5, 6],
                    weights=[5, 10, 15, 20, 25, 25]  # Больше тем для 4-6 курсов
                )[0]
                
                # Capacity от 1 до 3
                capacity = random.choices([1, 2, 3], weights=[50, 30, 20])[0]
                
                direction = random.choice(directions)
                
                topic = Topic.objects.create(
                    teacher=teacher,
                    title=title,
                    description=description,
                    department=department,
                    direction=direction,
                    course=course,
                    capacity=capacity,
                    is_active=True,
                )
                topics.append(topic)
        
        self.stdout.write(self.style.SUCCESS(f"Создано {len(topics)} тем"))
        
        # 6. Создаем заявки на темы
        self.stdout.write("Создание заявок на темы...")
        requests_created = 0
        
        # Распределяем заявки: 60% студентов подадут заявки
        num_applicants = int(len(enrollments) * 0.6)
        applicant_enrollments = random.sample(enrollments, num_applicants)
        
        for enrollment in applicant_enrollments:
            # Получаем курс студента
            try:
                student_course = int(enrollment.courses) if enrollment.courses else random.randint(1, 6)
            except (ValueError, TypeError):
                student_course = random.randint(1, 6)
            
            # Выбираем тему соответствующего курса
            available_topics = [t for t in topics if t.course == student_course]
            
            if not available_topics:
                # Если нет тем для этого курса, выбираем любую
                available_topics = topics
            
            if available_topics:
                topic = random.choice(available_topics)
                
                # Проверяем, не превышен ли лимит
                approved_count = topic.requests.filter(status='approved').count()
                
                # Статусы: 40% pending, 40% approved, 20% rejected
                status_choice = random.choices(
                    ['pending', 'approved', 'rejected'],
                    weights=[40, 40, 20]
                )[0]
                
                # Если тема уже заполнена, не одобряем новые заявки
                if status_choice == 'approved' and approved_count >= topic.capacity:
                    status_choice = 'rejected'
                
                request, created = TopicRequest.objects.get_or_create(
                    topic=topic,
                    enrollment=enrollment,
                    defaults={
                        'status': status_choice,
                        'comment': fake.text(max_nb_chars=100) if status_choice != 'pending' else '',
                        'decided_at': timezone.now() if status_choice != 'pending' else None,
                    }
                )
                
                if created:
                    requests_created += 1
                    
                    # Если заявка одобрена, обновляем enrollment
                    if status_choice == 'approved':
                        enrollment.title = topic.title
                        enrollment.adviser_name = topic.teacher.full_name
                        enrollment.adviser_position = topic.teacher.adviser_position
                        enrollment.department = topic.department
                        enrollment.save()
        
        self.stdout.write(self.style.SUCCESS(f"Создано {requests_created} заявок на темы"))
        
        # Итоговая статистика
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS("Генерация завершена!"))
        self.stdout.write(f"Год: {year_obj.year}")
        self.stdout.write(f"Групп: {Group.objects.filter(year=year_obj).count()}")
        self.stdout.write(f"Преподавателей: {TeacherProfile.objects.count()}")
        self.stdout.write(f"Студентов: {Student.objects.count()}")
        self.stdout.write(f"Записей обучения: {Enrollment.objects.filter(year=year_obj).count()}")
        self.stdout.write(f"Тем: {Topic.objects.count()}")
        self.stdout.write(f"Заявок: {TopicRequest.objects.count()}")
        self.stdout.write("\nПароли для преподавателей: teacher123")
        self.stdout.write("="*50)

