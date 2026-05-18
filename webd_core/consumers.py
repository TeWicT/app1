import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from .models import DiscussionThread, DiscussionMessage, TopicRequest, Year, Enrollment, Student, TeacherProfile


class DiscussionConsumer(AsyncWebsocketConsumer):
    MAX_MESSAGE_LEN = 4096

    async def connect(self):
        self.thread_id = self.scope['url_route']['kwargs'].get('thread_id')
        self.group_name = f"discussion_{self.thread_id}"

        allowed = await self._is_allowed()
        if not allowed:
            await self.close(code=4403)  # policy violation / forbidden
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            payload = json.loads(text_data)
        except json.JSONDecodeError:
            return

        msg_type = payload.get("type")
        if msg_type != "message":
            return
        text = (payload.get("text") or "").strip()
        if not text:
            return
        if len(text) > self.MAX_MESSAGE_LEN:
            return

        message = await self._create_message(text)
        if not message:
            return

        event = {
            "type": "chat.message",
            "author_name": message.author_name,
            "text": message.text,
            "created_at": message.created_at.strftime("%d.%m.%Y %H:%M"),
        }
        await self.channel_layer.group_send(self.group_name, event)

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "event": "message",
            "author_name": event["author_name"],
            "text": event["text"],
            "created_at": event["created_at"],
        }))

    @database_sync_to_async
    def _is_allowed(self) -> bool:
        try:
            thread = DiscussionThread.objects.select_related('topic', 'topic__teacher').get(id=self.thread_id)
        except DiscussionThread.DoesNotExist:
            return False
        user = self.scope.get('user') or AnonymousUser()
        if not user or not user.is_authenticated:
            return False
        # Teacher access
        teacher_profile = getattr(user, 'teacher_profile', None)
        if teacher_profile and teacher_profile.id == thread.topic.teacher_id:
            return True
        # Student access: enrollment of latest year approved for this topic
        student = Student.objects.filter(login=user.username).first()
        if not student:
            return False
        current_year = Year.objects.order_by("-year").first()
        if not current_year:
            return False
        try:
            enrollment = Enrollment.objects.get(student=student, year=current_year)
        except Enrollment.DoesNotExist:
            return False
        return TopicRequest.objects.filter(
            topic=thread.topic,
            enrollment=enrollment,
            status=TopicRequest.STATUS_APPROVED
        ).exists()

    @database_sync_to_async
    def _create_message(self, text: str):
        try:
            thread = DiscussionThread.objects.select_related('topic', 'topic__teacher').get(id=self.thread_id)
        except DiscussionThread.DoesNotExist:
            return None
        user = self.scope.get('user') or AnonymousUser()
        author_name = ""
        if hasattr(user, 'teacher_profile'):
            author_name = user.teacher_profile.full_name
        else:
            # resolve student full name by login
            student = Student.objects.filter(login=user.username).first()
            author_name = student.full_name if student else (user.get_username() if user.is_authenticated else "Гость")
        msg = DiscussionMessage.objects.create(
            thread=thread,
            author=user if user.is_authenticated else None,
            author_name=author_name,
            text=text,
        )
        return msg
