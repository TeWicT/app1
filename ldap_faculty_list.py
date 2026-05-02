from ldap3 import Server, Connection, ALL
from ldap3.core.exceptions import LDAPException

LDAP_SERVER = "ldaps://ldap.cs.prv"  # или ldap.cs.karelia.ru
LDAP_PORT = 636
LDAP_USE_SSL = True

BASE_DN = "dc=cs,dc=karelia,dc=ru"
FACULTY_BASE_DN = "ou=faculty,ou=people,dc=cs,dc=karelia,dc=ru"

# Если сервер запрещает анонимный bind — заполните:
BIND_DN = None
BIND_PASSWORD = None


def _safe_first(value):
    if isinstance(value, (list, tuple)):
        return value[0] if value else ""
    return value or ""


def main():
    try:
        server = Server(LDAP_SERVER, port=LDAP_PORT, use_ssl=LDAP_USE_SSL, get_info=ALL)
        if BIND_DN and BIND_PASSWORD:
            conn = Connection(server, user=BIND_DN, password=BIND_PASSWORD, auto_bind=True)
        else:
            conn = Connection(server, auto_bind=True)

        conn.search(
            search_base=FACULTY_BASE_DN,
            search_filter="(uid=*)",
            attributes=["uid", "cn", "sn", "givenName", "mail"],
        )

        print(f"Найдено пользователей в ou=faculty: {len(conn.entries)}")
        for i, entry in enumerate(conn.entries, 1):
            attrs = entry.entry_attributes_as_dict
            uid = _safe_first(attrs.get("uid"))
            cn = _safe_first(attrs.get("cn"))
            mail = _safe_first(attrs.get("mail"))
            print(f"{i}. uid={uid} | cn={cn} | mail={mail} | dn={entry.entry_dn}")

        conn.unbind()
    except LDAPException as exc:
        print("Ошибка LDAP:", exc)


if __name__ == "__main__":
    main()
