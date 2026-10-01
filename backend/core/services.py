import re
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .models import Dispute, Leg, Match, Notification, Player, Registration, Round, User

DEFAULTS = {"swiss_rounds": 8, "win": 3, "draw": 1, "loss": 0, "direct": 16, "playoff_size": 48,
    "playoff_qualify": 16, "tiebreakers": ["pts", "gd", "gf", "wins"],  # + ga, buchholz
    "wo_score": [3, 0], "round_days": 7, "ko_format": "single",
    "extra_time": True, "penalties": True}  # usados apenas para exibição/orientação da prorrogação
LEGS_TO_WIN = {"bo3": 2, "bo5": 3, "two_legs": 2}
FORMAT_LABEL = {"single": "Partida única", "bo3": "Melhor de 3", "bo5": "Melhor de 5", "two_legs": "Ida e volta"}
def cfg(season): return {**DEFAULTS, **season.config}

def notify(player, kind, text):
    if player: Notification.objects.create(user=player.user, kind=kind, text=text)

def standings(season):
    c = cfg(season)
    rows = {p.id: dict(player=p, j=0, v=0, e=0, d=0, gp=0, gc=0, pts=0, opps=[]) for p in season.players.all()}
    for m in Match.objects.filter(round__season=season, round__phase="swiss", status__in=Match.DONE):
        pairs = [(m.player_a_id, m.player_b_id, m.score_a, m.score_b)]
        if m.player_b_id: pairs.append((m.player_b_id, m.player_a_id, m.score_b, m.score_a))
        for pid, oid, gf, ga in pairs:
            r = rows[pid]; r["j"] += 1; r["gp"] += gf; r["gc"] += ga
            if oid: r["opps"].append(oid)
            k, pts = ("v", c["win"]) if gf > ga else ("d", c["loss"]) if gf < ga else ("e", c["draw"])
            r[k] += 1; r["pts"] += pts
    for r in rows.values():
        r["pts"] += sum(x.points for x in r["player"].penalties.all())
        r["sg"] = r["gp"] - r["gc"]
    val = {"pts": lambda r: r["pts"], "gd": lambda r: r["sg"], "gf": lambda r: r["gp"],
           "wins": lambda r: r["v"], "ga": lambda r: -r["gc"],
           "buchholz": lambda r: sum(rows[o]["pts"] for o in r["opps"])}
    out = sorted(rows.values(), key=lambda r: tuple(-val[k](r) for k in c["tiebreakers"]) + (r["player"].id,))
    for i, r in enumerate(out, 1):
        r["pos"] = i; r["zone"] = "direct" if i <= c["direct"] else \
            "playoff" if i <= c["direct"] + c["playoff_size"] else "out"
        del r["opps"]
    return out

def _pair(order, played):
    if not order: return []
    a, rest = order[0], order[1:]
    for i, b in enumerate(rest):
        if b not in played[a]:
            sub = _pair(rest[:i] + rest[i + 1:], played)
            if sub is not None: return [(a, b)] + sub
    return None

def _new_round(season, phase, name, pairs):
    c = cfg(season); n = (season.rounds.last().number + 1) if season.rounds.exists() else 1
    dl = timezone.now() + timedelta(days=c["round_days"])
    rd = Round.objects.create(season=season, phase=phase, number=n, name=name, deadline=dl,
                              match_format="single" if phase == "swiss" else c["ko_format"])
    for i, (a, b) in enumerate(pairs, 1):
        m = Match.objects.create(round=rd, slot=i, player_a=a, player_b=b, deadline=dl)
        if b is None:  # bye = vitória automática
            m.score_a, m.score_b, m.winner, m.status = c["wo_score"][0], c["wo_score"][1], a, "wo"; m.save()
        for p in (a, b): notify(p, "new_opponent", f"{name}: novo confronto disponível.")
    return rd

def _open(season):
    return Match.objects.filter(round__season=season).exclude(status__in=Match.DONE).exists()

