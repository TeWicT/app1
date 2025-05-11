# webd_core/middleware.py
class FoundYearMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Задаём foundyear, если его нет в сессии, например, по умолчанию 2024
        if 'foundyear' not in request.session:
            request.session['foundyear'] = 2024  # можно заменить на значение по логике

        # Теперь добавляем foundyear в context каждого запроса, чтобы он был доступен в шаблонах и представлениях
        request.foundyear = request.session['foundyear']
        
        response = self.get_response(request)
        return response
