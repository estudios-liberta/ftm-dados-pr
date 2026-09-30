#!/usr/bin/env python3
"""
Monta dados/fiscal.json — o resultado primário do setor público consolidado,
com as séries do SGS do Banco Central.

Uso:
    python3 scripts/fiscal.py

Só usa a biblioteca padrão; o download é o mesmo `sgs()` do atualizar.py (mesma
espera crescente, mesmas janelas de 10 anos). Roda na Action junto com o resto.

AS SÉRIES

  - **4649** — NFSP sem desvalorização cambial, fluxo mensal corrente, resultado
    primário, setor público consolidado, em R$ milhões. Começa em dez/2001.
  - **5793** — a mesma coisa em % do PIB, acumulada em 12 meses. Começa em
    nov/2002 (é a 4649 somada em 12 meses).
  - **4382** — PIB acumulado dos últimos 12 meses, valores correntes, R$ milhões.
    É o denominador que o BC usa nas razões de % do PIB.

O SINAL. O SGS publica isto como **necessidade de financiamento**: lá, número
positivo é *déficit*. Em dez/2022, por exemplo, a 5793 marca −1,25 — e 2022
fechou com superávit primário de 1,25% do PIB. Aqui tudo é multiplicado por −1,
do jeito que se lê no noticiário: **positivo é superávit, negativo é déficit**.
É o único ajuste feito nos números do BC.

O ACUMULADO NO ANO. Não existe pronto no SGS (o dado aberto do BC tem o fluxo
mensal e o acumulado em 12 meses, não o do ano), então sai daqui: soma dos
meses do ano até o mês, dividida pelo PIB dos últimos 12 meses.

Que esse denominador é o certo dá para conferir: refazendo o acumulado em 12
meses pela mesma receita — soma de 12 meses da 4649 dividida pela 4382 — o
resultado bate com a 5793 publicada em **129 meses, com diferença máxima de
0,005 p.p.**, que é o arredondamento da série do BC (ela sai com duas casas). A
conferência roda a cada atualização e aparece no log.

Em dezembro as duas contas coincidem, por construção: o acumulado do ano é o
acumulado de 12 meses.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from atualizar import sgs                                    # noqa: E402

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SAIDA = os.path.join(RAIZ, "dados", "fiscal.json")

INICIO = "2001-12"        # primeiro mês da 4649

# Cores do tema do Office, as mesmas dos outros gráficos do site.
AZUL, VERMELHO, VERDE, ROXO, CIANO, LARANJA = "#4F81BD", "#C0504D", "#9BBB59", "#8064A2", "#4BACC6", "#F79646"
AZUL_ESCURO, VINHO, OLIVA, AMARELO, BRANCO = "#1F497D", "#632523", "#77933C", "#FFFF00", "#FFFFFF"
CINZA = "#95A5A6"

# Anos anteriores no gráfico de comparação, do mais antigo para o mais recente.
# O ano corrente entra sempre em branco e mais grosso, por cima.
CORES_ANO = [CINZA, VINHO, ROXO, AZUL_ESCURO, OLIVA, LARANJA, VERMELHO, VERDE, CIANO, AZUL]

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


# --------------------------------------------------------------------------
# contas
# --------------------------------------------------------------------------

def num(mes):
    a, m = mes.split("-")
    return int(a) * 12 + int(m) - 1


def acumulado_12(mensal):
    """{mês: soma dos 12 meses até ele} — só onde os 12 meses existem."""
    ms = sorted(mensal)
    fora = {}
    for i in range(11, len(ms)):
        janela = ms[i - 11:i + 1]
        if num(janela[-1]) - num(janela[0]) != 11:
            continue                      # buraco na série: não inventa soma
        fora[ms[i]] = sum(mensal[m] for m in janela)
    return fora


def acumulado_ano(mensal):
    """{mês: soma dos meses daquele ano até ele}. Zera em janeiro."""
    fora, soma, ano = {}, 0.0, None
    for m in sorted(mensal):
        if m[:4] != ano:
            ano, soma = m[:4], 0.0
        soma += mensal[m]
        fora[m] = soma
    return fora


def sobre_pib(fluxo, pib12):
    """Fluxo em R$ milhões → % do PIB, com o PIB de 12 meses como denominador."""
    return {m: v / pib12[m] * 100 for m, v in fluxo.items() if m in pib12}


def confere_12_meses(calculado, oficial):
    """O acumulado em 12 meses refeito aqui contra a 5793 publicada."""
    difs = [abs(calculado[m] - oficial[m]) for m in calculado if m in oficial]
    if not difs:
        raise RuntimeError("nenhum mês em comum entre o cálculo e a série 5793")
    print("  confere com a 5793: %d meses, diferença média %.4f p.p., máxima %.4f p.p."
          % (len(difs), sum(difs) / len(difs), max(difs)))
    if max(difs) > 0.02:
        raise RuntimeError("o acumulado em 12 meses não bate com a 5793 (máx %.3f p.p.)" % max(difs))


# --------------------------------------------------------------------------
# montagem
# --------------------------------------------------------------------------

def ordem(chave):
    """No eixo de meses a chave é "2026-08" e a ordem alfabética serve; no de
    categorias é o número da categoria, e aí "10" vem antes de "2" se a ordem
    for de texto — a linha sai embaralhada."""
    return (0, int(chave), "") if chave.isdigit() else (1, 0, chave)


def serie(nome, cor, dados, casas=2, **extra):
    pares = [[m, round(v, casas)] for m, v in sorted(dados.items(), key=lambda kv: ordem(kv[0]))]
    return dict(nome=nome, cor=cor, dados=pares, **extra)


def variante(rot, series, unidade, **extra):
    return dict(rot=rot, series=series, unidade=unidade, **extra)


def por_ano(pct_ano, anos):
    """Uma série por ano, no eixo de meses (jan…dez), para comparar os anos."""
    atual = max(pct_ano)[:4]
    series = []
    for k, ano in enumerate(anos):
        dados = {str(int(m[5:7]) - 1): v for m, v in pct_ano.items() if m[:4] == ano}
        if not dados:
            continue
        destaque = dict(rotulo=True, largura=10) if ano == atual else {}
        series.append(serie(ano, BRANCO if ano == atual else CORES_ANO[k % len(CORES_ANO)],
                            dados, **destaque))
    return series


def main():
    print("Baixando as séries do SGS…")
    mensal_sgs = sgs(4649, INICIO)            # R$ milhões, sinal do SGS
    pib12 = sgs(4382, INICIO)                 # R$ milhões
    doze_sgs = sgs(5793, INICIO)              # % do PIB, sinal do SGS
    print("  4649: %d meses (%s → %s) | 4382: %d | 5793: %d"
          % (len(mensal_sgs), min(mensal_sgs), max(mensal_sgs), len(pib12), len(doze_sgs)))

    # aqui o sinal vira: positivo é superávit
    mensal = {m: -v for m, v in mensal_sgs.items()}
    doze = {m: -v for m, v in doze_sgs.items()}

    bi_mes = {m: v / 1000 for m, v in mensal.items()}
    bi_12 = {m: v / 1000 for m, v in acumulado_12(mensal).items()}
    bi_ano = {m: v / 1000 for m, v in acumulado_ano(mensal).items()}

    pct_12_calc = sobre_pib(acumulado_12(mensal), pib12)
    confere_12_meses(pct_12_calc, doze)
    pct_ano = sobre_pib(acumulado_ano(mensal), pib12)

    ref = max(mensal)
    anos = sorted({m[:4] for m in pct_ano})

    graficos = [
        dict(id="fiscal-primario-bi",
             titulo="Resultado primário do setor público consolidado",
             subtitulo="Em R$ bilhões correntes — positivo é superávit, negativo é déficit",
             variantes=[
                 variante("Acumulado em 12 meses", [serie("Resultado primário", BRANCO, bi_12, 1, rotulo=True)], "bi"),
                 variante("Acumulado no ano", [serie("No ano", BRANCO, bi_ano, 1, rotulo=True)], "bi"),
                 variante("No mês", [serie("No mês", AZUL, bi_mes, 1, tipo="barra")], "bi"),
             ],
             nota="Governo federal, estados, municípios e estatais, fora Petrobras e Eletrobras "
                  "(série 4649 do SGS). Em R$ correntes: R$ 1 bilhão de 2002 não é o mesmo de hoje "
                  "— para comparar ao longo do tempo, o gráfico seguinte, em % do PIB."),
        dict(id="fiscal-primario-pib",
             titulo="Resultado primário em % do PIB",
             subtitulo="Positivo é superávit, negativo é déficit",
             unidade="%",
             variantes=[
                 variante("Acumulado em 12 meses", [serie("% do PIB", BRANCO, doze, 2, rotulo=True)], "%"),
                 variante("Acumulado no ano", [serie("No ano", BRANCO, pct_ano, 2, rotulo=True)], "%"),
             ],
             nota="Acumulado em 12 meses é a série 5793 do SGS, com o sinal invertido. O acumulado "
                  "no ano é calculado aqui — soma dos meses do ano dividida pelo PIB dos últimos 12 "
                  "meses (série 4382), o mesmo denominador que o BC usa. Em dezembro as duas contas "
                  "coincidem."),
        dict(id="fiscal-primario-ano",
             titulo="Resultado primário acumulado no ano",
             subtitulo="Em % do PIB, mês a mês — cada linha é um ano",
             unidade="%",
             categorias=MESES,
             variantes=[
                 variante("Últimos 5 anos", por_ano(pct_ano, anos[-5:]), "%", categorias=MESES),
                 variante("Últimos 10 anos", por_ano(pct_ano, anos[-10:]), "%", categorias=MESES),
             ],
             nota="O ano corrente em branco, mais grosso. A linha de cada ano vai de janeiro até "
                  "dezembro; a do ano corrente para no último mês divulgado. Janeiro costuma ser o "
                  "mês mais forte da arrecadação, e dezembro o de maior despesa — por isso a "
                  "comparação só faz sentido mês contra o mesmo mês."),
    ]

    doc = dict(
        atualizado=datetime.date.today().isoformat(),
        referencia=ref,
        fonte="Banco Central (SGS) e FtM",
        categoria="Fiscal",
        secoes=[dict(titulo="Resultado primário", graficos=graficos)],
    )
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print("gravado %s (%.0f KB), referência %s" % (SAIDA, os.path.getsize(SAIDA) / 1024, ref))
    print("  em 12 meses: R$ %.1f bi (%.2f%% do PIB) em %s" % (bi_12[ref], doze[ref], ref))
    print("  no ano até %s: R$ %.1f bi (%.2f%% do PIB)" % (ref, bi_ano[ref], pct_ano[ref]))
    print("  comparação por ano: %s → %s" % (anos[0], anos[-1]))


if __name__ == "__main__":
    main()
