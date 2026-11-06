from django.db import migrations


def rename(apps, schema_editor):
    """A fase com 32 jogadores (16 jogos) é '16-avos de final'; versões antigas a chamavam de '32-avos'."""
    apps.get_model("core", "Round").objects.filter(phase="r32", name="32-avos").update(name="16-avos")


def unrename(apps, schema_editor):
    apps.get_model("core", "Round").objects.filter(phase="r32", name="16-avos").update(name="32-avos")


class Migration(migrations.Migration):
    dependencies = [("core", "0005_player_knockout_entry")]
    operations = [migrations.RunPython(rename, unrename)]
