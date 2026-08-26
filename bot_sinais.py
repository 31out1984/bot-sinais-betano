import os
import time
import itertools
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Servidor para enganar a checagem de porta do Render
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot esta rodando!")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# Inicia o servidor em segundo plano
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot esta rodando!")

def run_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# ATENÇÃO PARA O FECHAMENTO DOS PARÊNTESES NO FINAL:
threading.Thread(target=run_server, daemon=True).start()

# ------------------------------------------------------------------
# CONFIGURAÇÕES TELEGRAM
# ------------------------------------------------------------------
TELEGRAM_TOKEN = "8505709973:AAE_RvUEyNxXk2MB9LcxWP8jYRTeSG3PKl4"
CHAT_ID = "-1001767631044"  # Seu CHAT_ID ou @canal
LINK_BETANO = "https://www.betano.br/sport/futebol-virtual/"

LIGAS_MONITORADAS = [
    "Clássico das Américas",
    "Copa América",
    "Euro"
]

def enviar_mensagem(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": texto,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    headers = {'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
    data = json.dumps(payload).encode('utf-8')

    contexto_ssl = ssl.create_default_context()
    contexto_ssl.check_hostname = False
    contexto_ssl.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, data=data, headers=headers)

    try:
        with urllib.request.urlopen(req, context=contexto_ssl, timeout=10) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            if res_data.get("ok"):
                print("[+] Mensagem enviada no Telegram!", flush=True)
            else:
                print("[-] Erro do Telegram:", res_data, flush=True)
    except Exception as e:
        print("[-] Falha no envio:", e, flush=True)

# ------------------------------------------------------------------
# CÁLCULO DOS HORÁRIOS DA GRADE (FUSO HORÁRIO DE BRASÍLIA UTC-3)
# ------------------------------------------------------------------
def calcular_horarios_grade(liga):
    # Garante o horário exato de Brasília (UTC-3)
    fuso_brasil = timezone(timedelta(hours=-3))
    agora_br = datetime.now(timezone.utc).astimezone(fuso_brasil)

    # Dá 2 minutos de margem a partir de agora em Brasília
    base = agora_br + timedelta(minutes=2)
    minuto_atual = base.minute

    if "Clássico" in liga or "Classico" in liga:
        offset = 1  # :01, :04, :07, :10, :13, :16, :19...
    elif "Copa América" in liga or "Copa America" in liga:
        offset = 2  # :02, :05, :08, :11, :14, :17, :20...
    else:  # Euro
        offset = 0  # :00, :03, :06, :09, :12, :15, :18...

    resto = (minuto_atual - offset) % 3
    if resto != 0:
        minuto_proximo = minuto_atual + (3 - resto)
    else:
        minuto_proximo = minuto_atual

    primeiro_jogo = base.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=minuto_proximo)

    t1 = primeiro_jogo.strftime("%H:%M")
    t2 = (primeiro_jogo + timedelta(minutes=3)).strftime("%H:%M")
    t3 = (primeiro_jogo + timedelta(minutes=6)).strftime("%H:%M")

    return [t1, t2, t3]

# ------------------------------------------------------------------
# MENSAGENS DE SINAL, GREEN E RED
# ------------------------------------------------------------------
def enviar_sinal(liga):
    horarios = calcular_horarios_grade(liga)
    horarios_str = " | ".join(horarios)

    mensagem = f"""<b>⚽ SINAL CONFIRMADO - BETANO VIRTUAL ⚽</b>

🏟 <b>LIGA:</b> {liga}
🎯 <b>ENTRADA:</b> AMBAS MARCAM (SIM)
⏰ <b>HORÁRIOS:</b> {horarios_str}
🛡 <b>PROTEÇÃO:</b> Até 3 Tiros (Gale 2)

👉 <a href="{LINK_BETANO}">CLIQUE AQUI PARA APOSTAR NA BETANO</a>

⚠️ <i>Siga sua gestão de banca!</i>"""

    enviar_mensagem(mensagem)
    return horarios

