import csv, io
from rest_framework import permissions, serializers, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from . import services as sv
from .models import *

class AdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, req, view): return req.method in permissions.SAFE_METHODS or req.user.is_staff

def ser(model):
    return type(model.__name__ + "S", (serializers.ModelSerializer,),
                {"Meta": type("Meta", (), {"model": model, "fields": "__all__"})})
SeasonS, RoundS, PenaltyS, NotificationS, DisputeS = (ser(m) for m in (Season, Round, Penalty, Notification, Dispute))

class PlayerS(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()
    class Meta: model = Player; fields = "__all__"
    def get_avatar_url(self, p):
        if p.avatar_file:
            req = self.context.get("request")
            return req.build_absolute_uri(p.avatar_file.url) if req else p.avatar_file.url
        return p.avatar or None

class LegS(serializers.ModelSerializer):
    class Meta: model = Leg; fields = "__all__"

class MatchS(serializers.ModelSerializer):
    legs = LegS(many=True, read_only=True)
    match_format = serializers.CharField(source="round.match_format", read_only=True)
    class Meta: model = Match; fields = "__all__"

def err(fn):
    try: return Response(fn())
    except (ValueError, PermissionError) as e: return Response({"detail": str(e)}, status=400)

class SeasonViewSet(viewsets.ModelViewSet):
    queryset = Season.objects.all(); serializer_class = SeasonS; permission_classes = [AdminOrReadOnly]
    @action(detail=True)
    def standings(self, req, pk=None):
        return Response([{**{k: v for k, v in r.items() if k != "player"}, "player": PlayerS(r["player"], context={"request": req}).data}
                         for r in sv.standings(self.get_object())])
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def advance(self, req, pk=None):
        return err(lambda: RoundS(sv.advance(self.get_object())).data)
    @action(detail=True)
    def stats(self, req, pk=None):
        return Response(sv.stats(self.get_object()))
    @action(detail=True, methods=["post"], url_path="import-csv", permission_classes=[permissions.IsAdminUser])
    def import_csv(self, req, pk=None):  # colunas: email,name,nickname,ea_id,platform,country
        s = self.get_object(); n = 0
        for row in csv.DictReader(io.StringIO(req.FILES["file"].read().decode("utf-8-sig"))):
            u, _ = User.objects.get_or_create(email=row["email"].strip().lower())
            Player.objects.get_or_create(season=s, user=u, defaults={k: row.get(k, "") for k in
                ("name", "nickname", "ea_id", "platform", "country")}); n += 1
        return Response({"imported": n})

class DisputeViewSet(viewsets.ReadOnlyModelViewSet):
    """Disputas em aberto para o admin resolver: leg_number=null é o confronto inteiro (formato 'single')."""
    serializer_class = DisputeS; permission_classes = [permissions.IsAdminUser]
    def get_queryset(self):
        q, p = Dispute.objects.select_related("match").all(), self.request.query_params
        if p.get("season"): q = q.filter(match__round__season=p["season"])
        if p.get("resolved") is not None: q = q.filter(resolved=p["resolved"] == "true")
        return q

class RoundViewSet(viewsets.ModelViewSet):
    serializer_class = RoundS; permission_classes = [AdminOrReadOnly]  # admin pode editar prazo/formato
    def get_queryset(self):
        q = Round.objects.all(); sid = self.request.query_params.get("season")
        return q.filter(season=sid) if sid else q

class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationS; permission_classes = [permissions.IsAuthenticated]
    def get_queryset(self): return Notification.objects.filter(user=self.request.user)
    @action(detail=True, methods=["post"])
    def read(self, req, pk=None):
        n = self.get_object(); n.read = True; n.save(); return Response(NotificationS(n).data)
    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, req):
        self.get_queryset().update(read=True); return Response({"ok": True})

class PlayerViewSet(viewsets.ModelViewSet):
    queryset = Player.objects.all(); serializer_class = PlayerS; permission_classes = [AdminOrReadOnly]
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def penalty(self, req, pk=None):  # {"points": -3, "reason": "..."}  positivo = bônus, negativo = punição
        pt = Penalty.objects.create(player=self.get_object(), points=int(req.data["points"]), reason=req.data.get("reason", ""))
        sv.notify(pt.player, "penalty", f"Ajuste de pontos aplicado: {pt.points:+d} ({pt.reason})")
        return Response(PenaltyS(pt).data, status=201)
    @action(detail=True, methods=["patch"], permission_classes=[permissions.IsAuthenticated])
    def profile(self, req, pk=None):  # o próprio jogador edita nome, nickname, EA ID, plataforma, país e avatar (URL ou upload)
        p = self.get_object()
        if p.user_id != req.user.id: return Response({"detail": "Você só pode editar seu próprio perfil."}, status=403)
        updated = sv.update_profile(p, req.data, req.FILES.get("avatar_file"))
        return Response(PlayerS(updated, context={"request": req}).data)