@transaction.atomic
def generate_swiss_round(season):
    c = cfg(season)
    if _open(season): raise ValueError("Há partidas pendentes na rodada atual.")
    done = season.rounds.filter(phase="swiss").count()
    if done >= c["swiss_rounds"]: raise ValueError("Fase Swiss já concluída.")
    rank = [r["player"] for r in standings(season) if r["player"].status != "blocked"]
    played = {p.id: set() for p in rank}
    for m in Match.objects.filter(round__season=season, round__phase="swiss"):
        if m.player_b_id: played[m.player_a_id].add(m.player_b_id); played[m.player_b_id].add(m.player_a_id)
    bye = rank.pop() if len(rank) % 2 else None
    ids = [p.id for p in rank]; by = {p.id: p for p in rank}
    res = _pair(ids, played)
    if res is None: res = _pair(ids, {i: set() for i in ids})  # último recurso: permite repetição
    pairs = [(by[a], by[b]) for a, b in res] + ([(bye, None)] if bye else [])
    return _new_round(season, "swiss", f"Rodada {done + 1}", pairs)

def finalize(m, status="confirmed"):
    if m.score_a > m.score_b: m.winner = m.player_a
    elif m.score_b > m.score_a: m.winner = m.player_b
    elif m.pen_a is not None and m.pen_a != m.pen_b: m.winner = m.player_a if m.pen_a > m.pen_b else m.player_b
    elif m.round.phase == "swiss": m.winner = None
    else: raise ValueError("Mata-mata não pode terminar empatado: informe os pênaltis.")
    m.status = status; m.save(); m.disputes.update(resolved=True)
    for p in (m.player_a, m.player_b): notify(p, "result_confirmed", f"Resultado confirmado: {m.score_a} x {m.score_b}.")

@transaction.atomic
def submit_result(m, player, sa, sb, pa=None, pb=None, proof=None, et=False):
    if m.status in Match.DONE: raise ValueError("Partida já finalizada.")
    if player.id not in (m.player_a_id, m.player_b_id): raise PermissionError("Você não joga esta partida.")
    if et: m.extra_time = True
    if proof is not None:
        if player.id == m.player_a_id: m.proof_a = proof
        else: m.proof_b = proof
    m.reports[str(player.id)] = [sa, sb, pa, pb]  # sempre no formato A x B
    other = m.player_b if player.id == m.player_a_id else m.player_a
    theirs = m.reports.get(str(other.id))
    if not theirs:
        m.status = "awaiting"; m.save(); notify(other, "result_sent", "Seu adversário enviou um resultado. Confirme.")
    elif theirs == m.reports[str(player.id)]:
        m.score_a, m.score_b, m.pen_a, m.pen_b = sa, sb, pa, pb; finalize(m)
    else:
        m.status = "disputed"; m.save(); Dispute.objects.create(match=m)
        for p in (m.player_a, m.player_b): notify(p, "disputed", "Resultados divergentes: disputa aberta.")
    return m

@transaction.atomic
def admin_set_result(m, sa, sb, pa=None, pb=None):
    m.score_a, m.score_b, m.pen_a, m.pen_b = sa, sb, pa, pb; finalize(m, "resolved")

@transaction.atomic
def apply_wo(m, winner, reason):
    w, l = cfg(m.round.season)["wo_score"]
    m.score_a, m.score_b = (w, l) if winner.id == m.player_a_id else (l, w)
    m.winner, m.status, m.wo_reason = winner, "wo", reason; m.save()

PHASE_DEPTH = {"swiss": 0, "playoff1": 1, "playoff2": 2, "r32": 3, "r16": 4, "qf": 5, "sf": 6, "final": 7}
PHASE_LABEL = {"swiss": "Fase de grupos", "playoff1": "Playoff — Fase 1", "playoff2": "Playoff — Fase 2",
    "r32": "32-avos", "r16": "Oitavas", "qf": "Quartas", "sf": "Semifinal", "final": "Final", "champion": "Campeão"}

