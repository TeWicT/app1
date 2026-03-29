from django.urls import path
from . import views

urlpatterns = [
    path('', views.page_webd, name='page_webd'),
    path('login/', views.page_login, name='page_login'),
    path('identity/<int:foundyear>/', views.page_identity, name='page_identity'),
    path('query', views.query_view, name='query'),
    path('templates/', views.templates_view, name='page_templates'),
    path('file/<int:foundyear>/', views.upload_view, name='page_upload'),
    path('login/exit/', views.logout_view, name='logout'),
    path('query/report/', views.query_report, name='query_report'),
    path('topics/manage/', views.teacher_topics_view, name='teacher_topics'),
    path('topics/select/', views.student_topics_view, name='student_topics'),
    path('discussion/', views.student_discussion, name='student_discussion'),
    path('discussions/', views.teacher_discussions, name='teacher_discussions'),
    path('discussion/<int:thread_id>/', views.discussion_view, name='discussion_view'),


]