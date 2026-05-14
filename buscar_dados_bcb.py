"""
Painel USD/BRL - Banco Central do Brasil
=========================================
Busca cotacoes PTAX diarias da API oficial do BCB,
calcula medias mensais e gera HTML standalone com:
  - Aba 1: Historico + Media Movel + Projecao
  - Aba 2: Comparativo Institucional
  - Aba 3: Analise de Mercado (narrativa atualizada)

Pre-requisitos:
    pip install requests

Uso:
    python buscar_dados_bcb.py
"""

import requests
import json
import os
import sys
import traceback
import webbrowser
from datetime import datetime
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
        "$select": "cotacaoVenda,dataHoraCotacao"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; PainelBCB/1.0)",
        "Accept":     "application/json"
    }
    print(f"[BCB] Buscando cotacoes de {DATA_INICIAL} ate {hoje}...")
    r = requests.get(url, params=params, headers=headers, timeout=60)
    r.raise_for_status()
    dados = r.json()["value"]
    print(f"[BCB] {len(dados)} cotacoes diarias recebidas.")
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
    print(f"[BCB] {len(mensal)} medias mensais calculadas.")
    print(f"[BCB] Ultimo dado: {ultimo['dataHoraCotacao'][:10]} - R$ {ultimo['cotacaoVenda']:.4f}")
    return mensal, ultimo

