


from ldap3 import Server, Connection, ALL, ALL_ATTRIBUTES
from ldap3.core.exceptions import LDAPException, LDAPBindError

ldap_server = Server(app.config['LDAP_SERVER'],
port=app.config['LDAP_PORT'],
                      use_ssl=app.config['LDAP_USE_SSL'], get_info=ALL)


def get_ldap_user_data(uid):
     app.logger.debug("Trying to get LDAP data for user {}".format(uid))
     result = None
     if uid is None:
         return result
     try:
         c = Connection(ldap_server)
         c.bind()
         c.search(search_base="OU=people,DC=cs,DC=karelia,DC=ru",
                  search_filter="(uid=" + uid + ")",
attributes=ALL_ATTRIBUTES)
         if len(c.response) > 0:
             result = c.response[0]
         else:
             app.logger.debug("User with uid {} not found in LDAP".format(uid))
         c.unbind()
     except LDAPException as e:
         app.logger.error("LDAP error: %s", e)
     return None if result is None else result['attributes']

def login_user(uid, password):
     result = False
     if uid is None or password is None:
         app.logger.debug("Invalid input: None is not allowed")
         return result
     create_user_if_absent(uid) # if user was not logged before
     user = User.query.filter_by(uid=uid).first()
     if user is None:
         app.logger.debug("No such user {}".format(uid))
         return result
     try:
         app.logger.error("LDAP uid: %s", uid)
         c = Connection(ldap_server)
         c.bind()
         c.search(search_base="OU=people,DC=cs,DC=karelia,DC=ru",
                  search_filter="(uid={})".format(uid))
         if len(c.response) > 0:
             try:
                 if c.rebind(user=c.response[0]['dn'], password=password):
                     app.logger.debug("User {} succeed to authenticate through LDAP".format(uid))
                     result = True
                 else:
                     app.logger.debug("User {} failed to authenticate through LDAP".format(uid))
             except LDAPBindError as e:
                 app.logger.error('Error in LDAP rebind: %s', e)
         c.unbind()
     except LDAPException as e:
         app.logger.error("LDAP error: %s", e)

     if not result and user.password is not None:
         result = check_password_hash(user.password, password)
     return result