import random
import re
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .models import Dispute, Leg, Match, Notification, Player, Registration, Round, Season, User

DEFAULTS = {"swiss_rounds": 8, "win": 3, "draw": 1, "loss": 0, "direct": 16, "playoff_size": 48,
    "playoff_qualify": 16, "tiebreakers": ["pts", "gd", "gf", "wins"],  # + ga, buchholz
    "wo_score": [3, 0], "round_days": 7, "ko_format": "single",
    "extra_time": True, "penalties": True,  # usados apenas para exibição/orientação da prorrogação
    "format": "league",  # "league" (fase de liga/Swiss, padrão) ou "groups" (fase de grupos todos-contra-todos)
    "groups": 4, "group_qualify": 2,  # só para format="groups": nº de grupos e quantos de cada grupo avançam
    "score_deadline_hours": None}  # prazo p/ lançar o placar depois do horário da partida (None = round_days)
LEAGUE_PHASES = ("swiss", "groups")  # fases que valem pontos na classificação
KO_BY_SIZE = {32: "r32", 16: "r16", 8: "qf", 4: "sf", 2: "final"}
LEGS_TO_WIN = {"bo3": 2, "bo5": 3, "two_legs": 2}
FORMAT_LABEL = {"single": "Partida única", "bo3": "Melhor de 3", "bo5": "Melhor de 5", "two_legs": "Ida e volta"}
def cfg(season): return {**DEFAULTS, **season.config}
def is_groups(season): return cfg(season)["format"] == "groups"

def notify(player, kind, text):
    if player: Notification.objects.create(user=player.user, kind=kind, text=text)

def standings(season):
    c = cfg(season)
    rows = {p.id: dict(player=p, j=0, v=0, e=0, d=0, gp=0, gc=0, pts=0, opps=[]) for p in season.players.all()}
    for m in Match.objects.filter(round__season=season, round__phase__in=LEAGUE_PHASES, status__in=Match.DONE):
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
    groups = c["format"] == "groups"  # em grupos a tabela é separada por grupo e a posição vale dentro dele
    out = sorted(rows.values(), key=lambda r: ((r["player"].group or 0) if groups else 0,)
                 + tuple(-val[k](r) for k in c["tiebreakers"]) + (r["player"].id,))
    seen = {}
    for i, r in enumerate(out, 1):
        g = r["player"].group if groups else None; seen[g] = seen.get(g, 0) + 1; pos = seen[g] if groups else i
        r["pos"] = pos; r["group"] = g
        if groups: r["zone"] = "direct" if pos <= c["group_qualify"] else "out"
        else: r["zone"] = "direct" if pos <= c["direct"] else "playoff" if pos <= c["direct"] + c["playoff_size"] else "out"
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

def _aware(v):
    """Aceita datetime ou string ISO (vinda do front); devolve datetime com fuso ou None."""
    if not v: return None
    if isinstance(v, str):
        v = parse_datetime(v)
        if v is None: raise ValueError("Data/hora inválida.")
    return timezone.make_aware(v) if timezone.is_naive(v) else v

def _num(v, default, name, lo=0):
    if v in (None, ""): return default
    try: n = int(v)
    except (TypeError, ValueError): raise ValueError(f"Valor inválido em {name}.")
    if n < lo: raise ValueError(f"{name} deve ser pelo menos {lo}.")
    return n

def parse_schedule(season, data):
    """Opções de agendamento vindas do admin: start (1º jogo), round_gap_hours (entre rodadas do lote),
    slot_minutes + parallel (escalonar jogos dentro da rodada) e deadline_hours (prazo p/ lançar o placar)."""
    c = cfg(season); data = data or {}
    hours = c["score_deadline_hours"] or c["round_days"] * 24
    return {"start": _aware(data.get("start")),
            "round_gap_hours": _num(data.get("round_gap_hours"), c["round_days"] * 24, "Intervalo entre rodadas"),
            "slot_minutes": _num(data.get("slot_minutes"), 0, "Intervalo entre jogos"),
            "parallel": _num(data.get("parallel"), 0, "Jogos simultâneos"),
            "deadline_hours": _num(data.get("deadline_hours"), hours, "Prazo do placar", 1)}

