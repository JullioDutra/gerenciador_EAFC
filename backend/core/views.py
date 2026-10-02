import csv, io
from django.http import HttpResponse
from rest_framework import permissions, serializers, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from . import images, services as sv
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

def _reported_by(obj):  # quem lançou o placar (só uma pessoa valida); o outro jogador pode contestar
    return int(next(iter(obj.reports))) if obj.reports else None

class LegS(serializers.ModelSerializer):
    reported_by = serializers.SerializerMethodField()
    class Meta: model = Leg; fields = "__all__"
    def get_reported_by(self, l): return _reported_by(l)

class MatchS(serializers.ModelSerializer):
    legs = LegS(many=True, read_only=True)
    match_format = serializers.CharField(source="round.match_format", read_only=True)
    reported_by = serializers.SerializerMethodField()
    contestable = serializers.SerializerMethodField()
    class Meta: model = Match; fields = "__all__"
    def get_reported_by(self, m): return _reported_by(m)
    def get_contestable(self, m):
        return m.status == "confirmed" and m.round.season.rounds.last().id == m.round_id

def my_player(season, user):
    """Jogador do usuário neste campeonato; quem não participa só tem visualização."""
    p = Player.objects.filter(season=season, user=user).first()
    if p is None: raise PermissionError("Você não participa deste campeonato: aqui só dá para visualizar.")
    return p

def err(fn):
    try: return Response(fn())
    except (ValueError, PermissionError) as e: return Response({"detail": str(e)}, status=400)

