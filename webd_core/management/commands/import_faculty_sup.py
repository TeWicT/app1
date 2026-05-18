import os
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from ldap3 import ALL, BASE, SUBTREE, Connection, Server
from ldap3.core.exceptions import LDAPException

from webd_core.models import TeacherProfile


User = get_user_model()


def _safe_first(value) -> str:
    if isinstance(value, (list, tuple)):
        return str(value[0]) if value else ""
    return str(value) if value is not None else ""


def _connect() -> Connection:
    server = Server(
        settings.LDAP_SERVER,
        port=getattr(settings, "LDAP_PORT", 636),
        use_ssl=getattr(settings, "LDAP_USE_SSL", True),
        get_info=ALL,
    )
    bind_dn = os.getenv("LDAP_BIND_DN") or None
    bind_password = os.getenv("LDAP_BIND_PASSWORD") or ""
    if bind_dn:
        return Connection(server, user=bind_dn, password=bind_password, auto_bind=True)
    return Connection(server, auto_bind=True)


def _find_group_dn(conn: Connection, cn: str, group_base_dn: str) -> Optional[str]:
    conn.search(
        search_base=group_base_dn,
        search_filter=f"(cn={cn})",
        search_scope=SUBTREE,
        attributes=["cn"],
        size_limit=10,
    )
    if not conn.entries:
        return None
    return conn.entries[0].entry_dn


def _read_group_members(conn: Connection, group_dn: str) -> Tuple[List[str], List[str], List[str]]:
    """
    Возвращает:
    - member_dns: DNs из groupOfNames
    - unique_member_dns: DNs из groupOfUniqueNames
    - member_uids: uid из posixGroup
    """
    conn.search(
        search_base=group_dn,
        search_filter="(objectClass=*)",
        search_scope=BASE,
        attributes=["member", "uniqueMember", "memberUid", "cn"],
        size_limit=1,
    )
    if len(conn.entries) != 1:
        return [], [], []
    attrs: Dict = conn.entries[0].entry_attributes_as_dict
    member_dns = [str(x) for x in (attrs.get("member") or [])]
    unique_member_dns = [str(x) for x in (attrs.get("uniqueMember") or [])]
    member_uids = [str(x) for x in (attrs.get("memberUid") or [])]
    return member_dns, unique_member_dns, member_uids


def _fetch_people_by_dns(conn: Connection, dns: Iterable[str]) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    seen: Set[str] = set()
    for dn in dns:
        dn = str(dn).strip()
        if not dn or dn in seen:
            continue
        seen.add(dn)
        conn.search(
            search_base=dn,
            search_filter="(objectClass=*)",
            search_scope=BASE,
            attributes=["uid", "cn", "sn", "givenName", "mail"],
            size_limit=1,
        )
        if not conn.entries:
            results.append({"dn": dn, "uid": "", "cn": "", "sn": "", "givenName": "", "mail": ""})
            continue
        entry = conn.entries[0]
        attrs = entry.entry_attributes_as_dict
        results.append(
            {
                "dn": entry.entry_dn,
                "uid": _safe_first(attrs.get("uid")),
                "cn": _safe_first(attrs.get("cn")),
                "sn": _safe_first(attrs.get("sn")),
                "givenName": _safe_first(attrs.get("givenName")),
                "mail": _safe_first(attrs.get("mail")),
            }
        )
    return results


def _fetch_people_by_uids(conn: Connection, people_base_dn: str, uids: Sequence[str]) -> List[Dict[str, str]]:
    cleaned = [u.strip() for u in uids if u and u.strip()]
    if not cleaned:
        return []
    # OR-фильтр. Для больших списков лучше дробить, но для faculty_sup обычно размер разумный.
    uid_filter = "(|" + "".join([f"(uid={uid})" for uid in cleaned]) + ")"
    conn.search(
        search_base=people_base_dn,
        search_filter=uid_filter,
        search_scope=SUBTREE,
        attributes=["uid", "cn", "sn", "givenName", "mail"],
    )
    results: List[Dict[str, str]] = []
    for entry in conn.entries:
        attrs = entry.entry_attributes_as_dict
        results.append(
            {
                "dn": entry.entry_dn,
                "uid": _safe_first(attrs.get("uid")),
                "cn": _safe_first(attrs.get("cn")),
                "sn": _safe_first(attrs.get("sn")),
                "givenName": _safe_first(attrs.get("givenName")),
                "mail": _safe_first(attrs.get("mail")),
            }
        )
    return results


def _split_name(attrs: Dict[str, str]) -> Tuple[str, str]:
    """
    Возвращает (first_name, last_name) для Django User.
    Для отображения в интерфейсе всё равно используем TeacherProfile.full_name.
    """
    given = (attrs.get("givenName") or "").strip()
    sn = (attrs.get("sn") or "").strip()
    if given or sn:
        return given, sn
    cn = (attrs.get("cn") or "").strip()
    if not cn:
        return "", ""
    parts = cn.split()
    if len(parts) >= 2:
        return " ".join(parts[1:]), parts[0]
    return "", cn


