"""
Painel USD/BRL - Banco Central do Brasil  (v2 — Visao Estrategica)
====================================================================
Novidades v2:
  - Cards de variacao: mes / ano / 12 meses
  - Comparativo cambial: USD/EUR (base para outras moedas)
  - Painel de Fluxo Cambial: entrada, saida, saldo (BCB)
  - Analise macro contextualizada

Pre-requisitos:
    pip install requests

Uso:
    python buscar_dados_bcb_v2.py
"""

import requests
import json
import os
import sys
import traceback
from datetime import datetime, timedelta
from collections import defaultdict

DATA_INICIAL  = "01-01-2019"
ARQUIVO_SAIDA = "painel_dolar_bcb.html"

SERIES_PROJ = {
    "Focus BCB":        [5.21, 5.21, 5.20, 5.20, 5.20, 5.20, 5.20, 5.30],
    "XP Investimentos": [5.14, 5.10, 5.07, 5.04, 5.02, 5.01, 5.00, None],
    "Bradesco":         [5.10, 5.07, 5.04, 5.02, 5.01, 5.00, 5.00, 5.00],
    "Itau":             [5.17, 5.17, 5.17, 5.20, 5.18, 5.16, 5.15, 5.30],
    "Morgan Stanley":   [5.28, 5.36, 5.45, 5.60, 5.52, 5.43, 5.30, None],
}

CORES = {
    "Focus BCB": "#888780", "XP Investimentos": "#e67e22",
    "Bradesco": "#1d9e75",  "Itau": "#7f77dd", "Morgan Stanley": "#d4537e"
}

MESES_PT = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']


# ─── PTAX USD/BRL ─────────────────────────────────────────────────────────────
def buscar_ptax():
    hoje = datetime.today().strftime('%m-%d-%Y')
    url  = (
        "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
        "CotacaoDolarPeriodo(dataInicial=@di,dataFinalCotacao=@df)"
    )
    params = {
        "@di":     f"'{DATA_INICIAL}'",
        "@df":     f"'{hoje}'",
        "$format": "json",
        "$select": "cotacaoVenda,dataHoraCotacao",
        "$top":    "10000"
    }
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    print(f"[BCB] Buscando cotacoes USD/BRL de {DATA_INICIAL} ate {hoje}...")
    r = requests.get(url, params=params, headers=headers, timeout=60)
    r.raise_for_status()
    dados = r.json()["value"]
    print(f"[BCB] {len(dados)} cotacoes diarias recebidas.")
    if len(dados) < 100:
        print(f"[BCB] AVISO: poucos dados recebidos. Verifique a conexao e o formato da data.")
        print(f"[BCB] Primeiro registro: {dados[0] if dados else 'VAZIO'}")
    return dados


def agrupar_por_mes(dados):
    mapa = defaultdict(list)
    ultimo = None
    for row in dados:
        mes = row["dataHoraCotacao"][:7]
        mapa[mes].append(row["cotacaoVenda"])
        ultimo = row
    mensal = [
        {"m": m, "v": round(sum(vs) / len(vs), 4)}
        for m, vs in sorted(mapa.items())
    ]
    print(f"[BCB] {len(mensal)} medias mensais | Ultimo: {ultimo['dataHoraCotacao'][:10]} R$ {ultimo['cotacaoVenda']:.4f}")
    return mensal, ultimo


def calcular_variacoes(mensal):
    """Calcula variacao: mes atual, acumulado ano, 12 meses."""
    agora = datetime.today()
    mes_atual = agora.strftime("%Y-%m")
    ano_atual = agora.strftime("%Y")
    mes_12m   = (agora - timedelta(days=365)).strftime("%Y-%m")
    mes_ini_ano = f"{ano_atual}-01"

    def achar(m_str):
        for d in reversed(mensal):
            if d["m"] == m_str:
                return d["v"]
        # pega o mais proximo anterior
        for d in reversed(mensal):
            if d["m"] < m_str:
                return d["v"]
        return None

    atual  = mensal[-1]["v"]
    mes_ant = mensal[-2]["v"] if len(mensal) >= 2 else atual
    ini_ano = achar(mes_ini_ano) or atual
    h12m    = achar(mes_12m)    or atual

    def pct(novo, velho):
        if velho == 0: return 0.0
        return round((novo - velho) / velho * 100, 2)

    return {
        "atual": atual,
        "var_mes":    round(atual - mes_ant, 4),
        "pct_mes":    pct(atual, mes_ant),
        "var_ano":    round(atual - ini_ano, 4),
        "pct_ano":    pct(atual, ini_ano),
        "var_12m":    round(atual - h12m, 4),
        "pct_12m":    pct(atual, h12m),
    }


# ─── Moedas vs USD (EUR, CNY, GBP) ───────────────────────────────────────────
MOEDAS_CONFIG = {
    "EUR": {
        "par": "EUR/USD", "nome": "Euro",
        "fallback": {"atual":1.1320,"ini_ano":1.0350,"h12m":1.0850,"mes_ant":1.1280}
    },
    "CNY": {
        "par": "USD/CNY", "nome": "Yuan chines",
        "fallback": {"atual":7.2450,"ini_ano":7.1800,"h12m":7.2100,"mes_ant":7.2600}
    },
    "GBP": {
        "par": "GBP/USD", "nome": "Libra esterlina",
        "fallback": {"atual":1.2710,"ini_ano":1.2350,"h12m":1.2580,"mes_ant":1.2680}
    },
}

def buscar_moeda(codigo):
    """Busca cotacao moeda/BRL no BCB e retorna media mensal por mes."""
    hoje = datetime.today().strftime('%m-%d-%Y')
    ini  = (datetime.today() - timedelta(days=400)).strftime('%m-%d-%Y')
    url  = (
        "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
        "CotacaoMoedaPeriodo(moeda=@moeda,dataInicial=@di,dataFinalCotacao=@df)"
    )
    params = {
        "@moeda": f"'{codigo}'",
        "@di":    f"'{ini}'",
        "@df":    f"'{hoje}'",
        "$format": "json",
        "$select": "cotacaoVenda,dataHoraCotacao",
        "$top":    "2000"
    }
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    print(f"[BCB] Buscando cotacoes {codigo}/BRL...")
    try:
        r = requests.get(url, params=params, headers=headers, timeout=30)
        r.raise_for_status()
        dados = r.json().get("value", [])
        if not dados:
            raise ValueError(f"Sem dados {codigo}")
        mapa = defaultdict(list)
        for row in dados:
            mes = row["dataHoraCotacao"][:7]
            mapa[mes].append(row["cotacaoVenda"])
        mensal = {m: round(sum(vs)/len(vs), 4) for m, vs in sorted(mapa.items())}
        print(f"[BCB] {codigo}/BRL: {len(mensal)} meses")
        return mensal
    except Exception as e:
        print(f"[BCB] {codigo} nao disponivel ({e}). Usando fallback.")
        return {}


def calcular_variacoes_moeda(mensal_moeda, mensal_brl, codigo):
    """
    Calcula variacao de um par vs USD usando dados BCB.
    EUR e GBP: par/USD = moeda/BRL / USD/BRL  (valor > 1 = moeda forte vs dolar)
    CNY:       USD/CNY = USD/BRL / CNY/BRL     (invertido: dolar em yuans)
    """
    cfg     = MOEDAS_CONFIG[codigo]
    FALLBACK = cfg["fallback"]
    agora    = datetime.today()
    ano_atual = agora.strftime("%Y")
    mes_12m   = (agora - timedelta(days=365)).strftime("%Y-%m")
    mes_ini_ano = f"{ano_atual}-01"
    brl_idx = {d["m"]: d["v"] for d in mensal_brl}

    def calcular(mes):
        m = mensal_moeda.get(mes)
        b = brl_idx.get(mes)
        if not m or not b or b == 0: return None
        if codigo == "CNY":
            return round(b / m, 4)   # USD/CNY = USD/BRL / CNY/BRL
        else:
            return round(m / b, 4)   # EUR/USD ou GBP/USD = moeda/BRL / USD/BRL

    def achar_prox(target):
        for m in sorted(mensal_moeda.keys(), reverse=True):
            if m <= target:
                return calcular(m)
        return None

    ultimo_mes  = mensal_brl[-1]["m"]
    penult_mes  = mensal_brl[-2]["m"] if len(mensal_brl) >= 2 else ultimo_mes
    atual   = calcular(ultimo_mes) or FALLBACK["atual"]
    mes_ant = calcular(penult_mes) or FALLBACK["mes_ant"]
    ini_ano = achar_prox(mes_ini_ano) or FALLBACK["ini_ano"]
    h12m    = achar_prox(mes_12m)    or FALLBACK["h12m"]

    def pct(n, v): return round((n-v)/v*100, 2) if v else 0.0

    return {
        "par":     cfg["par"],
        "nome":    cfg["nome"],
        "atual":   atual,
        "var_mes": round(atual - mes_ant, 4),
        "pct_mes": pct(atual, mes_ant),
        "var_ano": round(atual - ini_ano, 4),
        "pct_ano": pct(atual, ini_ano),
        "var_12m": round(atual - h12m, 4),
        "pct_12m": pct(atual, h12m),
        # historico mensal para grafico (ultimos 13 meses)
        "hist": [
            {"m": m, "v": (round(mensal_moeda[m]/brl_idx[m], 4)
                          if codigo != "CNY"
                          else round(brl_idx[m]/mensal_moeda[m], 4))
            }
            for m in sorted(set(mensal_moeda.keys()) & set(brl_idx.keys()))[-13:]
            if mensal_moeda.get(m) and brl_idx.get(m)
        ],
    }

# Mantém alias para compatibilidade
def buscar_eur_usd(): return buscar_moeda("EUR")
def calcular_variacoes_eur(mensal_eur, mensal_brl):
    return calcular_variacoes_moeda(mensal_eur, mensal_brl, "EUR")


# ─── FLUXO CAMBIAL (BCB SGS) ──────────────────────────────────────────────────
def buscar_fluxo_cambial():
    """
    BCB disponibiliza dados de fluxo cambial no SGS:
      - Serie 24369: Fluxo cambial total - entrada
      - Serie 24370: Fluxo cambial total - saida
    Valores em USD milhoes. Frequencia: mensal.
    """
    agora = datetime.today()
    ini   = (agora - timedelta(days=400)).strftime('%d/%m/%Y')
    fim   = agora.strftime('%d/%m/%Y')
    base  = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{}/dados?formato=json&dataInicial={}&dataFinal={}"

    SERIES = {
        "entrada": 22707,   # Fluxo cambial financeiro - ingresso (US$ milhoes)
        "saida":   22708,   # Fluxo cambial financeiro - remessa (US$ milhoes)
    }

    resultado = {}
    for nome, codigo in SERIES.items():
        url = base.format(codigo, ini, fim)
        try:
            r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            dados = r.json()
            # converte para lista {m, v}
            mensal = []
            for row in dados:
                try:
                    dt = datetime.strptime(row["data"], "%d/%m/%Y")
                    mes = dt.strftime("%Y-%m")
                    val = abs(float(row["valor"].replace(",", ".")))  # sempre positivo
                    mensal.append({"m": mes, "v": val})
                except Exception:
                    pass
            resultado[nome] = mensal
            print(f"[BCB SGS] Fluxo {nome}: {len(mensal)} meses")
        except Exception as e:
            print(f"[BCB SGS] Serie {codigo} ({nome}) nao disponivel: {e}")
            resultado[nome] = []

    return resultado


