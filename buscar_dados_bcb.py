"""
Painel USD/BRL - Banco Central do Brasil
=========================================
Atualiza APENAS os dados dinamicos do painel_dolar_bcb.html existente.
O layout HTML nunca e sobrescrito — so os valores mudam.

Pre-requisitos:
    pip install requests

Uso:
    python buscar_dados_bcb.py
"""

import re
import requests
import json
import os
import sys
import traceback
from datetime import datetime, timedelta
from collections import defaultdict

DATA_INICIAL  = "01-01-2019"
ARQUIVO_HTML  = "painel_dolar_bcb.html"

SERIES_PROJ = {
    "Focus BCB":        [5.21, 5.21, 5.20, 5.20, 5.20, 5.20, 5.20, 5.30],
    "XP Investimentos": [5.14, 5.10, 5.07, 5.04, 5.02, 5.01, 5.00, None],
    "Bradesco":         [5.10, 5.07, 5.04, 5.02, 5.01, 5.00, 5.00, 5.00],
    "Itau":             [5.17, 5.17, 5.17, 5.20, 5.18, 5.16, 5.15, 5.30],
    "Morgan Stanley":   [5.28, 5.36, 5.45, 5.60, 5.52, 5.43, 5.30, None],
}

MESES_PT = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']

def mes_label(m):
    y, mo = m.split('-')
    return MESES_PT[int(mo)-1] + '/' + y[2:]


# ─── PTAX USD/BRL ─────────────────────────────────────────────────────────────
def buscar_ptax():
    hoje   = datetime.today().strftime('%m-%d-%Y')
    url    = (
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


# ─── Atualiza o HTML preservando o layout ─────────────────────────────────────
def atualizar_html(mensal, ultimo, n_diarios):
    pasta   = os.path.dirname(os.path.abspath(__file__))
    caminho = os.path.join(pasta, ARQUIVO_HTML)

    if not os.path.exists(caminho):
        print(f"[ERRO] Arquivo {ARQUIVO_HTML} nao encontrado em {pasta}")
        sys.exit(1)

    with open(caminho, "r", encoding="utf-8") as f:
        html = f.read()

    agora      = datetime.today()
    ultima_data = ultimo["dataHoraCotacao"][:10]   # YYYY-MM-DD
    ultima_ptax = ultimo["cotacaoVenda"]
    mes_atual   = mensal[-1]
    media_mes   = mes_atual["v"]
    mes_label_atual = mes_label(mes_atual["m"])

    # Formata data para DD/MM/YYYY
    d_fmt = datetime.strptime(ultima_data, "%Y-%m-%d").strftime("%d/%m/%Y")
    gerado_em = agora.strftime("%d/%m/%Y %H:%M")

    # ── 1. DATA array (dados mensais) ──────────────────────────────────────────
    data_json = json.dumps(mensal, ensure_ascii=False, separators=(',', ': '))
    html = re.sub(
        r'const DATA\s*=\s*\[.*?\];',
        f'const DATA  = {data_json};',
        html, flags=re.DOTALL
    )

    # ── 2. SPROJ (projecoes institucionais) ────────────────────────────────────
    sproj_json = json.dumps(SERIES_PROJ, ensure_ascii=False)
    # Converte None -> null para JavaScript
    sproj_js   = sproj_json.replace(': null', ': null').replace('null', 'null')
    html = re.sub(
        r'const SPROJ\s*=\s*\{.*?\};',
        f'const SPROJ = {sproj_js};',
        html, flags=re.DOTALL
    )

    # ── 3. Ultima PTAX (card) ──────────────────────────────────────────────────
    # Substitui o valor R$ X.XXXX dentro do primeiro card
    html = re.sub(
        r'(<div class="cl">Ultima PTAX \(venda\)</div>\s*<div class="cv">)R\$\s*[\d.]+(<)',
        rf'\g<1>R$ {ultima_ptax:.4f}\2',
        html
    )
    # Data embaixo do card
    html = re.sub(
        r'(<div class="cl">Ultima PTAX \(venda\)</div>.*?<div class="cs">)\d{2}/\d{2}/\d{4}(</div>)',
        rf'\g<1>{d_fmt}\2',
        html, flags=re.DOTALL
    )

    # ── 4. Media do mes atual (card) ───────────────────────────────────────────
    html = re.sub(
        r'(<div class="cl">Media do mes atual</div>\s*<div class="cv">)R\$\s*[\d.]+(<)',
        rf'\g<1>R$ {media_mes:.4f}\2',
        html
    )

    # ── 5. Subtitulo do mes (cs-mes) ───────────────────────────────────────────
    html = re.sub(
        r'(<div class="cs" id="cs-mes">)[^<]*(</div>)',
        rf'\g<1>{mes_label_atual}\2',
        html
    )

    # ── 6. Badge contador de cotacoes ─────────────────────────────────────────
    html = re.sub(
        r'(PTAX BCB &mdash; )[\d,]+(cotacoes reais)',
        rf'\g<1>{n_diarios:,}\2',
        html
    )

    # ── 7. "Gerado em" no subtitulo do header ─────────────────────────────────
    html = re.sub(
        r'(Gerado em )\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}',
        rf'\g<1>{gerado_em}',
        html
    )

    with open(caminho, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n[OK] {ARQUIVO_HTML} atualizado com sucesso!")
    print(f"     Ultima PTAX : R$ {ultima_ptax:.4f} ({d_fmt})")
    print(f"     Media {mes_label_atual}: R$ {media_mes:.4f}")
    print(f"     Cotacoes    : {n_diarios:,}")
    print(f"     Gerado em   : {gerado_em}")


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  Atualizador Painel USD/BRL — Banco Central do Brasil")
    print("=" * 60)

    is_ci = os.environ.get("CI", "false").lower() == "true"

    try:
        diarios        = buscar_ptax()
        mensal, ultimo = agrupar_por_mes(diarios)
        atualizar_html(mensal, ultimo, len(diarios))

        if not is_ci:
            print("\n     Abrindo no navegador...")
            import webbrowser
            pasta   = os.path.dirname(os.path.abspath(__file__))
            caminho = os.path.join(pasta, ARQUIVO_HTML)
            webbrowser.open(f"file:///{caminho.replace(os.sep, '/')}")

    except Exception as e:
        print(f"\n[ERRO] Inesperado: {e}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        print("\n" + "=" * 60)
        if not is_ci:
            input("Pressione Enter para fechar...")