def _new_round(season, phase, name, pairs, sched=None, batch_index=0):
    sched = sched or parse_schedule(season, {})
    n = (season.rounds.last().number + 1) if season.rounds.exists() else 1
    base = sched["start"]; has_time = base is not None
    if has_time: base = base + timedelta(hours=sched["round_gap_hours"] * batch_index)
    rd = Round.objects.create(season=season, phase=phase, number=n, name=name,
                              match_format="single" if phase in LEAGUE_PHASES else cfg(season)["ko_format"])
    if phase == "groups": pairs = [(a, b) for a, b in pairs if b is not None]  # rodízio: quem folga não ganha WO
    last_dl = None; parallel = sched["parallel"] or max(len(pairs), 1)
    for i, (a, b) in enumerate(pairs, 1):
        at = base + timedelta(minutes=sched["slot_minutes"] * ((i - 1) // parallel)) if has_time else None
        dl = (at or timezone.now()) + timedelta(hours=sched["deadline_hours"])
        if not has_time and batch_index: dl += timedelta(hours=sched["round_gap_hours"] * batch_index)
        m = Match.objects.create(round=rd, slot=i, player_a=a, player_b=b, scheduled_at=at, deadline=dl)
        last_dl = max(last_dl, dl) if last_dl else dl
        if b is None:  # bye = vitória automática
            m.score_a, m.score_b, m.winner, m.status = cfg(season)["wo_score"][0], cfg(season)["wo_score"][1], a, "wo"; m.save()
        when = f" em {timezone.localtime(at):%d/%m às %H:%M}" if at else ""
        for p in (a, b): notify(p, "new_opponent", f"{name}: novo confronto disponível{when}.")
    rd.deadline = last_dl; rd.save(update_fields=["deadline"])
    return rd

def _open(season):
    return Match.objects.filter(round__season=season).exclude(status__in=Match.DONE).exists()

def _rr_round(ids, r):
    """Rodada r (0-based) do todos-contra-todos pelo método do círculo; None = folga."""
    row = list(ids) + ([None] if len(ids) % 2 else [])
    n = len(row)
    if n < 2: return []
    rest = row[1:]; k = r % len(rest); rest = rest[len(rest) - k:] + rest[:len(rest) - k]
    row = [row[0]] + rest
    pairs = [(row[i], row[n - 1 - i]) for i in range(n // 2)]
    return [(b, a) if a is None else (a, b) for a, b in pairs]  # folga (None) sempre como 2º

def group_members(season):
    out = {}
    for p in season.players.exclude(status="blocked").order_by("id"):
        if p.group: out.setdefault(p.group, []).append(p)
    return out

def group_round_count(season):
    return max((len(m) + len(m) % 2 - 1 for m in group_members(season).values()), default=0)

@transaction.atomic
def draw_groups(season):
    """Sorteia os jogadores nos grupos (serpentina; cabeças de chave primeiro, se houver seed)."""
    if not is_groups(season): raise ValueError("Esta temporada usa fase de liga, não grupos.")
    if season.rounds.filter(phase="groups").exists(): raise ValueError("Os grupos já começaram: não dá para sortear de novo.")
    g = cfg(season)["groups"]
    players = list(season.players.exclude(status="blocked"))
    if g < 1 or len(players) < 2 * g: raise ValueError(f"São necessários pelo menos {2 * g} jogadores para {g} grupos.")
    random.shuffle(players); players.sort(key=lambda p: p.seed if p.seed is not None else 10**9)
    for i, p in enumerate(players):
        col = i % g; p.group = col + 1 if (i // g) % 2 == 0 else g - col; p.save(update_fields=["group"])
    season.players.filter(status="blocked").update(group=None)
    return players

def _check_groups_setup(season):
    c = cfg(season); mem = group_members(season)
    if len(mem) != c["groups"] or any(len(v) < 2 for v in mem.values()): raise ValueError("Sorteie os grupos antes de gerar as rodadas.")
    if c["group_qualify"] < 1 or c["group_qualify"] > min(len(v) for v in mem.values()):
        raise ValueError("Classificados por grupo maior que o menor grupo.")
    q = c["groups"] * c["group_qualify"]
    if q not in KO_BY_SIZE: raise ValueError(f"Grupos × classificados por grupo = {q}; precisa ser 2, 4, 8, 16 ou 32 para montar o mata-mata.")

@transaction.atomic
def generate_league_rounds(season, count=1, sched=None):
    """Gera `count` rodadas de uma vez (fase de liga/Swiss ou fase de grupos), todas com horário e prazo.
    Em lote, as rodadas seguintes usam a classificação atual e nunca repetem confronto já gerado."""
    c = cfg(season); sched = sched or parse_schedule(season, {}); count = max(int(count or 1), 1)
    if _open(season): raise ValueError("Há partidas pendentes na rodada atual.")
    made = []
    if is_groups(season):
        done = season.rounds.filter(phase="groups").count()
        if done == 0 and not any(p.group for p in season.players.all()): draw_groups(season)
        _check_groups_setup(season); total = group_round_count(season)
        if done >= total: raise ValueError("Fase de grupos já concluída.")
        mem = group_members(season)
        for i in range(min(count, total - done)):
            pairs = [pr for g in sorted(mem) for pr in _rr_round(mem[g], done + i)]
            made.append(_new_round(season, "groups", f"Rodada {done + i + 1}", pairs, sched, i))
        return made
    done = season.rounds.filter(phase="swiss").count()
    if done >= c["swiss_rounds"]: raise ValueError("Fase Swiss já concluída.")
    base_rank = [r["player"] for r in standings(season) if r["player"].status != "blocked"]
    for i in range(min(count, c["swiss_rounds"] - done)):
        played = {p.id: set() for p in base_rank}; had_bye = set()
        for m in Match.objects.filter(round__season=season, round__phase="swiss"):
            if m.player_b_id: played[m.player_a_id].add(m.player_b_id); played[m.player_b_id].add(m.player_a_id)
            else: had_bye.add(m.player_a_id)
        rank = list(base_rank); bye = None
        if len(rank) % 2:
            bye = next((p for p in reversed(rank) if p.id not in had_bye), rank[-1]); rank.remove(bye)
        ids = [p.id for p in rank]; by = {p.id: p for p in rank}
        res = _pair(ids, played)
        if res is None: res = _pair(ids, {i_: set() for i_ in ids})  # último recurso: permite repetição
        pairs = [(by[a], by[b]) for a, b in res] + ([(bye, None)] if bye else [])
        made.append(_new_round(season, "swiss", f"Rodada {done + i + 1}", pairs, sched, i))
    return made

def generate_swiss_round(season, sched=None):  # compatibilidade: uma rodada só
    return generate_league_rounds(season, 1, sched)[0]

def finalize(m, status="confirmed"):
    if m.score_a > m.score_b: m.winner = m.player_a
    elif m.score_b > m.score_a: m.winner = m.player_b
    elif m.pen_a is not None and m.pen_a != m.pen_b: m.winner = m.player_a if m.pen_a > m.pen_b else m.player_b
    elif m.round.phase in LEAGUE_PHASES: m.winner = None
    else: raise ValueError("Mata-mata não pode terminar empatado: informe os pênaltis.")
    m.status = status; m.save(); m.disputes.update(resolved=True)
    for p in (m.player_a, m.player_b): notify(p, "result_confirmed", f"Resultado confirmado: {m.score_a} x {m.score_b}.")

def check_deadline(m):
    """Depois do prazo só o admin lança/corrige placar ou libera mais tempo (extend_deadline)."""
    if m.deadline and timezone.now() > m.deadline:
        raise PermissionError("O prazo para lançar o placar acabou. Fale com o organizador para liberar mais tempo.")

def extend_deadline(m, deadline):
    m.deadline = _aware(deadline)
    if m.deadline is None: raise ValueError("Informe o novo prazo.")
    m.save(update_fields=["deadline"])
    for p in (m.player_a, m.player_b): notify(p, "deadline", f"Prazo do placar estendido até {timezone.localtime(m.deadline):%d/%m às %H:%M}.")
    return m

@transaction.atomic
def submit_result(m, player, sa, sb, pa=None, pb=None, proof=None, et=False):
    """Só UMA pessoa valida a partida: o primeiro placar enviado por um dos dois jogadores já fecha o resultado.
    O outro jogador pode contestar (contest) e o admin decide."""
    if m.status in Match.DONE: raise ValueError("Partida já finalizada.")
    if m.status == "disputed": raise ValueError("Partida em disputa: aguarde o organizador.")
    if player.id not in (m.player_a_id, m.player_b_id): raise PermissionError("Você não joga esta partida.")
    if m.player_b_id is None: raise ValueError("Esta partida não tem adversário.")
    check_deadline(m)
    if et: m.extra_time = True
    if proof is not None:
        if player.id == m.player_a_id: m.proof_a = proof
        else: m.proof_b = proof
    m.reports = {str(player.id): [sa, sb, pa, pb]}  # sempre no formato A x B
    m.score_a, m.score_b, m.pen_a, m.pen_b = sa, sb, pa, pb
    finalize(m)
    return m

@transaction.atomic
def contest(m, player):
    """O jogador que NÃO lançou o placar discorda: abre disputa para o admin resolver."""
    if player.id not in (m.player_a_id, m.player_b_id): raise PermissionError("Você não joga esta partida.")
    if m.status != "confirmed": raise ValueError("Só dá para contestar um resultado já lançado e não resolvido.")
    if str(player.id) in m.reports: raise ValueError("Você mesmo lançou este placar; peça ao organizador para corrigir.")
    if m.round.season.rounds.last().id != m.round_id: raise ValueError("Esta rodada já ficou para trás; fale com o organizador.")
    m.status = "disputed"; m.save(update_fields=["status"]); Dispute.objects.create(match=m)
    for p in (m.player_a, m.player_b): notify(p, "disputed", "Resultado contestado: disputa aberta para o organizador.")
    return m

@transaction.atomic
def admin_set_result(m, sa, sb, pa=None, pb=None):
    m.score_a, m.score_b, m.pen_a, m.pen_b = sa, sb, pa, pb; finalize(m, "resolved")

@transaction.atomic
def apply_wo(m, winner, reason):
    w, l = cfg(m.round.season)["wo_score"]
    m.score_a, m.score_b = (w, l) if winner.id == m.player_a_id else (l, w)
    m.winner, m.status, m.wo_reason = winner, "wo", reason; m.save()

PHASE_DEPTH = {"swiss": 0, "groups": 0, "playoff1": 1, "playoff2": 2, "r32": 3, "r16": 4, "qf": 5, "sf": 6, "final": 7}
PHASE_LABEL = {"swiss": "Fase de liga", "groups": "Fase de grupos", "playoff1": "Playoff — Fase 1", "playoff2": "Playoff — Fase 2",
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

def checkin_options(phone):
    """Todas as inscrições ligadas ao telefone — uma por campeonato (coluna 'Jogo' da planilha) — e a temporada de cada uma."""
    norm = normalize_phone(phone)
    if not norm: raise ValueError("Informe um telefone válido.")
    regs = Registration.objects.filter(phone_norm=norm).order_by("-created_raw", "-id")
    if not regs: raise ValueError("Não encontramos nenhuma inscrição com esse telefone.")
    latest = {}
    for r in regs: latest.setdefault((r.jogo or "").strip().lower(), r)  # inscrição repetida no mesmo campeonato: vale a mais recente
    return [(r, season_for_registration(r)) for r in latest.values()]

def season_for_registration(reg, fallback=None):
    """Temporada do campeonato da inscrição: a que tem o mesmo 'jogo'; senão a mais recente sem jogo definido (aceita qualquer)."""
    seasons = Season.objects.order_by("-id")
    if reg.jogo:
        s = seasons.filter(jogo__iexact=reg.jogo.strip()).first()
        if s: return s
    return seasons.filter(jogo="").first() or fallback

def checkin_lookup(phone):  # compatibilidade: primeira inscrição
    return checkin_options(phone)[0][0]

@transaction.atomic
def checkin_confirm(phone, season=None, registration_ids=None):
    """Check-in numa ou em várias inscrições do mesmo telefone (registration_ids; vazio = todas).
    Devolve (lista de jogadores criados/encontrados, inscrições)."""
    opts = checkin_options(phone)
    if registration_ids:
        wanted = {int(i) for i in registration_ids}
        opts = [(r, s) for r, s in opts if r.id in wanted]
        if not opts: raise ValueError("Selecione ao menos um campeonato para o check-in.")
    done = []
    first = opts[0][0]
    email = first.email or f"{first.phone_norm}@checkin.fc26"
    user, _ = User.objects.get_or_create(email=email)
    for reg, s in opts:
        s = s or season
        if s is None: raise ValueError(f"Não há campeonato aberto para \"{reg.jogo or 'esta inscrição'}\".")
        if reg.player_id and reg.player.season_id == s.id:
            done.append((reg.player, reg)); continue  # já fez check-in neste campeonato: só reloga
        first_name = (reg.nome.split() or [reg.nome])[0]
        player, created = Player.objects.get_or_create(season=s, user=user, defaults={
            "name": reg.nome, "nickname": reg.nick or first_name, "team": reg.equipe,
            "campus": reg.campus, "ea_id": reg.nick or "",
        })
        if not created:  # já existia (ex.: reimportação): mantém o que o jogador já tiver editado, só completa o que faltar
            changed = False
            for f, v in (("team", reg.equipe), ("campus", reg.campus)):
                if not getattr(player, f) and v: setattr(player, f, v); changed = True
            if changed: player.save()
        reg.player = player; reg.checked_in = True; reg.checked_in_at = timezone.now(); reg.save()
        done.append((player, reg))
    return done

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
    """Também aqui basta um dos jogadores lançar o placar do jogo."""
    if match.status in Match.DONE: raise ValueError("Confronto já finalizado.")
    if player.id not in (match.player_a_id, match.player_b_id): raise PermissionError("Você não joga esta partida.")
    check_deadline(match)
    leg, _ = Leg.objects.get_or_create(match=match, number=leg_number)
    if leg.status in Match.DONE: raise ValueError("Este jogo já foi finalizado.")
    if leg.status == "disputed": raise ValueError("Jogo em disputa: aguarde o organizador.")
    if match.round.match_format != "two_legs" and _decide(sa, sb, pa, pb) is None:  # na ida-e-volta o empate vale no agregado
        raise ValueError("Jogo empatado: inclua o resultado dos pênaltis.")
    if et: leg.extra_time = True
    if proof is not None:
        if player.id == match.player_a_id: leg.proof_a = proof
        else: leg.proof_b = proof
    leg.reports = {str(player.id): [sa, sb, pa, pb]}
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

def _bracket_order(n):
    """Ordem de cabeças de chave de um mata-mata de n vagas (1 só reencontra 2 na final): n=8 -> 1,8,4,5,2,7,3,6."""
    order = [1]
    while len(order) < n:
        m = len(order) * 2; order = [x for s_ in order for x in (s_, m + 1 - s_)]
    return order

def _first_knockout(season):
    """Fim da fase de grupos: os melhores de cada grupo entram no mata-mata, cruzando grupos diferentes quando possível."""
    c = cfg(season); rows = standings(season)
    q = sorted([r for r in rows if r["pos"] <= c["group_qualify"]], key=lambda r: (r["pos"], -r["pts"], -r["sg"], -r["gp"], r["player"].id))
    if len(q) not in KO_BY_SIZE: raise ValueError(f"{len(q)} classificados não formam um mata-mata (use 2, 4, 8, 16 ou 32).")
    by_seed = {i: r["player"] for i, r in enumerate(q, 1)}
    order = _bracket_order(len(q)); pairs = [[by_seed[order[i]], by_seed[order[i + 1]]] for i in range(0, len(order), 2)]
    for i, pr in enumerate(pairs):  # mesmo grupo no 1º confronto: troca o adversário com outro confronto, se isso resolver
        if pr[0].group != pr[1].group: continue
        for j, other in enumerate(pairs):
            if j != i and pr[1].group != other[0].group and other[1].group != pr[0].group:
                pr[1], other[1] = other[1], pr[1]; break
    qualified = [r["player"] for r in q]
    _flag(qualified, "main"); _flag([r["player"] for r in rows if r["player"] not in qualified], "eliminated")
    phase = KO_BY_SIZE[len(q)]; names = {"r32": "32-avos", "r16": "Oitavas", "qf": "Quartas", "sf": "Semifinal", "final": "Final"}
    return phase, names[phase], [tuple(pr) for pr in pairs]

@transaction.atomic
def advance(season, count=1, sched=None):
    """Avança para a próxima fase/rodada quando tudo está confirmado. Sempre devolve uma lista de rodadas criadas."""
    c = cfg(season); sched = sched or parse_schedule(season, {})
    if _open(season): raise ValueError("Existem partidas sem resultado confirmado.")
    last = season.rounds.last()
    league = "groups" if is_groups(season) else "swiss"
    total = group_round_count(season) if league == "groups" else c["swiss_rounds"]
    if last is None or (last.phase == league and season.rounds.filter(phase=league).count() < total):
        return generate_league_rounds(season, count, sched)
    if last.phase == "groups":
        phase, name, pairs = _first_knockout(season)
        return [_new_round(season, phase, name, pairs, sched)]
    rank = [r["player"] for r in standings(season)]; d = c["direct"]
    if last.phase == "swiss":
        pool, upper, lower = _playoff_split(rank, c)
        _flag(rank[d + c["playoff_size"]:], "eliminated"); _flag(rank[:d], "main"); _flag(pool, "playoff")
        return [_new_round(season, "playoff1", "Playoff — Fase 1", [(lower[i], lower[-1 - i]) for i in range(len(lower) // 2)], sched)]
    if last.phase == "playoff1":
        _, upper, _ = _playoff_split(rank, c)
        w = sorted(_winners(season, "playoff1"), key=rank.index)
        return [_new_round(season, "playoff2", "Playoff — Fase 2", [(upper[i], w[-1 - i]) for i in range(len(upper))], sched)]
    if last.phase == "playoff2":
        pool = _playoff_split(rank, c)[0]
        q = sorted(_winners(season, "playoff2"), key=rank.index); _flag(q, "main")
        _flag([p for p in pool if p not in q], "eliminated"); top = rank[:d]
        return [_new_round(season, "r32", "32-avos", [(top[i], q[-1 - i]) for i in range(len(top))], sched)]
    if last.phase == "final":
        champ = last.matches.first().winner; season.champion = champ; season.save()
        Player.objects.filter(id=champ.id).update(status="champion"); return [last]
    order = Round.PHASES[3:]; names = {"r16": "Oitavas", "qf": "Quartas", "sf": "Semifinal", "final": "Final"}
    nxt = order[order.index(last.phase) + 1]; w = _winners(season, last.phase)
    losers = [m.player_b if m.winner_id == m.player_a_id else m.player_a for m in last.matches.all()]
    _flag(losers, "eliminated")
    for p in losers: notify(p, "eliminated", "Você foi eliminado.")
    return [_new_round(season, nxt, names[nxt], [(w[i], w[i + 1]) for i in range(0, len(w), 2)], sched)]
