# webd_core/admin.py
from django.contrib import admin
from .models import Student, Document

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('login', 'full_name', 'study_year', 'courses', 'groups')
    search_fields = ('login', 'full_name', 'adviser_name', 'department')
    list_filter = ('study_year', 'department')

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('student', 'doc_type', 'uploaded_at')
    list_filter = ('doc_type',)
    search_fields = ('student__login',)
    raw_id_fields = ('student',)