import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Prefetch

from ldap3 import ALL, ALL_ATTRIBUTES, Connection, Server
from ldap3.core.exceptions import LDAPException

from webd_core.models import Document, Enrollment, Group, Student, Year


LEGACY_ROOT_DEFAULT = "groups/projects"


def _parse_index_clj(text: str) -> dict:
    """
    Lightweight parser for legacy EDN-like index.clj.
    We only extract string values from top-level keys and `:files` map keys.
    """
    data = {}

    def _unescape_legacy(value: str) -> str:
        # Разэкранируем стандартные последовательности из legacy-файлов
        value = value.replace(r'\"', '"')
        value = value.replace(r'\n', '\n')
        value = value.replace(r'\t', '\t')
        return value
    top_level_keys = [
        "department",
        "name",
        "adviser-name",
        "title",
        "adviser-rank",
        "adviser-position",
        "adviser-status",
    ]
    # Разбираем строковые значения, поддерживая экранированные кавычки внутри,
    # а также учитываем legacy-значение nil (например: :department nil).
    # Пример: :title "Развитие системы \"Курс\""
    for key in top_level_keys:
        # 1) quoted string: :key "value"
        match = re.search(rf":{re.escape(key)}\s+\"((?:\\.|[^\"])*)\"", text)
        if match:
            raw = match.group(1)
            data[key] = _unescape_legacy(raw).strip()
            continue
        # 2) nil: :key nil
        # NOTE: avoid f-string with literal "}" (it breaks parsing).
        match_nil = re.search(r":" + re.escape(key) + r"\s+nil(\s|,|\})", text)
        if match_nil:
            data[key] = ""

    files_match = re.search(r":files\s*\{(.*?)\}\s*,\s*:adviser-status", text, flags=re.S)
    if not files_match:
        files_match = re.search(r":files\s*\{(.*?)\}\s*\}", text, flags=re.S)
    files_block = files_match.group(1) if files_match else ""
    file_keys = set(re.findall(r":([a-zA-Z0-9\-]+)\s*\{", files_block))
    data["file_keys"] = file_keys
    return data


def _pick_file_from_dir(folder: Path):
    if not folder.exists() or not folder.is_dir():
        return None
    candidates = [p for p in folder.iterdir() if p.is_file()]
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


