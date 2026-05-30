import asyncio
import re
import httpx
from datetime import datetime
from playwright.async_api import async_playwright

# ─── CONFIGURAÇÕES ───────────────────────────────────────────
TELEGRAM_TOKEN = "8883817736:AAHIQFiJAw2wJRRkwG8gnsoX0dgDsHUItDI"
CHAT_ID = "1671953952"
WIN_STREAK_THRESHOLD = 3
LOSS_STREAK_THRESHOLD = 3
CHECK_INTERVAL = 120  # segundos
TARGET_URL = "https://www.winnershub.net/cla-efootball"
# ─────────────────────────────────────────────────────────────

sent_alerts: set[str] = set()
player_history: dict[str, list[str]] = {}
seen_match_keys: set[str] = set()


async def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, timeout=10)
            if resp.status_code != 200:
                print(f"[TELEGRAM ERROR] {resp.text}")
        except Exception as e:
            print(f"[TELEGRAM EXCEPTION] {e}")


def get_current_streak(form: list[str]) -> tuple:
    if not form:
        return None, 0
    last = form[-1]
    count = 0
    for r in reversed(form):
        if r == last:
            count += 1
        else:
            break
    return last, count


def parse_score(text: str):
    m = re.search(r'(\d+)\s*:\s*(\d+)', text)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


async def scrape_with_playwright() -> list[dict]:
    matches = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            viewport={"width": 1440, "height": 900}
        )
        page = await context.new_page()
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Abrindo site...")
            await page.goto(TARGET_URL, wait_until="networkidle", timeout=40000)
            await asyncio.sleep(4)

            # Clica em SCHEDULE se existir
            try:
                btn = page.locator("text=SCHEDULE").first
                await btn.click(timeout=5000)
                await asyncio.sleep(3)
            except Exception:
                pass

            # Pega todo o texto da página estruturado por linhas
            content = await page.inner_text("body")
            lines = [l.strip() for l in content.split("\n") if l.strip()]

            # Varre as linhas procurando padrão de partida
            i = 0
            while i < len(lines):
                line = lines[i]
                # Linha de horário: HH:MM
                if re.match(r'^\d{1,2}:\d{2}$', line):
                    time_val = line
                    # Próximas linhas: time1, player1, score, time2, player2
                    chunk = lines[i:i+10]
                    score_idx = None
                    for j, c in enumerate(chunk):
                        if re.search(r'\d+\s*:\s*\d+', c) and j > 0:
                            score_idx = j
                            break
                    if score_idx and score_idx >= 2:
                        score_text = chunk[score_idx]
                        scores = parse_score(score_text)
                        if scores:
                            g1, g2 = scores
                            # Jogador 1 = linha antes do placar (pulando nome do time)
                            p1_candidates = [c for c in chunk[1:score_idx] if len(c) > 1 and not c.isupper() or len(c) > 5]
                            p2_candidates = [c for c in chunk[score_idx+1:score_idx+5] if len(c) > 1]
                            p1 = p1_candidates[-1] if p1_candidates else None
                            p2 = p2_candidates[1] if len(p2_candidates) > 1 else (p2_candidates[0] if p2_candidates else None)
                            is_live = any("▶" in c or "LIVE" in c.upper() for c in chunk[:score_idx+3])
                            if p1 and p2 and p1 != p2:
                                matches.append({
                                    "time": time_val,
                                    "p1": p1, "p2": p2,
                                    "g1": g1, "g2": g2,
                                    "is_live": is_live
                                })
                i += 1

            print(f"[{datetime.now().strftime('%H:%M:%S')}] {len(matches)} partidas encontradas")

        except Exception as e:
            print(f"[BROWSER ERROR] {e}")
        finally:
            await browser.close()
    return matches


def update_history(matches: list[dict]):
    for m in matches:
        if m["is_live"]:
            continue
        key = f"{m['time']}|{m['p1']}|{m['p2']}|{m['g1']}:{m['g2']}"
        if key in seen_match_keys:
            continue
        seen_match_keys.add(key)

        p1, p2, g1, g2 = m["p1"], m["p2"], m["g1"], m["g2"]
        player_history.setdefault(p1, [])
        player_history.setdefault(p2, [])

        if g1 > g2:
            player_history[p1].append("W")
            player_history[p2].append("L")
        elif g2 > g1:
            player_history[p1].append("L")
            player_history[p2].append("W")
        else:
            player_history[p1].append("D")
            player_history[p2].append("D")

        player_history[p1] = player_history[p1][-30:]
        player_history[p2] = player_history[p2][-30:]


