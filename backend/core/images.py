"""Imagens dos confrontos de uma rodada, para o admin conferir e mandar no grupo (WhatsApp etc.)."""
import io
from pathlib import Path
from django.conf import settings
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

BG, PANEL, PANEL2 = (11, 18, 38), (20, 30, 58), (27, 40, 74)
ICE, MUTED, GOLD, TEAL = (232, 240, 255), (140, 156, 190), (245, 190, 60), (45, 212, 191)
W, PAD, ROW, HEAD, GROUP_H = 1080, 40, 118, 210, 64
FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu", "/usr/share/fonts/TTF", "/Library/Fonts", "C:/Windows/Fonts"]

def _font(size, bold=False):
    for name in (("DejaVuSans-Bold.ttf", "arialbd.ttf") if bold else ("DejaVuSans.ttf", "arial.ttf")):
        for d in FONT_DIRS:
            if (Path(d) / name).exists(): return ImageFont.truetype(str(Path(d) / name), size)
        try: return ImageFont.truetype(name, size)
        except OSError: pass
    return ImageFont.load_default(size)

def _fit(draw, text, font, width):
    if draw.textlength(text, font=font) <= width: return text
    while text and draw.textlength(text + "…", font=font) > width: text = text[:-1]
    return text + "…"

def _when(dt):
    return timezone.localtime(dt).strftime("%d/%m %H:%M") if dt else "—"

def _name(p):
    return (p.nickname if p else "FOLGA"), (p.team if p else "")

def render_matches(title, subtitle, matches, show_groups=False):
    """matches: lista de Match já ordenada. Com show_groups, separa por grupo (player_a.group)."""
    sections = []
    if show_groups:
        for g in sorted({m.player_a.group or 0 for m in matches}):
            sections.append((f"GRUPO {chr(64 + g)}" if g else "SEM GRUPO", [m for m in matches if (m.player_a.group or 0) == g]))
    else:
        sections.append((None, matches))
    h = HEAD + 70 + sum((GROUP_H if t else 0) + len(ms) * ROW for t, ms in sections)
    img = Image.new("RGB", (W, h), BG); d = ImageDraw.Draw(img)
    f_title, f_sub, f_nick, f_team, f_small, f_vs = _font(54, True), _font(26), _font(32, True), _font(21), _font(22), _font(26, True)
    x0 = PAD
    logo = Path(settings.BASE_DIR).parent / "frontend" / "src" / "assets" / "logoEsports.png"
    if logo.exists():
        lg = Image.open(logo).convert("RGBA"); lg.thumbnail((120, 120)); img.paste(lg, (PAD, 40), lg); x0 = PAD + 140
    d.text((x0, 42), _fit(d, title, f_title, W - x0 - PAD), font=f_title, fill=ICE)
    d.text((x0, 116), _fit(d, subtitle, f_sub, W - x0 - PAD), font=f_sub, fill=GOLD)
    d.line([(PAD, HEAD - 30), (W - PAD, HEAD - 30)], fill=PANEL2, width=3)
    y = HEAD
    for t, ms in sections:
        if t:
            d.text((PAD, y + 14), t, font=f_nick, fill=TEAL); y += GROUP_H
        for i, m in enumerate(ms):
            d.rounded_rectangle([PAD, y + 6, W - PAD, y + ROW - 6], radius=18, fill=PANEL if i % 2 == 0 else PANEL2)
            d.text((PAD + 22, y + 22), _when(m.scheduled_at), font=f_small, fill=GOLD)
            d.text((PAD + 22, y + 56), f"até {_when(m.deadline)}", font=f_small, fill=MUTED)
            mid, half = PAD + 190 + (W - 2 * PAD - 190) // 2, (W - 2 * PAD - 190 - 90) // 2
            d.text((mid, y + ROW // 2), "VS", font=f_vs, fill=GOLD, anchor="mm")
            for side, p in ((0, m.player_a), (1, m.player_b)):
                nick, team = _name(p)
                nick, team = _fit(d, nick, f_nick, half), _fit(d, team, f_team, half)
                if side == 0:
                    d.text((mid - 45, y + 40), nick, font=f_nick, fill=ICE, anchor="rm")
                    d.text((mid - 45, y + 76), team, font=f_team, fill=MUTED, anchor="rm")
                else:
                    d.text((mid + 45, y + 40), nick, font=f_nick, fill=ICE, anchor="lm")
                    d.text((mid + 45, y + 76), team, font=f_team, fill=MUTED, anchor="lm")
            y += ROW
    d.text((W // 2, h - 40), "Placar até o prazo indicado · depois dele, só o organizador libera mais tempo",
           font=f_small, fill=MUTED, anchor="mm")
    buf = io.BytesIO(); img.save(buf, "PNG", optimize=True); return buf.getvalue()
