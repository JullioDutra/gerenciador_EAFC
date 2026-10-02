from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from . import images, services as sv
from .models import Match, Player, Registration, Season, User


_seq = iter(range(10**6))

def mk_season(n, **cfg):
    k = next(_seq); s = Season.objects.create(name="T", year=2026, config=cfg)
    for i in range(n):
        Player.objects.create(season=s, user=User.objects.create_user(f"p{k}_{i}@x.com"), name=f"P{i}", nickname=f"nick{i}", team=f"Time{i}")
    return s


def play_all(s, who="a"):
    """Resolve todas as partidas abertas: o jogador A lança 2x1."""
    for m in Match.objects.filter(round__season=s).exclude(status__in=Match.DONE):
        if m.player_b_id: sv.submit_result(m, m.player_a, 2, 1)


class GroupsTests(TestCase):
    def test_groups_flow_to_knockout(self):
        s = mk_season(8, format="groups", groups=2, group_qualify=2)
        sv.draw_groups(s)
        sizes = sorted(len(v) for v in sv.group_members(s).values()); self.assertEqual(sizes, [4, 4])
        self.assertEqual(sv.group_round_count(s), 3)
        rounds = sv.advance(s, count=3)  # as 3 rodadas dos grupos de uma vez
        self.assertEqual(len(rounds), 3)
        seen = set()
        for m in Match.objects.filter(round__season=s):
            self.assertEqual(m.player_a.group, m.player_b.group)
            seen.add(frozenset((m.player_a_id, m.player_b_id)))
        self.assertEqual(len(seen), 12)  # 2 grupos x 6 confrontos, sem repetir
        with self.assertRaises(ValueError): sv.advance(s)  # ainda há partidas abertas
        play_all(s)
        rows = sv.standings(s); self.assertEqual({r["pos"] for r in rows}, {1, 2, 3, 4})
        ko = sv.advance(s)[0]
        self.assertEqual(ko.phase, "sf"); ms = list(ko.matches.all()); self.assertEqual(len(ms), 2)
        for m in ms: self.assertNotEqual(m.player_a.group, m.player_b.group)
        play_all(s); self.assertEqual(sv.advance(s)[0].phase, "final")

    def test_odd_group_has_no_byes(self):
        s = mk_season(6, format="groups", groups=2, group_qualify=1)
        rounds = sv.advance(s, count=10)
        self.assertEqual(len(rounds), 3)  # grupos de 3 -> 3 rodadas
        self.assertFalse(Match.objects.filter(player_b__isnull=True).exists())
        self.assertEqual(Match.objects.count(), 6)

    def test_invalid_qualifier_count(self):
        s = mk_season(9, format="groups", groups=3, group_qualify=1)
        with self.assertRaises(ValueError): sv.advance(s)

    def test_league_default_unchanged(self):
        s = mk_season(6, swiss_rounds=3)
        self.assertFalse(sv.is_groups(s))
        self.assertTrue(all(r["group"] is None for r in sv.standings(s)))


class BatchScheduleTests(TestCase):
    def test_swiss_batch_with_times(self):
        s = mk_season(8, swiss_rounds=5)
        start = timezone.now() + timedelta(days=1)
        sched = sv.parse_schedule(s, {"start": start.isoformat(), "round_gap_hours": 24, "slot_minutes": 30, "parallel": 2, "deadline_hours": 12})
        rounds = sv.advance(s, 3, sched); self.assertEqual(len(rounds), 3)
        pairs = [frozenset((m.player_a_id, m.player_b_id)) for m in Match.objects.filter(round__season=s)]
        self.assertEqual(len(pairs), len(set(pairs)))  # nenhum confronto repetido
        r1 = list(rounds[0].matches.all())
        self.assertEqual([m.scheduled_at - start for m in r1], [timedelta(0), timedelta(0), timedelta(minutes=30), timedelta(minutes=30)])
        self.assertEqual(r1[0].deadline - r1[0].scheduled_at, timedelta(hours=12))
        self.assertEqual(rounds[1].matches.first().scheduled_at - start, timedelta(hours=24))
        with self.assertRaises(ValueError): sv.advance(s)

    def test_deadline_blocks_players_until_admin_extends(self):
        s = mk_season(4, swiss_rounds=2); sv.advance(s)
        m = Match.objects.first(); m.deadline = timezone.now() - timedelta(minutes=1); m.save()
        with self.assertRaises(PermissionError): sv.submit_result(m, m.player_a, 1, 0)
        sv.extend_deadline(m, (timezone.now() + timedelta(hours=1)).isoformat())
        sv.submit_result(m, m.player_a, 1, 0); m.refresh_from_db(); self.assertEqual(m.status, "confirmed")


