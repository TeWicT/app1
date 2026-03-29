from typing import Optional

from django.conf import settings
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User

from ldap3 import Server, Connection, ALL, ALL_ATTRIBUTES
from ldap3.core.exceptions import LDAPException, LDAPBindError

from webd_core.models import Student, Year, Group, Enrollment, TeacherProfile


class LdapBackend(BaseBackend):
    """
    Django authentication backend that authenticates users against the CS LDAP.

    Логика:
    1. Подключаемся к LDAP (анонимно или сервисной учёткой).
    2. Ищем запись с uid=<username> под LDAP_BASE_DN.
    3. Берём DN найденной записи и пробуем bind с переданным паролем.
    4. Если bind успешен — создаём/обновляем локального Django-пользователя.
    """

    def authenticate(
        self,
        request,
        username: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs,
    ) -> Optional[User]:
        if not username or not password:
            return None

        # Настройки LDAP берём из settings.py
        ldap_server_uri = getattr(settings, "LDAP_SERVER", None)
        ldap_port = getattr(settings, "LDAP_PORT", None)
        ldap_use_ssl = getattr(settings, "LDAP_USE_SSL", True)
        ldap_base_dn = getattr(settings, "LDAP_BASE_DN", None)

        if not ldap_server_uri or not ldap_base_dn:
            # LDAP не сконфигурирован — тихо выходим
            return None

        server = Server(
            ldap_server_uri,
            port=ldap_port,
            use_ssl=ldap_use_ssl,
            get_info=ALL,
        )

        entry = None

        try:
            # 1. Анонимный bind (или с сервисной учёткой, если потребуется в будущем)
            conn = Connection(server, auto_bind=True)

            # 2. Ищем запись пользователя по uid
            conn.search(
                search_base=ldap_base_dn,
                search_filter=f"(uid={username})",
                attributes=ALL_ATTRIBUTES,
            )

            if len(conn.entries) != 1:
                conn.unbind()
                return None

            entry = conn.entries[0]
            user_dn = entry.entry_dn
            attrs = entry.entry_attributes_as_dict

            # 3. Пробуем bind уже как найденный пользователь
            try:
                user_conn = Connection(
                    server,
                    user=user_dn,
                    password=password,
                    auto_bind=True,
                )
                user_conn.unbind()
            except (LDAPBindError, LDAPException):
                conn.unbind()
                return None

            conn.unbind()

        except LDAPException:
            # Любые проблемы с LDAP — просто не аутентифицируем
            return None

        # 4. Создаём или обновляем локального Django-пользователя
        user, created = User.objects.get_or_create(username=username)

        # Пытаемся заполнить ФИО и почту из LDAP
        mail = ""
        if "mail" in attrs and attrs["mail"]:
            mail = attrs["mail"][0]

        first_name = ""
        if "givenName" in attrs and attrs["givenName"]:
            first_name = attrs["givenName"][0]

        last_name = ""
        if "sn" in attrs and attrs["sn"]:
            last_name = attrs["sn"][0]

        user.email = mail
        user.first_name = first_name
        user.last_name = last_name
        user.save()

        # 5. Если это студент (DN содержит ou=students), создаём/обновляем записи
        if entry is not None and "ou=students" in entry.entry_dn.lower():
            self._ensure_student_records(username, attrs, entry)
        # 6. Если это преподаватель (DN содержит ou=faculty), создаём профиль преподавателя
        elif entry is not None and "ou=faculty" in entry.entry_dn.lower():
            self._ensure_teacher_profile(user, attrs, entry)

        return user

    def get_user(self, user_id: int) -> Optional[User]:
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    @staticmethod
    def _extract_group_name_from_dn(dn: str) -> Optional[str]:
        """
        DN вида:
        cn=ФИО,ou=22405,ou=students,ou=people,dc=cs,dc=karelia,dc=ru
        Нужна часть '22405' — первая ou, которая не равна 'students'/'people'.
        """
        if not dn:
            return None
        for rdn in dn.split(","):
            rdn = rdn.strip()
            if rdn.lower().startswith("ou="):
                value = rdn.split("=", 1)[1]
                if value.lower() not in {"students", "people"}:
                    return value
        return None

    def _ensure_student_records(self, username: str, attrs: dict, entry) -> None:
        """
        После успешной LDAP-аутентификации студента:
        - создаёт (если нет) запись Student с логином и ФИО;
        - создаёт (если нет) группу для текущего учебного года;
        - создаёт (если нет) Enrollment, связывающую студента, год и группу.
        """
        # Текущий учебный год — максимальный в БД (как в middleware)
        current_year = Year.objects.order_by("-year").first()
        if not current_year:
            return

        # ФИО: пробуем взять из cn, если нет — из givenName + sn
        full_name = ""
        if "cn" in attrs and attrs["cn"]:
            full_name = attrs["cn"][0]
        else:
            given = attrs.get("givenName", [""])[0]
            sn = attrs.get("sn", [""])[0]
            full_name = f"{sn} {given}".strip() or username

        student, created_student = Student.objects.get_or_create(
            login=username,
            defaults={"full_name": full_name},
        )
        if not created_student and student.full_name != full_name:
            student.full_name = full_name
            student.save(update_fields=["full_name"])

        # Группа из DN
        group_name = self._extract_group_name_from_dn(entry.entry_dn)
        if not group_name:
            return

        group, _ = Group.objects.get_or_create(
            year=current_year,
            name=group_name,
            defaults={"is_latest": False},
        )

        # Курс: по требованию — брать 3-й символ из OU группы (например, ou=22406 -> '4')
        # Если не удаётся — фоллбек к homeDirectory (/home/NN/login -> 'N')
        courses_value = ""
        if group_name and len(group_name) >= 3 and group_name.isdigit():
            courses_value = group_name[2]
        else:
            home_dirs = attrs.get("homeDirectory") or []
            if home_dirs:
                raw_hd = home_dirs[0]
                # Ожидаемый формат: /home/NN/login
                parts = str(raw_hd).strip("/").split("/")
                if len(parts) >= 3 and parts[0] == "home":
                    year_part = parts[1]  # '04'
                    try:
                        courses_value = str(int(year_part))  # '04' -> 4 -> '4'
                    except (TypeError, ValueError):
                        courses_value = ""

        # Создаём Enrollment, если её ещё нет
        Enrollment.objects.get_or_create(
            student=student,
            year=current_year,
            defaults={
                "group": group,
                "courses": courses_value,
                "adviser_status": "",
                "adviser_position": "",
                "title": "",
                "adviser_name": "",
                "adviser_rank": "",
                "department": "",
            },
        )

    def _ensure_teacher_profile(self, user: User, attrs: dict, entry) -> None:
        """
        После успешной LDAP-аутентификации преподавателя (DN содержит ou=faculty):
        - создаёт (если нет) TeacherProfile, связанный с Django-пользователем;
        - использует ФИО из LDAP (cn / givenName + sn);
        - кафедра и должность берутся из дефолтов модели (можно будет редактировать в будущем).
        """
        # ФИО: сначала пробуем cn, потом givenName + sn
        full_name = ""
        if "cn" in attrs and attrs["cn"]:
            full_name = attrs["cn"][0]
        else:
            given = attrs.get("givenName", [""])[0]
            sn = attrs.get("sn", [""])[0]
            full_name = f"{sn} {given}".strip() or user.username

        profile, created = TeacherProfile.objects.get_or_create(
            user=user,
            defaults={
                "full_name": full_name,
                # department оставляем пустым (blank=True),
                # adviser_position возьмётся из default в модели
            },
        )

        # Если профиль уже был, но ФИО в LDAP изменилось — обновим
        if not created and profile.full_name != full_name:
            profile.full_name = full_name
            profile.save(update_fields=["full_name"])

