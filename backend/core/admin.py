from django.contrib import admin
from .models import *
for m in (User, Season, Player, Round, Match, Leg, Penalty, Dispute, Notification, Registration): admin.site.register(m)