def enviar_green(liga, tiro, placar):
    if tiro == 1:
        detalhe = "1º TIRO (SEM GALE)"
    else:
        detalhe = f"{tiro}º TIRO (GALE {tiro-1})"

    mensagem = f"""<b>BINGO! GREEN CONFIRMADO! ✅🎯</b>

🏟 <b>LIGA:</b> {liga}
🎯 <b>ENTRADA:</b> AMBAS MARCAM (SIM)
⚽ <b>PLACAR REAL:</b> {placar}
🔥 <b>RESULTADO:</b> Batemos no {detalhe}!

💰 <i>Lucro no bolso! Parabéns aos que pegaram!</i>
👉 <a href="{LINK_BETANO}">APOSTAR NA PRÓXIMA</a>"""
    enviar_mensagem(mensagem)

def enviar_red(liga):
    mensagem = f"""<b>❌ RED CONFIRMADO (SINAL FINALIZADO) ❌</b>

🏟 <b>LIGA:</b> {liga}
🎯 <b>ENTRADA:</b> AMBAS MARCAM (SIM)

⚠️ <i>Mantenha a gestão de banca! Respeite o stop-loss e aguarde a próxima oportunidade.</i>"""
    enviar_mensagem(mensagem)

# ------------------------------------------------------------------
# CONSULTA DE RESULTADOS NA API DA BETANO
# ------------------------------------------------------------------
def buscar_placar_real(liga, horario_alvo):
    url_results = "https://www.betano.br/api/virtuals/results"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json"
    }

    contexto_ssl = ssl.create_default_context()
    contexto_ssl.check_hostname = False
    contexto_ssl.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url_results, headers=headers)

    try:
        with urllib.request.urlopen(req, context=contexto_ssl, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))

            for evento in data.get("events", []):
                horario_evento = evento.get("time")
                nome_liga = evento.get("leagueName", "")

                if horario_evento == horario_alvo and liga.lower() in nome_liga.lower():
                    gols_casa = int(evento.get("homeScore", 0))
                    gols_fora = int(evento.get("awayScore", 0))

                    ambas_marcaram = (gols_casa > 0) and (gols_fora > 0)
                    placar = f"{gols_casa} x {gols_fora}"

                    return ambas_marcaram, placar
    except Exception as e:
        print(f"[-] Erro ao buscar resultado na Betano ({horario_alvo}): {e}", flush=True)

    return None, None

# ------------------------------------------------------------------
# VERIFICAÇÃO REAL COM REPETIÇÃO
# ------------------------------------------------------------------
def verificar_resultado_real(liga, horarios):
    for i, hor in enumerate(horarios, start=1):
        print(f"[*] Aguardando término do jogo das {hor} (Tiro {i})...", flush=True)

        # Espera o tempo aproximado do jogo
        time.sleep(160)

        # Faz até 4 tentativas com intervalo de 15 segundos para dar tempo de atualizar na Betano
        ambas_marcaram = False
        placar_final = "N/D"

        for tentativa in range(4):
            ambas, placar = buscar_placar_real(liga, hor)
            if ambas is not None:
                ambas_marcaram = ambas
                placar_final = placar
                break
            time.sleep(15)

        print(f"[>] Jogo {hor} | Placar: {placar_final} | Ambas Marcam: {ambas_marcaram}", flush=True)

        if ambas_marcaram:
            enviar_green(liga, i, placar_final)
            return True

    enviar_red(liga)
    return False

# ------------------------------------------------------------------
# LOOP PRINCIPAL
# ------------------------------------------------------------------
def monitorar_jogos():
    print("==========================================", flush=True)
    print("ROBÔ MESTRE DOS GREENS - CORRIGIDO", flush=True)
    print("==========================================", flush=True)

    ciclo_ligas = itertools.cycle(LIGAS_MONITORADAS)

    while True:
        try:
            liga_atual = next(ciclo_ligas)

            horarios = enviar_sinal(liga_atual)
            print(f"[+] Sinal enviado ({liga_atual}): {horarios}", flush=True)

            verificar_resultado_real(liga_atual, horarios)

            print("[+] Aguardando 5 minutos para o próximo sinal...", flush=True)
            time.sleep(300)

        except Exception as e:
            print(f"[-] Erro recuperado: {e}", flush=True)
            time.sleep(10)

if __name__ == "__main__":
    monitorar_jogos()
