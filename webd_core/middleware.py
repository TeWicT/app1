# webd_core/middleware.py
from django.db import connection
from .models import Student, TeacherProfile, AdminProfile, TopicRequest, Year


class FoundYearMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        default_year = self._get_default_year()
        if 'foundyear' not in request.session:
            request.session['foundyear'] = default_year

        request.foundyear = request.session.get('foundyear', default_year)
        request.student_profile = None
        request.teacher_profile = None
        request.admin_profile = None

        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            request.student_profile = Student.objects.filter(login=user.username).first()
            teacher_profile = getattr(user, 'teacher_profile', None)
            request.teacher_profile = teacher_profile
            request.admin_profile = AdminProfile.objects.filter(user=user).first()
            request.pending_request_count = 0
            request.topic_notifications = {'pending': 0, 'decided': 0}

            if teacher_profile:
                request.pending_request_count = TopicRequest.objects.filter(
                    topic__teacher=teacher_profile,
                    status=TopicRequest.STATUS_PENDING
                ).count()

            if request.student_profile:
                request.topic_notifications = {
                    'pending': TopicRequest.objects.filter(
                        enrollment__student=request.student_profile,
                        status=TopicRequest.STATUS_PENDING
                    ).count(),
                    'decided': TopicRequest.objects.filter(
                        enrollment__student=request.student_profile,
                        status__in=[TopicRequest.STATUS_APPROVED, TopicRequest.STATUS_REJECTED],
                        decided_at__isnull=False
                    ).count(),
                }

        response = self.get_response(request)
        return response

    @staticmethod
    def _get_default_year():
        """
        Возвращает текущий учебный год по данным из БД.

        На «чистой» базе таблица Year может ещё не существовать (до применения миграций),
        поэтому сначала проверяем наличие таблицы. Если её нет — возвращаем дефолтное
        значение (2024), чтобы не падать с OperationalError.
        """
        tables = connection.introspection.table_names()
        if "webd_core_year" not in tables:
            return 2026

        latest_year = Year.objects.order_by('-year').values_list('year', flat=True).first()
        return latest_year if latest_year else 2026