class SingleValidatorTests(TestCase):
    def test_one_report_closes_match_and_other_can_contest(self):
        s = mk_season(4, swiss_rounds=2); sv.advance(s)
        m = Match.objects.first(); sv.submit_result(m, m.player_a, 3, 1)
        m.refresh_from_db(); self.assertEqual((m.status, m.winner_id), ("confirmed", m.player_a_id))
        with self.assertRaises(ValueError): sv.submit_result(m, m.player_b, 0, 0)  # já fechada
        with self.assertRaises(ValueError): sv.contest(m, m.player_a)  # quem lançou não contesta
        sv.contest(m, m.player_b); m.refresh_from_db(); self.assertEqual(m.status, "disputed")
        with self.assertRaises(ValueError): sv.submit_result(m, m.player_b, 0, 0)
        sv.admin_set_result(m, 0, 2); m.refresh_from_db(); self.assertEqual((m.status, m.winner_id), ("resolved", m.player_b_id))

    def test_api_report(self):
        s = mk_season(4, swiss_rounds=2); sv.advance(s)
        m = Match.objects.first(); c = APIClient(); c.force_authenticate(m.player_a.user)
        r = c.post(f"/api/matches/{m.id}/report/", {"score_a": 2, "score_b": 2}, format="multipart")
        self.assertEqual(r.status_code, 200); self.assertEqual(r.data["status"], "confirmed"); self.assertEqual(r.data["reported_by"], m.player_a_id)


class ViewOnlyTests(TestCase):
    def test_mine_and_non_participant_is_view_only(self):
        s1, s2 = mk_season(4, swiss_rounds=2), mk_season(4, swiss_rounds=2)
        sv.advance(s2)
        user = s1.players.first().user
        Player.objects.create(season=s2, user=user, name="X", nickname="x")  # participa de s1 e s2
        outsider = User.objects.create_user("fora@x.com")
        c = APIClient(); c.force_authenticate(user)
        self.assertEqual({x["id"] for x in c.get("/api/seasons/mine/").data}, {s1.id, s2.id})
        c.force_authenticate(outsider)
        self.assertEqual(c.get("/api/seasons/mine/").data, [])
        m = Match.objects.filter(round__season=s2).first()
        r = c.post(f"/api/matches/{m.id}/report/", {"score_a": 1, "score_b": 0}, format="multipart")
        self.assertEqual(r.status_code, 400); self.assertIn("visualizar", r.data["detail"])
        self.assertEqual(c.post(f"/api/matches/{m.id}/contest/").status_code, 400)
        self.assertEqual(c.get(f"/api/seasons/{s2.id}/me/").status_code, 404)
        self.assertEqual(c.get(f"/api/seasons/{s2.id}/standings/").status_code, 200)  # ler continua liberado
        m.refresh_from_db(); self.assertEqual(m.status, "pending")


class CheckinTests(TestCase):
    def setUp(self):
        self.s1 = Season.objects.create(name="FC", year=2026, jogo="EA FC 26")
        self.s2 = Season.objects.create(name="LoL", year=2026, jogo="LoL")
        for jogo in ("EA FC 26", "LoL"):
            Registration.objects.create(nome="Ana Souza", email="ana@x.com", phone_norm="62999999999", jogo=jogo, nick="ana", external_id=jogo)

    def test_options_lists_each_championship(self):
        opts = sv.checkin_options("(62) 99999-9999")
        self.assertEqual({(r.jogo, s.id) for r, s in opts}, {("EA FC 26", self.s1.id), ("LoL", self.s2.id)})

    def test_checkin_one_or_all(self):
        regs = {r.jogo: r.id for r, _ in sv.checkin_options("62999999999")}
        done = sv.checkin_confirm("62999999999", None, [regs["LoL"]])
        self.assertEqual([p.season_id for p, _ in done], [self.s2.id])
        done = sv.checkin_confirm("62999999999")  # todas
        self.assertEqual({p.season_id for p, _ in done}, {self.s1.id, self.s2.id})
        self.assertEqual(Player.objects.count(), 2)  # LoL não duplicou
        with self.assertRaises(ValueError): sv.checkin_confirm("62999999999", None, [9999])

    def test_api(self):
        c = APIClient(); r = c.post("/api/checkin/lookup/", {"phone": "62999999999"}, format="json")
        self.assertEqual(len(r.data["registrations"]), 2)
        r = c.post("/api/checkin/confirm/", {"phone": "62999999999"}, format="json")
        self.assertEqual(sorted(r.data["seasons"]), sorted([self.s1.id, self.s2.id])); self.assertIn("token", r.data)