def check_alerts() -> list[str]:
    alerts = []
    for player, form in player_history.items():
        streak_type, count = get_current_streak(form)

        if streak_type == "W" and count >= WIN_STREAK_THRESHOLD:
            key = f"WIN|{player}|{count}"
            if key not in sent_alerts:
                # limpa alertas anteriores do mesmo jogador
                for k in list(sent_alerts):
                    if k.startswith(f"WIN|{player}|"):
                        sent_alerts.discard(k)
                sent_alerts.add(key)
                dots = "🟢" * min(count, 8)
                alerts.append(
                    f"🔥 <b>{player}</b> — SEQUÊNCIA DE VITÓRIAS!\n"
                    f"{dots}\n"
                    f"✅ <b>{count} vitórias seguidas</b>\n"
                    f"💰 Apostar <b>NA vitória</b> dele\n"
                    f"📊 Forma recente: {' '.join(form[-8:])}"
                )

        elif streak_type == "L" and count >= LOSS_STREAK_THRESHOLD:
            key = f"LOSS|{player}|{count}"
            if key not in sent_alerts:
                for k in list(sent_alerts):
                    if k.startswith(f"LOSS|{player}|"):
                        sent_alerts.discard(k)
                sent_alerts.add(key)
                dots = "🔴" * min(count, 8)
                alerts.append(
                    f"📉 <b>{player}</b> — SEQUÊNCIA DE DERROTAS!\n"
                    f"{dots}\n"
                    f"❌ <b>{count} derrotas seguidas</b>\n"
                    f"💰 Apostar <b>CONTRA</b> ele\n"
                    f"📊 Forma recente: {' '.join(form[-8:])}"
                )
        else:
            # Sequência quebrou — limpa alertas para não rereportar
            if streak_type != "W":
                for k in list(sent_alerts):
                    if k.startswith(f"WIN|{player}|"):
                        sent_alerts.discard(k)
            if streak_type != "L":
                for k in list(sent_alerts):
                    if k.startswith(f"LOSS|{player}|"):
                        sent_alerts.discard(k)

    return alerts


async def run():
    print("=" * 50)
    print("  CLA eFootball Monitor v1.0")
    print(f"  Alerta vitórias: {WIN_STREAK_THRESHOLD}+  |  Derrotas: {LOSS_STREAK_THRESHOLD}+")
    print(f"  Intervalo: {CHECK_INTERVAL}s")
    print("=" * 50)

    await send_telegram(
        "✅ <b>CLA Monitor iniciado!</b>\n\n"
        f"🔍 Monitorando a cada {CHECK_INTERVAL // 60} minutos\n"
        f"🔥 Alerta de vitórias: {WIN_STREAK_THRESHOLD}+ seguidas\n"
        f"📉 Alerta de derrotas: {LOSS_STREAK_THRESHOLD}+ seguidas\n\n"
        "Aguarde os primeiros alertas..."
    )

    cycle = 0
    while True:
        cycle += 1
        now = datetime.now().strftime("%d/%m %H:%M:%S")
        print(f"\n[Ciclo {cycle}] {now}")

        try:
            matches = await scrape_with_playwright()
            if matches:
                update_history(matches)
                alerts = check_alerts()
                for alert in alerts:
                    print(f"[ALERTA ENVIADO]")
                    await send_telegram(alert)

                # Status resumido a cada hora (30 ciclos de 2min)
                if cycle % 30 == 0 and player_history:
                    lines = []
                    for p, h in sorted(player_history.items()):
                        st, cnt = get_current_streak(h)
                        streak_str = f"{cnt}{st}" if st else "-"
                        lines.append(f"• {p}: {' '.join(h[-5:])}  seq:{streak_str}")
                    await send_telegram(
                        f"📊 <b>Resumo horário</b>\n\n" + "\n".join(lines)
                    )
            else:
                print("[AVISO] Nenhuma partida lida")

        except Exception as e:
            print(f"[ERRO] {e}")

        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(run())
