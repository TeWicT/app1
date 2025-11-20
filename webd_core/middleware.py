# webd_core/middleware.py
from .models import Student, TeacherProfile, TopicRequest


class FoundYearMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if 'foundyear' not in request.session:
            request.session['foundyear'] = 2024

        request.foundyear = request.session['foundyear']
        request.student_profile = None
        request.teacher_profile = None

        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            request.student_profile = Student.objects.filter(login=user.username).first()
            teacher_profile = getattr(user, 'teacher_profile', None)
            request.teacher_profile = teacher_profile
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
