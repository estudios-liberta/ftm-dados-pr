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

INICIO = "2001-12"        # primeiro mês das séries de fluxo mensal

# As séries do SGS. Primário e nominal têm a mesma estrutura: fluxo mensal em
# R$ milhões e acumulado em 12 meses em % do PIB.
RESULTADOS = [
    dict(id="primario", nome="primário", mensal=4649, pct12=5793,
         titulo="Resultado primário do setor público consolidado",
         curto="Resultado primário"),
    dict(id="nominal", nome="nominal", mensal=4583, pct12=5727,
         titulo="Resultado nominal do setor público consolidado",
         curto="Resultado nominal"),
]
PIB12 = 4382              # PIB acumulado em 12 meses, o denominador das razões

# As esferas do setor público consolidado, no fluxo mensal do resultado
# primário. Somadas, dão a 4649 — é o que o script confere a cada rodada.
# (4639, 4642 e 4645 são subtotais e ficam de fora para não contar duas vezes.)
ESFERAS = [
    (4640, "Governo Federal"),
    (4641, "Banco Central"),
    (4643, "Governos estaduais"),
    (4644, "Governos municipais"),
    (4646, "Estatais federais"),
    (4647, "Estatais estaduais"),
    (4648, "Estatais municipais"),
]

# Cores do tema do Office, as mesmas dos outros gráficos do site.
AZUL, VERMELHO, VERDE, ROXO, CIANO, LARANJA = "#4F81BD", "#C0504D", "#9BBB59", "#8064A2", "#4BACC6", "#F79646"
AZUL_ESCURO, VINHO, OLIVA, AMARELO, BRANCO = "#1F497D", "#632523", "#77933C", "#FFFF00", "#FFFFFF"
CINZA = "#95A5A6"

# Anos anteriores no gráfico de comparação, do mais antigo para o mais recente.
# O ano corrente entra sempre em branco e mais grosso, por cima.
CORES_ANO = [VINHO, ROXO, AZUL_ESCURO, OLIVA, LARANJA, VERMELHO, VERDE, CIANO, AZUL]

COR_ESFERA = {
    "Governo Federal": AZUL, "Governo Federal sem INSS": AZUL, "INSS": ROXO,
    "Banco Central": CIANO,
    "Governos estaduais": VERDE, "Governos municipais": AMARELO,
    "Estatais federais": LARANJA, "Estatais estaduais": VERMELHO,
    "Estatais municipais": CINZA,
}

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


def confere_12_meses(nome, calculado, oficial):
    """O acumulado em 12 meses refeito aqui contra a série publicada pelo BC.

    É o que garante o denominador do acumulado no ano: se a mesma receita
    reproduz a razão que o BC publica, ela serve para a do ano, que ele não
    publica."""
    difs = [abs(calculado[m] - oficial[m]) for m in calculado if m in oficial]
    if not difs:
        raise RuntimeError("nenhum mês em comum entre o cálculo e a série publicada (%s)" % nome)
    print("  %s: acumulado em 12 meses confere em %d meses, diferença média %.4f p.p., máxima %.4f p.p."
          % (nome, len(difs), sum(difs) / len(difs), max(difs)))
    if max(difs) > 0.02:
        raise RuntimeError("o acumulado em 12 meses do resultado %s não bate com a série do BC "
                           "(máx %.3f p.p.)" % (nome, max(difs)))


def confere_esferas(esferas, consolidado):
    """As sete esferas têm de somar o consolidado — em R$ milhões, no sinal do
    SGS mesmo (a conferência independe do sinal)."""
    difs = []
    for m, total in consolidado.items():
        if all(m in esferas[c] for c, _ in ESFERAS):
            difs.append(abs(sum(esferas[c][m] for c, _ in ESFERAS) - total))
    if not difs:
        raise RuntimeError("nenhum mês em comum entre as esferas e o consolidado")
    print("  esferas: somam o consolidado em %d meses, diferença máxima R$ %.0f mil"
          % (len(difs), max(difs) * 1000))
    if max(difs) > 1.0:          # R$ 1 milhão num total da ordem de R$ 100 bilhões
        raise RuntimeError("as esferas não somam o consolidado (máx R$ %.2f milhões)" % max(difs))


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


