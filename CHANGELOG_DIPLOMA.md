# Изменения с коммита `97cd629944f6efb7d767f8fe842658091bbf4d91` до текущего состояния

## Кратко
Добавлены новые поля и функции для тем, переработаны страницы «Предложить тему» и «Выбрать тему» с AJAX/JS, группировками и плавными анимациями, внедрены уведомления, создан набор management-команд для перехода на новый учебный год и генерации тестовых данных, расширена админка, добавлены зависимости (Faker).

## Технологии и библиотеки
- Django: модели, формы, middleware, представления, шаблоны, admin.
- Django management commands: `roll_year`, `generate_test_data`, `create_groups`.
- JavaScript (чистый): AJAX через `fetch`, DOM-манипуляции, кастомные анимации `requestAnimationFrame` для `<details>/<summary>`.
- CSS: кастомные таблицы, кнопки в стиле Bootstrap без подключения всего фреймворка; Animate.css подключен.
- Faker (requirements.txt) для генерации реалистичных тестовых данных.

## Модели (`webd_core/models.py`)
- `TeacherProfile`: поле `adviser_position` с choices.
- `Topic`: поля `course` (choices), `capacity`, `direction`.
- Константы `ADVISER_POSITION_CHOICES`, `COURSE_CHOICES`.

## Формы (`webd_core/forms.py`)
- `TopicForm` расширен полями `course`, `capacity`.
- `TeacherProfileForm` для редактирования `adviser_position`.

## Middleware (`webd_core/middleware.py`)
- `FoundYearMiddleware`: вычисление `pending_request_count` для преподавателей и `topic_notifications` для студентов.
- `_get_default_year` для динамического выбора года.

## Представления (`webd_core/views.py`)
- `page_webd`: выбор уникальных групп по текущему году.
- `teacher_topics_view`:
  - Действия `create_batch`, `update_topic`, `delete_topic`, `decision`.
  - Обработка `direction`, AJAX-ответы JSON.
  - Удаление темы отвязывает студентов и очищает данные Enrollment.
  - Группировка тем: свободные (по наличию свободных мест) и по курсам.
- `student_topics_view`:
  - Фильтрация тем по курсу студента.
  - Группировка по кафедре и направлению, если выбраны все кафедры.
  - Запрет множественных ожидающих заявок для студента.
- `_approve_topic_request`: сохраняет `adviser_position` в Enrollment из профиля преподавателя.

## Админка (`webd_core/admin.py`)
- Зарегистрированы `TeacherProfile`, `Topic`, `TopicRequest` с `list_display`, фильтрами и поиском.

## Management-команды
- `roll_year.py`: перенос невыпускных групп, очистка тем/заявок, сброс сессий (разлогин всех), создание фиксированных первокурсных групп, очистка полей привязок у студентов.
- `generate_test_data.py`: создание 500 студентов, 20 преподавателей, тем, заявок со статусами; опции `--year`, `--clear`.
- `create_groups.py`: генерация пустых групп на выбранные курсы/год, опции `--year`, `--courses`, `--groups-per-course`, `--latest`.

## Шаблоны и фронтенд
- `page_teacher_topics.html`:
  - Таблица ввода новых тем (расширяемая «+»), сохранение без перезагрузки.
  - Отображение существующих тем в режиме просмотра; иконки редактирования/удаления с inline-редактированием и AJAX-сохранением.
  - Колонка «Направление», группировка «Свободные темы» и по курсам.
- `page_topic_select.html` + `topic_table_fragment.html`:
  - Группировка тем по кафедре и направлению.
  - Кнопка «Подать заявку» в стиле Bootstrap-подобной кастомной кнопки.
  - Плавное раскрытие описания темы (скролл-эффект) через JS-анимации.
  - Отображение доступных мест, блокировка после достижения лимита утвержденных студентов.
  - Запрет второй заявки при наличии ожидающей.
- `topic_row_fragment.html`: фрагмент строки темы для переиспользования на странице преподавателя.
- `user_header.html`: увеличены `maxlength` логина/пароля; счетчики уведомлений рядом с «Предложить тему»/«Выбрать тему».
- Другие шаблоны: мелкие правки в отчетах/форматировании (`page_identity`, `page_query`, `report_template`).

## URLs (`webd_core/urls.py`)
- Подключение новых представлений/обработчиков тем.

## Зависимости
- `requirements.txt`: добавлен `Faker>=19.0.0`.

## Статистика изменений по строкам кода