def stats(season):
    ms = list(Match.objects.filter(round__season=season, status__in=Match.DONE).select_related("round"))
    per = {p.id: dict(player=p, played=0, wins=0, goals=0, best_streak=0, cur_streak=0,
                       unbeaten=0, cur_unbeaten=0, deepest="swiss") for p in season.players.all()}
    total_goals = total_matches = 0
    for m in sorted(ms, key=lambda x: (x.round.number, x.slot)):
        pairs = [(m.player_a_id, m.score_a, m.score_b)]
        if m.player_b_id: pairs.append((m.player_b_id, m.score_b, m.score_a))
        total_matches += 1; total_goals += (m.score_a or 0) + (m.score_b or 0)
        for pid, gf, ga in pairs:
            r = per[pid]; r["played"] += 1; r["goals"] += gf
            if PHASE_DEPTH[m.round.phase] >= PHASE_DEPTH[r["deepest"]]: r["deepest"] = m.round.phase
            if gf > ga: r["wins"] += 1; r["cur_streak"] += 1; r["cur_unbeaten"] += 1
            elif gf == ga: r["cur_streak"] = 0; r["cur_unbeaten"] += 1
            else: r["cur_streak"] = 0; r["cur_unbeaten"] = 0
            r["best_streak"] = max(r["best_streak"], r["cur_streak"]); r["unbeaten"] = max(r["unbeaten"], r["cur_unbeaten"])
    for p in per.values():
        if season.champion_id == p["player"].id: p["deepest"] = "champion"
    top = lambda key: max(per.values(), key=lambda r: r[key]) if per else None
    pick = lambda r: r and {"player": PlayerRef(r["player"]), **{k: r[k] for k in
        ("played", "wins", "goals", "best_streak", "unbeaten")}, "deepest": PHASE_LABEL[r["deepest"]]}
    return {
        "most_wins": pick(top("wins")), "most_goals": pick(top("goals")),
        "best_diff": pick(max(per.values(), key=lambda r: r["goals"] - _conceded(ms, r["player"].id)) if per else None),
        "most_played": pick(top("played")), "longest_win_streak": pick(top("best_streak")),
        "longest_unbeaten": pick(top("unbeaten")), "best_campaign": pick(max(per.values(), key=lambda r: PHASE_DEPTH.get(r["deepest"], PHASE_DEPTH["swiss"])) if per else None),
        "total_matches": total_matches, "total_goals": total_goals,
        "avg_goals_per_match": round(total_goals / total_matches, 2) if total_matches else 0,
    }
def _conceded(ms, pid):
    return sum((m.score_b if m.player_a_id == pid else m.score_a) or 0 for m in ms if pid in (m.player_a_id, m.player_b_id))
def PlayerRef(p): return {"id": p.id, "nickname": p.nickname, "name": p.name}

PROFILE_FIELDS = ("name", "nickname", "ea_id", "platform", "country", "avatar")

def normalize_phone(raw):
    """Só dígitos; remove o 55 (DDI Brasil) quando o número tem DDD + 9 dígitos + DDI (13 dígitos)."""
    digits = re.sub(r"\D", "", str(raw or ""))
    if len(digits) >= 12 and digits.startswith("55"): digits = digits[2:]
    return digits

REG_COLUMNS = {  # cabeçalho da planilha -> campo do Registration
    "ID": "external_id", "Data de Criação": "created_raw", "Jogo": "jogo", "Tipo de Inscrição": "tipo",
    "Nome do Líder": "nome", "Email do Líder": "email", "Matrícula do Líder": "matricula",
    "Vínculo do Líder": "vinculo", "Telefone do Líder": "phone_raw", "Nick do Líder no Jogo": "nick",
    "Liga Selecionada": None, "Equipe Selecionada": "equipe", "Nome da Equipe": "nome_equipe",
    "Status": "status", "Perfil": "perfil", "Campus/Mantida": "campus", "Curso": "curso",
}

def _cell_str(val):
    """Excel guarda números (telefone, matrícula) como float; sem isso vira '62992743475.0'."""
    if isinstance(val, float) and val.is_integer(): return str(int(val))
    return str(val).strip()

def import_registrations(fileobj, sheet_name="ea-sports-fc-26"):
    import openpyxl
    wb = openpyxl.load_workbook(fileobj, data_only=True, read_only=True)
    if sheet_name not in wb.sheetnames:
        raise ValueError(f"Aba '{sheet_name}' não encontrada. Abas disponíveis: {', '.join(wb.sheetnames)}")
    ws = wb[sheet_name]
    rows = ws.iter_rows(values_only=True)
    headers = next(rows)
    n = 0
    for row in rows:
        d = dict(zip(headers, row))
        if not any(d.values()): continue
        fields = {}
        for col, val in d.items():
            key = REG_COLUMNS.get(col)
            if not key or val is None: continue
            fields[key] = _cell_str(val)
        phone = fields.pop("phone_raw", "")
        fields["phone_raw"] = phone; fields["phone_norm"] = normalize_phone(phone)
        if not fields.get("nome") or not fields["phone_norm"]: continue
        ext = fields.get("external_id")
        if ext:
            Registration.objects.update_or_create(external_id=ext, defaults=fields)
        else:
            Registration.objects.update_or_create(phone_norm=fields["phone_norm"], jogo=fields.get("jogo", ""), defaults=fields)
        n += 1
    return n

