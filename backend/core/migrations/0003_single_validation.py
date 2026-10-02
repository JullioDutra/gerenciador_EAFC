from django.db import migrations


def _winner(sa, sb, pa, pb, a, b):
    if sa != sb: return a if sa > sb else b
    if pa is not None and pb is not None and pa != pb: return a if pa > pb else b
    return None


def confirm_awaiting(apps, schema_editor):
    """Regra nova: uma pessoa só valida. Partidas 'aguardando confirmação' já têm um placar lançado: passam a valer."""
    Match = apps.get_model("core", "Match")
    for m in Match.objects.filter(status="awaiting").select_related("round"):
        if len(m.reports) != 1: continue
        sa, sb, pa, pb = next(iter(m.reports.values()))
        w = _winner(sa, sb, pa, pb, m.player_a_id, m.player_b_id)
        if w is None and m.round.phase != "swiss": continue  # mata-mata empatado sem pênaltis: admin resolve
        m.score_a, m.score_b, m.pen_a, m.pen_b = sa, sb, pa, pb
        m.winner_id = w; m.status = "confirmed"; m.save()


class Migration(migrations.Migration):
    dependencies = [("core", "0002_groups_schedule_jogo")]
    operations = [migrations.RunPython(confirm_awaiting, migrations.RunPython.noop)]