### Общая статистика
- **Всего файлов изменено**: 18
- **Добавлено строк**: 2,759
- **Удалено строк**: 270
- **Чистое изменение**: +2,489 строк

### Детальная статистика по разделам

#### 1. Модели и структура данных
- **webd_core/models.py**: +108 / -7 = **+101 строка**
  - Добавлены поля `adviser_position`, `course`, `capacity`, `direction`
  - Добавлены константы для choices

#### 2. Формы
- **webd_core/forms.py**: +13 / -3 = **+10 строк**
  - Расширен `TopicForm`, добавлен `TeacherProfileForm`

#### 3. Middleware
- **webd_core/middleware.py**: +41 / -5 = **+36 строк**
  - Добавлена логика уведомлений и динамического выбора года

#### 4. Представления (Views)
- **webd_core/views.py**: +675 / -169 = **+506 строк**
  - Основная логика управления темами, заявками, группировками
  - AJAX-обработчики для создания, редактирования, удаления тем
  - Фильтрация и группировка тем для студентов и преподавателей

#### 5. Админ-панель
- **webd_core/admin.py**: +25 / -1 = **+24 строки**
  - Регистрация моделей `TeacherProfile`, `Topic`, `TopicRequest`
  - Настройка отображения, фильтров и поиска

#### 6. Management-команды
- **webd_core/management/commands/roll_year.py**: +129 / -0 = **+129 строк** (новый файл)
  - Перенос учебного года, очистка данных, создание групп

- **webd_core/management/commands/generate_test_data.py**: +348 / -0 = **+348 строк** (новый файл)
  - Генерация тестовых данных (500 студентов, 20 преподавателей)

- **webd_core/management/commands/create_groups.py**: +93 / -0 = **+93 строки** (новый файл)
  - Создание пустых групп для указанного года

**Итого по командам**: +570 строк (3 новых файла)

#### 7. Шаблоны (Templates)

##### Основные страницы
- **webd_core/templates/webd_core/page_teacher_topics.html**: +591 / -0 = **+591 строка** (новый файл)
  - Полностью переработанная страница управления темами преподавателя
  - Таблица ввода новых тем, inline-редактирование, AJAX-взаимодействие

- **webd_core/templates/webd_core/page_topic_select.html**: +376 / -0 = **+376 строк** (новый файл)
  - Страница выбора темы студентом
  - Группировка по кафедрам/направлениям, плавные анимации

##### Фрагменты шаблонов
- **webd_core/templates/webd_core/topic_row_fragment.html**: +119 / -0 = **+119 строк** (новый файл)
  - Фрагмент строки темы для переиспользования

- **webd_core/templates/webd_core/topic_table_fragment.html**: +100 / -0 = **+100 строк** (новый файл)
  - Фрагмент таблицы тем для переиспользования

##### Обновленные шаблоны
- **webd_core/templates/webd_core/user_header.html**: +13 / -5 = **+8 строк**
  - Увеличены лимиты полей, добавлены счетчики уведомлений

- **webd_core/templates/webd_core/report_template.html**: +82 / -46 = **+36 строк**
  - Обновления в форматировании отчетов

- **webd_core/templates/webd_core/page_query.html**: +41 / -32 = **+9 строк**
  - Мелкие правки в отображении запросов

- **webd_core/templates/webd_core/page_identity.html**: +1 / -1 = **0 строк** (без изменений)

**Итого по шаблонам**: +1,231 строка (4 новых файла, 4 обновленных)

#### 8. Маршрутизация
- **webd_core/urls.py**: +2 / -0 = **+2 строки**
  - Подключение новых представлений

#### 9. Зависимости
- **requirements.txt**: +2 / -1 = **+1 строка**
  - Добавлен `Faker>=19.0.0`

### Сводка по категориям

| Категория | Файлов | Добавлено | Удалено | Чистое изменение |
|-----------|--------|-----------|---------|-------------------|
| **Модели и данные** | 1 | 108 | 7 | +101 |
| **Формы** | 1 | 13 | 3 | +10 |
| **Middleware** | 1 | 41 | 5 | +36 |
| **Представления** | 1 | 675 | 169 | +506 |
| **Админ-панель** | 1 | 25 | 1 | +24 |
| **Management-команды** | 3 | 570 | 0 | +570 |
| **Шаблоны** | 8 | 1,231 | 84 | +1,147 |
| **Маршрутизация** | 1 | 2 | 0 | +2 |
| **Зависимости** | 1 | 2 | 1 | +1 |
| **ИТОГО** | **18** | **2,759** | **270** | **+2,489** |

