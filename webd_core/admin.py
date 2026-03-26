from django.contrib import admin
from .models import Year, Group, Student, Enrollment, Document, TeacherProfile, Topic, TopicRequest

class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 1
    verbose_name = "Текущий год обучения / группа"
    verbose_name_plural = "Годы обучения и группы студента"
    # Покажем только поля year и group
    fields = ('year', 'group','courses','adviser_status','adviser_position','title','adviser_name','adviser_rank','department')
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
    list_display = ("id", "name", "year", "is_latest", "is_master_latest")
    list_filter  = ("year", "is_latest", "is_master_latest")
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

@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "department", "adviser_position", "user", "created_at")
    list_filter = ("department", "adviser_position")
    search_fields = ("full_name", "user__username")
    raw_id_fields = ("user",)
    ordering = ("full_name",)

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "teacher", "department", "direction", "course", "capacity", "is_active", "created_at")
    list_filter = ("department", "course", "is_active", "created_at")
    search_fields = ("title", "teacher__full_name", "description")
    raw_id_fields = ("teacher",)
    ordering = ("-created_at",)

@admin.register(TopicRequest)
class TopicRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "topic", "enrollment", "status", "created_at", "decided_at")
    list_filter = ("status", "created_at", "decided_at")
    search_fields = ("topic__title", "enrollment__student__full_name", "enrollment__student__login")
    raw_id_fields = ("topic", "enrollment",)
    ordering = ("-created_at",)