class Command(BaseCommand):
    help = (
        "Импортирует всех пользователей из LDAP-группы (по cn) как преподавателей "
        "(создаёт User + TeacherProfile), даже если они ни разу не логинились."
    )

    def add_arguments(self, parser):
        parser.add_argument("--group-cn", default="faculty_sup", help="CN группы (по умолчанию faculty_sup)")
        parser.add_argument(
            "--group-base-dn",
            default=os.getenv("LDAP_GROUP_BASE_DN", "ou=group,dc=cs,dc=karelia,dc=ru"),
            help="Base DN для поиска групп (по умолчанию ou=group,dc=cs,dc=karelia,dc=ru)",
        )
        parser.add_argument(
            "--people-base-dn",
            default=os.getenv("LDAP_PEOPLE_BASE_DN", "ou=people,dc=cs,dc=karelia,dc=ru"),
            help="Base DN для поиска пользователей (по умолчанию ou=people,dc=cs,dc=karelia,dc=ru)",
        )
        parser.add_argument("--dry-run", action="store_true", help="Ничего не записывать в БД, только показать план")

    @transaction.atomic
    def handle(self, *args, **options):
        group_cn: str = options["group_cn"]
        group_base_dn: str = options["group_base_dn"]
        people_base_dn: str = options["people_base_dn"]
        dry_run: bool = bool(options["dry_run"])

        created_users = 0
        created_profiles = 0
        updated_profiles = 0
        skipped_no_uid = 0

        try:
            conn = _connect()
        except LDAPException as exc:
            raise RuntimeError(f"LDAP connection failed: {exc}") from exc

        try:
            group_dn = _find_group_dn(conn, group_cn, group_base_dn)
            if not group_dn:
                self.stderr.write(self.style.ERROR(f"Группа cn={group_cn!r} не найдена в {group_base_dn!r}"))
                return

            member_dns, unique_member_dns, member_uids = _read_group_members(conn, group_dn)
            people: List[Dict[str, str]] = []
            people.extend(_fetch_people_by_dns(conn, member_dns))
            people.extend(_fetch_people_by_dns(conn, unique_member_dns))
            people.extend(_fetch_people_by_uids(conn, people_base_dn, member_uids))

            # дедуп по uid, если он есть; иначе по dn
            uniq: Dict[str, Dict[str, str]] = {}
            for p in people:
                uid = (p.get("uid") or "").strip()
                key = uid or (p.get("dn") or "")
                if not key:
                    continue
                uniq[key] = p

            self.stdout.write(f"LDAP group: cn={group_cn} | dn={group_dn}")
            self.stdout.write(f"Found members (unique): {len(uniq)}")

            for key, attrs in sorted(uniq.items(), key=lambda kv: (kv[1].get("cn") or "", kv[1].get("uid") or "", kv[1].get("dn") or "")):
                uid = (attrs.get("uid") or "").strip()
                if not uid:
                    skipped_no_uid += 1
                    self.stdout.write(self.style.WARNING(f"skip (no uid): dn={attrs.get('dn','')} cn={attrs.get('cn','')}"))
                    continue

                full_name = (attrs.get("cn") or "").strip() or uid
                email = (attrs.get("mail") or "").strip()
                first_name, last_name = _split_name(attrs)

                if dry_run:
                    self.stdout.write(f"plan: create/ensure teacher uid={uid} cn={full_name} mail={email}")
                    continue

                user, user_created = User.objects.get_or_create(username=uid)
                if user_created:
                    created_users += 1
                    user.set_unusable_password()

                changed = False
                if email and user.email != email:
                    user.email = email
                    changed = True
                if first_name and user.first_name != first_name:
                    user.first_name = first_name
                    changed = True
                if last_name and user.last_name != last_name:
                    user.last_name = last_name
                    changed = True
                if changed:
                    user.save()

                profile, prof_created = TeacherProfile.objects.get_or_create(
                    user=user,
                    defaults={"full_name": full_name},
                )
                if prof_created:
                    created_profiles += 1
                else:
                    if full_name and profile.full_name != full_name:
                        profile.full_name = full_name
                        profile.save(update_fields=["full_name"])
                        updated_profiles += 1

            if dry_run:
                self.stdout.write(self.style.WARNING("dry-run: транзакция будет откатана"))
                transaction.set_rollback(True)
                return

            self.stdout.write(self.style.SUCCESS("Done"))
            self.stdout.write(f"created users: {created_users}")
            self.stdout.write(f"created teacher profiles: {created_profiles}")
            self.stdout.write(f"updated teacher profiles: {updated_profiles}")
            if skipped_no_uid:
                self.stdout.write(self.style.WARNING(f"skipped (no uid): {skipped_no_uid}"))
        finally:
            conn.unbind()

