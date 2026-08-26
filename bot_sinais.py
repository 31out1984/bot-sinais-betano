import os
import time
import json
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone, timedelta

# --- SERVIDOR WEB SIMPLES PARA O RENDER ---
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot Analitico Betano - Online")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

def iniciar_servidor_web():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    print(f"Servidor Web ativo na porta {port}", flush=True)
    server.serve_forever()

# --- CONFIGURAÇÕES ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8505709973:AAE_RvUEyNxXk2MB9LcxWP8jYRTeSG3PKl4")
CHAT_ID = os.environ.get("CHAT_ID", "SEU_CHAT_ID_AQUI")
# Insira sua chave gratuita do ScraperAPI abaixo ou configure nas Environment Variables do Render
SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY", "SUA_API_KEY_DO_SCRAPERAPI_AQUI")

LINK_BETANO = "https://www.betano.com"

LIGAS = {
    "Euro Copa": {"id": "euro", "offset": 0},
    "Clássicos": {"id": "classico", "offset": 1},
    "Copa América": {"id": "copa", "offset": 2}
}

sinais_ativos = []

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erro no Telegram: {e}", flush=True)

def buscar_resultados_betano(liga_key):
    target_url = f"https://br.betano.com/api/virtuals/results/{LIGAS[liga_key]['id']}"
    
    # Rotação de IP residencial via ScraperAPI para passar 100% no 403
    payload = {
        'api_key': SCRAPER_API_KEY,
        'url': target_url,
        'keep_headers': 'true'
    }

    try:
        response = requests.get('http://api.scraperapi.com', params=payload, timeout=25)
        if response.status_code == 200:
            dados = response.json()
            jogos = []
            for j in dados.get("games", []):
                home = j.get("homeScore", 0)
                away = j.get("awayScore", 0)
                jogos.append({
                    "id": j.get("id"),
                    "home": home,
                    "away": away,
                    "ambas": home > 0 and away > 0
                })
            return jogos
        else:
            print(f"Erro Betano ({liga_key}): Status {response.status_code}", flush=True)
    except Exception as e:
        print(f"Erro na requisição ({liga_key}): {e}", flush=True)
    return []

def calcular_assertividade_liga(jogos):
    if not jogos:
        return 0
    ambas_sim = sum(1 for j in jogos if j["ambas"])
    return int((ambas_sim / len(jogos)) * 100)

def calcular_proximos_horarios(liga_key):
    fuso_brasil = timezone(timedelta(hours=-3))
    agora = datetime.now(timezone.utc).astimezone(fuso_brasil) + timedelta(minutes=2)
    offset = LIGAS[liga_key]["offset"]
    
    resto = (agora.minute - offset) % 3
    proximo_minuto = agora.minute if resto == 0 else agora.minute + (3 - resto)
    base = agora.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=proximo_minuto)
    
    t1 = base.strftime("%H:%M")
    t2 = (base + timedelta(minutes=3)).strftime("%H:%M")
    t3 = (base + timedelta(minutes=6)).strftime("%H:%M")
    return [t1, t2, t3]

def analisar_e_operar():
    for liga_key in LIGAS:
        jogos = buscar_resultados_betano(liga_key)
        if len(jogos) < 3:
            continue
        
        if any(s["liga"] == liga_key for s in sinais_ativos):
            continue

        ultimos_3 = jogos[:3]
        sequencia_sem_ambas = all(not j["ambas"] for j in ultimos_3)
        assertividade = calcular_assertividade_liga(jogos)
        
        if sequencia_sem_ambas and assertividade >= 40:
            horarios = calcular_proximos_horarios(liga_key)
            horarios_str = " | ".join(horarios)
            
            msg = (
                f"⚽ <b>SINAL CONFIRMADO - BETANO VIRTUAL</b> ⚽\n\n"
                f"🏟️ <b>LIGA:</b> {liga_key}\n"
                f"🎯 <b>ENTRADA:</b> AMBAS MARCAM (SIM)\n"
                f"⏰ <b>HORÁRIOS:</b> {horarios_str}\n"
                f"🛡️ <b>PROTEÇÃO:</b> Até 2 Gales (3 Tiros)\n"
                f"📊 <b>ASSERTIVIDADE DA LIGA:</b> {assertividade}%\n\n"
                f"👉 <a href='{LINK_BETANO}'>CLIQUE AQUI PARA APOSTAR</a>\n"
                f"⚠️ <i>Siga sua gestão de banca!</i>"
            )
            enviar_telegram(msg)
            
            ultimo_id_conhecido = jogos[0]["id"] if jogos else None
            
            sinais_ativos.append({
                "liga": liga_key,
                "horarios": horarios,
                "ultimo_id": ultimo_id_conhecido,
                "tiro_atual": 0
            })
            print(f"Sinal disparado para {liga_key}!", flush=True)

def verificar_green_red():
    for sinal in sinais_ativos[:]:
        jogos = buscar_resultados_betano(sinal["liga"])
        if not jogos:
            continue
        
        jogo_mais_recente = jogos[0]
        
        if jogo_mais_recente["id"] != sinal["ultimo_id"]:
            sinal["ultimo_id"] = jogo_mais_recente["id"]
            sinal["tiro_atual"] += 1
            
            if jogo_mais_recente["ambas"]:
                tiro_txt = "1º TIRO (SEM GALE)" if sinal["tiro_atual"] == 1 else f"{sinal['tiro_atual']}º TIRO (GALE {sinal['tiro_atual'] - 1})"
                msg_green = (
                    f"<b>BINGO! GREEN CONFIRMADO! ✅🎯</b>\n\n"
                    f"🏟️ <b>LIGA:</b> {sinal['liga']}\n"
                    f"🎯 <b>ENTRADA:</b> AMBAS MARCAM (SIM)\n"
                    f"⚽ <b>PLACAR REAL:</b> {jogo_mais_recente['home']} x {jogo_mais_recente['away']}\n"
                    f"🔥 <b>RESULTADO:</b> Batemos no {tiro_txt}!\n\n"
                    f"💰 <i>Lucro no bolso!</i>"
                )
                enviar_telegram(msg_green)
                sinais_ativos.remove(sinal)
            elif sinal["tiro_atual"] >= 3:
                msg_red = (
                    f"<b>❌ RED CONFIRMADO (SINAL FINALIZADO) ❌</b>\n\n"
                    f"🏟️ <b>LIGA:</b> {sinal['liga']}\n"
                    f"🎯 <b>ENTRADA:</b> AMBAS MARCAM (SIM)\n\n"
                    f"⚠️ <i>Respeite o stop-loss e aguarde a próxima oportunidade.</i>"
                )
                enviar_telegram(msg_red)
                sinais_ativos.remove(sinal)

if __name__ == "__main__":
    t = threading.Thread(target=iniciar_servidor_web, daemon=True)
    t.start()

    print("Bot Analítico Betano iniciado...", flush=True)
    while True:
        analisar_e_operar()
        verificar_green_red()
        time.sleep(30)