class SeasonViewSet(viewsets.ModelViewSet):
    queryset = Season.objects.all(); serializer_class = SeasonS; permission_classes = [AdminOrReadOnly]
    @action(detail=False, permission_classes=[permissions.IsAuthenticated])
    def mine(self, req):  # campeonatos em que o usuário logado joga (o 1º acesso entra direto no seu, ou escolhe se forem vários)
        return Response([{**SeasonS(p.season).data, "player": p.id} for p in Player.objects.filter(user=req.user).select_related("season").order_by("-season_id")])
    @action(detail=True)
    def standings(self, req, pk=None):
        return Response([{**{k: v for k, v in r.items() if k != "player"}, "player": PlayerS(r["player"], context={"request": req}).data}
                         for r in sv.standings(self.get_object())])
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def advance(self, req, pk=None):
        """Gera a próxima rodada/fase. Opções (todas opcionais): count (rodadas de uma vez na liga/grupos), start (1º horário),
        round_gap_hours, slot_minutes, parallel, deadline_hours (prazo p/ lançar o placar)."""
        s, d = self.get_object(), req.data
        return err(lambda: RoundS(sv.advance(s, sv._num(d.get("count"), 1, "Rodadas", 1), sv.parse_schedule(s, d)), many=True).data)
    @action(detail=True, methods=["post"], url_path="draw-groups", permission_classes=[permissions.IsAdminUser])
    def draw_groups(self, req, pk=None):
        return err(lambda: PlayerS(sv.draw_groups(self.get_object()), many=True, context={"request": req}).data)
    @action(detail=True)
    def stats(self, req, pk=None):
        return Response(sv.stats(self.get_object()))
    @action(detail=True, methods=["get"], url_path="filter-values", permission_classes=[permissions.IsAdminUser])
    def filter_values(self, req, pk=None):
        return Response(sv.filter_values(self.get_object()))
    @action(detail=True, methods=["post"], url_path="import-from", permission_classes=[permissions.IsAdminUser])
    def import_from(self, req, pk=None):  # {"source": id, "filters": {"campus": "..."}, "top": N, "dry_run": true|false}
        s, d = self.get_object(), req.data
        def run():
            src = Season.objects.filter(pk=d.get("source")).first()
            if not src: raise ValueError("Escolha o campeonato de origem.")
            return sv.import_players_from(s, src, d.get("filters"), sv._num(d.get("top"), None, "Top", 1), d.get("dry_run", True) is not False)
        return err(run)
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
    def perform_update(self, serializer):
        old = serializer.instance.deadline; rd = serializer.save()
        if rd.deadline != old:  # novo prazo da rodada vale para as partidas que ainda seguiam o prazo antigo
            rd.matches.exclude(status__in=Match.DONE).filter(deadline=old).update(deadline=rd.deadline)
    @action(detail=True, methods=["get"], permission_classes=[permissions.IsAdminUser])
    def image(self, req, pk=None):
        """PNG com os confrontos da rodada (?group=N filtra um grupo, ?match=ID um confronto só) para mandar no grupo."""
        rd, p = self.get_object(), req.query_params
        ms = list(rd.matches.select_related("player_a", "player_b"))
        if p.get("match"): ms = [m for m in ms if str(m.id) == p["match"]]
        if p.get("group"): ms = [m for m in ms if str(m.player_a.group) == p["group"]]
        if not ms: return Response({"detail": "Nenhum confronto para gerar a imagem."}, status=404)
        season = rd.season; dl = max((m.deadline for m in ms if m.deadline), default=None)
        sub = f"{season.name} {season.year}" + (f" · Grupo {chr(64 + int(p['group']))}" if p.get("group") else "")
        png = images.render_matches(f"{rd.name} — {sv.PHASE_LABEL.get(rd.phase, rd.phase)}", sub, ms,
                                    show_groups=rd.phase == "groups" and not p.get("group"))
        resp = HttpResponse(png, content_type="image/png")
        resp["Content-Disposition"] = f'inline; filename="confrontos-rodada-{rd.number}.png"'
        return resp

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
    def report(self, req, pk=None):  # só uma pessoa valida: o placar enviado já fecha a partida; comprovante opcional
        m, d = self.get_object(), req.data
        return err(lambda: MatchS(sv.submit_result(m, my_player(m.round.season, req.user), int(d["score_a"]), int(d["score_b"]),
                                                   d.get("pen_a") or None, d.get("pen_b") or None,
                                                   req.FILES.get("proof"), str(d.get("et")).lower() == "true")).data)
    @action(detail=True, methods=["post"], url_path="set-result", permission_classes=[permissions.IsAdminUser])
    def set_result(self, req, pk=None):
        m, d = self.get_object(), req.data
        return err(lambda: (sv.admin_set_result(m, int(d["score_a"]), int(d["score_b"]), d.get("pen_a"), d.get("pen_b")),
                            MatchS(m).data)[1])
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def contest(self, req, pk=None):  # o jogador que não lançou o placar discorda: abre disputa para o admin
        m = self.get_object()
        return err(lambda: MatchS(sv.contest(m, my_player(m.round.season, req.user))).data)
    @action(detail=True, methods=["post"], url_path="extend-deadline", permission_classes=[permissions.IsAdminUser])
    def extend_deadline(self, req, pk=None):  # {"deadline": ISO} — só o admin libera mais tempo para lançar o placar
        m = self.get_object()
        return err(lambda: MatchS(sv.extend_deadline(m, req.data.get("deadline"))).data)
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def wo(self, req, pk=None):
        m = self.get_object(); w = Player.objects.get(pk=req.data["winner"])
        return err(lambda: (sv.apply_wo(m, w, req.data.get("reason", "")), MatchS(m).data)[1])
    @action(detail=True, methods=["post"], url_path="report-leg", permission_classes=[permissions.IsAuthenticated])
    def report_leg(self, req, pk=None):  # confronto de ida-e-volta / melhor-de-3/5: informa o jogo N
        m, d = self.get_object(), req.data
        return err(lambda: (sv.submit_leg_result(m, my_player(m.round.season, req.user), int(d["leg_number"]), int(d["score_a"]), int(d["score_b"]),
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

def _reg_data(reg, season):
    return {"id": reg.id, "jogo": reg.jogo, "equipe": reg.equipe, "campus": reg.campus, "curso": reg.curso,
            "already_checked_in": reg.checked_in, "nick": reg.nick,
            "season": {"id": season.id, "name": f"{season.name} {season.year}", "checkin_open": season.checkin_open} if season else None}

@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def checkin_lookup(req):  # {"phone": "..."} -> inscrições do telefone (uma por campeonato) para o jogador escolher onde fazer check-in
    try:
        opts = sv.checkin_options(req.data.get("phone", ""))
    except ValueError as e:
        return Response({"detail": str(e)}, status=404)
    reg = opts[0][0]
    return Response({"nome": reg.nome, "nick": reg.nick, "equipe": reg.equipe, "campus": reg.campus,
                      "curso": reg.curso, "jogo": reg.jogo, "already_checked_in": reg.checked_in,
                      "registrations": [_reg_data(r, s) for r, s in opts]})

@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def checkin_confirm(req):  # {"phone", "registrations": [ids] (vazio = todas), "season": id (opcional, só de reserva)}
    try:
        fallback = Season.objects.filter(pk=req.data.get("season")).first()
        done = sv.checkin_confirm(req.data.get("phone", ""), fallback, req.data.get("registrations") or None)
    except ValueError as e:
        return Response({"detail": str(e)}, status=400)
    player, reg = done[0]
    token, _ = Token.objects.get_or_create(user=player.user)
    return Response({"token": token.key, "player": PlayerS(player, context={"request": req}).data, "campus": reg.campus,
                     "seasons": [p.season_id for p, _ in done], "players": PlayerS([p for p, _ in done], many=True, context={"request": req}).data})

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
    p = Player.objects.filter(season_id=season_id, user=req.user).select_related("season").first()
    if p is None: return Response({"detail": "Você não participa deste campeonato."}, status=404)
    s = p.season
    row = next(r for r in sv.standings(s) if r["player"].id == p.id)
    mine = (Match.objects.filter(round__season=s, player_a=p) | Match.objects.filter(round__season=s, player_b=p)).distinct()
    done = mine.filter(status__in=Match.DONE)
    nxt = mine.exclude(status__in=Match.DONE).first(); last = done.last()
    return Response({"player": PlayerS(p, context={"request": req}).data, "group": row["group"], "format": sv.cfg(s)["format"], "position": row["pos"], "zone": row["zone"], "points": row["pts"],
        "record": [row["v"], row["e"], row["d"]], "gf": row["gp"], "ga": row["gc"], "gd": row["sg"],
        "next_match": MatchS(nxt).data if nxt else None, "last_match": MatchS(last).data if last else None,
        "history": MatchS(done, many=True).data})
