from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from .models import Student, Document
from .parsing import query  # your import logic
from .doc import generate_pdf  # your PDF logic
from .forms import UploadForm  # create a form for uploads


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
    try:
        student = Student.objects.get(login=request.user.username)
    except Student.DoesNotExist:
        student = None
    return render(request, 'webd_core/page_identity.html', {'user': request.user, 'student': student})


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