### Ключевые наблюдения
- **Наибольший объем изменений**: шаблоны (+1,147 строк) — переработка UI/UX с AJAX и анимациями
- **Вторая по объему категория**: представления (+506 строк) — бизнес-логика управления темами
- **Третья категория**: management-команды (+570 строк) — автоматизация процессов
- **Новых файлов создано**: 7 (3 команды + 4 шаблона)
- **Основной фокус**: функциональность управления темами курсовых работ с улучшенным пользовательским интерфейсом

## Ключевые сценарии, которые теперь поддерживаются
- Преподаватель: пакетное добавление, inline-редактирование, удаление тем с отвязкой студентов; группировка свободных/по курсам; уведомления о заявках.
- Студент: просмотр тем по своему курсу; группировка по кафедрам/направлениям; видимость доступных мест и занятых студентов; одна активная заявка; плавное раскрытие описаний; кнопка подачи заявки стилизована.
- Администратор: создание групп, генерация тестовых данных, перенос учебного года с очисткой сессий.

## Структура базы данных

### Общая информация
- **СУБД**: SQLite3 (для разработки)
- **ORM**: Django ORM
- **Всего таблиц**: 8 основных таблиц + таблица пользователей Django (`auth_user`)
- **Связи**: ForeignKey, OneToOneField

### Диаграмма связей

```
┌─────────────┐
│    Year     │ (Учебный год)
└──────┬──────┘
       │
       ├─────────────────┐
       │                 │
┌──────▼──────┐    ┌─────▼──────┐
│   Group     │    │ Enrollment │
│             │    │            │
│ - name      │◄───┤ - student  │
│ - year (FK) │    │ - year (FK)│
│ - is_latest │    │ - group(FK)│
└─────────────┘    │ - courses  │
                   │ - title   │
                   │ - adviser_*│
                   │ - department│
                   └─────┬──────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
    ┌────▼────┐    ┌─────▼─────┐   ┌────▼──────┐
    │Document │    │TopicRequest│   │  Student  │
    │         │    │            │   │          │
    │-enroll(FK)│   │-topic (FK) │   │-login    │
    │-doc_type │   │-enroll(FK) │   │-full_name│
    │-file     │   │-status     │   └──────────┘
    └─────────┘    │-comment    │
                   └─────┬──────┘
                         │
                   ┌─────▼──────┐
                   │   Topic    │
                   │            │
                   │-teacher(FK)│
                   │-title      │
                   │-description│
                   │-department │
                   │-direction  │
                   │-course     │
                   │-capacity   │
                   └─────┬──────┘
                         │
                   ┌─────▼──────────┐
                   │ TeacherProfile │
                   │                │
                   │-user (OneToOne)│
                   │-full_name      │
                   │-department     │
                   │-adviser_position│
                   └────────────────┘
                         │
                   ┌─────▼──────┐
                   │  auth_user  │
                   │  (Django)  │
                   └────────────┘
```

### Описание таблиц

#### 1. `Year` (Учебный год)
**Назначение**: Хранение учебных годов (например, 2023, 2024, 2025)

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| `id` | Integer (PK) | Auto | Первичный ключ |
| `year` | PositiveInteger | Unique, NOT NULL | Год обучения (например, 2024) |

**Связи**:
- `Group.year` → ForeignKey (CASCADE)
- `Enrollment.year` → ForeignKey (CASCADE)

**Индексы**: `year` (unique)

---

#### 2. `Group` (Группа студентов)
**Назначение**: Группы студентов, привязанные к учебному году

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| `id` | Integer (PK) | Auto | Первичный ключ |
| `name` | CharField(50) | NOT NULL | Название группы (например, "22305") |
| `year_id` | Integer (FK) | NOT NULL | Ссылка на Year |
| `is_latest` | Boolean | Default: False | Выпускной год (4-й курс) |

**Связи**:
- `year` → ForeignKey(Year, CASCADE)
- `Enrollment.group` → ForeignKey (PROTECT)

**Ограничения**: `unique_together = ('name', 'year')` — уникальность комбинации название+год

**Индексы**: Составной индекс на (`name`, `year`)

---

#### 3. `Student` (Студент)
**Назначение**: Базовая информация о студентах

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| `id` | Integer (PK) | Auto | Первичный ключ |
| `login` | CharField(50) | Unique, NOT NULL | Уникальный логин студента |
| `full_name` | CharField(200) | NOT NULL | Полное имя студента |

