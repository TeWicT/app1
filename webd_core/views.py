from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db import transaction
from django.db.models import Q, Prefetch, Count
from django.utils import timezone
from django.urls import reverse
from .models import (
    Student,
    Document,
    Enrollment,
    Year,
    Group,
    Topic,
    TopicRequest,
    DEPARTMENTS,
    ADVISER_POSITION_CHOICES,
    COURSE_CHOICES,
)
from .forms import StudentForm
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from collections import defaultdict
from django.template.loader import render_to_string
from .utils.pdf import html_to_pdf

GROUP_METHOD_DEFAULT = 'default'
SORT_METHOD_DEFAULT = 'by-student-name'
SORT_ORDER_DEFAULT = 'ascending'
HAVE_INDEX_DEFAULT = 'registered'
def _parse_course(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


SORT_FIELDS = {
    'by-student-name': ['student__full_name', 'adviser_name', 'id'],
    'by-adviser-name': ['adviser_name', 'student__full_name', 'id'],
    'by-identity-date': ['id'],
}


def _get_ordering(sort_method: str, sort_order: str):
    fields = SORT_FIELDS.get(sort_method, SORT_FIELDS[SORT_METHOD_DEFAULT])
    if sort_order == 'descending':
        return [f"-{field}" for field in fields]
    return fields


def _apply_common_filters(post_data):
    years = post_data.getlist('years')
    groups = post_data.getlist('groups')
    department = post_data.get('department', '').strip()
    name = post_data.get('name', '').strip()
    adviser = post_data.get('adviser-name', '').strip()
    have_index = post_data.get('have-index', HAVE_INDEX_DEFAULT)
    group_method = post_data.get('group-method', GROUP_METHOD_DEFAULT)
    sort_method = post_data.get('sort-method', SORT_METHOD_DEFAULT)
    sort_order = post_data.get('sort-order', SORT_ORDER_DEFAULT)

    qs = Enrollment.objects.select_related('student', 'group', 'year').all()

    if years and any(years):
        year_values = [int(y) for y in years if y and y.isdigit()]
        if year_values:
            qs = qs.filter(year__year__in=year_values)
    if groups and any(groups):
        group_values = [g for g in groups if g]
        if group_values:
            qs = qs.filter(group__name__in=group_values)
    if department:
        qs = qs.filter(department__iexact=department)
    if name:
        qs = qs.filter(student__full_name__icontains=name)
    if adviser:
        qs = qs.filter(adviser_name__icontains=adviser)

    if have_index == 'registered':
        qs = qs.exclude(Q(title__isnull=True) | Q(title=''))
    elif have_index == 'unregistered':
        qs = qs.filter(Q(title__isnull=True) | Q(title=''))

    qs = qs.order_by(*_get_ordering(sort_method, sort_order))

    filters = {
        'group_method': group_method if group_method in {'default', 'flatten'} else GROUP_METHOD_DEFAULT,
        'sort_method': sort_method,
        'sort_order': sort_order if sort_order in {'ascending', 'descending'} else SORT_ORDER_DEFAULT,
        'have_index': have_index if have_index in {'registered', 'unregistered', 'all'} else HAVE_INDEX_DEFAULT,
    }
    return qs, filters


def _build_row(enroll, doc_types):
    docs = {d.doc_type: d for d in enroll.documents.all()}
    sfiles = []
    for code, _ in doc_types:
        doc = docs.get(code)
        sfiles.append({
            'file': bool(doc),
            'in_time': True,
            'link': doc.file.url if doc else '',
        })
    return {
        'year': enroll.year.year,
        'department': enroll.department,
        'group': enroll.group.name,
        'title': enroll.title,
        'name': enroll.student.full_name,
        'logins': enroll.student.login,
        'adviser_name_formatted': enroll.adviser_name,
        'sfiles': sfiles,
    }


def _attach_indexes(rows):
    return [dict(row, index=idx) for idx, row in enumerate(rows, start=1)]


def _collect_grouped_rows(qs):
    grouped = defaultdict(lambda: defaultdict(dict))
    flat_rows = {False: [], True: []}

    for enroll in qs:
        is_latest = enroll.group.is_latest
        doc_types = Document.get_doc_types_for_group(is_latest)
        row = _build_row(enroll, doc_types)

        year_entry = grouped[enroll.year.year]
        dept_entry = year_entry.setdefault(enroll.department, {})
        group_entry = dept_entry.setdefault(enroll.group.name, {
            'rows': [],
            'doc_types': doc_types,
            'is_latest': is_latest,
        })
        group_entry['rows'].append(row)
        flat_rows[is_latest].append(row)

    return grouped, flat_rows


def _build_group_panels(grouped):
    panels = []

    for year in sorted(grouped.keys(), reverse=True):
        depts = grouped[year]
        year_total = sum(len(group_data['rows']) for dept_data in depts.values() for group_data in dept_data.values())
        for dept in sorted(depts.keys(), key=lambda d: d or ''):
            groups = depts[dept]
            dept_total = sum(len(group_data['rows']) for group_data in groups.values())
            for group_name in sorted(groups.keys()):
                group_data = groups[group_name]
                rows = _attach_indexes(group_data['rows'])
                panels.append({
                    'year': year,
                    'year_total': year_total,
                    'dept': dept,
                    'dept_total': dept_total,
                    'group': group_name,
                    'group_total': len(rows),
                    'rows': rows,
                    'files': [{'code': code, 'name': label} for code, label in group_data['doc_types']],
                    'is_latest': group_data['is_latest'],
                })
    return panels


def _build_flat_sections(flat_rows):
    sections = []
    titles = {
        False: 'Группы, продолжающие обучение',
        True: 'Группы выпускного года',
    }

    for is_latest in (False, True):
        rows = flat_rows[is_latest]
        if not rows:
            continue
        sections.append({
            'caption': titles[is_latest],
            'files': [{'code': code, 'name': label} for code, label in Document.get_doc_types_for_group(is_latest)],
            'students': _attach_indexes(rows),
            'is_latest': is_latest,
        })
    return sections


def page_webd(request):
    foundyear = request.foundyear
    year = Year.objects.values_list('year', flat=True)
    groups = Group.objects.filter(year__year=foundyear).values('name').distinct()
    departments     = [{'value': d}  for d in DEPARTMENTS]
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            if Student.objects.filter(login=user.username).exists():
                return redirect('page_identity', foundyear=foundyear)
            if hasattr(user, 'teacher_profile'):
                return redirect('teacher_topics')
            return redirect('page_webd')
        else:
            error = 'Неверный логин или пароль'
    
    return render(request, 'webd_core/page_webd.html', {
        'error': error,
        'foundyear': foundyear,
        'years':year,
        'groups':groups,
        'departments':departments,
        })


def page_login(request):
    
    return page_webd(request)


@login_required(login_url='page_webd')
def page_identity(request,foundyear):
    student = getattr(request, 'student_profile', None)
    if not student:
        messages.error(request, "Раздел доступен только студентам.")
        return redirect('teacher_topics')
    try:
        year = Year.objects.get(year=foundyear)
        enrollment = Enrollment.objects.get(student=student, year=year)
    except (Year.DoesNotExist, Enrollment.DoesNotExist):
        messages.error(request, "Не удалось найти запись обучения для выбранного года.")
        return redirect('page_webd')
    print(student,enrollment)
    # Подготовка справочников
    positions = [{'value': value, 'label': label, 'selected': value == enrollment.adviser_position} for value, label in ADVISER_POSITION_CHOICES]
    all_ranks = ['без звания','доцент','профессор']
    ranks     = [{'value': r, 'selected': r == enrollment.adviser_rank}     for r in all_ranks]
    departments     = [{'value': d, 'selected': d == enrollment.department}  for d in DEPARTMENTS]

    if request.method == 'POST':
        form = StudentForm(request.POST, instance=enrollment)
        if form.is_valid():
            form.save()
            # переход на GET, чтобы обновить student и убрать повторы POST
            return redirect('page_identity', foundyear=year.year)
    else:
        form = StudentForm(instance=enrollment)

    return render(request, 'webd_core/page_identity.html', {
        'student': student,
        'enroll':enrollment,
        'form': form,
        'positions': positions,
        'ranks': ranks,
        'departments': departments,
        'is_editable': True,
        'have_prev_year': False,
        'foundyear': foundyear,
    })


@login_required(login_url='page_webd')
def query_view(request):
    qs, filters = _apply_common_filters(request.POST)

    grouped, flat_rows = _collect_grouped_rows(qs)
    panels = _build_group_panels(grouped)
    flat_sections = _build_flat_sections(flat_rows)

    if filters['group_method'] == 'flatten':
        panels = []
    else:
        flat_sections = []

    context = {
        'panels': panels,
        'admin': request.user.is_staff,
        'caption': 'Результаты поиска',
        'foundyear': request.foundyear,
        'group_method': filters['group_method'],
        'flat_sections': flat_sections,
    }
    return render(request, 'webd_core/page_query.html', context)

def templates_view(request):
    foundyear = request.foundyear

    return render(request, 'webd_core/page_templates.html',{'foundyear':foundyear})


@login_required(login_url='page_webd')
def query_report(request):
    qs, filters = _apply_common_filters(request.POST)
    grouped, flat_rows = _collect_grouped_rows(qs)
    panels = _build_group_panels(grouped)
    flat_sections = _build_flat_sections(flat_rows)

    if filters['group_method'] == 'flatten':
        panels = []
    else:
        flat_sections = []

    context = {
        'panels': panels,
        'flat_sections': flat_sections,
        'group_method': filters['group_method'],
    }
    html = render_to_string('webd_core/report_template.html', context)

    pdf_bytes = html_to_pdf(html)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="report.pdf"'
    return response


@login_required
@require_http_methods(["GET", "POST"])
def upload_view(request,foundyear):
    student = getattr(request, 'student_profile', None)
    if not student:
        messages.error(request, "Раздел доступен только студентам.")
        return redirect('teacher_topics')
    try:
        year = Year.objects.get(year=foundyear)
        enrollment = Enrollment.objects.get(student=student, year=year)
    except (Year.DoesNotExist, Enrollment.DoesNotExist):
        messages.error(request, "Не удалось найти запись обучения для выбранного года.")
        return redirect('page_webd')
    results = {}
    doc_types = Document.get_doc_types_for_group(enrollment.group.is_latest)
    
    if request.method == "POST":
        doc_type = request.POST.get("for-doc")

        # Проверка на валидность типа документа
        valid_doc_types = dict(doc_types).keys()
        if doc_type not in valid_doc_types:
            messages.error(request, "Недопустимый тип документа.")
            return redirect(request.path)

        if "send-file" in request.POST:
            uploaded_file = request.FILES.get("doc-file")
            if not uploaded_file:
                results[doc_type] = {"success": False, "result": "Файл не выбран"}
            elif uploaded_file.size > 10 * 1024 * 1024:
                results[doc_type] = {"success": False, "result": "Размер файла превышает 10 Мб"}
            else:
                document, _ = Document.objects.get_or_create(enrollment=enrollment, doc_type=doc_type)
                document.file = uploaded_file
                document.save()
                results[doc_type] = {"success": True, "result": "Файл успешно загружен"}

        elif "delete-file" in request.POST:
            try:
                document = Document.objects.get(enrollment=enrollment, doc_type=doc_type)
                document.file.delete(save=False)
                document.delete()
                results[doc_type] = {"success": True, "result": "Файл удалён"}
            except Document.DoesNotExist:
                results[doc_type] = {"success": False, "result": "Файл не найден"}

    # Словарь файлов, ключ — тип, значение — объект Document или None
    documents = {doc.doc_type: doc for doc in enrollment.documents.all()}
    files = documents

    context = {
        "student": student,
        "enroll":enrollment,
        "doc_types": doc_types,
        "files": files,
        "results": results,
        "foundyear": foundyear,
    }

    return render(request, "webd_core/page_upload.html", context)



@login_required(login_url='page_webd')
def teacher_topics_view(request):
    teacher = getattr(request, 'teacher_profile', None)
    if not teacher:
        messages.error(request, "Страница доступна только преподавателям.")
        return redirect('page_webd')

    topics_qs = teacher.topics.prefetch_related(
        Prefetch(
            'requests',
            queryset=TopicRequest.objects.select_related(
                'enrollment__student',
                'enrollment__group'
            ).order_by('-created_at')
        )
    ).order_by('created_at')

    # Группировка тем: свободные и по курсам
    free_topics = []
    course_topics = {}  # {course: [topic_rows]}
    
    for topic in topics_qs:
        requests = list(topic.requests.all())
        approved = [r for r in requests if r.status == TopicRequest.STATUS_APPROVED]
        pending = [r for r in requests if r.status == TopicRequest.STATUS_PENDING]
        free_slots = max(topic.capacity - len(approved), 0)
        
        topic_row = {
            'topic': topic,
            'approved': approved,
            'pending': pending,
            'free_slots': free_slots,
        }
        
        # Если есть свободные места, добавляем в свободные темы
        if free_slots > 0:
            free_topics.append(topic_row)
        else:
            # Иначе группируем по курсу студентов
            if approved:
                # Берем курс первого одобренного студента
                first_student_course = _parse_course(approved[0].enrollment.courses)
                if first_student_course:
                    course_topics.setdefault(first_student_course, []).append(topic_row)
                else:
                    # Если курс не определен, добавляем в свободные
                    free_topics.append(topic_row)
            else:
                # Если нет одобренных, но нет свободных мест (не должно быть, но на всякий случай)
                free_topics.append(topic_row)
    
    # Добавляем индексы для каждой группы
    idx_counter = 1
    for topic_row in free_topics:
        topic_row['index'] = idx_counter
        idx_counter += 1
    
    for course in sorted(course_topics.keys(), reverse=True):
        for topic_row in course_topics[course]:
            topic_row['index'] = idx_counter
            idx_counter += 1

    course_choices = COURSE_CHOICES

    def _teacher_department():
        if teacher.department:
            return teacher.department
        return DEPARTMENTS[0]

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create_batch':
            titles = request.POST.getlist('title[]')
            descriptions = request.POST.getlist('description[]')
            directions = request.POST.getlist('direction[]')
            courses = request.POST.getlist('course[]')
            capacities = request.POST.getlist('capacity[]')

            created = 0
            errors = []
            for idx, title in enumerate(titles):
                title = (title or '').strip()
                if not title:
                    continue
                description = (descriptions[idx] if idx < len(descriptions) else '').strip()
                direction = (directions[idx] if idx < len(directions) else '').strip()
                course_val = _parse_course(courses[idx] if idx < len(courses) else None)
                capacity_val = _parse_course(capacities[idx] if idx < len(capacities) else None)
                if course_val not in [choice[0] for choice in COURSE_CHOICES]:
                    errors.append(f"Строка {idx+1}: некорректный курс.")
                    continue
                if not capacity_val or capacity_val < 1:
                    errors.append(f"Строка {idx+1}: количество студентов должно быть положительным.")
                    continue

                Topic.objects.create(
                    teacher=teacher,
                    title=title,
                    description=description,
                    direction=direction,
                    department=_teacher_department(),
                    course=course_val,
                    capacity=capacity_val,
                    is_active=True,
                )
                created += 1
            if errors:
                for err in errors:
                    messages.error(request, err)
            if created:
                messages.success(request, f"Добавлено тем: {created}")
            if created or errors:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    from django.http import JsonResponse
                    return JsonResponse({'success': created > 0, 'created': created, 'errors': errors})
                return redirect('teacher_topics')
        elif action == 'update_topic':
            result, error_messages = _handle_topic_update(request, teacher)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                from django.http import JsonResponse
                if result:
                    return JsonResponse({'success': True})
                else:
                    return JsonResponse({'success': False, 'errors': error_messages or ['Ошибка обновления']}, status=400)
            if result:
                return redirect('teacher_topics')
        elif action == 'delete_topic':
            topic_id = request.POST.get('topic_id')
            _handle_topic_delete(request, teacher, topic_id)
            return redirect('teacher_topics')
        elif action == 'decision':
            request_id = request.POST.get('request_id')
            decision = request.POST.get('decision')
            comment = request.POST.get('comment', '').strip()
            if _handle_topic_decision(teacher, request_id, decision, comment, request):
                return redirect('teacher_topics')

    # Сортируем курсы по убыванию для отображения
    sorted_courses = sorted(course_topics.keys(), reverse=True) if course_topics else []
    
    context = {
        'free_topics': free_topics,
        'course_topics': course_topics,
        'sorted_courses': sorted_courses,
        'course_choices': course_choices,
        'page_teacher_topics': True,
        'foundyear': request.foundyear,
    }
    return render(request, 'webd_core/page_teacher_topics.html', context)


@login_required(login_url='page_webd')
def student_topics_view(request):
    student = getattr(request, 'student_profile', None)
    if not student:
        messages.error(request, "Страница доступна только студентам.")
        return redirect('teacher_topics')
    try:
        year = Year.objects.get(year=request.foundyear)
        enrollment = Enrollment.objects.get(student=student, year=year)
    except (Year.DoesNotExist, Enrollment.DoesNotExist):
        messages.error(request, "Не найдена запись обучения для выбранного года.")
        return redirect('page_webd')

    dept_param = request.GET.get('department')
    if dept_param is None:
        selected_department = enrollment.department or ''
    else:
        selected_department = dept_param
    student_course = _parse_course(enrollment.courses)

    if request.method == 'POST':
        selected_department = request.POST.get('department', selected_department)
        topic_id = request.POST.get('topic_id')
        if topic_id:
            _create_topic_request(enrollment, topic_id, request)
        redirect_url = reverse('student_topics')
        if selected_department:
            redirect_url = f"{redirect_url}?department={selected_department}"
        return redirect(redirect_url)

    topics_qs = Topic.objects.filter(is_active=True)
    if student_course:
        topics_qs = topics_qs.filter(course=student_course)
    if selected_department:
        topics_qs = topics_qs.filter(department=selected_department)
    topics_qs = topics_qs.select_related('teacher').prefetch_related(
        Prefetch(
            'requests',
            queryset=TopicRequest.objects.select_related(
                'enrollment__student', 'enrollment__group'
            )
        )
    ).order_by('created_at')

    requests_qs = TopicRequest.objects.filter(enrollment=enrollment).select_related('topic', 'topic__teacher')
    request_map = {req.topic_id: req for req in requests_qs}
    approved_request = next((req for req in requests_qs if req.status == TopicRequest.STATUS_APPROVED), None)
    student_has_pending = any(req.status == TopicRequest.STATUS_PENDING for req in requests_qs)

    departments = [{'value': d, 'selected': d == selected_department} for d in DEPARTMENTS]

    topic_entries = []
    for idx, topic in enumerate(topics_qs, start=1):
        topic_requests = list(topic.requests.all())
        approved = [r for r in topic_requests if r.status == TopicRequest.STATUS_APPROVED]
        pending = [r for r in topic_requests if r.status == TopicRequest.STATUS_PENDING]
        free_slots = max(topic.capacity - len(approved), 0)
        topic_entries.append({
            'topic': topic,
            'index': idx,
            'approved': approved,
            'pending': pending,
            'free_slots': free_slots,
            'student_request': request_map.get(topic.id),
        })

    # Всегда группируем по кафедрам и направлениям
    topic_groups = []
    dept_map = {}
    for entry in topic_entries:
        dept = entry['topic'].department or 'Не указано'
        direction = entry['topic'].direction or 'Не указано'
        dept_map.setdefault(dept, {}).setdefault(direction, []).append(entry)
    
    # Сортируем кафедры
    sorted_depts = sorted(dept_map.keys(), key=lambda d: DEPARTMENTS.index(d) if d in DEPARTMENTS else d)
    for dept in sorted_depts:
        dept_data = dept_map[dept]
        # Сортируем направления
        for direction in sorted(dept_data.keys()):
            topic_groups.append({
                'department': dept,
                'direction': direction,
                'entries': dept_data[direction]
            })
    
    grouped_view = True  # Всегда используем группировку

    context = {
        'topic_groups': topic_groups,
        'grouped_view': grouped_view,
        'departments': departments,
        'selected_department': selected_department,
        'request_map': request_map,
        'approved_request': approved_request,
        'student_has_pending': student_has_pending,
        'page_topic_select': True,
        'foundyear': request.foundyear,
        'student_course': student_course,
    }
    return render(request, 'webd_core/page_topic_select.html', context)


def _handle_topic_decision(teacher, request_id, decision, comment, request):
    topic_request = TopicRequest.objects.filter(id=request_id, topic__teacher=teacher).select_related('topic', 'enrollment__student').first()
    if not topic_request:
        messages.error(request, "Заявка не найдена.")
        return True

    if decision == 'approve':
        if _approve_topic_request(topic_request, comment, request):
            messages.success(request, f"Заявка студента {topic_request.enrollment.student.full_name} принята.")
        return True
    if decision == 'reject':
        _reject_topic_request(topic_request, comment)
        messages.info(request, f"Заявка студента {topic_request.enrollment.student.full_name} отклонена.")
        return True

    messages.error(request, "Неизвестное действие.")
    return False


def _handle_topic_update(request, teacher):
    topic_id = request.POST.get('topic_id')
    if not topic_id:
        error_msg = "Не указана тема для обновления."
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            messages.error(request, error_msg)
        return False, [error_msg]
    
    topic = Topic.objects.filter(id=topic_id, teacher=teacher).first()
    if not topic:
        error_msg = "Тема не найдена."
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            messages.error(request, error_msg)
        return False, [error_msg]

    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    direction = request.POST.get('direction', '').strip()
    course = request.POST.get('course')
    capacity = request.POST.get('capacity')

    errors = []
    if not title:
        errors.append("Название темы обязательно.")
    try:
        course_int = int(course)
        if course_int not in [choice[0] for choice in COURSE_CHOICES]:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("Некорректное значение курса.")

    try:
        capacity_int = int(capacity)
        if capacity_int < 1:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("Количество студентов должно быть положительным числом.")

    if errors:
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            for err in errors:
                messages.error(request, err)
        return False, errors

    topic.title = title
    topic.description = description
    topic.direction = direction
    topic.course = course_int
    topic.capacity = capacity_int
    topic.save(update_fields=['title', 'description', 'direction', 'course', 'capacity', 'updated_at'])
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        messages.success(request, "Данные темы обновлены.")
    return True, []


def _approve_topic_request(topic_request, comment, request):
    now = timezone.now()
    topic = topic_request.topic
    current_approved = topic.requests.filter(status=TopicRequest.STATUS_APPROVED).exclude(id=topic_request.id).count()
    if current_approved >= topic.capacity:
        messages.error(request, "Достигнут лимит студентов для этой темы.")
        return False
    with transaction.atomic():
        topic_request.status = TopicRequest.STATUS_APPROVED
        topic_request.comment = comment
        topic_request.decided_at = now
        topic_request.save(update_fields=['status', 'comment', 'decided_at'])

        enrollment = topic_request.enrollment
        topic = topic_request.topic
        enrollment.title = topic.title
        enrollment.adviser_name = topic.teacher.full_name
        enrollment.department = topic.department
        enrollment.adviser_position = topic.teacher.adviser_position
        enrollment.save(update_fields=['title', 'adviser_name', 'department', 'adviser_position'])

        TopicRequest.objects.filter(enrollment=enrollment).exclude(id=topic_request.id).update(
            status=TopicRequest.STATUS_REJECTED,
            comment='Заявка отклонена: выбрана другая тема',
            decided_at=now,
        )

        if current_approved + 1 >= topic.capacity:
            TopicRequest.objects.filter(topic=topic, status=TopicRequest.STATUS_PENDING).exclude(id=topic_request.id).update(
                status=TopicRequest.STATUS_REJECTED,
                comment='Лимит по теме достигнут',
                decided_at=now,
            )
    return True


def _handle_topic_delete(request, teacher, topic_id):
    topic = Topic.objects.filter(id=topic_id, teacher=teacher).first()
    if not topic:
        messages.error(request, "Тема не найдена.")
        return False

    with transaction.atomic():
        TopicRequest.objects.filter(topic=topic).update(
            status=TopicRequest.STATUS_REJECTED,
            comment='Тема удалена преподавателем',
            decided_at=timezone.now()
        )
        TopicRequest.objects.filter(topic=topic).delete()
        Enrollment.objects.filter(
            title=topic.title,
            adviser_name=topic.teacher.full_name,
            department=topic.department
        ).update(title='', adviser_name='', department='', adviser_position='')
        topic.delete()
        messages.success(request, "Тема удалена.")
    return True
def _reject_topic_request(topic_request, comment):
    topic_request.status = TopicRequest.STATUS_REJECTED
    topic_request.comment = comment
    topic_request.decided_at = timezone.now()
    topic_request.save(update_fields=['status', 'comment', 'decided_at'])


def _create_topic_request(enrollment, topic_id, request):
    topic = Topic.objects.filter(id=topic_id).select_related('teacher').first()
    if not topic:
        messages.error(request, "Тема не найдена.")
        return
    if not topic.is_active:
        messages.error(request, "Тема уже недоступна.")
        return
    if TopicRequest.objects.filter(
        enrollment=enrollment,
        status=TopicRequest.STATUS_PENDING
    ).exclude(topic=topic).exists():
        messages.info(request, "У вас уже есть заявка, ожидающая решения. Дождитесь ответа преподавателя.")
        return
    approved_count = topic.requests.filter(status=TopicRequest.STATUS_APPROVED).count()
    if approved_count >= topic.capacity:
        messages.info(request, "Лимит студентов для этой темы исчерпан.")
        return
    if TopicRequest.objects.filter(enrollment=enrollment, status=TopicRequest.STATUS_APPROVED).exists():
        messages.info(request, "У вас уже есть утверждённая тема.")
        return

    topic_request, created = TopicRequest.objects.get_or_create(topic=topic, enrollment=enrollment)
    if created:
        messages.success(request, "Заявка отправлена преподавателю.")
        return

    if topic_request.status == TopicRequest.STATUS_PENDING:
        messages.info(request, "Заявка уже находится на рассмотрении.")
        return
    if topic_request.status == TopicRequest.STATUS_REJECTED:
        topic_request.status = TopicRequest.STATUS_PENDING
        topic_request.comment = ''
        topic_request.decided_at = None
        topic_request.save(update_fields=['status', 'comment', 'decided_at'])
        messages.success(request, "Заявка повторно отправлена.")
        return

    messages.info(request, "По этой теме уже принято решение.")


def logout_view(request):
    logout(request)
    return redirect('page_webd')