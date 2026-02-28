from ldap3 import Server, Connection, ALL, ALL_ATTRIBUTES

LDAP_SERVER = 'ldaps://ldap.cs.prv'  # или просто 'ldap.cs.karelia.ru'
LDAP_PORT = 636                        # ваш порт
LDAP_USE_SSL = True                   # или True, если нужен LDAPS

BASE_DN = 'dc=cs,dc=karelia,dc=ru'  # видно из Server info
UID = 'etitov'

def main():
    server = Server(LDAP_SERVER, port=LDAP_PORT, use_ssl=LDAP_USE_SSL, get_info=ALL)
    conn = Connection(server, auto_bind=True)

    # пример поиска по uid
    conn.search(
        search_base=BASE_DN,
        search_filter=f'(uid={UID})',        # фильтр
        attributes=ALL_ATTRIBUTES
    )

    print('Найдено записей:', len(conn.entries))
    for entry in conn.entries:
        print(entry.entry_dn)
        print(entry.entry_attributes_as_dict)

    conn.unbind()

if __name__ == '__main__':
    main()