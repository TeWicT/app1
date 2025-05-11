from django.contrib import admin
from .models import Year, Group, Student, Enrollment, Document

class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 1
    verbose_name = "Текущий год обучения / группа"
    verbose_name_plural = "Годы обучения и группы студента"
    # Покажем только поля year и group
    fields = ('year', 'group','adviser_status','adviser_position','title','adviser_name','adviser_rank','department')
    # Сделаем именно селект (для год–группа используем всплывающее окно для создания новой группы)
    raw_id_fields = ('group',)
    # +иконка для «добавить новую группу» откроет попап, где можно её создать

@admin.register(Year)
class YearAdmin(admin.ModelAdmin):
    list_display = ("id", "year")
    search_fields = ("year",)
    ordering = ("-year",)

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "year")
    list_filter  = ("year",)
    search_fields= ("name",)

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("id", "login", "full_name")
    search_fields= ("login", "full_name")
    inlines = [EnrollmentInline]




@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display   = ("id", "enrollment", "doc_type", "uploaded_at")
    list_filter    = ("doc_type",)
    search_fields  = ("enrollment__student__login",)
