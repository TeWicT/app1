import argparse
import os
import sys
from typing import Iterable, List, Optional, Set, Tuple

from ldap3 import ALL, SUBTREE, Connection, Server
from ldap3.core.exceptions import LDAPException


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _safe_first(value) -> str:
    if isinstance(value, (list, tuple)):
        return str(value[0]) if value else ""
    return str(value) if value is not None else ""


def _connect(
    server_uri: str,
    port: int,
    use_ssl: bool,
    bind_dn: Optional[str],
    bind_password: Optional[str],
) -> Connection:
    server = Server(server_uri, port=port, use_ssl=use_ssl, get_info=ALL)
    if bind_dn:
        return Connection(server, user=bind_dn, password=bind_password or "", auto_bind=True)
    return Connection(server, auto_bind=True)


def _find_user_dn_and_memberof(conn: Connection, base_dn: str, uid: str) -> Tuple[Optional[str], List[str]]:
    conn.search(
        search_base=base_dn,
        search_filter=f"(uid={uid})",
        search_scope=SUBTREE,
        # DN не является LDAP-атрибутом: ldap3 отдаёт его как entry.entry_dn
        attributes=["memberOf", "cn", "uid"],
        size_limit=5,
    )
    if len(conn.entries) != 1:
        return None, []
    entry = conn.entries[0]
    attrs = entry.entry_attributes_as_dict
    member_of = attrs.get("memberOf") or []
    return entry.entry_dn, [str(x) for x in member_of]


def _search_groups_by_membership(conn: Connection, base_dn: str, uid: str, user_dn: str) -> List[str]:
    """
    На разных LDAP-схемах группы описываются по-разному. Самые частые варианты:
    - groupOfNames / groupOfUniqueNames: member / uniqueMember содержит DN пользователя
    - posixGroup: memberUid содержит uid пользователя
    """
    group_filter = (
        "(|"
        f"(member={user_dn})"
        f"(uniqueMember={user_dn})"
        f"(memberUid={uid})"
        ")"
    )
    conn.search(
        search_base=base_dn,
        search_filter=group_filter,
        search_scope=SUBTREE,
        # DN не является LDAP-атрибутом: ldap3 отдаёт его как entry.entry_dn
        attributes=["cn", "ou", "description"],
    )
    return [e.entry_dn for e in conn.entries]


def _format_group_dn(dn: str) -> str:
    # печатаем короткое имя, если есть cn/ou в первом RDN
    first_rdn = dn.split(",", 1)[0].strip()
    return f"{first_rdn}  ({dn})"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Show all LDAP groups for a user (via memberOf and group membership search)."
    )
    parser.add_argument("uid", help="User uid/login, e.g. chistyak")
    parser.add_argument(
        "--base-dn",
        default=os.getenv("LDAP_BASE_DN", "dc=cs,dc=karelia,dc=ru"),
        help="Search base DN (default: LDAP_BASE_DN env or dc=cs,dc=karelia,dc=ru)",
    )
    parser.add_argument(
        "--server",
        default=os.getenv("LDAP_SERVER", "ldaps://ldap.cs.prv"),
        help="LDAP server URI (default: LDAP_SERVER env or ldaps://ldap.cs.prv)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("LDAP_PORT", "636")),
        help="LDAP port (default: LDAP_PORT env or 636)",
    )
    parser.add_argument(
        "--ssl/--no-ssl",
        dest="use_ssl",
        default=_env_bool("LDAP_USE_SSL", True),
        help="Use SSL (LDAPS). Default from LDAP_USE_SSL env (True if unset).",
    )
    parser.add_argument(
        "--bind-dn",
        default=os.getenv("LDAP_BIND_DN"),
        help="Optional bind DN for service account (env: LDAP_BIND_DN).",
    )
    parser.add_argument(
        "--bind-password",
        default=os.getenv("LDAP_BIND_PASSWORD"),
        help="Optional bind password (env: LDAP_BIND_PASSWORD).",
    )
    args = parser.parse_args()

    uid = args.uid.strip()
    if not uid:
        print("Empty uid", file=sys.stderr)
        return 2

    try:
        conn = _connect(args.server, args.port, args.use_ssl, args.bind_dn, args.bind_password)
        try:
            user_dn, member_of = _find_user_dn_and_memberof(conn, args.base_dn, uid)
            if not user_dn:
                print(f"User uid={uid!r} not found under base DN {args.base_dn!r}", file=sys.stderr)
                return 3

            groups: Set[str] = set(member_of)
            # Если memberOf пустой/не отдаётся — добираем через поиск групп по membership.
            groups.update(_search_groups_by_membership(conn, args.base_dn, uid, user_dn))

            print(f"User: uid={uid} | dn={user_dn}")
            if not groups:
                print("Groups: (none found)")
                return 0

            print(f"Groups: {len(groups)}")
            for dn in sorted(groups, key=str.lower):
                print(f"- {_format_group_dn(dn)}")
            return 0
        finally:
            conn.unbind()
    except LDAPException as exc:
        print(f"LDAP error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