**Связи**:
- `Enrollment.student` → ForeignKey (CASCADE)

**Индексы**: `login` (unique)

---

#### 4. `Enrollment` (Запись обучения)
**Назначение**: Связь студента с годом обучения, группой и информацией о курсовой работе

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| `id` | Integer (PK) | Auto | Первичный ключ |
| `student_id` | Integer (FK) | NOT NULL | Ссылка на Student |
| `year_id` | Integer (FK) | NOT NULL | Ссылка на Year |
| `group_id` | Integer (FK) | NOT NULL | Ссылка на Group |
| `courses` | CharField(10) | Blank=True | Курс студента |
| `adviser_status` | CharField(100) | Blank=True | Ученая степень руководителя |
| `adviser_position` | CharField(100) | Blank=True | Должность руководителя |
| `title` | CharField(255) | Blank=True | Тема курсовой работы |
| `adviser_name` | CharField(200) | Blank=True | ФИО руководителя |
| `adviser_rank` | CharField(100) | Blank=True | Ученое звание руководителя |
| `department` | CharField(100) | Blank=True, Choices | Кафедра (ПМиК, ИМО, ГиТ, МА, ТВиАД, ТМОМИ) |

**Связи**:
- `student` → ForeignKey(Student, CASCADE)
- `year` → ForeignKey(Year, CASCADE)
- `group` → ForeignKey(Group, PROTECT)
- `Document.enrollment` → ForeignKey (CASCADE)
- `TopicRequest.enrollment` → ForeignKey (CASCADE)

**Ограничения**: `unique_together = ('student', 'year')` — один студент может иметь одну запись на год

**Индексы**: Составной индекс на (`student_id`, `year_id`)

---

#### 5. `Document` (Документ)
**Назначение**: Загруженные документы студента (отчеты, презентации, ВКР и т.д.)

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| `id` | Integer (PK) | Auto | Первичный ключ |
| `enrollment_id` | Integer (FK) | NOT NULL | Ссылка на Enrollment |
| `doc_type` | CharField(30) | NOT NULL, Choices | Тип документа |
| `file` | FileField | NOT NULL | Путь к файлу |
| `uploaded_at` | DateTime | Auto_now_add | Дата загрузки |

**Типы документов** (`doc_type`):
- **Промежуточные**: `interim_report` (Пр. отчет), `interim_presentation` (Пр. ЭП)
- **Обычные финальные**: `final_report` (Отчет), `final_presentation` (ЭП)
- **Выпускные (только для is_latest=True)**: 
  - `practice_nir_report` (Отчет по практике НИР)
  - `thesis_text` (Текст ВКР)
  - `thesis_presentation` (Презентация ВКР)
  - `plagiarism_check` (Проверка на плагиат)
  - `advisor_review` (Отзыв руководителя)

**Связи**:
- `enrollment` → ForeignKey(Enrollment, CASCADE)

**Ограничения**: `unique_together = ('enrollment', 'doc_type')` — один тип документа на запись обучения

**Индексы**: Составной индекс на (`enrollment_id`, `doc_type`)

**Путь загрузки**: `media/students/{year}/{group}/{student}/{filename}`

---

#### 6. `TeacherProfile` (Профиль преподавателя)
**Назначение**: Расширенная информация о преподавателях

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| `id` | Integer (PK) | Auto | Первичный ключ |
| `user_id` | Integer (FK) | Unique, NOT NULL | Ссылка на auth_user (OneToOne) |
| `full_name` | CharField(200) | NOT NULL | ФИО преподавателя |
| `department` | CharField(100) | Blank=True, Choices | Кафедра |
| `adviser_position` | CharField(100) | Default='преподаватель', Choices | Должность руководителя |
| `created_at` | DateTime | Auto_now_add | Дата создания профиля |

**Варианты должности** (`adviser_position`):
- `преподаватель`
- `ст. преподаватель`
- `доцент`
- `профессор`
- `зав. кафедрой`
- `другая`

**Связи**:
- `user` → OneToOneField(User, CASCADE)
- `Topic.teacher` → ForeignKey (CASCADE)

**Индексы**: `user_id` (unique)

---

