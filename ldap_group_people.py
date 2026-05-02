import argparse
import os
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from ldap3 import ALL, BASE, SUBTREE, Connection, Server
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


def _chunks(seq: Sequence[str], n: int) -> Iterable[Sequence[str]]:
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def _find_group_dn(conn: Connection, base_dn: str, cn: str, group_base_dn: Optional[str]) -> Optional[str]:
    search_base = group_base_dn or base_dn
    conn.search(
        search_base=search_base,
        search_filter=f"(cn={cn})",
        search_scope=SUBTREE,
        attributes=["cn"],
        size_limit=10,
    )
    if not conn.entries:
        return None
    # если нашлось несколько — берём первый; при необходимости можно уточнить group_base_dn
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
            results.append({"dn": dn, "uid": "", "cn": "", "mail": ""})
            continue
        entry = conn.entries[0]
        attrs = entry.entry_attributes_as_dict
        results.append(
            {
                "dn": entry.entry_dn,
                "uid": _safe_first(attrs.get("uid")),
                "cn": _safe_first(attrs.get("cn")),
                "mail": _safe_first(attrs.get("mail")),
            }
        )
    return results


def _fetch_people_by_uids(conn: Connection, people_base_dn: str, uids: Sequence[str]) -> List[Dict[str, str]]:
    if not uids:
        return []
    cleaned = [u.strip() for u in uids if u and u.strip()]
    if not cleaned:
        return []

    results: List[Dict[str, str]] = []
    for chunk in _chunks(cleaned, 50):
        uid_filter = "(|" + "".join([f"(uid={uid})" for uid in chunk]) + ")"
        conn.search(
            search_base=people_base_dn,
            search_filter=uid_filter,
            search_scope=SUBTREE,
            attributes=["uid", "cn", "sn", "givenName", "mail"],
        )
        for entry in conn.entries:
            attrs = entry.entry_attributes_as_dict
            results.append(
                {
                    "dn": entry.entry_dn,
                    "uid": _safe_first(attrs.get("uid")),
                    "cn": _safe_first(attrs.get("cn")),
                    "mail": _safe_first(attrs.get("mail")),
                }
            )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List people who are members of an LDAP group (by cn)."
    )
    parser.add_argument("group_cn", help="Group CN, e.g. faculty_sup")
    parser.add_argument(
        "--base-dn",
        default=os.getenv("LDAP_BASE_DN", "dc=cs,dc=karelia,dc=ru"),
        help="Search base DN (default: LDAP_BASE_DN env or dc=cs,dc=karelia,dc=ru)",
    )
    parser.add_argument(
        "--group-base-dn",
        default=os.getenv("LDAP_GROUP_BASE_DN"),
        help="Optional base DN for groups (env: LDAP_GROUP_BASE_DN). Example: ou=group,dc=cs,dc=karelia,dc=ru",
    )
    parser.add_argument(
        "--people-base-dn",
        default=os.getenv("LDAP_PEOPLE_BASE_DN", "ou=people,dc=cs,dc=karelia,dc=ru"),
        help="Base DN for people search (default: LDAP_PEOPLE_BASE_DN env or ou=people,dc=cs,dc=karelia,dc=ru)",
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

    group_cn = args.group_cn.strip()
    if not group_cn:
        print("Empty group_cn", file=sys.stderr)
        return 2

    try:
        conn = _connect(args.server, args.port, args.use_ssl, args.bind_dn, args.bind_password)
        try:
            group_dn = _find_group_dn(conn, args.base_dn, group_cn, args.group_base_dn)
            if not group_dn:
                print(f"Group cn={group_cn!r} not found", file=sys.stderr)
                return 3

            member_dns, unique_member_dns, member_uids = _read_group_members(conn, group_dn)
            people: List[Dict[str, str]] = []
            people.extend(_fetch_people_by_dns(conn, member_dns))
            people.extend(_fetch_people_by_dns(conn, unique_member_dns))
            people.extend(_fetch_people_by_uids(conn, args.people_base_dn, member_uids))

            # Дедуп по DN/uid
            uniq: Dict[str, Dict[str, str]] = {}
            for p in people:
                key = p.get("dn") or p.get("uid") or repr(p)
                uniq[key] = p

            print(f"Group: cn={group_cn} | dn={group_dn}")
            print(f"Members: {len(uniq)}")
            for p in sorted(uniq.values(), key=lambda x: (x.get("cn") or "", x.get("uid") or "", x.get("dn") or "")):
                print(f"- uid={p.get('uid','')} | cn={p.get('cn','')} | mail={p.get('mail','')} | dn={p.get('dn','')}")
            return 0
        finally:
            conn.unbind()
    except LDAPException as exc:
        print(f"LDAP error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