def por_ano(pct_ano, anos, cinza=False):
    """Uma série por ano, no eixo de meses (jan…dez), para comparar os anos.

    Com `cinza`, os anos anteriores viram um feixe de fundo — linha fina,
    cinza e translúcida, fora da legenda e da caixa do mouse. É o que deixa
    "todos os anos" legível: o que se lê é onde o ano corrente cai dentro do
    feixe, não o valor de 2007.
    """
    atual = max(pct_ano)[:4]
    series = []
    for k, ano in enumerate(anos):
        dados = {str(int(m[5:7]) - 1): v for m, v in pct_ano.items() if m[:4] == ano}
        # ano passado só entra inteiro (2001 tem dezembro e mais nada, porque é
        # onde a série começa); o ano corrente entra com o que já tem
        if not dados or (ano != atual and len(dados) < 12):
            continue
        if ano == atual:
            series.append(serie(ano, BRANCO, dados, rotulo=True, largura=10))
        elif cinza:
            series.append(serie(ano, CINZA, dados, largura=3, opacidade=0.5, legenda=False))
        else:
            series.append(serie(ano, CORES_ANO[k % len(CORES_ANO)], dados))
    return series


def variantes_por_ano(pct_ano, anos):
    v = []
    for n in (5, 10):
        if len(anos) > n:
            v.append(variante("Últimos %d anos" % n, por_ano(pct_ano, anos[-n:]), "%", categorias=MESES))
    v.append(variante("Todos os anos", por_ano(pct_ano, anos, cinza=True), "%", categorias=MESES))
    return v


def tres_graficos(r, mensal, doze_pct, pct_ano, anos):
    """Os três formatos de um resultado (primário ou nominal): R$ bilhões,
    % do PIB e o acumulado no ano comparando os anos."""
    bi_12 = {m: v / 1000 for m, v in acumulado_12(mensal).items()}
    bi_mes = {m: v / 1000 for m, v in mensal.items()}
    quem = "O resultado nominal é o primário menos os juros nominais da dívida — " \
           "é o que de fato muda o estoque da dívida. " if r["id"] == "nominal" else ""
    return [
        dict(id="fiscal-%s-bi" % r["id"],
             titulo=r["titulo"],
             subtitulo="Em R$ bilhões correntes — positivo é superávit, negativo é déficit",
             variantes=[
                 variante("Acumulado em 12 meses", [serie(r["curto"], BRANCO, bi_12, 1, rotulo=True)], "bi"),
                 variante("No mês", [serie("No mês", AZUL, bi_mes, 1, tipo="barra")], "bi"),
             ],
             nota=quem + "Governo federal, Banco Central, estados, municípios e estatais, fora "
                  "Petrobras e Eletrobras (série %d do SGS). Em R$ correntes: R$ 1 bilhão de 2002 "
                  "não é o mesmo de hoje — para comparar ao longo do tempo, o gráfico seguinte, em "
                  "%% do PIB." % r["mensal"]),
        dict(id="fiscal-%s-pib" % r["id"],
             titulo="Resultado %s em %% do PIB" % r["nome"],
             subtitulo="Acumulado em 12 meses — positivo é superávit, negativo é déficit",
             unidade="%",
             series=[serie("% do PIB", BRANCO, doze_pct, 2, rotulo=True)],
             nota="Série %d do SGS, com o sinal invertido." % r["pct12"]),
        dict(id="fiscal-%s-ano" % r["id"],
             titulo="Resultado %s acumulado no ano" % r["nome"],
             subtitulo="Em % do PIB, mês a mês — cada linha é um ano",
             unidade="%",
             categorias=MESES,
             variantes=variantes_por_ano(pct_ano, anos),
             nota="O ano corrente em branco, mais grosso. A linha de cada ano vai de janeiro até "
                  "dezembro; a do ano corrente para no último mês divulgado. Como o SGS não publica "
                  "o acumulado no ano, ele é calculado aqui: soma dos meses do ano dividida pelo PIB "
                  "dos últimos 12 meses (série %d), o mesmo denominador que o BC usa nas razões "
                  "dele. Em dezembro essa conta coincide com o acumulado em 12 meses." % PIB12),
    ]