#### 7. `Topic` (Тема курсовой работы)
**Назначение**: Темы курсовых работ, предлагаемые преподавателями

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| `id` | Integer (PK) | Auto | Первичный ключ |
| `teacher_id` | Integer (FK) | NOT NULL | Ссылка на TeacherProfile |
| `title` | CharField(255) | NOT NULL | Название темы |
| `description` | TextField | Blank=True | Описание темы |
| `department` | CharField(100) | NOT NULL, Choices | Кафедра |
| `direction` | CharField(100) | Blank=True | Направление группы |
| `course` | PositiveSmallInteger | Default=1, Choices | Курс (1-6) |
| `capacity` | PositiveSmallInteger | Default=1 | Количество студентов на тему |
| `is_active` | Boolean | Default=True | Активна ли тема |
| `created_at` | DateTime | Auto_now_add | Дата создания |
| `updated_at` | DateTime | Auto_now | Дата последнего обновления |

**Связи**:
- `teacher` → ForeignKey(TeacherProfile, CASCADE)
- `TopicRequest.topic` → ForeignKey (CASCADE)

**Индексы**: Индекс на `teacher_id`, `created_at` (для сортировки)

---

#### 8. `TopicRequest` (Заявка на тему)
**Назначение**: Заявки студентов на темы курсовых работ

| Поле | Тип | Ограничения | Описание |
|------|-----|-------------|----------|
| `id` | Integer (PK) | Auto | Первичный ключ |
| `topic_id` | Integer (FK) | NOT NULL | Ссылка на Topic |
| `enrollment_id` | Integer (FK) | NOT NULL | Ссылка на Enrollment |
| `status` | CharField(20) | Default='pending', Choices | Статус заявки |
| `comment` | TextField | Blank=True | Комментарий преподавателя |
| `created_at` | DateTime | Auto_now_add | Дата создания заявки |
| `decided_at` | DateTime | Null=True, Blank=True | Дата принятия решения |

**Статусы** (`status`):
- `pending` — Ожидает решения
- `approved` — Принята
- `rejected` — Отклонена

**Связи**:
- `topic` → ForeignKey(Topic, CASCADE)
- `enrollment` → ForeignKey(Enrollment, CASCADE)

**Ограничения**: `unique_together = ('topic', 'enrollment')` — одна заявка студента на тему

**Индексы**: Составной индекс на (`topic_id`, `enrollment_id`), индекс на `created_at`

---

### Дополнительные таблицы Django

#### `auth_user` (Пользователи системы)
**Назначение**: Стандартная таблица Django для аутентификации

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | Integer (PK) | Первичный ключ |
| `username` | CharField(150) | Уникальное имя пользователя |
| `password` | CharField(128) | Хеш пароля |
| `email` | EmailField | Email |
| `first_name`, `last_name` | CharField | Имя и фамилия |
| `is_staff`, `is_superuser`, `is_active` | Boolean | Флаги доступа |
| `date_joined`, `last_login` | DateTime | Даты |

**Связи**:
- `TeacherProfile.user` → OneToOneField

---

### Ключевые особенности структуры

1. **Многоуровневая иерархия**:
   - `Year` → `Group` → `Enrollment` → `Document`/`TopicRequest`
   - `User` → `TeacherProfile` → `Topic` → `TopicRequest`

2. **Ограничения целостности**:
   - `CASCADE` для зависимых данных (удаление года удаляет группы)
   - `PROTECT` для групп (нельзя удалить группу, если есть записи Enrollment)
   - `unique_together` предотвращает дублирование записей

3. **Гибкость данных**:
   - Поля `Enrollment` могут быть пустыми до выбора темы
   - Поддержка нескольких типов документов в зависимости от типа группы
   - Статусы заявок позволяют отслеживать процесс утверждения

4. **Масштабируемость**:
   - Поддержка нескольких учебных годов одновременно
   - Возможность хранения исторических данных
   - Группировка по кафедрам и направлениям

5. **Безопасность**:
   - Связь преподавателей с системой аутентификации Django
   - Уникальные логины студентов
   - Защита от удаления критических данных (PROTECT на Group)

### Статистика таблиц

| Таблица | Основных полей | ForeignKey | Индексов | Ограничений unique |
|---------|---------------|------------|----------|-------------------|
| `Year` | 1 | 0 | 1 | 1 |
| `Group` | 2 | 1 | 1 | 1 (составной) |
| `Student` | 2 | 0 | 1 | 1 |
| `Enrollment` | 9 | 3 | 1 | 1 (составной) |
| `Document` | 3 | 1 | 1 | 1 (составной) |
| `TeacherProfile` | 4 | 1 | 1 | 1 |
| `Topic` | 8 | 1 | 2 | 0 |
| `TopicRequest` | 5 | 2 | 2 | 1 (составной) |
| **ИТОГО** | **34** | **9** | **10** | **7** |




