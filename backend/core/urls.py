from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views
r = DefaultRouter()
r.register("seasons", views.SeasonViewSet); r.register("players", views.PlayerViewSet)
r.register("rounds", views.RoundViewSet, basename="round")
r.register("matches", views.MatchViewSet, basename="match")
r.register("notifications", views.NotificationViewSet, basename="notification")
r.register("disputes", views.DisputeViewSet, basename="dispute")
urlpatterns = [path("", include(r.urls)), path("auth/register/", views.register),
               path("seasons/<int:season_id>/me/", views.me),
               path("checkin/lookup/", views.checkin_lookup), path("checkin/confirm/", views.checkin_confirm),
               path("registrations/import/", views.import_registrations)]
