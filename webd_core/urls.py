from django.urls import path
from . import views

urlpatterns = [
    path('', views.page_webd, name='page_webd'),
    path('login/', views.page_login, name='page_login'),
    path('identity/', views.page_identity, name='page_identity'),
    path('query/', views.query_view, name='query'),
    path('templates/', views.templates_view, name='templates'),
    path('upload/', views.upload_view, name='upload'),
    path('login/exit/', views.logout_view, name='logout'),
]