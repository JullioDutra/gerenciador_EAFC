# core/middleware.py
from django.shortcuts import redirect

class BloquearAdminParaJogadoresMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Verifica se o caminho acessado é o painel de administração
        if request.path.startswith('/admin/'):
            # Se o usuário estiver logado, mas NÃO for da equipe (is_staff=False)
            if request.user.is_authenticated and not request.user.is_staff:
                # Redireciona o jogador para a página inicial
                # Você pode mudar '/' para o caminho do painel do jogador se preferir
                return redirect('/')
        
        response = self.get_response(request)
        return response