# FC Manager — backend (Django + DRF + PostgreSQL)
    pip install -r requirements.txt
    python manage.py makemigrations core && python manage.py migrate && python manage.py createsuperuser
    python manage.py runserver
    python manage.py test core
Fluxo do admin: criar Season (config JSON opcional, ver DEFAULTS em core/services.py) → importar CSV/inscrições →
POST /api/seasons/{id}/advance/ repetidamente (liga/grupos → [playoff] → mata-mata → final/campeão).

- **Formato**: `config.format` = `"league"` (padrão, Swiss) ou `"groups"` (`groups`, `group_qualify`; classificados = grupos × por grupo ∈ {2,4,8,16,32}).
  `POST /seasons/{id}/draw-groups/` sorteia os grupos (também sorteados na 1ª geração); `PATCH /players/{id}/ {"group": n}` ajusta.
- **Gerar rodadas**: `advance` aceita `count` (rodadas de uma vez na liga/grupos), `start` (horário do 1º jogo),
  `parallel` + `slot_minutes` (escalonar jogos), `round_gap_hours`, `deadline_hours` (prazo p/ lançar o placar).
- **Placar**: só uma pessoa valida — `POST /matches/{id}/report/` já fecha a partida; o outro jogador pode `POST /matches/{id}/contest/`.
  Depois de `deadline`, jogadores não lançam mais; só o admin (`POST /matches/{id}/extend-deadline/ {"deadline": ISO}` ou `set-result`).
- **Check-in**: `Season.jogo` liga a temporada à coluna "Jogo" da planilha. `POST /checkin/lookup/` lista as inscrições do telefone (uma por campeonato);
  `POST /checkin/confirm/ {"phone", "registrations": [ids]}` faz o check-in nas escolhidas (vazio = todas).
- **Imagens**: `GET /rounds/{id}/image/` (admin; `?group=N`, `?match=ID`) devolve um PNG com os confrontos, horários e prazos.
