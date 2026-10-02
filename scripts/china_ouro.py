#!/usr/bin/env python3
"""
Baixa do UN Comtrade o comércio chinês de ouro não monetário em bruto (HS
710812) e grava dados/china-ouro.json — o cache que o reservas.py lê.

Uso:
    python3 scripts/china_ouro.py              # completa o que falta no cache
    python3 scripts/china_ouro.py --tudo       # refaz desde o começo

POR QUE UM CACHE. A China não entra na estatística de ouro não monetário do
FMI, que é a fonte dos dois gráficos de comércio; o jeito de completá-los é o
dado de alfândega que ela reporta à ONU. Mas o portal da própria alfândega
chinesa (stats.customs.gov.cn) está atrás de um WAF que devolve 412 e depois
400 para qualquer cliente automatizado, e o endpoint aberto do Comtrade aceita
**um período por chamada** e corta em 429 se as chamadas vierem coladas — com
17 segundos entre elas ele aguenta. São ~140 meses, ou seja uns 40 minutos de
coleta. Isso não cabe numa rodada de script: daí o cache em dados/, que entra
no repo e só é refeito quando se quer.

Uma chamada traz os dois fluxos do mês (X e M), então é um pedido por mês.

O QUE A SÉRIE COBRE. No Comtrade a China só reporta esse detalhe mensal de 2016
em diante, e com atraso: quando este script foi escrito o mensal ia até dezembro
de 2024. **O anual vai mais longe** — 2025 já está lá —, então o script busca
também os totais de cada ano, que são onze chamadas a mais.

O anual se encaixa no mesmo gráfico sem conversão nenhuma: a soma móvel de
quatro trimestres no 4º trimestre de um ano **é** o total daquele ano. Dá para
conferir: pelo mensal, os quatro trimestres até 2016-Q4 somam US$ 60,60 bi de
importação, que é exatamente o anual de 2016 publicado. O script refaz essa
conferência a cada rodada, em todo ano que tenha os doze meses.
"""
import datetime
import json
import os
import sys
import time
import urllib.request

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SAIDA = os.path.join(RAIZ, "dados", "china-ouro.json")

PRODUTO = "710812"        # ouro não monetário em bruto, exceto em pó
RELATOR = 156             # China (continente)
INICIO = (2015, 1)
ESPERA = 17               # segundos entre chamadas; abaixo disso o Comtrade corta em 429
URL = ("https://comtradeapi.un.org/public/v1/preview/C/%s/HS?reporterCode=%d"
       "&period=%s&cmdCode=%s&partnerCode=0")


def meses(ate):
    a, m = INICIO
    while (a, m) <= ate:
        yield "%04d%02d" % (a, m)
        m += 1
        if m > 12:
            a, m = a + 1, 1


def um_periodo(freq, periodo):
    """Um período do Comtrade → {"X": valor, "M": valor}, em US$.

    Uma chamada traz os dois fluxos, então é um pedido por período."""
    r = json.load(urllib.request.urlopen(URL % (freq, RELATOR, periodo, PRODUTO), timeout=90))
    fora = {}
    for d in r.get("data") or []:
        if d.get("flowCode") in ("X", "M"):
            fora[d["flowCode"]] = d["primaryValue"]
    return fora


def buscar(cache, chave, freq, periodos, rotulo):
    """Busca os períodos que faltam e guarda em cache[chave]."""
    cache.setdefault(chave, {})
    guardados = sorted(cache[chave])
    refazer = set(guardados[-3:])          # os mais recentes podem ser revisados
    pendentes = [p for p in periodos if p not in cache[chave] or p in refazer]
    print("%s: %d em cache, %d a buscar (~%d min)"
          % (rotulo, len(guardados), len(pendentes), len(pendentes) * ESPERA / 60), flush=True)
    for i, p in enumerate(pendentes, 1):
        for tentativa in range(3):
            try:
                v = um_periodo(freq, p)
                if v:
                    cache[chave][p] = v
                    print("  %s  X %.3f bi  M %.3f bi" % (p, v.get("X", 0) / 1e9, v.get("M", 0) / 1e9),
                          flush=True)
                else:
                    cache[chave].pop(p, None)
                    print("  %s  sem dado" % p, flush=True)
                break
            except Exception as e:
                espera = ESPERA * (tentativa + 2)
                print("  %s  %s — repito em %ds" % (p, str(e)[:40], espera), flush=True)
                time.sleep(espera)
        if i % 10 == 0:
            gravar(cache)
        time.sleep(ESPERA)


def confere_anos(cache):
    """O anual publicado contra a soma dos doze meses — a amarração entre as
    duas frequências, e o que garante que o ponto anual pode entrar no mesmo
    gráfico que o mensal."""
    piores = []
    for ano, v in sorted(cache.get("anos", {}).items()):
        meses_ = [cache["meses"][m] for m in cache.get("meses", {}) if m[:4] == ano]
        if len(meses_) != 12:
            continue
        for fluxo in ("X", "M"):
            if not all(fluxo in m for m in meses_) or fluxo not in v:
                continue
            soma = sum(m[fluxo] for m in meses_)
            piores.append((abs(soma - v[fluxo]) / max(v[fluxo], 1.0), ano, fluxo))
    if not piores:
        print("  (nenhum ano com os doze meses para conferir)", flush=True)
        return
    pior, ano, fluxo = max(piores)
    print("  anual confere com a soma dos 12 meses em %d pares ano/fluxo; "
          "pior diferença %.4f%% (%s, %s)" % (len(piores), pior * 100, ano, fluxo), flush=True)


def main():
    tudo = "--tudo" in sys.argv
    so_anos = "--anos" in sys.argv
    cache = {"produto": PRODUTO, "fonte": "UN Comtrade (China, HS %s)" % PRODUTO,
             "meses": {}, "anos": {}}
    if not tudo and os.path.exists(SAIDA):
        with open(SAIDA, encoding="utf-8") as f:
            cache.update(json.load(f))
    hoje = datetime.date.today()
    if not so_anos:
        buscar(cache, "meses", "M", list(meses((hoje.year, hoje.month))), "mensal")
    buscar(cache, "anos", "A", [str(a) for a in range(INICIO[0], hoje.year + 1)], "anual")
    confere_anos(cache)
    gravar(cache)


def gravar(cache):
    cache["atualizado"] = datetime.date.today().isoformat()
    ms = sorted(cache["meses"])
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        f.write("\n")
    anos = sorted(cache.get("anos", {}))
    if ms:
        print("gravado %s: %d meses (%s a %s) e %d anos (%s a %s)"
              % (SAIDA, len(ms), ms[0], ms[-1], len(anos),
                 anos[0] if anos else "-", anos[-1] if anos else "-"), flush=True)


if __name__ == "__main__":
    main()
