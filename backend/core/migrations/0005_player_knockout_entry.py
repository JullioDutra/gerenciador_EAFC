from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0004_checkin_open")]
    operations = [migrations.AddField(model_name="player", name="knockout_entry", field=models.BooleanField(default=False))]