def grafico_esferas(esferas, fed_sem_inss, inss):
    """Quem faz o resultado primário: as sete esferas que somam o consolidado,
    e um segundo recorte com o INSS separado do resto do Governo Federal."""
    def colunas(itens):
        # barra=1 no gráfico: sem fresta entre um mês e o seguinte, a pilha
        # ganha cara de área empilhada
        return [serie(nome, COR_ESFERA.get(nome, CINZA),
                      {m: v / 1000 for m, v in acumulado_12(d).items()}, 1, tipo="barra")
                for nome, d in itens]

    sete = [(nome, esferas[cod]) for cod, nome in ESFERAS]
    com_inss = ([("Governo Federal sem INSS", fed_sem_inss), ("INSS", inss)] +
                [(nome, esferas[cod]) for cod, nome in ESFERAS if nome != "Governo Federal"])
    return dict(
        id="fiscal-primario-esferas",
        titulo="Resultado primário por esfera",
        subtitulo="Em R$ bilhões correntes, acumulado em 12 meses — positivo é superávit",
        variantes=[
            variante("Por esfera", colunas(sete), "bi", barra=1),
            variante("Com o INSS à parte", colunas(com_inss), "bi", barra=1),
        ],
        nota="Colunas empilhadas: quem está em superávit sobe a partir do zero, quem está em "
             "déficit desce — a altura de cada cor é o quanto aquela esfera põe ou tira, e o "
             "resultado consolidado é a diferença entre as duas pilhas. As sete esferas somam o "
             "consolidado: o script confere isso a cada rodada e a diferença máxima em 297 meses "
             "é de R$ 20 mil, puro arredondamento. O INSS entra dentro do Governo Federal (séries "
             "7853 e 7854, que somadas dão a 4640); o segundo recorte separa os dois. Petrobras e "
             "Eletrobras estão fora das estatais desde 2009.")


def main():
    print("Baixando as séries do SGS…")
    pib12 = sgs(PIB12, INICIO)
    esferas = {cod: sgs(cod, INICIO) for cod, _ in ESFERAS}
    fed_sem_inss, inss = sgs(7853, INICIO), sgs(7854, INICIO)

    secoes, ref = [], ""
    for r in RESULTADOS:
        mensal_sgs = sgs(r["mensal"], INICIO)
        doze_sgs = sgs(r["pct12"], INICIO)
        # aqui o sinal vira: positivo é superávit
        mensal = {m: -v for m, v in mensal_sgs.items()}
        doze = {m: -v for m, v in doze_sgs.items()}

        pct_12_calc = sobre_pib(acumulado_12(mensal), pib12)
        confere_12_meses(r["nome"], pct_12_calc, doze)
        pct_ano = sobre_pib(acumulado_ano(mensal), pib12)
        anos = sorted({m[:4] for m in pct_ano})

        graficos = tres_graficos(r, mensal, doze, pct_ano, anos)
        if r["id"] == "primario":
            graficos.append(grafico_esferas(
                {c: {m: -v for m, v in d.items()} for c, d in esferas.items()},
                {m: -v for m, v in fed_sem_inss.items()},
                {m: -v for m, v in inss.items()}))
            confere_esferas(esferas, mensal_sgs)
        secoes.append(dict(titulo="Resultado " + r["nome"], graficos=graficos))
        ref = max(ref, max(mensal))
        print("  %s: 12 meses R$ %.1f bi (%.2f%% do PIB) em %s"
              % (r["nome"], sum(mensal[m] for m in sorted(mensal)[-12:]) / 1000, doze[max(doze)], max(mensal)))

    doc = dict(
        atualizado=datetime.date.today().isoformat(),
        referencia=ref,
        fonte="Banco Central (SGS) e FtM",
        categoria="Fiscal",
        secoes=secoes,
    )
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print("gravado %s (%.0f KB), referência %s" % (SAIDA, os.path.getsize(SAIDA) / 1024, ref))
    for sec in secoes:
        print("  %-20s %s" % (sec["titulo"] + ":", ", ".join(g["id"] for g in sec["graficos"])))


if __name__ == "__main__":
    main()