def checkin_lookup(phone):
    norm = normalize_phone(phone)
    if not norm: raise ValueError("Informe um telefone válido.")
    reg = Registration.objects.filter(phone_norm=norm).order_by("-created_raw").first()
    if not reg: raise ValueError("Não encontramos nenhuma inscrição com esse telefone.")
    return reg

@transaction.atomic
def checkin_confirm(phone, season):
    reg = checkin_lookup(phone)
    if reg.player_id and reg.player.season_id == season.id:
        return reg.player, reg  # já fez check-in nesta temporada: só reloga
    email = reg.email or f"{reg.phone_norm}@checkin.fc26"
    user, _ = User.objects.get_or_create(email=email)
    first_name = (reg.nome.split() or [reg.nome])[0]
    player, created = Player.objects.get_or_create(season=season, user=user, defaults={
        "name": reg.nome, "nickname": reg.nick or first_name, "team": reg.equipe,
        "campus": reg.campus, "ea_id": reg.nick or "",
    })
    if not created:  # já existia (ex.: reimportação): mantém o que o jogador já tiver editado, só completa o que faltar
        changed = False
        for f, v in (("team", reg.equipe), ("campus", reg.campus)):
            if not getattr(player, f) and v: setattr(player, f, v); changed = True
        if changed: player.save()
    reg.player = player; reg.checked_in = True; reg.checked_in_at = timezone.now(); reg.save()
    return player, reg

def update_profile(player, data, avatar_file=None):
    for f in PROFILE_FIELDS:
        if f in data: setattr(player, f, data[f])
    if avatar_file is not None: player.avatar_file = avatar_file
    player.save(); return player

def _decide(sa, sb, pa, pb):
    """Retorna 'a', 'b' ou None (empate sem pênaltis informados ainda)."""
    if sa != sb: return "a" if sa > sb else "b"
    if pa is not None and pb is not None and pa != pb: return "a" if pa > pb else "b"
    return None

@transaction.atomic
def submit_leg_result(match, player, leg_number, sa, sb, pa=None, pb=None, proof=None, et=False):
    if match.status in Match.DONE: raise ValueError("Confronto já finalizado.")
    if player.id not in (match.player_a_id, match.player_b_id): raise PermissionError("Você não joga esta partida.")
    leg, _ = Leg.objects.get_or_create(match=match, number=leg_number)
    if leg.status in Match.DONE: raise ValueError("Este jogo já foi finalizado.")
    if et: leg.extra_time = True
    if proof is not None:
        if player.id == match.player_a_id: leg.proof_a = proof
        else: leg.proof_b = proof
    leg.reports[str(player.id)] = [sa, sb, pa, pb]
    other = match.player_b if player.id == match.player_a_id else match.player_a
    theirs = leg.reports.get(str(other.id))
    if not theirs:
        leg.status = "awaiting"; leg.save(); notify(other, "result_sent", f"Seu adversário enviou o placar do jogo {leg_number}. Confirme.")
        return leg
    if theirs != leg.reports[str(player.id)]:
        leg.status = "disputed"; leg.save()
        Dispute.objects.create(match=match, leg_number=leg_number)
        for p in (match.player_a, match.player_b): notify(p, "disputed", f"Placares divergentes no jogo {leg_number}: disputa aberta.")
        return leg
    if _decide(sa, sb, pa, pb) is None:
        raise ValueError("Jogo empatado: inclua o resultado dos pênaltis ao reenviar.")  # a transação é desfeita; reenviem com pênaltis
    leg.score_a, leg.score_b, leg.pen_a, leg.pen_b = sa, sb, pa, pb; leg.status = "confirmed"; leg.save()
    advance_series(match)
    return leg

@transaction.atomic
def admin_set_leg_result(match, leg_number, sa, sb, pa=None, pb=None):
    leg, _ = Leg.objects.get_or_create(match=match, number=leg_number)
    leg.score_a, leg.score_b, leg.pen_a, leg.pen_b = sa, sb, pa, pb; leg.status = "resolved"; leg.save()
    match.disputes.filter(leg_number=leg_number).update(resolved=True)
    advance_series(match)

