from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Year, Group, Student, Enrollment, Document
from io import BytesIO

User = get_user_model()

class QueryViewTests(TestCase):
    def setUp(self):
        # create user and login
        self.user = User.objects.create_user(username='testuser', password='pass')
        self.client = Client()
        self.client.login(username='testuser', password='pass')
        # create years
        self.year2024 = Year.objects.create(year=2024)
        self.year2025 = Year.objects.create(year=2025)
        # create groups
        self.groupA = Group.objects.create(name='A', year=self.year2024)
        self.groupB = Group.objects.create(name='B', year=self.year2025)
        # create student
        self.student1 = Student.objects.create(login='stu1', full_name='Ivanov Ivan')
        # enrollments
        self.enr1 = Enrollment.objects.create(
            student=self.student1, year=self.year2024, group=self.groupA,
            courses='1', adviser_name='Petrov P', adviser_position='преподаватель', adviser_rank='доцент', department='ИМО', title='Title1'
        )
        self.enr2 = Enrollment.objects.create(
            student=self.student1, year=self.year2025, group=self.groupB,
            courses='2', adviser_name='Sidorov S', adviser_position='доцент', adviser_rank='профессор', department='МА', title='Title2'
        )

    def test_query_no_filters(self):
        response = self.client.post(reverse('query'))
        self.assertEqual(response.status_code, 200)
        # both titles should appear
        self.assertContains(response, 'Title1')
        self.assertContains(response, 'Title2')

    def test_query_filter_by_year(self):
        response = self.client.post(reverse('query'), {'years': ['2024']})
        self.assertContains(response, 'Title1')
        self.assertNotContains(response, 'Title2')

    def test_query_filter_by_group(self):
        response = self.client.post(reverse('query'), {'groups': ['B']})
        self.assertContains(response, 'Title2')
        self.assertNotContains(response, 'Title1')

    def test_query_filter_by_department(self):
        response = self.client.post(reverse('query'), {'department': 'ИМО'})
        self.assertContains(response, 'Title1')
        self.assertNotContains(response, 'Title2')

    def test_query_filter_by_name(self):
        response = self.client.post(reverse('query'), {'name': 'Ivanov'})
        self.assertContains(response, 'Title1')
        self.assertContains(response, 'Title2')
        response2 = self.client.post(reverse('query'), {'name': 'Petro'})
        self.assertNotContains(response2, 'Title1')

    def test_query_filter_by_adviser(self):
        response = self.client.post(reverse('query'), {'adviser-name': 'Petrov'})
        self.assertContains(response, 'Title1')
        self.assertNotContains(response, 'Title2')

class UploadViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        # create test user + login
        self.user = User.objects.create_user(username="alice", password="pw")
        self.client.login(username="alice", password="pw")

        # create a year, group, student and enrollment
        self.year = Year.objects.create(year=2025)
        self.group = Group.objects.create(name="G1", year=self.year)
        self.student = Student.objects.create(login="alice", full_name="Alice Example")
        self.enrollment = Enrollment.objects.create(
            student=self.student,
            year=self.year,
            group=self.group,
            courses="1",
        )

    def test_get_upload_page(self):
        url = reverse('page_upload', kwargs={'foundyear': self.year.year})
        response = self.client.get(url)
        # now we render, so expect 200 OK
        self.assertEqual(response.status_code, 200)
        # context must include our enrollment and empty results
        self.assertEqual(response.context['foundyear'], self.year.year)
        self.assertIn('files', response.context)
        self.assertFalse(response.context['results'])  # no POST yet

    def test_post_upload_file(self):
        url = reverse('page_upload', kwargs={'foundyear': self.year.year})
        fake_file = BytesIO(b"PDFDATA")
        fake_file.name = "doc.pdf"
        response = self.client.post(url, {
            'for-doc': Document.INTERIM_REPORT,
            'send-file': 'Send',
            'doc-file': fake_file,
        }, format='multipart')
        # still a 200 render
        self.assertEqual(response.status_code, 200)
        # our results dict should indicate success
        results = response.context['results']
        self.assertTrue(results[Document.INTERIM_REPORT]['success'])
        self.assertEqual(results[Document.INTERIM_REPORT]['result'], "Файл успешно загружен")
        # and the document should exist in the DB
        self.assertTrue(Document.objects.filter(
            enrollment=self.enrollment,
            doc_type=Document.INTERIM_REPORT
        ).exists())

    def test_post_delete_file(self):
        # first create a Document
        doc = Document.objects.create(
            enrollment=self.enrollment,
            doc_type=Document.FINAL_REPORT,
            file="dummy.pdf"
        )
        url = reverse('page_upload', kwargs={'foundyear': self.year.year})
        response = self.client.post(url, {
            'for-doc': Document.FINAL_REPORT,
            'delete-file': 'Delete',
        })
        self.assertEqual(response.status_code, 200)
        results = response.context['results']
        self.assertTrue(results[Document.FINAL_REPORT]['success'])
        self.assertEqual(results[Document.FINAL_REPORT]['result'], "Файл удалён")
        self.assertFalse(Document.objects.filter(pk=doc.pk).exists())