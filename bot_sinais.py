import os
import time
import json
import threading
import urllib.request
import urllib.parse
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

# --- CONFIGURAÇÕES DO TELEGRAM ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "SEU_TOKEN_AQUI")
CHAT_ID = os.environ.get("CHAT_ID", "SEU_CHAT_ID_AQUI")
LINK_BETANO = "https://www.betano.com"

LIGAS = {
    "Euro Copa": {"id": "euro", "offset": 0},
    "Clássicos": {"id": "classico", "offset": 1},
    "Copa América": {"id": "copa", "offset": 2}
}

sinais_ativos = []

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }).encode("utf-8")
    
    headers = {"Content-Type": "application/json"}
    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            pass
    except Exception as e:
        print(f"Erro no Telegram: {e}", flush=True)

def buscar_resultados_betano(liga_key):
    url = f"https://br.betano.com/api/virtuals/results/{LIGAS[liga_key]['id']}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                dados = json.loads(response.read().decode("utf-8"))
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
    except Exception:
        pass
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
        if len(jogos) < 5:
            continue
        
        if any(s["liga"] == liga_key for s in sinais_ativos):
            continue

        ultimos_3 = jogos[:3]
        sequencia_sem_ambas = all(not j["ambas"] for j in ultimos_3)
        assertividade = calcular_assertividade_liga(jogos)
        
        if sequencia_sem_ambas and assertividade >= 52:
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