class Command(BaseCommand):
    help = (
        "Импортирует архивные работы из media/groups/projects/"
        "(год/курс/группа/логин) в модели Student/Enrollment/Document."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--root",
            default=LEGACY_ROOT_DEFAULT,
            help="Путь внутри MEDIA_ROOT до legacy-архива (по умолчанию: groups/projects)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только показать, что будет импортировано, без записи в БД",
        )
        parser.add_argument(
            "--skip-ldap",
            action="store_true",
            help="Не делать LDAP-поиск ФИО (использовать только index.clj)",
        )
        parser.add_argument(
            "--prune-without-index",
            action="store_true",
            help="Удалить документы, у которых в папке студента отсутствует index.clj",
        )

    def _ldap_full_name_by_login(self, username: str):
        ldap_server_uri = getattr(settings, "LDAP_SERVER", None)
        ldap_port = getattr(settings, "LDAP_PORT", None)
        ldap_use_ssl = getattr(settings, "LDAP_USE_SSL", True)
        ldap_base_dn = getattr(settings, "LDAP_BASE_DN", None)
        if not ldap_server_uri or not ldap_base_dn:
            return None

        try:
            server = Server(
                ldap_server_uri,
                port=ldap_port,
                use_ssl=ldap_use_ssl,
                get_info=ALL,
            )
            conn = Connection(server, auto_bind=True)
            conn.search(
                search_base=ldap_base_dn,
                search_filter=f"(uid={username})",
                attributes=ALL_ATTRIBUTES,
            )
            if len(conn.entries) != 1:
                conn.unbind()
                return None

            attrs = conn.entries[0].entry_attributes_as_dict
            cn = (attrs.get("cn") or [""])[0].strip()
            if cn:
                conn.unbind()
                return cn
            given = (attrs.get("givenName") or [""])[0].strip()
            sn = (attrs.get("sn") or [""])[0].strip()
            conn.unbind()
            full_name = f"{sn} {given}".strip()
            return full_name or None
        except LDAPException:
            return None

    @transaction.atomic
    def handle(self, *args, **options):
        media_root = Path(settings.MEDIA_ROOT)
        legacy_root = media_root / options["root"]
        dry_run = options["dry_run"]
        skip_ldap = options["skip_ldap"]
        prune_without_index = options.get("prune_without_index", False)
        ldap_name_cache = {}

        if not legacy_root.exists():
            self.stdout.write(self.style.ERROR(f"Папка не найдена: {legacy_root}"))
            return

        # Очистка: удаляем записи Enrollment и документы без index.clj в папке студента
        if prune_without_index:
            # 1) Сначала чистим Enrollment (документы удалятся каскадно)
            self.stdout.write("Проверяю и удаляю Enrollment без index.clj...")
            pruned_enrollments = 0
            enroll_qs = Enrollment.objects.select_related("student", "group", "year")
            for enroll in enroll_qs.iterator():
                year_value = enroll.year.year
                course_value = (enroll.courses or "").strip() or "0"
                group_value = enroll.group.name
                login_value = enroll.student.login
                student_dir = (
                    Path(settings.MEDIA_ROOT)
                    / "groups"
                    / "projects"
                    / str(year_value)
                    / str(course_value)
                    / group_value
                    / login_value
                )
                index_file = student_dir / "index.clj"
                if not index_file.exists():
                    pruned_enrollments += 1
                    if not dry_run:
                        enroll.delete()
            note = " (DRY RUN)" if dry_run else ""
            self.stdout.write(self.style.WARNING(f"Удалено записей Enrollment без index.clj: {pruned_enrollments}{note}"))

            # 2) Дополнительно подчистим "осиротевшие" документы,
            #    у которых по пути нет index.clj (на случай несоответствий путей)
            self.stdout.write("Проверяю и удаляю документы без index.clj...")
            pruned_documents = 0
            for doc in Document.objects.select_related("enrollment").iterator():
                file_rel = (doc.file.name or "").strip()
                if not file_rel:
                    continue
                file_abs = (media_root / file_rel).resolve()
                parts = file_abs.parts
                if "projects" in parts:
                    i = parts.index("projects")
                    # ожидаем projects/<year>/<course>/<group>/<login>/...
                    if len(parts) >= i + 5:
                        student_dir = Path(*parts[: i + 5])
                        index_file = student_dir / "index.clj"
                        if not index_file.exists():
                            pruned_documents += 1
                            if not dry_run:
                                doc.delete()
            self.stdout.write(self.style.WARNING(f"Удалено документов без index.clj: {pruned_documents}{note}"))

        imported_students = 0
        imported_enrollments = 0
        imported_documents = 0

        self.stdout.write(f"Сканирую архив: {legacy_root}")

        year_dirs = [p for p in legacy_root.iterdir() if p.is_dir() and p.name.isdigit()]
        year_dirs.sort(key=lambda p: int(p.name))

        for year_dir in year_dirs:
            year_value = int(year_dir.name)
            year_obj, _ = Year.objects.get_or_create(year=year_value)

            course_dirs = [p for p in year_dir.iterdir() if p.is_dir() and p.name.isdigit()]
            course_dirs.sort(key=lambda p: int(p.name))

            for course_dir in course_dirs:
                course_value = int(course_dir.name)

                for group_dir in [p for p in course_dir.iterdir() if p.is_dir()]:
                    group_name = group_dir.name
                    group_obj, _ = Group.objects.get_or_create(
                        year=year_obj,
                        name=group_name,
                        defaults={"is_latest": False, "is_master_latest": False},
                    )

                    for student_dir in [p for p in group_dir.iterdir() if p.is_dir()]:
                        login = student_dir.name.strip()
                        if not login:
                            continue

                        index_file = student_dir / "index.clj"
                        # Если нет index.clj — пропускаем такие работы полностью
                        if not index_file.exists():
                            continue

                        index_data = {}
                        try:
                            index_data = _parse_index_clj(index_file.read_text(encoding="utf-8", errors="ignore"))
                        except Exception:
                            index_data = {}

                        full_name = (index_data.get("name") or "").strip()
                        if not skip_ldap:
                            if login not in ldap_name_cache:
                                ldap_name_cache[login] = self._ldap_full_name_by_login(login)
                            ldap_name = ldap_name_cache[login]
                            if ldap_name:
                                full_name = ldap_name
                        if not full_name:
                            full_name = login
                        department = index_data.get("department", "")
                        adviser_name = index_data.get("adviser-name", "")
                        title = index_data.get("title", "")
                        adviser_rank = index_data.get("adviser-rank", "")
                        adviser_position = index_data.get("adviser-position", "")
                        adviser_status = index_data.get("adviser-status", "")

                        if not dry_run:
                            student_obj, student_created = Student.objects.get_or_create(
                                login=login,
                                defaults={"full_name": full_name},
                            )
                            if student_created:
                                imported_students += 1
                            elif full_name and student_obj.full_name != full_name:
                                student_obj.full_name = full_name
                                student_obj.save(update_fields=["full_name"])

                            enrollment_obj, enrollment_created = Enrollment.objects.get_or_create(
                                student=student_obj,
                                year=year_obj,
                                defaults={
                                    "group": group_obj,
                                    "courses": str(course_value),
                                    "department": department,
                                    "adviser_name": adviser_name,
                                    "title": title,
                                    "adviser_rank": adviser_rank,
                                    "adviser_position": adviser_position,
                                    "adviser_status": adviser_status,
                                },
                            )
                            if enrollment_created:
                                imported_enrollments += 1
                            else:
                                changed = False
                                if enrollment_obj.group_id != group_obj.id:
                                    enrollment_obj.group = group_obj
                                    changed = True
                                if str(enrollment_obj.courses or "") != str(course_value):
                                    enrollment_obj.courses = str(course_value)
                                    changed = True
                                update_fields = []
                                # Для кафедры важно уметь "обнулить" значение, если в index.clj стоит nil/пусто.
                                # Поэтому department обновляем всегда, если отличается.
                                if getattr(enrollment_obj, "department") != department:
                                    enrollment_obj.department = department
                                    update_fields.append("department")
                                for field_name, value in (
                                    ("adviser_name", adviser_name),
                                    ("title", title),
                                    ("adviser_rank", adviser_rank),
                                    ("adviser_position", adviser_position),
                                    ("adviser_status", adviser_status),
                                ):
                                    if value and getattr(enrollment_obj, field_name) != value:
                                        setattr(enrollment_obj, field_name, value)
                                        update_fields.append(field_name)
                                if changed:
                                    update_fields.extend(["group", "courses"])
                                if update_fields:
                                    enrollment_obj.save(update_fields=update_fields)
                        else:
                            enrollment_obj = None

                        # Собираем файлы с диска по фиксированным путям
                        interim_report_path = _pick_file_from_dir(student_dir / "interim" / "report")
                        interim_presentation_path = _pick_file_from_dir(student_dir / "interim" / "presentation")
                        preport_path = _pick_file_from_dir(student_dir / "final" / "preport")
                        report_path = _pick_file_from_dir(student_dir / "final" / "report")
                        presentation_path = _pick_file_from_dir(student_dir / "final" / "presentation")
                        antiplagiat_path = _pick_file_from_dir(student_dir / "final" / "antiplagiat")
                        supreview_path = _pick_file_from_dir(student_dir / "final" / "supreview")
                        review_path = _pick_file_from_dir(student_dir / "final" / "review")

                        # Признаки "выпускной" и "магистерской выпускной" группы по наличию специфичных файлов
                        has_latest_signs = any(
                            p is not None for p in (preport_path, antiplagiat_path, supreview_path, review_path)
                        )
                        has_master_review = review_path is not None

                        # Для не-выпускных групп:
                        # final/report/report.pdf -> FINAL_REPORT ("Отчет")
                        # final/presentation/slides.pdf -> FINAL_PRESENTATION ("ЭП")
                        # Для выпускных групп (включая магистратуру):
                        # final/report/report.pdf -> THESIS_TEXT ("Текст ВКР")
                        # final/presentation/slides.pdf -> THESIS_PRESENTATION ("Презент. ВКР")
                        if has_latest_signs or group_obj.is_latest or group_obj.is_master_latest:
                            report_doc_type = "thesis_text"
                            presentation_doc_type = "thesis_presentation"
                        else:
                            report_doc_type = "final_report"
                            presentation_doc_type = "final_presentation"

                        file_map = {
                            "interim_report": interim_report_path,
                            "interim_presentation": interim_presentation_path,
                            "practice_nir_report": preport_path,
                            report_doc_type: report_path,
                            presentation_doc_type: presentation_path,
                            "plagiarism_check": antiplagiat_path,
                            "advisor_review": supreview_path,
                            "review": review_path,
                        }

                        # Переустановим флаги группы при наличии признаков
                        if not dry_run and has_latest_signs and not group_obj.is_latest:
                            group_obj.is_latest = True
                            group_obj.save(update_fields=["is_latest"])
                        if not dry_run and has_master_review and not group_obj.is_master_latest:
                            group_obj.is_master_latest = True
                            group_obj.save(update_fields=["is_master_latest"])

                        if dry_run or enrollment_obj is None:
                            continue

                        allowed_doc_types = {code for code, _ in Document.get_doc_types_for_group(
                            group_obj.is_latest,
                            group_obj.is_master_latest,
                        )}
                        for doc_type, file_path in file_map.items():
                            if file_path is None or doc_type not in allowed_doc_types:
                                continue

                            rel_path = file_path.relative_to(media_root).as_posix()
                            document_obj, _ = Document.objects.get_or_create(
                                enrollment=enrollment_obj,
                                doc_type=doc_type,
                            )
                            if document_obj.file.name != rel_path:
                                document_obj.file.name = rel_path
                                document_obj.save(update_fields=["file"])
                                imported_documents += 1

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: данные не записывались в БД"))
            return

        self.stdout.write(self.style.SUCCESS("Импорт legacy-архива завершен"))
        self.stdout.write(f"Новых студентов: {imported_students}")
        self.stdout.write(f"Новых записей Enrollment: {imported_enrollments}")
        self.stdout.write(f"Добавлено/обновлено документов: {imported_documents}")
