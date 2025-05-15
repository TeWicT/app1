from django.shortcuts import render, redirect, get_object_or_404    
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from .models import Student, Document,Enrollment, Year,Group
from .doc import generate_pdf  # your PDF logic
from .forms import  StudentForm  # create a form for uploads
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from collections import defaultdict
def page_webd(request):
    foundyear = request.foundyear
    year = Year.objects.all()
    groups = Group.objects.values('name')
    all_departments = ['ПМиК','ИМО','ГиТ','МА','ТВиАД','ТМОМИ']
    departments     = [{'value': d}  for d in all_departments]
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('page_identity',foundyear=foundyear)
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
    student = Student.objects.get(login=request.user.username)
    year = Year.objects.get(year=foundyear)
    enrollment = Enrollment.objects.get(student=student,year=year)
    print(student,enrollment)
    # Подготовка справочников
    all_positions = ['преподаватель','ст. преподаватель','доцент','профессор','зав. кафедрой','другая']
    positions = [{'value': p, 'selected': p == enrollment.adviser_position} for p in all_positions]
    all_ranks = ['без звания','доцент','профессор']
    ranks     = [{'value': r, 'selected': r == enrollment.adviser_rank}     for r in all_ranks]
    all_departments = ['ПМиК','ИМО','ГиТ','МА','ТВиАД','ТМОМИ']
    departments     = [{'value': d, 'selected': d == enrollment.department}  for d in all_departments]

    if request.method == 'POST':
        form = StudentForm(request.POST, instance=enrollment)
        if form.is_valid():
            form.save()
            # переход на GET, чтобы обновить student и убрать повторы POST
            return redirect('page_identity',foundyear=year)
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
    # 1. Сбор и фильтрация записей
    years      = request.POST.getlist('years')
    groups     = request.POST.getlist('groups')
    department = request.POST.get('department', '').strip()
    name       = request.POST.get('name', '').strip()
    adviser    = request.POST.get('adviser-name', '').strip()

    qs = Enrollment.objects.select_related('student','group','year').all()
    if years and any(years):
        qs = qs.filter(year__year__in=[int(y) for y in years if y.isdigit()])
    if groups and any(groups):
        qs = qs.filter(group__name__in=groups)
    if department:
        qs = qs.filter(department__iexact=department)
    if name:
        qs = qs.filter(student__full_name__icontains=name)
    if adviser:
        qs = qs.filter(adviser_name__icontains=adviser)

    # 2. Типы документов и заголовок колонок
    doc_types = Document.DOC_TYPES
    files = [{'code': code, 'name': label} for code, label in doc_types]

    # 3. Формирование «плоского» списка строк
    flat = []
    for idx, enroll in enumerate(qs.order_by('-year__year','group__name','student__full_name'), start=1):
        docs = {d.doc_type: d for d in enroll.documents.all()}
        sfiles = []
        for code, _ in doc_types:
            doc = docs.get(code)
            sfiles.append({
                'file':    bool(doc),
                'in_time': True,
                'link':    doc.file.url if doc else '',
            })
        flat.append({
            'year':                   enroll.year.year,
            'department':             enroll.department,
            'group':                  enroll.group.name,
            'index':                  idx,
            'title':                  enroll.title,
            'name':                   enroll.student.full_name,
            'logins':                 enroll.student.login,
            'adviser_name_formatted': enroll.adviser_name,
            'sfiles':                 sfiles,
        })

    # 4. Группировка по годам → кафедрам → группам
    grouped = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for row in flat:
        grouped[row['year']][row['department']][row['group']].append(row)

    # 5. Подсчёт количества работ на каждом уровне
    counts = {}
    for year, depts in grouped.items():
        counts[year] = {
            'total': sum(len(rows) for grp in depts.values() for rows in grp.values()),
            'departments': {
                dept: {
                    'total': sum(len(rows) for rows in groups.values()),
                    'groups': {grp: len(rows) for grp, rows in groups.items()}
                }
                for dept, groups in depts.items()
            }
        }
    panels = []
    for year, info in counts.items():
        for dept, dinfo in info['departments'].items():
            for grp, cnt in dinfo['groups'].items():
                panels.append({
                    'year': year,
                    'year_total': info['total'],
                    'dept': dept,
                    'dept_total': dinfo['total'],
                    'group': grp,
                    'group_total': cnt,
                    'rows': grouped[year][dept][grp],
                })

    return render(request, 'webd_core/page_query.html', {
        'grouped_data': grouped,
        'panels':       panels,
        'files':        files,
        'admin':        request.user.is_staff,
        'caption':      'Результаты поиска',
        'foundyear': request.foundyear
    })

def templates_view(request):
    foundyear = request.foundyear

    return render(request, 'webd_core/page_templates.html',{'foundyear':foundyear})



@login_required
@require_http_methods(["GET", "POST"])
def upload_view(request,foundyear):
    student = Student.objects.get(login=request.user.username)
    year = Year.objects.get(year=foundyear)
    enrollment = Enrollment.objects.get(student=student,year=year)
    results = {}
    
    if request.method == "POST":
        doc_type = request.POST.get("for-doc")

        # Проверка на валидность типа документа
        valid_doc_types = dict(Document.DOC_TYPES).keys()
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
        "doc_types": Document.DOC_TYPES,
        "files": files,
        "results": results,
        "foundyear": foundyear,
    }

    return render(request, "webd_core/page_upload.html", context)



def logout_view(request):
    logout(request)
    return redirect('page_webd')