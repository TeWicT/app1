from django.apps import AppConfig


class WebdCoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'webd_core'
    def ready(self):
        import webd_core.signals