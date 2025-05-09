# webd_core/admin.py
from django.contrib import admin
from .models import Student, Document

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('login', 'name', 'year', 'course', 'group')
    search_fields = ('login', 'name', 'adviser_name', 'department')
    list_filter = ('year', 'department')

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('student', 'doc_type', 'uploaded_at')
    list_filter = ('doc_type',)
    search_fields = ('student__login',)
    raw_id_fields = ('student',)