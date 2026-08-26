import os
import time
import requests
from datetime import datetime, timezone, timedelta

# Configurações do Telegram
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8505709973:AAE_RvUEyNxXk2MB9LcxWP8jYRTeSG3PKl4")
CHAT_ID = os.environ.get("CHAT_ID", "SEU_CHAT_ID_AQUI")
LINK_BETANO = "https://www.betano.com"

# Ligas e seus IDs no Futebol Virtual da Betano
LIGAS = {
    "Euro Copa": {"id": "euro", "offset": 0},
    "Clássicos": {"id": "classico", "offset": 1},
    "Copa América": {"id": "copa", "offset": 2}
}

# Armazenamento em memória dos resultados
historico_jogos = {liga: [] for liga in LIGAS}
sinais_ativos = []

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensagem, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erro ao enviar Telegram: {e}")

def buscar_resultados_betano(liga_key):
    """Busca os últimos resultados da liga via API"""
    # Endpoint de simulação da API de resultados Betano
    url = f"https://br.betano.com/api/virtuals/results/{LIGAS[liga_key]['id']}"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            dados = r.json()
            # Retorna lista de jogos com placares [home, away]
            return [{"home": j["homeScore"], "away": j["awayScore"], "ambas": j["homeScore"] > 0 and j["awayScore"] > 0} for j in dados.get("games", [])]
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
        
        # Regra 1: Verificar se os últimos 3 jogos NÃO bateram Ambas Marcam
        ultimos_3 = jogos[:3]
        sequencia_sem_ambas = all(not j["ambas"] for j in ultimos_3)
        
        # Regra 2: Assertividade da liga precisa estar acima de 52%
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
            
            # Registra o sinal para acompanhamento de GREEN/RED
            sinais_ativos.append({
                "liga": liga_key,
                "horarios": horarios,
                "tiro_atual": 0
            })

def verificar_green_red():
    for sinal in sinais_ativos[:]:
        jogos = buscar_resultados_betano(sinal["liga"])
        if not jogos:
            continue
        
        ultimo_jogo = jogos[0]
        if ultimo_jogo["ambas"]:
            tiro_txt = "1º TIRO (SEM GALE)" if sinal["tiro_atual"] == 0 else f"{sinal['tiro_atual'] + 1}º TIRO (GALE {sinal['tiro_atual']})"
            msg_green = (
                f"<b>BINGO! GREEN CONFIRMADO! ✅🎯</b>\n\n"
                f"🏟️ <b>LIGA:</b> {sinal['liga']}\n"
                f"🎯 <b>ENTRADA:</b> AMBAS MARCAM (SIM)\n"
                f"⚽ <b>PLACAR REAL:</b> {ultimo_jogo['home']} x {ultimo_jogo['away']}\n"
                f"🔥 <b>RESULTADO:</b> Batemos no {tiro_txt}!\n\n"
                f"💰 <i>Lucro no bolso!</i>"
            )
            enviar_telegram(msg_green)
            sinais_ativos.remove(sinal)
        else:
            sinal["tiro_atual"] += 1
            if sinal["tiro_atual"] >= 3:
                msg_red = (
                    f"<b>❌ RED CONFIRMADO (SINAL FINALIZADO) ❌</b>\n\n"
                    f"🏟️ <b>LIGA:</b> {sinal['liga']}\n"
                    f"🎯 <b>ENTRADA:</b> AMBAS MARCAM (SIM)\n\n"
                    f"⚠️ <i>Respeite o stop-loss e aguarde a próxima oportunidade.</i>"
                )
                enviar_telegram(msg_red)
                sinais_ativos.remove(sinal)

if __name__ == "__main__":
    print("Bot Analítico Betano iniciado...")
    while True:
        analisar_e_operar()
        verificar_green_red()
        time.sleep(60)
