from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **kw):
        u = self.model(email=self.normalize_email(email), **kw); u.set_password(password); u.save(); return u
    def create_superuser(self, email, password=None, **kw):
        return self.create_user(email, password, is_staff=True, is_superuser=True, **kw)

class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    USERNAME_FIELD = "email"; REQUIRED_FIELDS = []
    objects = UserManager()

class Season(models.Model):
    name = models.CharField(max_length=80)
    year = models.PositiveIntegerField()
    config = models.JSONField(default=dict, blank=True)  # sobrescreve DEFAULTS (ver services.py)
    champion = models.ForeignKey("Player", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    def __str__(self): return f"{self.name} {self.year}"

class Player(models.Model):
    STATUS = [("active", "Ativo"), ("playoff", "Playoff"), ("main", "Fase principal"),
              ("eliminated", "Eliminado"), ("blocked", "Bloqueado"), ("champion", "Campeão")]
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="players")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="players")
    name = models.CharField(max_length=120); nickname = models.CharField(max_length=40)
    ea_id = models.CharField(max_length=60, blank=True); platform = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=2, blank=True); avatar = models.URLField(blank=True)
    avatar_file = models.ImageField(upload_to="avatars/", null=True, blank=True)  # tem prioridade sobre 'avatar' (URL) quando definido
    team = models.CharField(max_length=80, blank=True)  # clube/time escolhido (ex.: PSG, Flamengo) vindo da pré-inscrição
    campus = models.CharField(max_length=120, blank=True)  # região/campus, vindo do check-in
    number = models.PositiveIntegerField(null=True, blank=True); seed = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default="active")
    class Meta: unique_together = [("season", "user")]
    def __str__(self): return self.nickname

class Round(models.Model):
    PHASES = ["swiss", "playoff1", "playoff2", "r32", "r16", "qf", "sf", "final"]
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="rounds")
    phase = models.CharField(max_length=10); number = models.PositiveIntegerField()
    name = models.CharField(max_length=40); deadline = models.DateTimeField(null=True, blank=True)
    match_format = models.CharField(max_length=12, default="single")  # single|bo3|bo5|two_legs
    class Meta: ordering = ["number"]

class Match(models.Model):
    STATUS = [("pending", "Pendente"), ("awaiting", "Aguardando confirmação"), ("confirmed", "Confirmado"),
              ("disputed", "Contestação aberta"), ("resolved", "Resolvido pelo admin"), ("wo", "WO")]
    DONE = ("confirmed", "resolved", "wo")
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="matches")
    slot = models.PositiveIntegerField(default=0)
    player_a = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="+")
    player_b = models.ForeignKey(Player, null=True, blank=True, on_delete=models.CASCADE, related_name="+")  # null = bye
    score_a = models.PositiveIntegerField(null=True, blank=True); score_b = models.PositiveIntegerField(null=True, blank=True)
    pen_a = models.PositiveIntegerField(null=True, blank=True); pen_b = models.PositiveIntegerField(null=True, blank=True)
    winner = models.ForeignKey(Player, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    status = models.CharField(max_length=10, choices=STATUS, default="pending")
    extra_time = models.BooleanField(default=False, help_text="Foi à prorrogação")
    deadline = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True); wo_reason = models.CharField(max_length=200, blank=True)
    reports = models.JSONField(default=dict, blank=True)  # {player_id: [sa, sb, pa, pb]}
    proof_a = models.FileField(upload_to="proofs/", null=True, blank=True)
    proof_b = models.FileField(upload_to="proofs/", null=True, blank=True)
    class Meta: ordering = ["round__number", "slot"]

class Leg(models.Model):
    """Um jogo dentro de um confronto de ida-e-volta ou melhor-de-3/5 (round.match_format != 'single')."""
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="legs")
    number = models.PositiveSmallIntegerField()
    score_a = models.PositiveIntegerField(null=True, blank=True); score_b = models.PositiveIntegerField(null=True, blank=True)
    pen_a = models.PositiveIntegerField(null=True, blank=True); pen_b = models.PositiveIntegerField(null=True, blank=True)
    extra_time = models.BooleanField(default=False, help_text="Foi à prorrogação")
    status = models.CharField(max_length=10, choices=Match.STATUS, default="pending")
    wo_reason = models.CharField(max_length=200, blank=True)
    reports = models.JSONField(default=dict, blank=True)  # {player_id: [sa, sb, pa, pb]}
    proof_a = models.FileField(upload_to="proofs/", null=True, blank=True)
    proof_b = models.FileField(upload_to="proofs/", null=True, blank=True)
    class Meta: unique_together = [("match", "number")]; ordering = ["number"]

class Penalty(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="penalties")
    points = models.IntegerField(help_text="negativo = punição, positivo = bônus")
    reason = models.CharField(max_length=200); created = models.DateTimeField(auto_now_add=True)

class Dispute(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="disputes")
    leg_number = models.PositiveSmallIntegerField(null=True, blank=True)  # null = disputa é sobre o confronto único
    opened = models.DateTimeField(auto_now_add=True); resolved = models.BooleanField(default=False)
    resolution = models.TextField(blank=True)

class Registration(models.Model):
    """Pré-inscrição importada da planilha do evento (fora deste sistema). O check-in por telefone
    procura aqui os dados do jogador em vez de pedir um cadastro novo."""
    external_id = models.CharField(max_length=80, blank=True)
    jogo = models.CharField(max_length=60, blank=True)
    tipo = models.CharField(max_length=20, blank=True)  # individual | team
    nome = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    matricula = models.CharField(max_length=30, blank=True)
    vinculo = models.CharField(max_length=30, blank=True)  # student, staff...
    phone_raw = models.CharField(max_length=30, blank=True)
    phone_norm = models.CharField(max_length=15, db_index=True)  # só dígitos, sem DDI, usado na busca do check-in
    nick = models.CharField(max_length=60, blank=True)
    equipe = models.CharField(max_length=80, blank=True)  # clube/time escolhido
    nome_equipe = models.CharField(max_length=120, blank=True)  # nome da equipe (jogos em grupo)
    status = models.CharField(max_length=30, blank=True)
    perfil = models.CharField(max_length=40, blank=True)
    campus = models.CharField(max_length=120, blank=True)
    curso = models.CharField(max_length=120, blank=True)
    created_raw = models.CharField(max_length=40, blank=True)  # data de criação original, como veio na planilha
    checked_in = models.BooleanField(default=False)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    player = models.ForeignKey(Player, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    class Meta: ordering = ["-created_raw"]

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=30); text = models.CharField(max_length=250)
    read = models.BooleanField(default=False); created = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ["-created"]