class MatchViewSet(viewsets.ModelViewSet):
    serializer_class = MatchS; permission_classes = [AdminOrReadOnly]
    def get_queryset(self):
        q, p = Match.objects.all(), self.request.query_params
        for key, f in (("season", "round__season"), ("round", "round"), ("status", "status")):
            if p.get(key): q = q.filter(**{f: p[key]})
        return q
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def report(self, req, pk=None):  # também confirma: o adversário envia o mesmo placar; comprovante opcional
        m, d = self.get_object(), req.data
        me_ = Player.objects.get(season=m.round.season, user=req.user)
        return err(lambda: MatchS(sv.submit_result(m, me_, int(d["score_a"]), int(d["score_b"]),
                                                   d.get("pen_a") or None, d.get("pen_b") or None,
                                                   req.FILES.get("proof"), str(d.get("et")).lower() == "true")).data)
    @action(detail=True, methods=["post"], url_path="set-result", permission_classes=[permissions.IsAdminUser])
    def set_result(self, req, pk=None):
        m, d = self.get_object(), req.data
        return err(lambda: (sv.admin_set_result(m, int(d["score_a"]), int(d["score_b"]), d.get("pen_a"), d.get("pen_b")),
                            MatchS(m).data)[1])
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def wo(self, req, pk=None):
        m = self.get_object(); w = Player.objects.get(pk=req.data["winner"])
        return err(lambda: (sv.apply_wo(m, w, req.data.get("reason", "")), MatchS(m).data)[1])
    @action(detail=True, methods=["post"], url_path="report-leg", permission_classes=[permissions.IsAuthenticated])
    def report_leg(self, req, pk=None):  # confronto de ida-e-volta / melhor-de-3/5: informa o jogo N
        m, d = self.get_object(), req.data
        me_ = Player.objects.get(season=m.round.season, user=req.user)
        return err(lambda: (sv.submit_leg_result(m, me_, int(d["leg_number"]), int(d["score_a"]), int(d["score_b"]),
                                                 d.get("pen_a") or None, d.get("pen_b") or None, req.FILES.get("proof"),
                                                 str(d.get("et")).lower() == "true"),
                            MatchS(m).data)[1])
    @action(detail=True, methods=["post"], url_path="set-leg-result", permission_classes=[permissions.IsAdminUser])
    def set_leg_result(self, req, pk=None):
        m, d = self.get_object(), req.data
        return err(lambda: (sv.admin_set_leg_result(m, int(d["leg_number"]), int(d["score_a"]), int(d["score_b"]),
                                                    d.get("pen_a"), d.get("pen_b")), MatchS(m).data)[1])

@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def register(req):
    u = User.objects.create_user(req.data["email"], req.data["password"]); return Response({"id": u.id}, status=201)

class RegistrationS(serializers.ModelSerializer):
    class Meta: model = Registration; fields = "__all__"

@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def checkin_lookup(req):  # {"phone": "..."} -> dados da pré-inscrição, para o jogador conferir antes de confirmar
    try:
        reg = sv.checkin_lookup(req.data.get("phone", ""))
    except ValueError as e:
        return Response({"detail": str(e)}, status=404)
    return Response({"nome": reg.nome, "nick": reg.nick, "equipe": reg.equipe, "campus": reg.campus,
                      "curso": reg.curso, "jogo": reg.jogo, "already_checked_in": reg.checked_in})

@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def checkin_confirm(req):  # {"phone": "...", "season": id} -> cria/liga o jogador e já devolve o token de acesso
    try:
        season = Season.objects.get(pk=req.data.get("season"))
        player, reg = sv.checkin_confirm(req.data.get("phone", ""), season)
    except (ValueError, Season.DoesNotExist) as e:
        return Response({"detail": str(e) or "Temporada inválida."}, status=400)
    token, _ = Token.objects.get_or_create(user=player.user)
    return Response({"token": token.key, "player": PlayerS(player, context={"request": req}).data, "campus": reg.campus})

@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def import_registrations(req):  # multipart: file=<xlsx>, sheet=<nome da aba, opcional>
    try:
        n = sv.import_registrations(req.FILES["file"], req.data.get("sheet", "ea-sports-fc-26"))
    except ValueError as e:
        return Response({"detail": str(e)}, status=400)
    return Response({"imported": n})

@api_view(["GET"])
def me(req, season_id):
    p = Player.objects.get(season_id=season_id, user=req.user); s = p.season
    row = next(r for r in sv.standings(s) if r["player"].id == p.id)
    mine = (Match.objects.filter(round__season=s, player_a=p) | Match.objects.filter(round__season=s, player_b=p)).distinct()
    done = mine.filter(status__in=Match.DONE)
    nxt = mine.exclude(status__in=Match.DONE).first(); last = done.last()
    return Response({"player": PlayerS(p, context={"request": req}).data, "position": row["pos"], "zone": row["zone"], "points": row["pts"],
        "record": [row["v"], row["e"], row["d"]], "gf": row["gp"], "ga": row["gc"], "gd": row["sg"],
        "next_match": MatchS(nxt).data if nxt else None, "last_match": MatchS(last).data if last else None,
        "history": MatchS(done, many=True).data})
