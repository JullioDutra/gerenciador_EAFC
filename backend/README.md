# FC Manager — backend (Django + DRF + PostgreSQL)
    pip install -r requirements.txt
    python manage.py makemigrations core && python manage.py migrate && python manage.py createsuperuser
    python manage.py runserver
Fluxo do admin: criar Season (config JSON opcional, ver DEFAULTS em core/services.py) → importar CSV →
POST /api/seasons/{id}/advance/ repetidamente (gera Swiss 1..8 → playoff → 32-avos → … → final/campeão).
Jogador: POST /api/matches/{id}/report/ {score_a, score_b}; o adversário envia o mesmo placar para confirmar.