def advance_series(match):
    fmt = match.round.match_format
    legs = list(match.legs.filter(status__in=Match.DONE).order_by("number"))
    if fmt == "two_legs":
        if len(legs) < 2: return
        agg_a = sum(l.score_a for l in legs); agg_b = sum(l.score_b for l in legs)
        d = _decide(agg_a, agg_b, legs[-1].pen_a, legs[-1].pen_b)
        if d is None: raise ValueError("Agregado empatado: informe os pênaltis do jogo decisivo.")
        match.score_a, match.score_b = agg_a, agg_b
        match.winner = match.player_a if d == "a" else match.player_b
    else:  # bo3 / bo5
        need = LEGS_TO_WIN.get(fmt, 1)
        wins_a = sum(1 for l in legs if _decide(l.score_a, l.score_b, l.pen_a, l.pen_b) == "a")
        wins_b = len(legs) - wins_a
        if wins_a < need and wins_b < need:
            match.score_a, match.score_b = wins_a, wins_b; match.save(); return  # série continua
        match.score_a, match.score_b = wins_a, wins_b
        match.winner = match.player_a if wins_a >= need else match.player_b
    match.status = "confirmed"; match.save()
    for p in (match.player_a, match.player_b): notify(p, "result_confirmed", f"Confronto decidido: {match.score_a} x {match.score_b}.")

def _winners(season, phase):
    return [m.winner for m in season.rounds.filter(phase=phase).last().matches.order_by("slot")]

def _flag(players, status): Player.objects.filter(id__in=[p.id for p in players]).update(status=status)

def _playoff_split(rank, c):
    pool = rank[c["direct"]:c["direct"] + c["playoff_size"]]
    n_low = 2 * (c["playoff_size"] - c["playoff_qualify"])  # 32 piores jogam a fase 1
    return pool, pool[:len(pool) - n_low], pool[len(pool) - n_low:]  # pool, upper (entram depois), lower

@transaction.atomic
def advance(season):
    """Avança para a próxima fase/rodada quando tudo está confirmado."""
    c = cfg(season)
    if _open(season): raise ValueError("Existem partidas sem resultado confirmado.")
    last = season.rounds.last()
    if last is None or (last.phase == "swiss" and season.rounds.filter(phase="swiss").count() < c["swiss_rounds"]):
        return generate_swiss_round(season)
    rank = [r["player"] for r in standings(season)]; d = c["direct"]
    if last.phase == "swiss":
        pool, upper, lower = _playoff_split(rank, c)
        _flag(rank[d + c["playoff_size"]:], "eliminated"); _flag(rank[:d], "main"); _flag(pool, "playoff")
        return _new_round(season, "playoff1", "Playoff — Fase 1", [(lower[i], lower[-1 - i]) for i in range(len(lower) // 2)])
    if last.phase == "playoff1":
        _, upper, _ = _playoff_split(rank, c)
        w = sorted(_winners(season, "playoff1"), key=rank.index)
        return _new_round(season, "playoff2", "Playoff — Fase 2", [(upper[i], w[-1 - i]) for i in range(len(upper))])
    if last.phase == "playoff2":
        pool = _playoff_split(rank, c)[0]
        q = sorted(_winners(season, "playoff2"), key=rank.index); _flag(q, "main")
        _flag([p for p in pool if p not in q], "eliminated"); top = rank[:d]
        return _new_round(season, "r32", "32-avos", [(top[i], q[-1 - i]) for i in range(len(top))])
    if last.phase == "final":
        champ = last.matches.first().winner; season.champion = champ; season.save()
        Player.objects.filter(id=champ.id).update(status="champion"); return last
    order = Round.PHASES[3:]; names = {"r16": "Oitavas", "qf": "Quartas", "sf": "Semifinal", "final": "Final"}
    nxt = order[order.index(last.phase) + 1]; w = _winners(season, last.phase)
    losers = [m.player_b if m.winner_id == m.player_a_id else m.player_a for m in last.matches.all()]
    _flag(losers, "eliminated")
    for p in losers: notify(p, "eliminated", "Você foi eliminado.")
    return _new_round(season, nxt, names[nxt], [(w[i], w[i + 1]) for i in range(0, len(w), 2)])
