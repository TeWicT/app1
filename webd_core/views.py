from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from .models import Student, Document
from .parsing import query  # your import logic
from .doc import generate_pdf  # your PDF logic
from .forms import UploadForm, StudentForm  # create a form for uploads


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


@login_required(login_url='page_webd')
def upload_view(request):
    form = UploadForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        doc = form.save(commit=False)
        doc.student = Student.objects.get(login=request.user.username)
        doc.save()
        return redirect('upload')
    return render(request, 'webd_core/page_upload.html', {'form': form, 'documents': Document.objects.filter(student__login=request.user.username)})


def logout_view(request):
    logout(request)
    return redirect('page_webd')