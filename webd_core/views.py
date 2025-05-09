from django.shortcuts import render, redirect, get_object_or_404    
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from .models import Student, Document
from .parsing import query  # your import logic
from .doc import generate_pdf  # your PDF logic
from .forms import UploadForm, StudentForm  # create a form for uploads
from django.views.decorators.http import require_http_methods
from django.contrib import messages

def page_webd(request):
    if request.user.is_authenticated:
        return redirect('page_identity')
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('page_identity')
        else:
            error = 'Неверный логин или пароль'
    return render(request, 'webd_core/page_webd.html', {'error': error})


def page_login(request):
    # optional separate login page
    return page_webd(request)


@login_required(login_url='page_webd')
def page_identity(request):
    student = Student.objects.get(login=request.user.username)

    # Подготовка справочников
    all_positions = ['преподаватель','ст. преподаватель','доцент','профессор','зав. кафедрой','другая']
    positions = [{'value': p, 'selected': p == student.adviser_position} for p in all_positions]
    all_ranks = ['без звания','доцент','профессор']
    ranks     = [{'value': r, 'selected': r == student.adviser_rank}     for r in all_ranks]
    all_departments = ['ПМиК','ИМО','ГиТ','МА','ТВиАД','ТМОМИ']
    departments     = [{'value': d, 'selected': d == student.department}  for d in all_departments]

    if request.method == 'POST':
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            # переход на GET, чтобы обновить student и убрать повторы POST
            return redirect('page_identity')
    else:
        form = StudentForm(instance=student)

    return render(request, 'webd_core/page_identity.html', {
        'student': student,
        'form': form,
        'positions': positions,
        'ranks': ranks,
        'departments': departments,
        'is_editable': True,
        'have_prev_year': False,
    })


@login_required(login_url='page_webd')
def query_view(request):
    params = request.GET if request.method == 'GET' else {}
    students = query(None, params)
    return render(request, 'webd_core/page_query.html', {'students': students})


def templates_view(request):
    cfg = None  # load config if needed
    # your logic to list or edit templates
    return render(request, 'webd_core/page_templates.html')



@login_required
@require_http_methods(["GET", "POST"])
def upload_view(request):
    student = Student.objects.get(login=request.user.username)
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
                document, _ = Document.objects.get_or_create(student=student, doc_type=doc_type)
                document.file = uploaded_file
                document.save()
                results[doc_type] = {"success": True, "result": "Файл успешно загружен"}

        elif "delete-file" in request.POST:
            try:
                document = Document.objects.get(student=student, doc_type=doc_type)
                document.file.delete(save=False)
                document.delete()
                results[doc_type] = {"success": True, "result": "Файл удалён"}
            except Document.DoesNotExist:
                results[doc_type] = {"success": False, "result": "Файл не найден"}

    # Словарь файлов, ключ — тип, значение — объект Document или None
    documents = {doc.doc_type: doc for doc in student.documents.all()}
    files = documents

    context = {
        "student": student,
        "doc_types": Document.DOC_TYPES,
        "files": files,
        "results": results,
    }

    return render(request, "webd_core/page_upload.html", context)



def logout_view(request):
    logout(request)
    return redirect('page_webd')