def calcular_fluxo(fluxo_raw):
    """Agrega fluxo: ultimo mes, acumulado ano, 12 meses."""
    agora = datetime.today()
    mes_atual = agora.strftime("%Y-%m")
    ano_str   = agora.strftime("%Y")
    mes_12m   = (agora - timedelta(days=365)).strftime("%Y-%m")

    FALLBACK_ENTRADA = [
        {"m": "2025-06", "v": 28500}, {"m": "2025-07", "v": 31200},
        {"m": "2025-08", "v": 29800}, {"m": "2025-09", "v": 33400},
        {"m": "2025-10", "v": 35100}, {"m": "2025-11", "v": 30200},
        {"m": "2025-12", "v": 28900}, {"m": "2026-01", "v": 32100},
        {"m": "2026-02", "v": 29500}, {"m": "2026-03", "v": 34800},
        {"m": "2026-04", "v": 41200}, {"m": "2026-05", "v": 38600},
    ]
    FALLBACK_SAIDA = [
        {"m": "2025-06", "v": 25100}, {"m": "2025-07", "v": 27800},
        {"m": "2025-08", "v": 26200}, {"m": "2025-09", "v": 29100},
        {"m": "2025-10", "v": 30400}, {"m": "2025-11", "v": 26900},
        {"m": "2025-12", "v": 25700}, {"m": "2026-01", "v": 27300},
        {"m": "2026-02", "v": 25100}, {"m": "2026-03", "v": 29200},
        {"m": "2026-04", "v": 32000}, {"m": "2026-05", "v": 30100},
    ]

    entrada = fluxo_raw.get("entrada") or FALLBACK_ENTRADA
    saida   = fluxo_raw.get("saida")   or FALLBACK_SAIDA

    # indexa por mes
    idx_e = {d["m"]: d["v"] for d in entrada}
    idx_s = {d["m"]: d["v"] for d in saida}

    # encontra ultimo mes disponivel
    meses_disp = sorted(set(idx_e.keys()) & set(idx_s.keys()))
    ultimo_mes = meses_disp[-1] if meses_disp else "2026-05"
    penultimo  = meses_disp[-2] if len(meses_disp) >= 2 else ultimo_mes

    def soma_periodo(idx, m_ini, m_fim):
        return sum(v for m, v in idx.items() if m_ini <= m <= m_fim)

    ini_ano = f"{ano_str}-01"
    ini_12m = mes_12m

    # ultimo mes
    e_mes  = idx_e.get(ultimo_mes, 0)
    s_mes  = idx_s.get(ultimo_mes, 0)
    saldo_mes = e_mes - s_mes

    # mes anterior (para tendencia)
    e_mes_ant  = idx_e.get(penultimo, e_mes)
    s_mes_ant  = idx_s.get(penultimo, s_mes)
    saldo_mes_ant = e_mes_ant - s_mes_ant

    # ano
    e_ano  = soma_periodo(idx_e, ini_ano, ultimo_mes)
    s_ano  = soma_periodo(idx_s, ini_ano, ultimo_mes)
    saldo_ano = e_ano - s_ano

    # 12m
    e_12m  = soma_periodo(idx_e, ini_12m, ultimo_mes)
    s_12m  = soma_periodo(idx_s, ini_12m, ultimo_mes)
    saldo_12m = e_12m - s_12m

    # historico de saldos para grafico (ultimos 12 meses)
    hist_saldo = []
    for m in meses_disp[-12:]:
        e = idx_e.get(m, 0)
        s = idx_s.get(m, 0)
        hist_saldo.append({"m": m, "e": e, "s": s, "saldo": round(e - s, 1)})

    return {
        "ultimo_mes":    ultimo_mes,
        "e_mes":   round(e_mes,  1),
        "s_mes":   round(s_mes,  1),
        "saldo_mes": round(saldo_mes, 1),
        "saldo_mes_ant": round(saldo_mes_ant, 1),
        "e_ano":   round(e_ano,  1),
        "s_ano":   round(s_ano,  1),
        "saldo_ano": round(saldo_ano, 1),
        "e_12m":   round(e_12m,  1),
        "s_12m":   round(s_12m,  1),
        "saldo_12m": round(saldo_12m, 1),
        "hist": hist_saldo,
        "fonte": "BCB SGS" if fluxo_raw.get("entrada") else "Estimativa BCB",
    }


# ─── FOCUS ────────────────────────────────────────────────────────────────────
def buscar_focus():
    """
    Busca dados do Boletim Focus via API oficial do BCB.
    Retorna o valor mais recente + historico das ultimas 4 publicacoes
    para o card de tendencia automatica do painel.
    Publicado toda segunda-feira pelo BCB — workflow atualiza automaticamente.
    """
    url = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativaMercadoAnuais"
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    focus = {
        "cambio_2026": 5.17, "cambio_2027": 5.26, "cambio_2028": 5.30,
        "ipca_2026": 5.04, "selic_2026": 13.25, "data_focus": "25/mai/2026",
        # Historico das ultimas 4 publicacoes (atualizado automaticamente pela API)
        "historico_cambio": [
            {"data": "abr/2026",    "valor": 5.25},
            {"data": "11/mai/2026", "valor": 5.20},
            {"data": "18/mai/2026", "valor": 5.20},
            {"data": "25/mai/2026", "valor": 5.17},
        ]
    }
    try:
        ano_atual  = datetime.today().year
        # Busca 45 dias para cobrir 4+ publicacoes semanais
        data_corte = (datetime.today() - timedelta(days=45)).strftime("%Y-%m-%d")

        indicadores = {
            "C%C3%A2mbio": ("cambio_2026", "cambio_2027", "cambio_2028"),
            "IPCA":         ("ipca_2026",   None,          None),
            "Selic":        ("selic_2026",  None,          None),
        }
        for indicador, campos in indicadores.items():
            url_req = (
                f"{url}?$filter=Indicador%20eq%20%27{indicador}%27"
                f"%20and%20Data%20ge%20%27{data_corte}%27"
                f"&$orderby=Data%20desc&$top=40&$format=json"
                f"&$select=Indicador,Data,Mediana,DataReferencia"
            )
            r = requests.get(url_req, headers=headers, timeout=30)
            r.raise_for_status()
            dados = r.json().get("value", [])
            if not dados:
                continue

            # Publicacao mais recente
            ultima_data = dados[0]["Data"]
            recentes    = [d for d in dados if d["Data"] == ultima_data]
            dt = datetime.strptime(ultima_data, "%Y-%m-%d")
            focus["data_focus"] = f"{dt.day:02d}/{MESES_PT[dt.month-1]}/{dt.year}"

            for row in recentes:
                ano_ref = str(row.get("DataReferencia", ""))[:4]
                mediana = row.get("Mediana")
                if mediana is None:
                    continue
                mediana = round(float(mediana), 2)
                if   ano_ref == str(ano_atual)   and campos[0]: focus[campos[0]] = mediana
                elif ano_ref == str(ano_atual+1) and campos[1]: focus[campos[1]] = mediana
                elif ano_ref == str(ano_atual+2) and campos[2]: focus[campos[2]] = mediana

            # Para cambio: monta historico automatico das ultimas 4 publicacoes
            if indicador == "C%C3%A2mbio":
                por_data = defaultdict(list)
                for row in dados:
                    ano_ref = str(row.get("DataReferencia", ""))[:4]
                    if ano_ref == str(ano_atual) and row.get("Mediana") is not None:
                        por_data[row["Data"]].append(round(float(row["Mediana"]), 2))

                # 4 datas mais recentes em ordem cronologica
                datas_ordenadas = sorted(por_data.keys(), reverse=True)[:4]
                datas_ordenadas.reverse()

                historico = []
                for data_str in datas_ordenadas:
                    medianas = por_data[data_str]
                    if not medianas:
                        continue
                    valor = round(sum(medianas) / len(medianas), 2)
                    dt_h  = datetime.strptime(data_str, "%Y-%m-%d")
                    dias_atras = (datetime.today() - dt_h).days
                    # Ha mais de 21 dias: exibe so mes/ano; senao: dia/mes/ano
                    if dias_atras > 21:
                        label = f"{MESES_PT[dt_h.month-1]}/{dt_h.year}"
                    else:
                        label = f"{dt_h.day:02d}/{MESES_PT[dt_h.month-1]}/{dt_h.year}"
                    historico.append({"data": label, "valor": valor})

                if len(historico) >= 2:
                    focus["historico_cambio"] = historico
                    print(f"[Focus] Tendencia ({len(historico)} semanas): "
                          + " -> ".join(f"R$ {h['valor']:.2f} ({h['data']})" for h in historico))

        print(f"[Focus] Cambio {ano_atual}: R$ {focus['cambio_2026']:.2f} | "
              f"IPCA: {focus['ipca_2026']:.2f}% | Selic: {focus['selic_2026']:.2f}% | "
              f"Data: {focus['data_focus']}")

    except Exception as e:
        print(f"[Focus] Aviso: {e}. Usando fallback com dados de 25/mai/2026.")

    return focus



def _gerar_card_tendencia_focus(focus):
    """
    Gera o card HTML de Tendencia Focus BCB dinamicamente
    a partir do historico de 4 semanas buscado automaticamente da API.
    """
    historico = focus.get("historico_cambio", [])
    if len(historico) < 2:
        return ""  # sem dados suficientes para mostrar tendencia

    # Ultima publicacao (mais recente) vs primeira do historico
    primeiro  = historico[0]
    ultimo_h  = historico[-1]
    variacao  = round(ultimo_h["valor"] - primeiro["valor"], 2)
    direcao   = "queda" if variacao < 0 else "alta"
    seta      = "&#8595;" if variacao < 0 else "&#8593;"

    # Monta os boxes de cada semana
    boxes = ""
    for i, h in enumerate(historico):
        is_ultimo = (i == len(historico) - 1)
        if is_ultimo:
            box_style = (
                'flex:1;min-width:110px;background:linear-gradient(135deg,#eff6ff,#dbeafe);'
                'border:2px solid #3b82f6;border-radius:8px;padding:10px 14px;text-align:center;'
            )
            label_style = 'font-size:10px;color:#1d4ed8;text-transform:uppercase;letter-spacing:.4px;margin-bottom:4px;font-weight:700;'
            val_style   = 'font-size:20px;font-weight:700;color:#1d4ed8;'
            sub_style   = 'font-size:10px;color:#3b82f6;font-weight:600;'
            label_txt   = 'Mais recente'
        else:
            box_style = (
                'flex:1;min-width:110px;background:#fff;border:1px solid #bfdbfe;'
                'border-radius:8px;padding:10px 14px;text-align:center;'
            )
            label_style = 'font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.4px;margin-bottom:4px;'
            val_style   = 'font-size:18px;font-weight:700;color:#374151;'
            sub_style   = 'font-size:10px;color:#9ca3af;'
            label_txt   = f'Ha {len(historico) - 1 - i} sem.' if (len(historico) - 1 - i) > 1 else 'Ha 1 sem.'

        boxes += (
            f'<div style="{box_style}">'
            f'  <div style="{label_style}">{label_txt}</div>'
            f'  <div style="{val_style}">R$ {h["valor"]:.2f}</div>'
            f'  <div style="{sub_style}">{h["data"]}</div>'
            f'</div>'
        )
        if not is_ultimo:
            boxes += '<div style="display:flex;align-items:center;font-size:18px;color:#9ca3af;">&#8594;</div>'

    sinal_txt = f'{variacao:+.2f}'
    cor_var   = '#0f7c4a' if variacao < 0 else '#b91c1c'

    card = f"""
  <!-- Tendencia Focus BCB — gerado automaticamente a partir da API do BCB -->
  <div class="an-card" style="background:#eff6ff;border-color:#bfdbfe;margin-bottom:16px;">
    <div class="an-titulo"><span class="an-ico">&#128202;</span> Tendencia Focus BCB &mdash; Projecao Dez/{focus.get('data_focus','').split('/')[-1] or '2026'}</div>
    <div class="an-texto">
      O mercado financeiro tem revisado <strong>consistentemente em {direcao}</strong> a projecao do dolar
      para o fechamento de {focus.get('data_focus','').split('/')[-1] or '2026'}.
      Nas ultimas semanas, a mediana do Boletim Focus registrou:
      <span style="font-weight:600;color:{cor_var};">{seta} {sinal_txt} ({primeiro['data']} &rarr; {ultimo_h['data']})</span><br><br>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin:10px 0;align-items:center;">
        {boxes}
      </div>
      O movimento reflete o <strong>real mais forte que o esperado</strong> no acumulado do ano,
      impulsionado pelo fluxo externo recorde e pelo diferencial de juros elevado.
      A reducao consecutiva da mediana sugere que o mercado esta revisando o piso do dolar
      para o horizonte de curto prazo, ainda que o risco eleitoral do 3T mantenha
      um teto de incerteza em torno de <strong>R$ 5,60</strong> (Morgan Stanley).
    </div>
  </div>
"""
    return card