def gerar_html(mensal, ultimo, total_diarios):
    data_geracao = datetime.now().strftime("%d/%m/%Y %H:%M")
    ultimo_dt    = datetime.strptime(ultimo["dataHoraCotacao"][:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    ultimo_val   = f"{ultimo['cotacaoVenda']:.4f}"
    media_mes    = f"{mensal[-1]['v']:.4f}"
    dados_js     = json.dumps(mensal, ensure_ascii=False)
    proj_js      = json.dumps(SERIES_PROJ, ensure_ascii=False)
    cores_js     = json.dumps(CORES, ensure_ascii=False)

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
.wrap{{max-width:1120px;margin:0 auto;padding:28px 20px;}}
.hdr{{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:24px;gap:12px;flex-wrap:wrap;}}
.hdr h1{{font-size:20px;font-weight:600;margin-bottom:3px;}}
.hdr p{{font-size:12px;color:var(--txt2);}}
.badge{{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:500;padding:5px 11px;border-radius:20px;}}
.badge-ok{{background:#d1fae5;color:#065f46;border:1px solid #6ee7b7;}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px;}}
@media(max-width:700px){{.cards{{grid-template-columns:repeat(2,1fr);}}}}
.card{{background:var(--bg2);border:1px solid var(--borda);border-radius:var(--rl);padding:16px 18px;box-shadow:var(--sh);}}
.cl{{font-size:10px;color:var(--txt2);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px;font-weight:600;}}
.cv{{font-size:22px;font-weight:700;color:var(--txt);line-height:1.2;}}
.cs{{font-size:11px;color:var(--txt3);margin-top:4px;}}
.up{{color:#b91c1c;}}.dn{{color:#0f7c4a;}}
.tabs{{display:flex;gap:4px;border-bottom:1px solid var(--borda);margin-bottom:0;flex-wrap:wrap;}}
.tab{{padding:9px 20px;font-size:13px;font-weight:500;border:none;background:none;color:var(--txt2);cursor:pointer;border-bottom:2.5px solid transparent;margin-bottom:-1px;transition:all .15s;}}
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
.cw{{position:relative;width:100%;height:320px;}}
.igrid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:20px;}}
@media(max-width:700px){{.igrid{{grid-template-columns:repeat(2,1fr);}}}}
.ic{{background:var(--bg);border:1px solid var(--borda);border-radius:var(--rl);padding:13px 15px;}}
.ic.hl{{background:linear-gradient(135deg,#f0f7ff,#e8f4fd);border-color:#bcd6f0;}}
.in{{font-size:12px;font-weight:600;color:var(--txt);margin-bottom:9px;display:flex;align-items:center;gap:6px;}}
.idot{{width:9px;height:9px;border-radius:50%;flex-shrink:0;}}
.ir{{display:flex;justify-content:space-between;font-size:11px;padding:2.5px 0;}}
.irl{{color:var(--txt2);}}.irv{{font-weight:600;color:var(--txt);}}
.inote{{font-size:10px;color:var(--txt3);margin-top:8px;padding-top:7px;border-top:1px solid var(--borda);}}
/* Analise narrativa */
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
</style>
</head>
<body>
<div class="wrap">

<div class="hdr">
  <div>
    <h1>Painel USD/BRL - Banco Central do Brasil</h1>
    <p>Cotacoes PTAX diarias · Medias mensais · Projecao por Media Movel · Comparativo e Analise de Mercado · Gerado em {data_geracao}</p>
  </div>
  <span class="badge badge-ok">&#10003; PTAX BCB &mdash; {total_diarios:,} cotacoes reais</span>
</div>

<div class="cards">
  <div class="card">
    <div class="cl">Ultima PTAX (venda)</div>
    <div class="cv">R$ {ultimo_val}</div>
    <div class="cs">{ultimo_dt}</div>
  </div>
  <div class="card">
    <div class="cl">Media do mes atual</div>
    <div class="cv">R$ {media_mes}</div>
    <div class="cs" id="cs-mes">mai/2026</div>
  </div>
  <div class="card">
    <div class="cl">Variacao no periodo</div>
    <div class="cv" id="c-var">-</div>
    <div class="cs" id="c-var-d">-</div>
  </div>
  <div class="card">
    <div class="cl">Focus dez/26</div>
    <div class="cv">R$ 5,20</div>
    <div class="cs">Boletim Focus · 11/mai/2026</div>
  </div>
</div>

<div class="tabs">
  <button class="tab on" onclick="setTab('h',this)">&#128200; Historico + Media Movel</button>
  <button class="tab"    onclick="setTab('i',this)">&#127968; Comparativo Institucional</button>
  <button class="tab"    onclick="setTab('a',this)">&#128240; Analise de Mercado</button>
</div>

<!-- PAINEL 1: HISTORICO -->
<div id="ph" class="panel">
  <div class="ptitle">Evolucao historica PTAX (BCB) e projecao por media movel</div>
  <div class="ctrl">
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
  <div class="leg">
    <div class="li"><div class="ll" style="background:var(--azul)"></div>PTAX mensal (BCB)</div>
    <div class="li"><div class="ll" style="background:repeating-linear-gradient(90deg,var(--azul2) 0 5px,transparent 5px 9px)"></div>Media movel</div>
    <div class="li"><div class="ll" style="background:var(--laranja)"></div>Projecao MM</div>
    <div class="li"><div class="ll" style="background:#aab7b8;opacity:.6"></div>Banda &plusmn;1&sigma;</div>
  </div>
  <div class="cw"><canvas id="chH" aria-label="Historico PTAX e projecao USD/BRL"></canvas></div>
</div>

<!-- PAINEL 2: INSTITUCIONAL -->
<div id="pi" class="panel" style="display:none">
  <div class="ptitle">Projecoes institucionais sobrepostas ao historico PTAX</div>
  <div class="igrid">
    <div class="ic">
      <div class="in"><div class="idot" style="background:#888780"></div>Focus - BCB</div>
      <div class="ir"><span class="irl">Dez/2026</span><span class="irv">R$ 5,20</span></div>
      <div class="ir"><span class="irl">2027</span><span class="irv">R$ 5,30</span></div>
      <div class="ir"><span class="irl">2028</span><span class="irv">R$ 5,35</span></div>
      <div class="inote">Mediana de mercado · Boletim Focus 11/mai/2026</div>
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
      <div class="ir"><span class="irl">Mediana</span><span class="irv">R$ 5,15</span></div>
      <div class="ir"><span class="irl">Maximo</span><span class="irv up">R$ 5,60</span></div>
      <div class="inote">5 instituicoes · relatorios mai/2026</div>
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
  <div class="cw"><canvas id="chI" aria-label="Comparativo de projecoes USD/BRL por instituicao"></canvas></div>
</div>

<!-- PAINEL 3: ANALISE DE MERCADO -->
<div id="pa" class="panel" style="display:none">
  <div class="ptitle">Analise de Mercado &mdash; O que esta movendo o dolar em mai/2026</div>

  <!-- Termometro de pressao cambial -->
  <div class="an-card neutro" style="margin-bottom:16px;">
    <div class="an-titulo"><span class="an-ico">&#127777;</span> Termometro cambial atual</div>
    <div class="termometro-wrap">
      <div class="termometro-label"><span>Real muito forte</span><span>Neutro</span><span>Dolar muito forte</span></div>
      <div class="termometro">
        <div class="termometro-marker" style="left:28%"></div>
      </div>
      <div class="termometro-val">Real levemente apreciado &mdash; USD/BRL ~R$ 4,98 (mai/2026)</div>
    </div>
    <div class="an-texto" style="margin-top:10px;">
      O dolar recuou de <strong>R$ 6,18 (jan/2025)</strong> para <strong>R$ 4,98 (mai/2026)</strong>, queda de 19,5% em 16 meses. 
      O real registrou a <strong>2a maior valorizacao entre 28 moedas emergentes</strong> no acumulado de 2026, 
      impulsionado por fluxo externo recorde e diferencial de juros elevado.
    </div>
  </div>

  <!-- Grade de fatores -->
  <div class="an-grid">

    <div class="an-card positivo">
      <div class="an-titulo"><span class="an-ico">&#9650;</span> Fatores que fortalecem o real</div>
      <div class="an-texto">
        <strong>Diferencial de juros (carry trade):</strong> Com a Selic em 14,75% e o Fed entre 3,50-3,75%, 
        o spread real e um dos mais atrativos do mundo, atraindo capital estrangeiro para renda fixa brasileira.<br><br>
        <strong>Fluxo externo recorde:</strong> Na semana de 20-24/abr, o Brasil registrou entrada liquida de 
        <strong>US$ 9,2 bilhoes</strong> &mdash; o maior ingresso semanal da historia (BTG Pactual/BCB). 
        Investidores estrangeiros representam 61,2% dos negocios da B3 em 2026, primeiro vez acima de 60%.<br><br>
        <strong>Commodities e geopolitica:</strong> O conflito no Oriente Medio manteve o petroleo acima de US$ 100, 
        beneficiando o Brasil como exportador. A XP classifica o Brasil como <em>"vencedor relativo"</em> no 
        contexto geopolitico atual.<br><br>
        <strong>Dolar global mais fraco:</strong> O indice DXY recuou ~9% em 2025. 
        Com o Fed cortando juros, o capital migra para emergentes com retorno superior.
      </div>
    </div>

    <div class="an-card risco">
      <div class="an-titulo"><span class="an-ico">&#9660;</span> Fatores de risco (pressao de alta no dolar)</div>
      <div class="an-texto">
        <strong>Eleicoes presidenciais (out/2026):</strong> Anos eleitorais no Brasil seguem um padrao historico claro: 
        1S calmo, 3T com pico de volatilidade, 4T com acomodacao pos-urnas. 
        O Morgan Stanley projeta pico de <strong>R$ 5,60 no 3T26</strong> por conta desse risco.<br><br>
        <strong>Risco fiscal:</strong> O aumento dos gastos em ano eleitoral preocupa o mercado. 
        Qualquer deterioracao nas contas publicas pode reverter o fluxo externo rapidamente.<br><br>
        <strong>Reducao do diferencial de juros:</strong> A Selic em ciclo de queda estreita o spread 
        com os EUA. Se o corte for percebido como precipitado, o real perde atratividade.<br><br>
        <strong>Inflacao importada:</strong> Petroleo caro e cambio mais forte criam pressoes opostas. 
        A XP aponta "perspectivas inflacionarias que pioraram por fatores globais e domesticos".
      </div>
    </div>

    <div class="an-card destaque">
      <div class="an-titulo"><span class="an-ico">&#128201;</span> Por que as instituicoes divergem?</div>
      <div class="an-texto">
        <div class="inst-reason">
          <div class="inst-reason-header">
            <div class="inst-dot2" style="background:#e67e22"></div>
            <span class="inst-nome">XP e Bradesco &mdash; R$ 5,00</span>
            <span class="inst-proj">Mais otimistas c/ real</span>
          </div>
          <div class="inst-reason-texto">
            Apostam na continuidade do fluxo externo para emergentes e no papel do Brasil 
            como exportador de commodities em ambiente geopolitico tenso. 
            Selic restritiva (13-14%) sustenta o carry trade por mais tempo.
          </div>
        </div>
        <div class="inst-reason">
          <div class="inst-reason-header">
            <div class="inst-dot2" style="background:#7f77dd"></div>
            <span class="inst-nome">Itau &mdash; R$ 5,15</span>
            <span class="inst-proj">Cenario moderado</span>
          </div>
          <div class="inst-reason-texto">
            Reconhece os fundamentos positivos mas pondera que o estreitamento do 
            diferencial de juros ao longo de 2026 limita a apreciacao adicional do real. 
            Projeta leve reversao em 2027 para R$ 5,30.
          </div>
        </div>
        <div class="inst-reason">
          <div class="inst-reason-header">
            <div class="inst-dot2" style="background:#d4537e"></div>
            <span class="inst-nome">Morgan Stanley &mdash; R$ 5,60 (pico 3T)</span>
            <span class="inst-proj">Mais pessimista</span>
          </div>
          <div class="inst-reason-texto">
            Da maior peso ao risco eleitoral. Historicamente, eleicoes brasileiras provocam 
            volatilidade acima da media no 3T. O banco projeta acomodacao post-eleicao 
            para R$ 5,30, mas considera o desfecho "muito binario".
          </div>
        </div>
        <div class="inst-reason">
          <div class="inst-reason-header">
            <div class="inst-dot2" style="background:#888780"></div>
            <span class="inst-nome">Focus BCB &mdash; R$ 5,20</span>
            <span class="inst-proj">Mediana de mercado</span>
          </div>
          <div class="inst-reason-texto">
            Mediana de dezenas de instituicoes. Reflete o consenso geral que ve o real 
            levemente apreciado, mas com upside limitado dado o contexto fiscal e eleitoral.
          </div>
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
            <div class="monitor-val">4,91%</div>
            <div class="monitor-sub">9a alta consecutiva</div>
          </div>
        </div>
        <div style="margin-top:14px;">
          <strong>Nivel critico a observar:</strong><br>
          <span class="tag tag-baixo">R$ 4,80 &mdash; suporte forte</span>
          <span class="tag tag-medio">R$ 5,20 &mdash; resistencia Focus</span>
          <span class="tag tag-alto">R$ 5,60 &mdash; pico eleitoral (MS)</span>
        </div>
      </div>
    </div>

  </div><!-- /an-grid -->

  <!-- Implicacao para o setor -->
  <div class="an-card" style="background:#f0f7ff;border-color:#93c5fd;margin-top:4px;">
    <div class="an-titulo"><span class="an-ico">&#128188;</span> Implicacao para o setor de tecnologia financeira e automacao comercial</div>
    <div class="an-texto">
      Com o dolar testando o suporte de <strong>R$ 4,90-5,00</strong>, empresas do setor de tecnologia 
      que operam com componentes ou licencas dolarizadas enfrentam impacto direto nos custos e margens. 
      O cenario de consenso aponta para <strong>leve recuperacao no 2S26</strong> (R$ 5,15-5,30) 
      puxada pelo risco eleitoral &mdash; o que exige planejamento cambial por segmento:<br><br>
      <strong>&#9679; Solucoes para automacao comercial:</strong> equipamentos e componentes importados 
      (leitores, impressoras fiscais, modulos de conectividade) sofrem repasse imediato da variacao cambial 
      ao custo do produto. A banda R$ 5,00-5,60 projetada para 2026 amplia a incerteza no planejamento 
      de estoques e precificacao de contratos plurianuais.<br><br>
      <strong>&#9679; Ferramentas para meios de pagamento diversos:</strong> solucoes que processam 
      transacoes em moeda estrangeira ou que repassam taxas indexadas ao dolar (gateways internacionais, 
      adquirencias cross-border) beneficiam-se do real mais forte no curto prazo, mas devem monitorar 
      a reversao esperada no 3T26 com o risco eleitoral.<br><br>
      <strong>&#9679; Plataformas para transferencia de fundos:</strong> operacoes de remessa e 
      conversao cambial estao diretamente expostas a volatilidade. O pico projetado de R$ 5,60 
      (Morgan Stanley, 3T26) pode impactar spreads e competitividade frente a fintechs globais.<br><br>
      <strong>&#9679; Terminais de autoatendimento e consulta de precos:</strong> hardware importado 
      (displays, processadores, leitores biometricos) sofre pressao de custo com dolar acima de R$ 5,20. 
      Contratos de manutencao e atualizacao de software com fornecedores internacionais devem ser 
      revisados considerando a banda R$ 5,00-5,60 para o horizonte de 12 meses.<br><br>
      <strong>Estrategia recomendada:</strong> trava cambial na faixa atual (R$ 4,90-5,00) para 
      compromissos de importacao via contratos a termo. Renegociar contratos de fornecimento 
      com clausulas de reajuste cambial atreladas ao PTAX do BCB para proteger margens operacionais.
    </div>
  </div>

</div><!-- /pa -->

<div class="foot">
  Fonte: API PTAX Banco Central do Brasil (olinda.bcb.gov.br) · {total_diarios:,} cotacoes diarias · 
  Ultimo dado: {ultimo_dt} · Analise narrativa baseada em relatorios publicos de mai/2026 (XP, Bradesco, Itau, Morgan Stanley, BTG, Focus BCB, Rico, Suno) · 
  Gerado em {data_geracao} · Nao constitui recomendacao de investimento.
</div>

</div><!-- /wrap -->

<script>
const DATA  = {dados_js};
const SPROJ = {proj_js};
const CORES = {cores_js};

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

let chH=null, chI=null;

function setTab(t,el){{
  document.querySelectorAll('.tab').forEach(b=>b.className='tab');
  el.className='tab on';
  document.getElementById('ph').style.display=t==='h'?'':'none';
  document.getElementById('pi').style.display=t==='i'?'':'none';
  document.getElementById('pa').style.display=t==='a'?'':'none';
  if(t==='i') renderI();
}}

function renderH(){{
  const s=document.getElementById('ss').value;
  const e=document.getElementById('se').value;
  if(!s||!e||s>e) return;
  const mm=+document.getElementById('sm').value;
  const n=Math.max(1,Math.min(24,+document.getElementById('np').value||6));
  const fd=DATA.filter(d=>d.m>=s&&d.m<=e);
  if(fd.length<2) return;
  const lbs=fd.map(d=>nm(d.m)), vs=fd.map(d=>d.v);
  const mav=maFn(vs,mm), {{p,u,l}}=buildProj(vs,mm,n);
  const lm=fd[fd.length-1].m;
  const pl=Array.from({{length:n}},(_,i)=>nm(addM(lm,i+1)));
  const all=[...lbs,...pl], hl=lbs.length, lv=vs[vs.length-1];
  const pad=Array(hl-1).fill(null);
  const cur=vs[vs.length-1], fst=vs[0], dv=cur-fst, dp=dv/fst*100;
  const vel=document.getElementById('c-var');
  vel.textContent=`${{dv>=0?'+':''}}R$ ${{dv.toFixed(2)}}`;
  vel.className='cv '+(dv>=0?'up':'dn');
  document.getElementById('c-var-d').textContent=`${{dp>=0?'+':''}}${{dp.toFixed(2)}}% - ${{nm(s)}} a ${{nm(e)}}`;
  const ds=[
    {{label:'PTAX mensal (BCB)',data:[...vs,...Array(n).fill(null)],borderColor:'#1a5fa8',backgroundColor:'rgba(26,95,168,0.06)',borderWidth:2,fill:true,tension:0.35,order:3,pointRadius:vs.map((_,i)=>i===vs.length-1?5:1.5),pointBackgroundColor:'#1a5fa8',pointBorderWidth:0}},
    {{label:'Media movel',data:[...mav,...Array(n).fill(null)],borderColor:'#2e86c1',borderWidth:2,borderDash:[7,4],pointRadius:0,fill:false,tension:0.4,order:2}},
    {{label:'Projecao MM',data:[...pad,lv,...p],borderColor:'#e67e22',backgroundColor:'rgba(230,126,34,0.06)',borderWidth:2.5,fill:false,tension:0.3,order:1,pointRadius:[...Array(hl-1).fill(0),5,...Array(n).fill(3.5)],pointBackgroundColor:'#e67e22',pointBorderWidth:0}},
    {{label:'Banda sup',data:[...Array(hl-1).fill(null),lv,...u],borderColor:'rgba(170,183,184,0.3)',borderWidth:1,pointRadius:0,fill:'+1',backgroundColor:'rgba(170,183,184,0.12)',tension:0.3,order:5}},
    {{label:'Banda inf',data:[...Array(hl-1).fill(null),lv,...l],borderColor:'rgba(170,183,184,0.3)',borderWidth:1,pointRadius:0,fill:false,tension:0.3,order:6}}
  ];
  if(chH) chH.destroy();
  chH=new Chart(document.getElementById('chH'),{{type:'line',data:{{labels:all,datasets:ds}},options:{{responsive:true,maintainAspectRatio:false,interaction:{{mode:'index',intersect:false}},plugins:{{legend:{{display:false}},tooltip:{{backgroundColor:'#fff',borderColor:'#e2e5eb',borderWidth:1,titleColor:'#1a1a2e',bodyColor:'#5a6070',padding:10,boxPadding:4,callbacks:{{label:c=>c.parsed.y===null?null:` ${{c.dataset.label}}: R$ ${{c.parsed.y.toFixed(4)}}`}}}}}},scales:{{x:{{grid:{{color:'rgba(0,0,0,0.04)'}},ticks:{{color:'#9aa0ab',font:{{size:10}},maxRotation:45,autoSkip:true,maxTicksLimit:22}}}},y:{{grid:{{color:'rgba(0,0,0,0.04)'}},ticks:{{color:'#9aa0ab',font:{{size:10}},callback:v=>`R$ ${{v.toFixed(2)}}`}}}}}}}}}});
}}

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
    {{label:'PTAX mensal (BCB)',data:[...hv,...Array(pm.length).fill(null)],borderColor:'#1a5fa8',backgroundColor:'rgba(26,95,168,0.06)',borderWidth:2.5,fill:true,tension:0.35,order:20,pointRadius:hv.map((_,i)=>i===hv.length-1?5:1.5),pointBackgroundColor:'#1a5fa8',pointBorderWidth:0}},
    {{label:'Banda sup',data:mk([5.28,5.35,5.42,5.60,5.52,5.43,5.30,5.30]),borderColor:'rgba(170,183,184,0.25)',borderWidth:1,pointRadius:0,fill:'+1',backgroundColor:'rgba(170,183,184,0.09)',tension:0.3,order:19}},
    {{label:'Banda inf',data:mk([5.05,5.03,5.02,5.01,5.00,5.00,5.00,5.00]),borderColor:'rgba(170,183,184,0.25)',borderWidth:1,pointRadius:0,fill:false,tension:0.3,order:18}},
    ...instDs
  ];
  if(chI) chI.destroy();
  chI=new Chart(document.getElementById('chI'),{{type:'line',data:{{labels:all,datasets:ds}},options:{{responsive:true,maintainAspectRatio:false,interaction:{{mode:'index',intersect:false}},plugins:{{legend:{{display:false}},tooltip:{{backgroundColor:'#fff',borderColor:'#e2e5eb',borderWidth:1,titleColor:'#1a1a2e',bodyColor:'#5a6070',padding:10,boxPadding:4,callbacks:{{label:c=>c.parsed.y===null?null:` ${{c.dataset.label}}: R$ ${{c.parsed.y.toFixed(2)}}`}}}}}},scales:{{x:{{grid:{{color:'rgba(0,0,0,0.04)'}},ticks:{{color:'#9aa0ab',font:{{size:10}},maxRotation:45}}}},y:{{grid:{{color:'rgba(0,0,0,0.04)'}},min:4.5,ticks:{{color:'#9aa0ab',font:{{size:10}},callback:v=>`R$ ${{v.toFixed(2)}}`}}}}}}}}}});
}}

(function(){{
  const todayM=new Date().toISOString().slice(0,7);
  const ss=document.getElementById('ss'), se=document.getElementById('se');
  DATA.forEach(d=>{{
    ss.innerHTML+=`<option value="${{d.m}}">${{nm(d.m)}}</option>`;
    se.innerHTML+=`<option value="${{d.m}}">${{nm(d.m)}}${{d.m===todayM?' *':''}}</option>`;
  }});
  ss.value=DATA.find(d=>d.m>='2022-01')?.m||DATA[0].m;
  se.value=DATA[DATA.length-1].m;
  const h=renderH;
  ss.onchange=se.onchange=document.getElementById('sm').onchange=document.getElementById('np').oninput=document.getElementById('np').onchange=h;
  renderH();
}})();
</script>
</body>
</html>"""
    return html

# ─── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  Painel USD/BRL - Banco Central do Brasil")
    print("=" * 60)
    try:
        try:
            import requests
        except ImportError:
            print("\n[ERRO] Biblioteca requests nao encontrada.")
            print("   Execute: pip install requests")
            input("\nPressione Enter para fechar...")
            sys.exit(1)

        diarios = buscar_ptax()
        mensal, ultimo = agrupar_por_mes(diarios)
        html = gerar_html(mensal, ultimo, len(diarios))

        # Quando empacotado pelo PyInstaller, usa a pasta do .exe
        # Quando rodado como .py, usa a pasta do script
        if getattr(sys, 'frozen', False):
            pasta = os.path.dirname(sys.executable)
        else:
            pasta = os.path.dirname(os.path.abspath(__file__))
        caminho = os.path.join(pasta, ARQUIVO_SAIDA)

        with open(caminho, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"\n[OK] Painel gerado: {caminho}")
        print(f"     {len(diarios):,} cotacoes -> {len(mensal)} medias mensais")
        print(f"     Ultima cotacao: {ultimo['dataHoraCotacao'][:10]} - R$ {ultimo['cotacaoVenda']:.4f}")
        print(f"\n     Abrindo no navegador...")

        webbrowser.open(f"file:///{caminho.replace(os.sep, '/')}")

    except requests.exceptions.ConnectionError:
        print("\n[ERRO] Sem conexao com a internet ou API do BCB indisponivel.")
    except requests.exceptions.Timeout:
        print("\n[ERRO] Timeout: a API do BCB demorou demais para responder.")
    except requests.exceptions.HTTPError as e:
        print(f"\n[ERRO] HTTP: {e}")
    except Exception as e:
        print(f"\n[ERRO] Inesperado: {e}")
        traceback.print_exc()
    finally:
        print("\n" + "=" * 60)
        input("Pressione Enter para fechar...")