class ImageTests(TestCase):
    def test_round_image_endpoint_admin_only(self):
        s = mk_season(8, format="groups", groups=2, group_qualify=2)
        rd = sv.advance(s, 1, sv.parse_schedule(s, {"start": timezone.now().isoformat()}))[0]
        admin = User.objects.create_superuser("adm@x.com", "pw"); c = APIClient()
        self.assertEqual(c.get(f"/api/rounds/{rd.id}/image/").status_code, 401)
        c.force_authenticate(admin); r = c.get(f"/api/rounds/{rd.id}/image/")
        self.assertEqual((r.status_code, r["Content-Type"]), (200, "image/png")); self.assertTrue(r.content.startswith(b"\x89PNG"))
        self.assertEqual(c.get(f"/api/rounds/{rd.id}/image/?group=1").status_code, 200)


class KnockoutOnlyTests(TestCase):
    def test_full_bracket_with_byes_to_champion(self):
        s = mk_season(6, format="knockout")
        r1 = sv.advance(s)[0]
        self.assertEqual(r1.phase, "qf"); ms = list(r1.matches.all()); self.assertEqual(len(ms), 4)
        self.assertEqual(sum(m.player_b_id is None for m in ms), 2)  # 8 vagas - 6 jogadores = 2 folgas
        self.assertTrue(all(m.status == "wo" for m in ms if m.player_b_id is None))
        play_all(s); self.assertEqual(sv.advance(s)[0].phase, "sf")
        play_all(s); self.assertEqual(sv.advance(s)[0].phase, "final")
        play_all(s); sv.advance(s); s.refresh_from_db()
        self.assertIsNotNone(s.champion_id)

    def test_limits(self):
        with self.assertRaises(ValueError): sv.advance(mk_season(1, format="knockout"))
        with self.assertRaises(ValueError): sv.advance(mk_season(33, format="knockout"))
        self.assertEqual(sv.advance(mk_season(2, format="knockout"))[0].phase, "final")


class CheckinClosedTests(TestCase):
    def test_closed_season_blocks_new_but_not_returning(self):
        s = Season.objects.create(name="FC", year=2026, jogo="FC")
        for ph in ("1", "2"): Registration.objects.create(nome="N" + ph, email=f"n{ph}@x.com", phone_norm="6211111111" + ph, jogo="FC")
        sv.checkin_confirm("62111111111")
        s.checkin_open = False; s.save()
        sv.checkin_confirm("62111111111")  # já fez: só reloga
        with self.assertRaises(ValueError): sv.checkin_confirm("62111111112")
        self.assertEqual(Player.objects.count(), 1)
        self.assertFalse(sv.checkin_options("62111111112")[0][1].checkin_open)


class ImportFromTests(TestCase):
    def setUp(self):
        self.src = Season.objects.create(name="Antigo", year=2025)
        for i, (campus, st) in enumerate([("Anápolis", "main"), ("Goiânia", "main"), ("Anápolis", "eliminated")]):
            p = Player.objects.create(season=self.src, user=User.objects.create_user(f"o{i}@x.com"), name=f"O{i}", nickname=f"o{i}", campus=campus, status=st)
            Registration.objects.create(nome=p.name, phone_norm=f"6200000000{i}", curso="Direito" if i == 0 else "Medicina", player=p)
        self.dst = Season.objects.create(name="Novo", year=2026)

    def test_filters_and_import(self):
        r = sv.import_players_from(self.dst, self.src, {"campus": "anáp"}, dry_run=True)
        self.assertEqual((r["matched"], r["new"]), (2, 2)); self.assertEqual(self.dst.players.count(), 0)  # prévia não grava
        r = sv.import_players_from(self.dst, self.src, {"campus": "anáp", "status": "main"}, dry_run=False)
        self.assertEqual(r["new"], 1); self.assertEqual(self.dst.players.get().nickname, "o0")
        r = sv.import_players_from(self.dst, self.src, {"curso": "medic"}, dry_run=False)  # filtro por campo da inscrição
        self.assertEqual(r["new"], 2); self.assertEqual(self.dst.players.count(), 3)
        r = sv.import_players_from(self.dst, self.src, {}, dry_run=False); self.assertEqual((r["new"], r["already"]), (0, 3))

    def test_top_guards_and_api(self):
        with self.assertRaises(ValueError): sv.import_players_from(self.dst, self.dst)
        with self.assertRaises(ValueError): sv.select_players(self.src, {"senha": "x"})
        self.assertEqual(len(sv.select_players(self.src, top=2)), 2)
        adm = User.objects.create_superuser("a@x.com", "pw"); c = APIClient(); c.force_authenticate(adm)
        r = c.post(f"/api/seasons/{self.dst.id}/import-from/", {"source": self.src.id, "filters": {"campus": "goi"}, "dry_run": False}, format="json")
        self.assertEqual((r.status_code, r.data["new"]), (200, 1))
        self.assertIn("Anápolis", c.get(f"/api/seasons/{self.src.id}/filter-values/").data["campus"])