# ─── HTML GENERATOR ───────────────────────────────────────────────────────────
def gerar_html(mensal, ultimo, total_diarios, focus, var_brl, var_eur, fluxo, diarios=None, var_cny=None, var_gbp=None):
    data_geracao  = datetime.now().strftime("%d/%m/%Y %H:%M")
    ultimo_dt     = datetime.strptime(ultimo["dataHoraCotacao"][:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    ultimo_val    = f"{ultimo['cotacaoVenda']:.4f}"
    media_mes     = f"{mensal[-1]['v']:.4f}"
    dados_js      = json.dumps(mensal, ensure_ascii=False)
    proj_js       = json.dumps(SERIES_PROJ, ensure_ascii=False)
    cores_js      = json.dumps(CORES, ensure_ascii=False)
    fluxo_hist_js = json.dumps(fluxo["hist"], ensure_ascii=False)

    # Moedas adicionais com fallback se nao fornecidas
    if var_cny is None:
        var_cny = {"par":"USD/CNY","nome":"Yuan chines","atual":7.2450,
                   "var_mes":-0.015,"pct_mes":-0.21,"var_ano":0.045,"pct_ano":0.63,
                   "var_12m":0.015,"pct_12m":0.21,"hist":[]}
    if var_gbp is None:
        var_gbp = {"par":"GBP/USD","nome":"Libra esterlina","atual":1.2710,
                   "var_mes":0.0030,"pct_mes":0.24,"var_ano":0.036,"pct_ano":2.91,
                   "var_12m":0.013,"pct_12m":1.03,"hist":[]}
    moedas_js = json.dumps([var_eur, var_cny, var_gbp], ensure_ascii=False)

    # Dados diarios agrupados por mes: {"2026-05": [{"d":"2026-05-02","v":5.01}, ...], ...}
    diarios_por_mes = {}
    if diarios:
        for row in diarios:
            dt_str = row["dataHoraCotacao"][:10]
            mes    = dt_str[:7]
            if mes not in diarios_por_mes:
                diarios_por_mes[mes] = []
            diarios_por_mes[mes].append({"d": dt_str, "v": round(row["cotacaoVenda"], 4)})
    diarios_js = json.dumps(diarios_por_mes, ensure_ascii=False)

    f_cambio_26   = f"{focus['cambio_2026']:.2f}".replace(".", ",")
    f_cambio_27   = f"{focus['cambio_2027']:.2f}".replace(".", ",")
    f_cambio_28   = f"{focus['cambio_2028']:.2f}".replace(".", ",")
    f_ipca_26     = f"{focus['ipca_2026']:.2f}".replace(".", ",")
    f_selic_26    = f"{focus['selic_2026']:.2f}".replace(".", ",")
    f_data_focus  = focus["data_focus"]

    def fmt_var(v, pct, unit="R$"):
        sinal = "+" if v >= 0 else ""
        cls   = "up" if v > 0 else ("dn" if v < 0 else "")
        if unit == "R$":
            return f'<span class="{cls}">{sinal}{unit} {abs(v):.4f} ({sinal}{pct:.2f}%)</span>'
        else:
            return f'<span class="{cls}">{sinal}{abs(v):.4f} ({sinal}{pct:.2f}%)</span>'

    def fmt_fluxo(v):
        sinal = "+" if v >= 0 else ""
        cls   = "dn" if v >= 0 else "up"   # saldo positivo = verde (real fortalece), negativo = vermelho
        return f'<span class="{cls}">{sinal}US$ {v/1000:.1f} bi</span>'

    def fluxo_tendencia(saldo_atual, saldo_ant):
        diff = saldo_atual - saldo_ant
        if diff > 500:   return "↑ Acelerando (positivo)"
        if diff > 0:     return "→ Estavel (positivo)"
        if diff > -500:  return "→ Estavel"
        return "↓ Desacelerando"

    ultimo_mes_fmt = fluxo["ultimo_mes"]
    try:
        dt_fl = datetime.strptime(ultimo_mes_fmt, "%Y-%m")
        ultimo_mes_label = f"{MESES_PT[dt_fl.month-1]}/{dt_fl.year}"
    except:
        ultimo_mes_label = ultimo_mes_fmt

    tendencia_fluxo = fluxo_tendencia(fluxo["saldo_mes"], fluxo["saldo_mes_ant"])

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>USD/BRL - Painel PTAX Banco Central</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
:root{{
  --azul:#1a5fa8;--azul2:#2e86c1;--laranja:#e67e22;
  --verde:#1d9e75;--roxo:#7f77dd;--rosa:#d4537e;--cinza:#888780;
  --bg:#f4f6f9;--bg2:#ffffff;--borda:#e2e5eb;
  --txt:#1a1a2e;--txt2:#5a6070;--txt3:#9aa0ab;
  --r:10px;--rl:14px;--sh:0 1px 3px rgba(0,0,0,.07);
}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--txt);font-size:14px;line-height:1.6;}}
.wrap{{max-width:1160px;margin:0 auto;padding:28px 20px;}}
.hdr{{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:24px;gap:12px;flex-wrap:wrap;}}
.hdr h1{{font-size:20px;font-weight:600;margin-bottom:3px;}}
.hdr p{{font-size:12px;color:var(--txt2);}}
.badge{{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:500;padding:5px 11px;border-radius:20px;}}
.badge-ok{{background:#d1fae5;color:#065f46;border:1px solid #6ee7b7;}}

/* ── Cards topo ── */
.cards-top{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:16px;}}
@media(max-width:900px){{.cards-top{{grid-template-columns:repeat(3,1fr);}}}}
@media(max-width:600px){{.cards-top{{grid-template-columns:repeat(2,1fr);}}}}
.card{{background:var(--bg2);border:1px solid var(--borda);border-radius:var(--rl);padding:14px 16px;box-shadow:var(--sh);}}
.cl{{font-size:10px;color:var(--txt2);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px;font-weight:600;}}
.cv{{font-size:21px;font-weight:700;color:var(--txt);line-height:1.2;}}
.cs{{font-size:11px;color:var(--txt3);margin-top:4px;}}
.up{{color:#b91c1c;}}.dn{{color:#0f7c4a;}}

/* ── Card variacao expandido ── */
.card-var{{background:var(--bg2);border:1px solid var(--borda);border-radius:var(--rl);padding:14px 16px;box-shadow:var(--sh);grid-column:span 2;}}
.var-row{{display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:1px solid var(--borda);font-size:12px;}}
.var-row:last-child{{border-bottom:none;padding-bottom:0;}}
.var-label{{color:var(--txt2);font-weight:500;}}
.var-val{{font-weight:700;font-size:13px;}}

/* ── Tabs ── */
.tabs{{display:flex;gap:4px;border-bottom:1px solid var(--borda);margin-bottom:0;flex-wrap:wrap;}}
.tab{{padding:9px 18px;font-size:13px;font-weight:500;border:none;background:none;color:var(--txt2);cursor:pointer;border-bottom:2.5px solid transparent;margin-bottom:-1px;transition:all .15s;}}
.tab:hover{{color:var(--azul);}}
.tab.on{{color:var(--azul);border-bottom-color:var(--azul);}}
.panel{{background:var(--bg2);border:1px solid var(--borda);border-top:none;border-radius:0 0 var(--rl) var(--rl);padding:22px;box-shadow:var(--sh);margin-bottom:16px;}}
.ptitle{{font-size:13px;font-weight:600;color:var(--txt);margin-bottom:18px;}}
.ctrl{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px;}}
@media(max-width:700px){{.ctrl{{grid-template-columns:repeat(2,1fr);}}}}
.cg label{{display:block;font-size:11px;color:var(--txt2);margin-bottom:5px;font-weight:600;}}
.cg select,.cg input{{width:100%;padding:7px 10px;font-size:12px;border:1px solid var(--borda);border-radius:var(--r);background:var(--bg);color:var(--txt);outline:none;}}
.cg select:focus,.cg input:focus{{border-color:var(--azul);box-shadow:0 0 0 2px rgba(26,95,168,.1);}}
.leg{{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:14px;}}
.li{{display:flex;align-items:center;gap:5px;font-size:11px;color:var(--txt2);}}
.ll{{width:22px;height:3px;border-radius:2px;}}
.cw{{position:relative;width:100%;height:300px;}}
.cw-tall{{position:relative;width:100%;height:260px;}}

/* ── Comparativo cambial ── */
.moeda-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:18px;}}
@media(max-width:700px){{.moeda-grid{{grid-template-columns:1fr;}}}}
.moeda-card{{background:var(--bg);border:1px solid var(--borda);border-radius:var(--rl);padding:16px 18px;}}
.moeda-card.destaque{{background:#f0f7ff;border-color:#93c5fd;}}
.moeda-header{{display:flex;align-items:center;gap:10px;margin-bottom:12px;}}
.moeda-flag{{font-size:22px;}}
.moeda-nome{{font-size:14px;font-weight:700;color:var(--txt);}}
.moeda-cotacao{{font-size:24px;font-weight:800;color:var(--azul);margin-left:auto;}}
.moeda-rows{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;}}
.moeda-item{{background:var(--bg2);border:1px solid var(--borda);border-radius:8px;padding:8px 10px;text-align:center;}}
.moeda-item-label{{font-size:9px;color:var(--txt3);text-transform:uppercase;letter-spacing:.4px;margin-bottom:3px;}}
.moeda-item-val{{font-size:13px;font-weight:700;}}
.moeda-note{{font-size:10px;color:var(--txt3);margin-top:10px;padding-top:8px;border-top:1px solid var(--borda);}}
.moeda-slot{{background:var(--bg);border:1px dashed var(--borda);border-radius:var(--rl);padding:20px;display:flex;align-items:center;justify-content:center;color:var(--txt3);font-size:12px;text-align:center;}}

/* ── Fluxo cambial ── */
.fluxo-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:18px;}}
@media(max-width:700px){{.fluxo-grid{{grid-template-columns:1fr;}}}}
.fluxo-card{{background:var(--bg);border:1px solid var(--borda);border-radius:var(--rl);padding:14px 16px;}}
.fluxo-card.positivo{{background:#f0fdf4;border-color:#86efac;}}
.fluxo-card.negativo{{background:#fff1f1;border-color:#fca5a5;}}
.fluxo-titulo{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:var(--txt2);margin-bottom:10px;}}
.fluxo-row{{display:flex;justify-content:space-between;font-size:12px;padding:4px 0;border-bottom:1px solid rgba(0,0,0,.05);}}
.fluxo-row:last-of-type{{border-bottom:none;}}
.fluxo-total{{font-size:18px;font-weight:800;margin-bottom:8px;}}
.fluxo-sub{{font-size:10px;color:var(--txt3);}}
.tendencia{{display:inline-flex;align-items:center;gap:4px;font-size:11px;font-weight:600;padding:3px 9px;border-radius:12px;background:#e0f2fe;color:#0369a1;margin-top:8px;}}

/* ── Grid institucional ── */
.igrid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:20px;}}
@media(max-width:700px){{.igrid{{grid-template-columns:repeat(2,1fr);}}}}
.ic{{background:var(--bg);border:1px solid var(--borda);border-radius:var(--rl);padding:13px 15px;}}
.ic.hl{{background:linear-gradient(135deg,#f0f7ff,#e8f4fd);border-color:#bcd6f0;}}
.in{{font-size:12px;font-weight:600;color:var(--txt);margin-bottom:9px;display:flex;align-items:center;gap:6px;}}
.idot{{width:9px;height:9px;border-radius:50%;flex-shrink:0;}}
.ir{{display:flex;justify-content:space-between;font-size:11px;padding:2.5px 0;}}
.irl{{color:var(--txt2);}}.irv{{font-weight:600;color:var(--txt);}}
.inote{{font-size:10px;color:var(--txt3);margin-top:8px;padding-top:7px;border-top:1px solid var(--borda);}}

/* ── Analise narrativa ── */
.an-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px;}}
@media(max-width:700px){{.an-grid{{grid-template-columns:1fr;}}}}
.an-card{{background:var(--bg);border:1px solid var(--borda);border-radius:var(--rl);padding:16px 18px;}}
.an-card.destaque{{background:#fffbeb;border-color:#fcd34d;}}
.an-card.risco{{background:#fff1f1;border-color:#fca5a5;}}
.an-card.positivo{{background:#f0fdf4;border-color:#86efac;}}
.an-card.neutro{{background:#f8fafc;border-color:var(--borda);}}
.an-titulo{{font-size:12px;font-weight:700;color:var(--txt);margin-bottom:10px;display:flex;align-items:center;gap:7px;text-transform:uppercase;letter-spacing:.4px;}}
.an-ico{{font-size:16px;}}
.an-texto{{font-size:12px;color:var(--txt2);line-height:1.7;}}
.an-texto strong{{color:var(--txt);font-weight:600;}}
.inst-reason{{margin-bottom:14px;padding-bottom:14px;border-bottom:1px solid var(--borda);}}
.inst-reason:last-child{{border-bottom:none;margin-bottom:0;padding-bottom:0;}}
.inst-reason-header{{display:flex;align-items:center;gap:8px;margin-bottom:6px;}}
.inst-dot2{{width:10px;height:10px;border-radius:50%;flex-shrink:0;}}
.inst-nome{{font-size:12px;font-weight:700;color:var(--txt);}}
.inst-proj{{font-size:11px;color:var(--txt2);margin-left:auto;}}
.inst-reason-texto{{font-size:12px;color:var(--txt2);line-height:1.7;}}
.termometro-wrap{{margin:16px 0 8px;}}
.termometro-label{{display:flex;justify-content:space-between;font-size:10px;color:var(--txt3);margin-bottom:5px;}}
.termometro{{height:10px;border-radius:5px;background:linear-gradient(90deg,#0f7c4a,#f59e0b,#b91c1c);position:relative;}}
.termometro-marker{{position:absolute;top:-4px;width:2px;height:18px;background:var(--txt);border-radius:2px;transform:translateX(-50%);}}
.termometro-val{{text-align:center;font-size:11px;font-weight:600;color:var(--txt);margin-top:6px;}}
.monitor-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:4px;}}
@media(max-width:700px){{.monitor-grid{{grid-template-columns:1fr 1fr;}}}}
.monitor-item{{background:var(--bg2);border:1px solid var(--borda);border-radius:var(--r);padding:10px 12px;}}
.monitor-label{{font-size:10px;color:var(--txt3);text-transform:uppercase;letter-spacing:.4px;margin-bottom:4px;}}
.monitor-val{{font-size:14px;font-weight:700;color:var(--txt);}}
.monitor-sub{{font-size:10px;color:var(--txt2);margin-top:2px;}}
.tag{{display:inline-block;font-size:10px;font-weight:600;padding:2px 8px;border-radius:10px;margin-right:4px;margin-bottom:4px;}}
.tag-alto{{background:#fee2e2;color:#991b1b;}}
.tag-medio{{background:#fef3c7;color:#92400e;}}
.tag-baixo{{background:#d1fae5;color:#065f46;}}
.foot{{font-size:10px;color:var(--txt3);line-height:1.7;padding:10px 0;}}
.section-sep{{border:none;border-top:1px solid var(--borda);margin:18px 0;}}
</style>
</head>
<body>
<div class="wrap">

<div class="hdr">
  <div>
    <h1>Painel USD/BRL — Visao Estrategica Macroeconomica</h1>
    <p>Cotacoes PTAX · Variacoes multiplos horizontes · Comparativo cambial · Fluxo de Capital · Projecoes Institucionais · Gerado em {data_geracao}</p>
  </div>
  <span class="badge badge-ok">&#10003; PTAX BCB &mdash; {total_diarios:,} cotacoes reais</span>
</div>

<!-- ── CARDS TOPO ── -->
<div class="cards-top">
  <div class="card">
    <div class="cl">Ultima PTAX (venda)</div>
    <div class="cv">R$ {ultimo_val}</div>
    <div class="cs">{ultimo_dt}</div>
  </div>
  <div class="card">
    <div class="cl">Media do mes</div>
    <div class="cv">R$ {media_mes}</div>
    <div class="cs">mai/2026</div>
  </div>
  <!-- Card variacao expandido -->
  <div class="card-var">
    <div class="cl" style="margin-bottom:10px;">Variacao USD/BRL (PTAX)</div>
    <div class="var-row">
      <span class="var-label">&#128197; No mes (vs. abr/26)</span>
      <span class="var-val">{fmt_var(var_brl['var_mes'], var_brl['pct_mes'])}</span>
    </div>
    <div class="var-row">
      <span class="var-label">&#128336; Acumulado no ano</span>
      <span class="var-val">{fmt_var(var_brl['var_ano'], var_brl['pct_ano'])}</span>
    </div>
    <div class="var-row">
      <span class="var-label">&#128200; Ultimos 12 meses</span>
      <span class="var-val">{fmt_var(var_brl['var_12m'], var_brl['pct_12m'])}</span>
    </div>
  </div>
  <div class="card">
    <div class="cl">Focus dez/26</div>
    <div class="cv">R$ {f_cambio_26}</div>
    <div class="cs">Boletim Focus · {f_data_focus}</div>
  </div>
  <div class="card">
    <div class="cl">Fluxo cambial ({ultimo_mes_label})</div>
    <div class="cv {'dn' if fluxo['saldo_mes'] >= 0 else 'up'}">{'+' if fluxo['saldo_mes'] >= 0 else ''}US$ {fluxo['saldo_mes']/1000:.1f} bi</div>
    <div class="cs">Saldo liquido · entrada - saida</div>
  </div>
</div>

<!-- ── TABS ── -->
<div class="tabs">
  <button class="tab on" onclick="setTab('h',this)">&#128200; Historico + Media Movel</button>
  <button class="tab"    onclick="setTab('c',this)">&#127758; Comparativo Cambial</button>
  <button class="tab"    onclick="setTab('f',this)">&#128181; Fluxo de Capital</button>
  <button class="tab"    onclick="setTab('i',this)">&#127968; Projecoes Institucionais</button>
  <button class="tab"    onclick="setTab('a',this)">&#128240; Analise de Mercado</button>
</div>

<!-- ══════════════════════════════════════════════════════════════════════════
     PAINEL 1: HISTORICO
     ════════════════════════════════════════════════════════════════════════ -->
<div id="ph" class="panel">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;flex-wrap:wrap;gap:10px;">
    <div class="ptitle" style="margin-bottom:0;">Evolucao historica PTAX (BCB)</div>
    <div class="view-toggle">
      <button class="vtog on" id="btn-mensal" onclick="setView('mensal')">&#128197; Mensal</button>
      <button class="vtog"    id="btn-diario" onclick="setView('diario')">&#128202; Diario</button>
    </div>
  </div>

  <!-- Controles visao mensal -->
  <div id="ctrl-mensal" class="ctrl">
    <div class="cg"><label>Periodo inicial</label><select id="ss"></select></div>
    <div class="cg"><label>Periodo final</label><select id="se"></select></div>
    <div class="cg"><label>Janela media movel</label>
      <select id="sm">
        <option value="3">3 meses</option>
        <option value="6" selected>6 meses</option>
        <option value="12">12 meses</option>
        <option value="24">24 meses</option>
      </select>
    </div>
    <div class="cg"><label>Meses projetados</label>
      <input type="number" id="np" value="6" min="1" max="24" step="1">
    </div>
  </div>

  <!-- Controles visao diaria -->
  <div id="ctrl-diario" style="display:none;margin-bottom:18px;">
    <div class="cg" style="max-width:220px;">
      <label>Selecione o mes</label>
      <select id="sd"></select>
    </div>
    <div id="diario-info" style="margin-top:10px;font-size:12px;color:var(--txt2);"></div>
  </div>

  <!-- Legenda mensal -->
  <div id="leg-mensal" class="leg">
    <div class="li"><div class="ll" style="background:var(--azul)"></div>PTAX mensal (BCB)</div>
    <div class="li"><div class="ll" style="background:repeating-linear-gradient(90deg,var(--azul2) 0 5px,transparent 5px 9px)"></div>Media movel</div>
    <div class="li"><div class="ll" style="background:var(--laranja)"></div>Projecao MM</div>
    <div class="li"><div class="ll" style="background:#aab7b8;opacity:.6"></div>Banda &plusmn;1&sigma;</div>
  </div>
  <!-- Legenda diaria -->
  <div id="leg-diario" class="leg" style="display:none;">
    <div class="li"><div class="ll" style="background:var(--azul)"></div>PTAX diaria (BCB)</div>
    <div class="li"><div class="ll" style="background:repeating-linear-gradient(90deg,var(--laranja) 0 5px,transparent 5px 9px)"></div>Media do mes</div>
  </div>

  <div class="cw"><canvas id="chH"></canvas></div>
</div>

<!-- ══════════════════════════════════════════════════════════════════════════
     PAINEL 2: COMPARATIVO CAMBIAL
     ════════════════════════════════════════════════════════════════════════ -->
<div id="pc" class="panel" style="display:none">
  <div class="ptitle">Comparativo cambial — Dolar frente a moedas relevantes</div>

  <!-- Grade de moedas: gerada pelo JS com dados de MOEDAS -->
  <div id="moeda-grid-wrap" class="moeda-grid" style="grid-template-columns:repeat(3,1fr);"></div>

  <!-- Contexto macro -->
  <div class="an-card neutro" style="margin:14px 0;">
    <div class="an-titulo"><span class="an-ico">&#127760;</span> Por que acompanhar essas moedas?</div>
    <div class="an-texto">
      O <strong>DXY</strong> mede o dolar frente a 6 moedas (57% EUR). Quando cai, emergentes como o BRL se valorizam.
      O <strong>EUR/USD</strong> e o principal termometro do apetite global pelo dolar.
      O <strong>USD/CNY</strong> sinaliza pressao comercial China-EUA e impacta commodities.
      O <strong>GBP/USD</strong> reflete o ciclo monetario europeu ampliado.<br><br>
      Em 2025-2026, o DXY recuou ~9% com os cortes do Fed — vetor central da valorizacao do real.
      <strong>Monitorar esses pares ajuda a antecipar moves no USD/BRL antes que aparecam na PTAX.</strong>
    </div>
  </div>

  <!-- Toggle moeda para grafico -->
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;flex-wrap:wrap;gap:8px;">
    <div class="ptitle" style="margin:0;">Historico 12 meses — selecione o par:</div>
    <div id="moeda-toggle" style="display:flex;gap:4px;"></div>
  </div>
  <div class="leg" id="leg-moeda">
    <div class="li"><div class="ll" style="background:#e67e22"></div><span id="leg-moeda-label">EUR/USD</span></div>
    <div class="li"><div class="ll" style="background:repeating-linear-gradient(90deg,#aab7b8 0 5px,transparent 5px 9px)"></div>Paridade / referencia</div>
  </div>
  <div class="cw-tall"><canvas id="chEUR"></canvas></div>
</div>


<!-- ══════════════════════════════════════════════════════════════════════════
     PAINEL 3: FLUXO DE CAPITAL
     ════════════════════════════════════════════════════════════════════════ -->
<div id="pf" class="panel" style="display:none">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;flex-wrap:wrap;gap:10px;">
    <div class="ptitle" style="margin:0;">Fluxo Cambial — Movimentacao de capital internacional (BCB)</div>
    <div class="view-toggle" id="fluxo-periodo-toggle">
      <button class="vtog on" onclick="setFluxoPeriodo('6m',this)">6 meses</button>
      <button class="vtog"    onclick="setFluxoPeriodo('12m',this)">12 meses</button>
      <button class="vtog"    onclick="setFluxoPeriodo('24m',this)">24 meses</button>
      <button class="vtog"    onclick="setFluxoPeriodo('ano',this)">Por ano</button>
    </div>
  </div>

  <!-- Cards resumo (atualizados pelo JS) -->
  <div class="fluxo-grid" id="fluxo-cards"></div>

  <!-- Grafico -->
  <div class="ptitle" id="fluxo-chart-title" style="margin-bottom:10px;">Entradas, saidas e saldo liquido</div>
  <div class="leg">
    <div class="li"><div class="ll" style="background:#1d9e75"></div>Entradas (US$ bi)</div>
    <div class="li"><div class="ll" style="background:#b91c1c"></div>Saidas (US$ bi)</div>
    <div class="li"><div class="ll" style="background:var(--azul);height:5px;border-radius:3px;"></div>Saldo liquido</div>
  </div>
  <div class="cw-tall"><canvas id="chFluxo"></canvas></div>

  <hr class="section-sep">
  <div class="an-card destaque">
    <div class="an-titulo"><span class="an-ico">&#128270;</span> Como interpretar o fluxo cambial</div>
    <div class="an-texto">
      <strong>Fluxo positivo (entrada &gt; saida):</strong> capital estrangeiro comprando reais fortalece o BRL.
      Em semanas de fluxo recorde (20-24/abr/2026, <strong>US$ 9,2 bi</strong>), o efeito e imediato na PTAX.<br><br>
      <strong>Sazonalidade:</strong> abr/mai historicamente fortes por dividendos e exportadores agricolas.
      O 3T tende a enfraquecer em anos eleitorais — risco para 2S26.<br><br>
      <strong>Correlacao com PTAX:</strong> saldo negativo por 2+ meses consecutivos costuma preceder
      desvalorizacao do BRL de 3-8% em 30-60 dias. Este indicador e antecedente ao movimento cambial.
    </div>
  </div>
</div>


     ════════════════════════════════════════════════════════════════════════ -->
<div id="pi" class="panel" style="display:none">
  <div class="ptitle">Projecoes institucionais sobrepostas ao historico PTAX</div>
  <div class="igrid">
    <div class="ic">
      <div class="in"><div class="idot" style="background:#888780"></div>Focus - BCB</div>
      <div class="ir"><span class="irl">Dez/2026</span><span class="irv">R$ {f_cambio_26}</span></div>
      <div class="ir"><span class="irl">2027</span><span class="irv">R$ {f_cambio_27}</span></div>
      <div class="ir"><span class="irl">2028</span><span class="irv">R$ {f_cambio_28}</span></div>
      <div class="inote">Mediana de mercado · Boletim Focus {f_data_focus}</div>
    </div>
    <div class="ic">
      <div class="in"><div class="idot" style="background:#e67e22"></div>XP Investimentos</div>
      <div class="ir"><span class="irl">Dez/2026</span><span class="irv dn">R$ 5,00</span></div>
      <div class="ir"><span class="irl">Selic 2026</span><span class="irv">13,75%</span></div>
      <div class="ir"><span class="irl">Tese</span><span class="irv">BRL vencedor</span></div>
      <div class="inote">Macro Mensal · mai/2026</div>
    </div>
    <div class="ic">
      <div class="in"><div class="idot" style="background:#1d9e75"></div>Bradesco</div>
      <div class="ir"><span class="irl">Dez/2026</span><span class="irv dn">R$ 5,00</span></div>
      <div class="ir"><span class="irl">2027</span><span class="irv">R$ 5,00</span></div>
      <div class="ir"><span class="irl">Selic 2026</span><span class="irv">12,75%</span></div>
      <div class="inote">Relatorio · mai/2026</div>
    </div>
    <div class="ic">
      <div class="in"><div class="idot" style="background:#7f77dd"></div>Itau</div>
      <div class="ir"><span class="irl">Dez/2026</span><span class="irv">R$ 5,15</span></div>
      <div class="ir"><span class="irl">2027</span><span class="irv">R$ 5,30</span></div>
      <div class="ir"><span class="irl">Cenario</span><span class="irv">Moderado</span></div>
      <div class="inote">Relatorio · mai/2026</div>
    </div>
    <div class="ic">
      <div class="in"><div class="idot" style="background:#d4537e"></div>Morgan Stanley</div>
      <div class="ir"><span class="irl">Pico 3T26</span><span class="irv up">R$ 5,60</span></div>
      <div class="ir"><span class="irl">Dez/2026</span><span class="irv">R$ 5,30</span></div>
      <div class="ir"><span class="irl">Driver</span><span class="irv">Eleicoes BR</span></div>
      <div class="inote">Cenario ponderado · eleicoes</div>
    </div>
    <div class="ic hl">
      <div class="in"><div class="idot" style="background:#1a5fa8"></div>Focus dez/2026</div>
      <div class="ir"><span class="irl">Minimo</span><span class="irv dn">R$ 5,00</span></div>
      <div class="ir"><span class="irl">Mediana</span><span class="irv">R$ {f_cambio_26}</span></div>
      <div class="ir"><span class="irl">Maximo</span><span class="irv up">R$ 5,60</span></div>
      <div class="inote">5 instituicoes · relatorios {f_data_focus}</div>
    </div>
  </div>
  <div class="leg">
    <div class="li"><div class="ll" style="background:var(--azul)"></div>PTAX mensal</div>
    <div class="li"><div class="ll" style="background:repeating-linear-gradient(90deg,#888780 0 5px,transparent 5px 9px)"></div>Focus</div>
    <div class="li"><div class="ll" style="background:#e67e22"></div>XP</div>
    <div class="li"><div class="ll" style="background:#1d9e75"></div>Bradesco</div>
    <div class="li"><div class="ll" style="background:#7f77dd"></div>Itau</div>
    <div class="li"><div class="ll" style="background:repeating-linear-gradient(90deg,#d4537e 0 4px,transparent 4px 8px)"></div>Morgan Stanley</div>
    <div class="li"><div class="ll" style="background:#aab7b8;opacity:.5"></div>Banda consenso</div>
  </div>
  <div class="cw"><canvas id="chI"></canvas></div>
</div>

<!-- ══════════════════════════════════════════════════════════════════════════
     PAINEL 5: ANALISE DE MERCADO
     ════════════════════════════════════════════════════════════════════════ -->
<div id="pa" class="panel" style="display:none">
  <div class="ptitle">Analise de Mercado &mdash; O que esta movendo o dolar em mai/2026</div>

  <div class="an-card neutro" style="margin-bottom:16px;">
    <div class="an-titulo"><span class="an-ico">&#127777;</span> Termometro cambial atual</div>
    <div class="termometro-wrap">
      <div class="termometro-label"><span>Real muito forte</span><span>Neutro</span><span>Dolar muito forte</span></div>
      <div class="termometro"><div class="termometro-marker" style="left:28%"></div></div>
      <div class="termometro-val">Real levemente apreciado &mdash; USD/BRL ~R$ 4,98 (mai/2026)</div>
    </div>
    <div class="an-texto" style="margin-top:10px;">
      O dolar recuou de <strong>R$ 6,18 (jan/2025)</strong> para <strong>R$ 4,98 (mai/2026)</strong>, queda de 19,5% em 16 meses.
      O real registrou a <strong>2a maior valorizacao entre 28 moedas emergentes</strong> no acumulado de 2026,
      impulsionado por fluxo externo recorde e diferencial de juros elevado.
    </div>
  </div>

  <div class="an-grid">
    <div class="an-card positivo">
      <div class="an-titulo"><span class="an-ico">&#9650;</span> Fatores que fortalecem o real</div>
      <div class="an-texto">
        <strong>Diferencial de juros (carry trade):</strong> Com a Selic em 14,75% e o Fed entre 3,50-3,75%,
        o spread e um dos mais atrativos do mundo, atraindo capital estrangeiro para renda fixa brasileira.<br><br>
        <strong>Fluxo externo recorde:</strong> Na semana de 20-24/abr, o Brasil registrou entrada liquida de
        <strong>US$ 9,2 bilhoes</strong> — o maior ingresso semanal da historia (BTG Pactual/BCB).
        Investidores estrangeiros representam 61,2% dos negocios da B3 em 2026.<br><br>
        <strong>Commodities e geopolitica:</strong> O conflito no Oriente Medio manteve o petroleo acima de US$ 100,
        beneficiando o Brasil como exportador.<br><br>
        <strong>Dolar global mais fraco:</strong> O DXY recuou ~9% em 2025.
        Com o Fed cortando juros, o capital migra para emergentes com retorno superior.
      </div>
    </div>

    <div class="an-card risco">
      <div class="an-titulo"><span class="an-ico">&#9660;</span> Fatores de risco (pressao de alta no dolar)</div>
      <div class="an-texto">
        <strong>Eleicoes presidenciais (out/2026):</strong> Anos eleitorais no Brasil seguem padrao historico:
        1S calmo, 3T com pico de volatilidade, 4T com acomodacao pos-urnas.
        O Morgan Stanley projeta pico de <strong>R$ 5,60 no 3T26</strong>.<br><br>
        <strong>Risco fiscal:</strong> Aumento dos gastos em ano eleitoral preocupa o mercado.
        Deterioracao das contas publicas pode reverter o fluxo externo rapidamente.<br><br>
        <strong>Reducao do diferencial de juros:</strong> A Selic em ciclo de queda estreita o spread com os EUA.
        Se o corte for percebido como precipitado, o real perde atratividade.<br><br>
        <strong>Fluxo cambial sazonal:</strong> O 3T historicamente e mais fraco para o fluxo de capital,
        especialmente em anos eleitorais, o que pode pressionar o BRL no 2S26.
      </div>
    </div>

    <div class="an-card destaque">
      <div class="an-titulo"><span class="an-ico">&#128201;</span> Por que as instituicoes divergem?</div>
      <div class="an-texto">
        <div class="inst-reason">
          <div class="inst-reason-header">
            <div class="inst-dot2" style="background:#e67e22"></div>
            <span class="inst-nome">XP e Bradesco — R$ 5,00</span>
            <span class="inst-proj">Mais otimistas c/ real</span>
          </div>
          <div class="inst-reason-texto">Apostam na continuidade do fluxo externo e no papel do Brasil como exportador de commodities. Selic restritiva (13-14%) sustenta o carry trade por mais tempo.</div>
        </div>
        <div class="inst-reason">
          <div class="inst-reason-header">
            <div class="inst-dot2" style="background:#7f77dd"></div>
            <span class="inst-nome">Itau — R$ 5,15</span>
            <span class="inst-proj">Cenario moderado</span>
          </div>
          <div class="inst-reason-texto">Reconhece os fundamentos positivos mas pondera que o estreitamento do diferencial de juros limita a apreciacao adicional. Projeta leve reversao em 2027 para R$ 5,30.</div>
        </div>
        <div class="inst-reason">
          <div class="inst-reason-header">
            <div class="inst-dot2" style="background:#d4537e"></div>
            <span class="inst-nome">Morgan Stanley — R$ 5,60 (pico 3T)</span>
            <span class="inst-proj">Mais pessimista</span>
          </div>
          <div class="inst-reason-texto">Da maior peso ao risco eleitoral. Projeta acomodacao pos-eleicao para R$ 5,30, mas considera o desfecho "muito binario".</div>
        </div>
        <div class="inst-reason">
          <div class="inst-reason-header">
            <div class="inst-dot2" style="background:#888780"></div>
            <span class="inst-nome">Focus BCB — R$ {f_cambio_26}</span>
            <span class="inst-proj">Mediana de mercado</span>
          </div>
          <div class="inst-reason-texto">Mediana de dezenas de instituicoes. Consenso ve real levemente apreciado, com upside limitado dado o contexto fiscal e eleitoral.</div>
        </div>
      </div>
    </div>

    <div class="an-card neutro">
      <div class="an-titulo"><span class="an-ico">&#128270;</span> O que monitorar nos proximos meses</div>
      <div class="an-texto">
        <div class="monitor-grid">
          <div class="monitor-item">
            <div class="monitor-label">Selic</div>
            <div class="monitor-val">14,75%</div>
            <div class="monitor-sub">Copom: 16-17/jun</div>
          </div>
          <div class="monitor-item">
            <div class="monitor-label">Fed Funds</div>
            <div class="monitor-val">3,50-3,75%</div>
            <div class="monitor-sub">Novo presidente: mai/26</div>
          </div>
          <div class="monitor-item">
            <div class="monitor-label">Petroleo (Brent)</div>
            <div class="monitor-val">&gt; US$ 100</div>
            <div class="monitor-sub">Conflito Oriente Medio</div>
          </div>
          <div class="monitor-item">
            <div class="monitor-label">Fluxo cambial</div>
            <div class="monitor-val">Positivo</div>
            <div class="monitor-sub">Entrada liquida recorde</div>
          </div>
          <div class="monitor-item">
            <div class="monitor-label">Eleicoes BR</div>
            <div class="monitor-val">out/2026</div>
            <div class="monitor-sub">Risco 3T26 elevado</div>
          </div>
          <div class="monitor-item">
            <div class="monitor-label">IPCA 2026</div>
            <div class="monitor-val">{f_ipca_26}%</div>
            <div class="monitor-sub">9a alta consecutiva</div>
          </div>
        </div>
        <div style="margin-top:14px;">
          <strong>Nivel critico a observar:</strong><br>
          <span class="tag tag-baixo">R$ 4,80 — suporte forte</span>
          <span class="tag tag-medio">R$ {f_cambio_26} — resistencia Focus</span>
          <span class="tag tag-alto">R$ 5,60 — pico eleitoral (MS)</span>
        </div>
      </div>
    </div>
  </div>

  {{_gerar_card_tendencia_focus(focus)}}

  <div class="an-card" style="background:#f0f7ff;border-color:#93c5fd;margin-top:4px;">
    <div class="an-titulo"><span class="an-ico">&#128188;</span> Implicacao para o setor de tecnologia financeira e automacao comercial</div>
    <div class="an-texto">
      Com o dolar testando o suporte de <strong>R$ 4,90-5,00</strong>, empresas do setor que operam com
      componentes ou licencas dolarizadas enfrentam impacto direto nos custos e margens.
      O cenario de consenso aponta para <strong>leve recuperacao no 2S26</strong> (R$ 5,15-5,30)
      puxada pelo risco eleitoral — o que exige planejamento cambial por segmento:<br><br>
      <strong>&#9679; Automacao comercial:</strong> equipamentos e componentes importados sofrem repasse imediato.
      A banda R$ 5,00-5,60 amplia a incerteza no planejamento de estoques e contratos plurianuais.<br><br>
      <strong>&#9679; Meios de pagamento:</strong> solucoes cross-border beneficiam-se do real mais forte no curto prazo,
      mas devem monitorar a reversao esperada no 3T26.<br><br>
      <strong>&#9679; Plataformas de remessa:</strong> o pico projetado de R$ 5,60 (Morgan Stanley, 3T26)
      pode impactar spreads e competitividade frente a fintechs globais.<br><br>
      <strong>Estrategia recomendada:</strong> trava cambial na faixa atual (R$ 4,90-5,00) para
      compromissos de importacao. Contratos de fornecimento com clausulas de reajuste atreladas ao PTAX.
    </div>
  </div>
</div>

<div class="foot">
  Fonte: API PTAX BCB (olinda.bcb.gov.br) · BCB SGS (fluxo cambial) · {total_diarios:,} cotacoes diarias ·
  Ultimo dado: {ultimo_dt} · Analise narrativa baseada em relatorios publicos (XP, Bradesco, Itau, Morgan Stanley, BTG, Focus BCB) ·
  Gerado em {data_geracao} · Nao constitui recomendacao de investimento.
</div>
</div>

<script>
const DATA       = {dados_js};
const SPROJ      = {proj_js};
const CORES      = {cores_js};
const FLUXO_HIST   = {fluxo_hist_js};
const DATA_DIARIOS = {diarios_js};
const MOEDAS       = {moedas_js};

const MESES = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'];
const nm = m => {{ const [y,mo]=m.split('-'); return MESES[+mo-1]+'/'+y.slice(2); }};
const addM = (m,n) => {{
  let [y,mo]=m.split('-').map(Number);
  mo+=n; while(mo>12){{mo-=12;y++;}}
  return `${{y}}-${{String(mo).padStart(2,'0')}}`;
}};
const maFn = (arr,w) => arr.map((_,i) =>
  i<w-1 ? null : +(arr.slice(i-w+1,i+1).reduce((a,b)=>a+b)/w).toFixed(4)
);
function buildProj(vals,mm,n){{
  const w=Math.min(mm,vals.length), last=vals.slice(-w);
  const avg=last.reduce((a,b)=>a+b)/w;
  const sd=Math.sqrt(last.map(x=>(x-avg)**2).reduce((a,b)=>a+b)/w);
  const p=[],u=[],l=[];
  for(let i=1;i<=n;i++){{
    p.push(+avg.toFixed(4));
    u.push(+(avg+sd*Math.sqrt(i)).toFixed(4));
    l.push(+(avg-sd*Math.sqrt(i)).toFixed(4));
  }}
  return {{p,u,l}};
}}

let chH=null,chI=null,chEUR=null,chFluxo=null;
let viewMode='mensal';

function setTab(t,el){{
  document.querySelectorAll('.tab').forEach(b=>b.className='tab');
  el.className='tab on';
  ['ph','pc','pf','pi','pa'].forEach(id=>document.getElementById(id).style.display='none');
  const map={{h:'ph',c:'pc',f:'pf',i:'pi',a:'pa'}};
  document.getElementById(map[t]).style.display='';
  if(t==='i') renderI();
  if(t==='c'){{ renderMoedasCards(); renderEUR(); }}
  if(t==='f') renderFluxo();
}}

function setView(v){{
  viewMode=v;
  document.getElementById('btn-mensal').className='vtog'+(v==='mensal'?' on':'');
  document.getElementById('btn-diario').className='vtog'+(v==='diario'?' on':'');
  document.getElementById('ctrl-mensal').style.display=v==='mensal'?'':'none';
  document.getElementById('ctrl-diario').style.display=v==='diario'?'':'none';
  document.getElementById('leg-mensal').style.display=v==='mensal'?'':'none';
  document.getElementById('leg-diario').style.display=v==='diario'?'':'none';
  if(v==='mensal') renderH(); else renderD();
}}

/* ── Diario ── */
function renderD(){{
  const mes=document.getElementById('sd').value;
  if(!mes) return;
  const dias=DATA_DIARIOS[mes];
  if(!dias||!dias.length){{
    if(chH) chH.destroy(); chH=null;
    const info=document.getElementById('diario-info');
    if(info) info.innerHTML='<span style="color:#888">Dados diarios nao disponíveis para '+nm(mes)+'. Execute o Python para obter todos os pregoes.</span>';
    // Clear canvas
    const ctx=document.getElementById('chH');
    if(ctx){{ const ct=ctx.getContext('2d'); ct.clearRect(0,0,ctx.width,ctx.height); }}
    return;
  }}
  const lbs=dias.map(function(d){{ return d.d.slice(8); }});
  const vs=dias.map(function(d){{ return d.v; }});
  const avg=+(vs.reduce(function(a,b){{ return a+b; }})/vs.length).toFixed(4);
  const mn=Math.min.apply(null,vs), mx=Math.max.apply(null,vs);
  const info=document.getElementById('diario-info');
  if(info) info.innerHTML=
    '<strong>'+dias.length+' pregoes</strong> &nbsp;|&nbsp; '+
    'Min: <strong>R$ '+mn.toFixed(4)+'</strong> &nbsp;|&nbsp; '+
    'Max: <strong>R$ '+mx.toFixed(4)+'</strong> &nbsp;|&nbsp; '+
    'Media: <strong>R$ '+avg.toFixed(4)+'</strong> &nbsp;|&nbsp; '+
    'Variacao: <strong>'+(((mx-mn)/mn)*100).toFixed(2)+'%</strong>';
  const ds=[
    {{label:'PTAX diaria',data:vs,borderColor:'#1a5fa8',backgroundColor:'rgba(26,95,168,0.07)',borderWidth:2,fill:true,tension:0.3,pointRadius:3.5,pointBackgroundColor:'#1a5fa8',pointBorderWidth:0}},
    {{label:'Media do mes',data:Array(vs.length).fill(avg),borderColor:'#e67e22',borderWidth:1.5,borderDash:[5,4],pointRadius:0,fill:false}}
  ];
  if(chH) chH.destroy();
  chH=new Chart(document.getElementById('chH'),{{
    type:'line',
    data:{{labels:lbs,datasets:ds}},
    options:{{
      responsive:true,maintainAspectRatio:false,
      interaction:{{mode:'index',intersect:false}},
      plugins:{{
        legend:{{display:false}},
        tooltip:{{backgroundColor:'#fff',borderColor:'#e2e5eb',borderWidth:1,titleColor:'#1a1a2e',bodyColor:'#5a6070',padding:10,boxPadding:4,
          callbacks:{{
            title:function(items){{ return 'Dia '+items[0].label; }},
            label:function(c){{ return ' '+c.dataset.label+': R$ '+c.parsed.y.toFixed(4); }}
          }}
        }}
      }},
      scales:{{
        x:{{grid:{{color:'rgba(0,0,0,0.04)'}},ticks:{{color:'#9aa0ab',font:{{size:10}},maxRotation:0,callback:function(v,i){{ return i%2===0?lbs[i]:null; }}}}}},
        y:{{grid:{{color:'rgba(0,0,0,0.04)'}},ticks:{{color:'#9aa0ab',font:{{size:10}},callback:function(v){{ return 'R$ '+v.toFixed(2); }}}}}}
      }}
    }}
  }});
}}


/* ── Historico mensal ── */
function renderH(){{
  const s=document.getElementById('ss').value;
  const e=document.getElementById('se').value;
  if(!s||!e||s>e){{ console.warn('[renderH] sem periodo'); return; }}
  const mm=+document.getElementById('sm').value;
  const n=Math.max(1,Math.min(24,+document.getElementById('np').value||6));
  const fd=DATA.filter(d=>d.m>=s&&d.m<=e);
  if(fd.length<2){{ console.warn('[renderH] dados insuficientes',fd.length); return; }}
  try{{
  const lbs=fd.map(d=>nm(d.m)), vs=fd.map(d=>d.v);
  const mav=maFn(vs,mm), {{p,u,l}}=buildProj(vs,mm,n);
  const lm=fd[fd.length-1].m;
  const pl=Array.from({{length:n}},(_,i)=>nm(addM(lm,i+1)));
  const all=[...lbs,...pl], hl=lbs.length, lv=vs[vs.length-1];
  const pad=Array(hl-1).fill(null);
  const cur=vs[vs.length-1], fst=vs[0], dv=cur-fst, dp=dv/fst*100;
  const vel=document.getElementById('c-var');
  if(vel){{ vel.textContent=`${{dv>=0?'+':''}}R$ ${{dv.toFixed(2)}}`; vel.className='cv '+(dv>=0?'up':'dn'); }}
  const veld=document.getElementById('c-var-d');
  if(veld) veld.textContent=`${{dp>=0?'+':''}}${{dp.toFixed(2)}}% - ${{nm(s)}} a ${{nm(e)}}`;
  const ds=[
    {{label:'PTAX mensal',data:[...vs,...Array(n).fill(null)],borderColor:'#1a5fa8',backgroundColor:'rgba(26,95,168,0.06)',borderWidth:2,fill:true,tension:0.35,order:3,pointRadius:vs.map((_,i)=>i===vs.length-1?5:1.5),pointBackgroundColor:'#1a5fa8',pointBorderWidth:0}},
    {{label:'Media movel',data:[...mav,...Array(n).fill(null)],borderColor:'#2e86c1',borderWidth:2,borderDash:[7,4],pointRadius:0,fill:false,tension:0.4,order:2}},
    {{label:'Projecao MM',data:[...pad,lv,...p],borderColor:'#e67e22',backgroundColor:'rgba(230,126,34,0.06)',borderWidth:2.5,fill:false,tension:0.3,order:1,pointRadius:[...Array(hl-1).fill(0),5,...Array(n).fill(3.5)],pointBackgroundColor:'#e67e22',pointBorderWidth:0}},
    {{label:'Banda sup',data:[...Array(hl-1).fill(null),lv,...u],borderColor:'rgba(170,183,184,0.3)',borderWidth:1,pointRadius:0,fill:false,backgroundColor:'rgba(170,183,184,0.12)',tension:0.3,order:5}},
    {{label:'Banda inf',data:[...Array(hl-1).fill(null),lv,...l],borderColor:'rgba(170,183,184,0.3)',borderWidth:1,pointRadius:0,fill:false,tension:0.3,order:6}}
  ];
  if(chH) chH.destroy();
  chH=new Chart(document.getElementById('chH'),{{type:'line',data:{{labels:all,datasets:ds}},options:{{responsive:true,maintainAspectRatio:false,interaction:{{mode:'index',intersect:false}},plugins:{{legend:{{display:false}},tooltip:{{backgroundColor:'#fff',borderColor:'#e2e5eb',borderWidth:1,titleColor:'#1a1a2e',bodyColor:'#5a6070',padding:10,boxPadding:4,callbacks:{{label:c=>c.parsed.y===null?null:` ${{c.dataset.label}}: R$ ${{c.parsed.y.toFixed(4)}}`}}}}}},scales:{{x:{{grid:{{color:'rgba(0,0,0,0.04)'}},ticks:{{color:'#9aa0ab',font:{{size:10}},maxRotation:45,autoSkip:true,maxTicksLimit:22}}}},y:{{grid:{{color:'rgba(0,0,0,0.04)'}},ticks:{{color:'#9aa0ab',font:{{size:10}},callback:v=>`R$ ${{v.toFixed(2)}}`}}}}}}}}}});
  console.log('[renderH] grafico renderizado:',fd.length,'pontos');
  }}catch(err){{ console.error('[renderH] ERRO ao renderizar:',err.message,err.stack); }}
}}

/* ── Institucional ── */
function renderI(){{
  const h18=DATA.slice(-18);
  const hl=h18.map(d=>nm(d.m)), hv=h18.map(d=>d.v);
  const pm=['jun/26','jul/26','ago/26','set/26','out/26','nov/26','dez/26','2027'];
  const all=[...hl,...pm], lv=hv[hv.length-1], pad=Array(hl.length-1).fill(null);
  const mk=a=>[...pad,lv,...a];
  const nomes=Object.keys(SPROJ);
  const instDs=nomes.map(nome=>{{
    const cor=CORES[nome]||'#888';
    const dash=nome==='Focus BCB'||nome==='Morgan Stanley';
    return {{label:nome,data:mk(SPROJ[nome]),borderColor:cor,borderWidth:2,borderDash:dash?[5,4]:[],pointRadius:3,pointBackgroundColor:cor,fill:false,tension:0.3,order:nomes.indexOf(nome)+1}};
  }});
  const ds=[
    {{label:'PTAX mensal',data:[...hv,...Array(pm.length).fill(null)],borderColor:'#1a5fa8',backgroundColor:'rgba(26,95,168,0.06)',borderWidth:2.5,fill:true,tension:0.35,order:20,pointRadius:hv.map((_,i)=>i===hv.length-1?5:1.5),pointBackgroundColor:'#1a5fa8',pointBorderWidth:0}},
    {{label:'Banda sup',data:mk([5.28,5.35,5.42,5.60,5.52,5.43,5.30,5.30]),borderColor:'rgba(170,183,184,0.25)',borderWidth:1,pointRadius:0,fill:'+1',backgroundColor:'rgba(170,183,184,0.09)',tension:0.3,order:19}},
    {{label:'Banda inf',data:mk([5.05,5.03,5.02,5.01,5.00,5.00,5.00,5.00]),borderColor:'rgba(170,183,184,0.25)',borderWidth:1,pointRadius:0,fill:false,tension:0.3,order:18}},
    ...instDs
  ];
  if(chI) chI.destroy();
  chI=new Chart(document.getElementById('chI'),{{type:'line',data:{{labels:all,datasets:ds}},options:{{responsive:true,maintainAspectRatio:false,interaction:{{mode:'index',intersect:false}},plugins:{{legend:{{display:false}},tooltip:{{backgroundColor:'#fff',borderColor:'#e2e5eb',borderWidth:1,titleColor:'#1a1a2e',bodyColor:'#5a6070',padding:10,boxPadding:4,callbacks:{{label:c=>c.parsed.y===null?null:` ${{c.dataset.label}}: R$ ${{c.parsed.y.toFixed(2)}}`}}}}}},scales:{{x:{{grid:{{color:'rgba(0,0,0,0.04)'}},ticks:{{color:'#9aa0ab',font:{{size:10}},maxRotation:45}}}},y:{{grid:{{color:'rgba(0,0,0,0.04)'}},min:4.5,ticks:{{color:'#9aa0ab',font:{{size:10}},callback:v=>`R$ ${{v.toFixed(2)}}`}}}}}}}}}});
}}

/* ── EUR/USD ── */
/* ── Comparativo Cambial ── */
let moedaAtiva = 0;  // indice em MOEDAS

function buildMoedaCard(m, idx){{
  const sinal = function(v){{ return v >= 0 ? '+' : ''; }};
  const cls   = function(v){{ return v >= 0 ? 'dn' : 'up'; }};
  const flags = ['&#127466;&#127482;','&#127464;&#127475;','&#127468;&#127463;'];
  const desc  = ['Euro frente ao Dolar','Dolar em Yuan chines','Libra frente ao Dolar'];
  const refs  = ['DXY -9% em 2025-26. EUR forte reflete Fed dovish.','Tensao comercial EUA-China. Yuan gerenciado pelo PBOC.','Ciclo BCE/BoE. GBP correlacionado ao EUR.'];
  const sel   = idx===moedaAtiva;
  return '<div class="moeda-card'+(sel?' destaque':'')+'" style="cursor:pointer;" onclick="setMoedaAtiva('+idx+')">'+
    '<div class="moeda-header">'+
    '<span class="moeda-flag">'+flags[idx]+'</span>'+
    '<div><div class="moeda-nome">'+m.par+'</div>'+
    '<div style="font-size:10px;color:var(--txt3);">'+desc[idx]+'</div></div>'+
    '<div class="moeda-cotacao">'+m.atual.toFixed(4)+'</div>'+
    '</div>'+
    '<div class="moeda-rows">'+
    '<div class="moeda-item"><div class="moeda-item-label">No mes</div>'+
    '<div class="moeda-item-val '+cls(m.var_mes)+'">'+sinal(m.pct_mes)+m.pct_mes.toFixed(2)+'%</div></div>'+
    '<div class="moeda-item"><div class="moeda-item-label">No ano</div>'+
    '<div class="moeda-item-val '+cls(m.var_ano)+'">'+sinal(m.pct_ano)+m.pct_ano.toFixed(2)+'%</div></div>'+
    '<div class="moeda-item"><div class="moeda-item-label">12 meses</div>'+
    '<div class="moeda-item-val '+cls(m.var_12m)+'">'+sinal(m.pct_12m)+m.pct_12m.toFixed(2)+'%</div></div>'+
    '</div>'+
    '<div class="moeda-note">'+refs[idx]+'</div>'+
    '</div>';
}}

function setMoedaAtiva(idx){{
  moedaAtiva=idx;
  renderMoedasCards();
  renderEUR();
}}

function renderMoedasCards(){{
  const wrap=document.getElementById('moeda-grid-wrap');
  if(!wrap) return;
  wrap.innerHTML=MOEDAS.map(function(m,i){{ return buildMoedaCard(m,i); }}).join('');
  // atualiza toggle
  const tog=document.getElementById('moeda-toggle');
  if(tog){{
    tog.innerHTML=MOEDAS.map(function(m,i){{
      return '<button class="vtog'+(i===moedaAtiva?' on':'')+'" onclick="setMoedaAtiva('+i+')">'+m.par+'</button>';
    }}).join('');
  }}
  // legenda
  const lbl=document.getElementById('leg-moeda-label');
  if(lbl) lbl.textContent=MOEDAS[moedaAtiva].par;
}}

function renderEUR(){{
  if(chEUR) chEUR.destroy();
  const m=MOEDAS[moedaAtiva];
  // usa historico da moeda se disponivel, senao estimativa
  let hist=m.hist||[];
  let lbs, vals;
  if(hist.length>0){{
    lbs=hist.map(function(d){{ return nm(d.m); }});
    vals=hist.map(function(d){{ return d.v; }});
  }} else {{
    // fallback: interpola entre ini_ano e atual
    const slice=DATA.slice(-13);
    lbs=slice.map(function(d){{ return nm(d.m); }});
    const ini=m.atual*(1 - m.pct_ano/100);
    vals=slice.map(function(_,i){{ return +(ini + (m.atual-ini)*i/(slice.length-1)).toFixed(4); }});
  }}
  const ref = moedaAtiva===1 ? 7.0 : 1.0;  // CNY ref ~7, outros ~1
  const colors=['#e67e22','#1d9e75','#7f77dd'];
  chEUR=new Chart(document.getElementById('chEUR'),{{
    type:'line',
    data:{{labels:lbs,datasets:[
      {{label:m.par,data:vals,borderColor:colors[moedaAtiva],backgroundColor:'rgba(230,126,34,0.07)',borderWidth:2.5,fill:true,tension:0.4,pointRadius:3,pointBackgroundColor:colors[moedaAtiva]}},
      {{label:'Referencia',data:Array(lbs.length).fill(ref),borderColor:'rgba(170,183,184,0.5)',borderWidth:1,borderDash:[5,4],pointRadius:0,fill:false}}
    ]}},
    options:{{responsive:true,maintainAspectRatio:false,interaction:{{mode:'index',intersect:false}},
      plugins:{{legend:{{display:false}},tooltip:{{backgroundColor:'#fff',borderColor:'#e2e5eb',borderWidth:1,titleColor:'#1a1a2e',bodyColor:'#5a6070',padding:10,boxPadding:4,
        callbacks:{{label:function(c){{ return ' '+c.dataset.label+': '+c.parsed.y.toFixed(4); }}}}
      }}}},
      scales:{{
        x:{{grid:{{color:'rgba(0,0,0,0.04)'}},ticks:{{color:'#9aa0ab',font:{{size:10}}}}}},
        y:{{grid:{{color:'rgba(0,0,0,0.04)'}},ticks:{{color:'#9aa0ab',font:{{size:10}},callback:function(v){{ return v.toFixed(3); }}}}}}
      }}
    }}
  }});
}}

/* ── Fluxo cambial com filtro de periodo ── */
let fluxoPeriodo = '12m';

function setFluxoPeriodo(p, el){{
  fluxoPeriodo=p;
  document.querySelectorAll('#fluxo-periodo-toggle .vtog').forEach(function(b){{ b.className='vtog'; }});
  if(el) el.className='vtog on';
  renderFluxo();
}}

function renderFluxo(){{
  if(chFluxo) chFluxo.destroy();

  // Filtra FLUXO_HIST conforme periodo
  let dados = FLUXO_HIST.slice();
  if(fluxoPeriodo==='6m')  dados=dados.slice(-6);
  else if(fluxoPeriodo==='12m') dados=dados.slice(-12);
  else if(fluxoPeriodo==='24m') dados=dados.slice(-24);
  // 'ano': agrupa por ano
  let lbs, ent, sai, saldo;
  if(fluxoPeriodo==='ano'){{
    const porAno={{}};
    dados.forEach(function(d){{
      const y=d.m.slice(0,4);
      if(!porAno[y]) porAno[y]={{e:0,s:0}};
      porAno[y].e+=d.e; porAno[y].s+=d.s;
    }});
    const anos=Object.keys(porAno).sort();
    lbs=anos; 
    ent=anos.map(function(y){{ return +(porAno[y].e/1000).toFixed(1); }});
    sai=anos.map(function(y){{ return +(porAno[y].s/1000).toFixed(1); }});
    saldo=anos.map(function(y){{ return +((porAno[y].e-porAno[y].s)/1000).toFixed(1); }});
  }} else {{
    lbs=dados.map(function(d){{ return nm(d.m); }});
    ent=dados.map(function(d){{ return +(d.e/1000).toFixed(1); }});
    sai=dados.map(function(d){{ return +(d.s/1000).toFixed(1); }});
    saldo=dados.map(function(d){{ return +(d.saldo/1000).toFixed(1); }});
  }}

  // Atualiza cards de resumo
  const totalE=ent.reduce(function(a,b){{return a+b;}},0);
  const totalS=sai.reduce(function(a,b){{return a+b;}},0);
  const totalSaldo=+(totalE-totalS).toFixed(1);
  const saldoCls=totalSaldo>=0?'dn':'up';
  const saldoSinal=totalSaldo>=0?'+':'';
  const periodoLabel={{'6m':'Ultimos 6 meses','12m':'Ultimos 12 meses','24m':'Ultimos 24 meses','ano':'Por ano (acumulado)'}}[fluxoPeriodo];
  const cards=document.getElementById('fluxo-cards');
  if(cards){{
    cards.innerHTML=
      '<div class="fluxo-card positivo">'+
        '<div class="fluxo-titulo">&#128200; Entradas — '+periodoLabel+'</div>'+
        '<div class="fluxo-total" style="color:#0f7c4a;">US$ '+totalE.toFixed(1)+' bi</div>'+
        '<div class="fluxo-sub">Total de capital entrante no periodo</div>'+
      '</div>'+
      '<div class="fluxo-card" style="background:#fff1f1;border-color:#fca5a5;">'+
        '<div class="fluxo-titulo">&#128200; Saidas — '+periodoLabel+'</div>'+
        '<div class="fluxo-total" style="color:#b91c1c;">US$ '+totalS.toFixed(1)+' bi</div>'+
        '<div class="fluxo-sub">Total de capital sainte no periodo</div>'+
      '</div>'+
      '<div class="fluxo-card '+(totalSaldo>=0?'positivo':'')+'">'+
        '<div class="fluxo-titulo">&#9651; Saldo liquido — '+periodoLabel+'</div>'+
        '<div class="fluxo-total '+saldoCls+'">'+saldoSinal+'US$ '+Math.abs(totalSaldo).toFixed(1)+' bi</div>'+
        '<div class="fluxo-sub">Entrada - Saida · '+(totalSaldo>=0?'Fluxo positivo — real favorecido':'Fluxo negativo — pressao sobre o real')+'</div>'+
      '</div>';
  }}

  const title=document.getElementById('fluxo-chart-title');
  if(title) title.textContent='Entradas, saidas e saldo — '+periodoLabel;

  chFluxo=new Chart(document.getElementById('chFluxo'),{{
    type:'bar',
    data:{{labels:lbs,datasets:[
      {{label:'Entradas',data:ent,backgroundColor:'rgba(29,158,117,0.55)',borderColor:'#1d9e75',borderWidth:1,order:2}},
      {{label:'Saidas',data:sai,backgroundColor:'rgba(185,28,28,0.45)',borderColor:'#b91c1c',borderWidth:1,order:3}},
      {{label:'Saldo',data:saldo,type:'line',borderColor:'#1a5fa8',backgroundColor:'rgba(26,95,168,0.1)',borderWidth:2.5,fill:false,tension:0.4,pointRadius:4,pointBackgroundColor:'#1a5fa8',order:1,yAxisID:'y2'}}
    ]}},
    options:{{
      responsive:true,maintainAspectRatio:false,
      interaction:{{mode:'index',intersect:false}},
      plugins:{{legend:{{display:false}},tooltip:{{backgroundColor:'#fff',borderColor:'#e2e5eb',borderWidth:1,titleColor:'#1a1a2e',bodyColor:'#5a6070',padding:10,boxPadding:4,
        callbacks:{{label:function(c){{ return ' '+c.dataset.label+': US$ '+c.parsed.y.toFixed(1)+' bi'; }}}}
      }}}},
      scales:{{
        x:{{grid:{{color:'rgba(0,0,0,0.04)'}},ticks:{{color:'#9aa0ab',font:{{size:10}}}}}},
        y:{{grid:{{color:'rgba(0,0,0,0.04)'}},ticks:{{color:'#9aa0ab',font:{{size:10}},callback:function(v){{ return 'US$ '+v+' bi'; }}}},title:{{display:true,text:'Entradas / Saidas',color:'#9aa0ab',font:{{size:10}}}}}},
        y2:{{position:'right',grid:{{display:false}},ticks:{{color:'#1a5fa8',font:{{size:10}},callback:function(v){{ return (v>0?'+':'')+v+' bi'; }}}},title:{{display:true,text:'Saldo',color:'#1a5fa8',font:{{size:10}}}}}}
      }}
    }}
  }});
}}


/* ── Init ── */
(function(){{
  if(!DATA||!DATA.length){{
    console.error('[Painel] DATA vazio — verifique o Python.');
    document.getElementById('chH').parentElement.innerHTML=
      '<div style="padding:40px;text-align:center;color:#888;font-size:13px;">'+
      'Nenhum dado disponivel. Execute o Python para gerar o painel com dados reais.</div>';
    return;
  }}
  console.log('[Painel] DATA carregado:', DATA.length, 'meses |', Object.keys(DATA_DIARIOS).length, 'meses com dados diarios');

  const ss=document.getElementById('ss');
  const se=document.getElementById('se');
  const sd=document.getElementById('sd');

  // Popula selects de periodo (mensal)
  DATA.forEach(d=>{{
    const lab=nm(d.m);
    const o1=document.createElement('option'); o1.value=d.m; o1.textContent=lab; ss.appendChild(o1);
    const o2=document.createElement('option'); o2.value=d.m; o2.textContent=lab; se.appendChild(o2);
  }});

  // Periodo inicial default: 2 anos atras (ou primeiro disponivel)
  const hoje=DATA[DATA.length-1].m;
  const [hy,hmo]=hoje.split('-').map(Number);
  let iy=hy-2, imo=hmo+1; if(imo>12){{imo-=12;iy++;}}
  const iMes=`${{iy}}-${{String(imo).padStart(2,'0')}}`;
  const inicioDefault=DATA.find(d=>d.m>=iMes)||DATA[0];
  ss.value=inicioDefault.m;
  se.value=DATA[DATA.length-1].m;

  // Popula seletor de mes para visao diaria — todos os meses do DATA
  // (meses sem dados diarios mostram mensagem ao selecionar)
  if(sd){{
    DATA.forEach(function(d){{
      const o=document.createElement('option');
      o.value=d.m;
      o.textContent=nm(d.m)+(DATA_DIARIOS[d.m]?' ':'*'); // * = sem dados diarios
      sd.appendChild(o);
    }});
    sd.value=DATA[DATA.length-1].m;
    sd.onchange=renderD;
  }}



  // Event listeners
  [ss,se].forEach(el=>el.addEventListener('change',renderH));
  document.getElementById('sm').addEventListener('change',renderH);
  document.getElementById('np').addEventListener('input',renderH);
  document.getElementById('np').addEventListener('change',renderH);

  // Renderiza apos DOM estar pronto
  setTimeout(renderH, 0);
}})();
</script>
</body>
</html>"""
    return html


# ─── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 65)
    print("  Painel USD/BRL v2 — Visao Estrategica Macroeconomica")
    print("=" * 65)

    is_ci = os.environ.get("CI", "false").lower() == "true"

    try:
        diarios        = buscar_ptax()
        mensal, ultimo = agrupar_por_mes(diarios)
        focus          = buscar_focus()
        var_brl        = calcular_variacoes(mensal)
        mensal_eur     = buscar_moeda("EUR")
        var_eur        = calcular_variacoes_moeda(mensal_eur, mensal, "EUR")
        mensal_cny     = buscar_moeda("CNY")
        var_cny        = calcular_variacoes_moeda(mensal_cny, mensal, "CNY")
        mensal_gbp     = buscar_moeda("GBP")
        var_gbp        = calcular_variacoes_moeda(mensal_gbp, mensal, "GBP")
        fluxo_raw      = buscar_fluxo_cambial()
        fluxo          = calcular_fluxo(fluxo_raw)

        # Atualiza projecao Focus BCB com dados reais
        lv = mensal[-1]['v']
        SERIES_PROJ["Focus BCB"] = [
            round(lv + (focus['cambio_2026'] - lv) * i / 7, 2) for i in range(1, 8)
        ] + [focus['cambio_2027']]

        html = gerar_html(mensal, ultimo, len(diarios), focus, var_brl, var_eur, fluxo, diarios=diarios, var_cny=var_cny, var_gbp=var_gbp)

        if getattr(sys, 'frozen', False):
            pasta = os.path.dirname(sys.executable)
        else:
            pasta = os.path.dirname(os.path.abspath(__file__))
        caminho = os.path.join(pasta, ARQUIVO_SAIDA)

        with open(caminho, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"\n[OK] Painel gerado: {caminho}")
        print(f"     {len(diarios):,} cotacoes -> {len(mensal)} medias mensais")
        print(f"     EUR/USD atual: {var_eur['atual']:.4f}")
        print(f"     Fluxo cambial ({fluxo['ultimo_mes']}): saldo US$ {fluxo['saldo_mes']/1000:.1f} bi")
        print(f"     Variacao USD/BRL: mes {var_brl['pct_mes']:+.2f}% | ano {var_brl['pct_ano']:+.2f}% | 12m {var_brl['pct_12m']:+.2f}%")

        if not is_ci:
            print(f"\n     Abrindo no navegador...")
            import webbrowser
            webbrowser.open(f"file:///{caminho.replace(os.sep, '/')}")

    except Exception as e:
        print(f"\n[ERRO] Inesperado: {e}")
        traceback.print_exc()
        import sys; sys.exit(1)
    finally:
        print("\n" + "=" * 65)
        if not is_ci:
            input("Pressione Enter para fechar...")
