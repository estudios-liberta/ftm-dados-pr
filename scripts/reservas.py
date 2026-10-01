#!/usr/bin/env python3
"""
Monta dados/reservas.json — a categoria "Reservas internacionais" do site, a
partir da planilha `dados/reservas de ouro.xlsx`.

Uso:
    python3 scripts/reservas.py
    python3 scripts/reservas.py "dados/outra planilha.xlsx"

Só usa a biblioteca padrão: a leitura do .xlsx é a classe `Planilha` do
scripts/divida.py (zipfile + ElementTree). Não entra na Action — a planilha
chega à mão, como o Relatório da Dívida.

AS QUATRO ABAS

  - **Currency Comp** — composição das reservas alocadas por moeda, trimestral
    de 1999-Q1 em diante, em **US$ milhões**, mais o ouro a preço de mercado e
    o preço do ouro em US$ por onça troy. Dólar canadense e dólar australiano
    só aparecem em 2012-Q4 e o yuan em 2016-Q4: antes disso estavam dentro de
    "Outras moedas", e é por isso que aquela faixa encolhe de repente.
  - **Variação reservas de ouro acum** — variação acumulada desde 2000 das
    reservas de ouro de cada país, em toneladas (a base, 2000-Q1, é vazia).
  - **variação reservas de ouro anual** — a mesma coisa em variação de quatro
    trimestres (começa em 2001-Q1).
  - **% de ouro nas reservas** — participação do ouro nas reservas de cada
    país, **em fração** (0,833 = 83,3%).

O TOTAL. As abas de país trazem duas colunas de total: "Total above", que é a
soma das colunas de país, e "IMF World", o agregado mundial do próprio FMI. A
primeira quebra nos trimestres recentes — a maioria dos países ainda não
reportou e a soma passa a misturar quem reportou com quem não: ela marca
−6.027 t em 2026-Q2, quando o mundo comprou ouro. O total daqui é o do FMI, que
é consistente ponta a ponta (e que, por isso mesmo, não fecha com a soma das
colunas de país).

O eixo X é trimestral: a chave é "2000-Q1" e o `app.js` trata isso com
`trimestral: true`.
"""
import datetime
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from divida import Planilha                                  # noqa: E402

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SAIDA = os.path.join(RAIZ, "dados", "reservas.json")

ABA_MOEDAS = "Currency Comp"
ABA_ACUM = "Variação reservas de ouro acum"
ABA_ANUAL = "variação reservas de ouro anual"
ABA_PCT = "% de ouro nas reservas"

TOTAL = "IMF World6 (may not sum to country total)"

# Cores do tema do Office, as mesmas dos outros gráficos do site, mais seis
# tons a mais: o gráfico do G20 tem vinte linhas e as catorze de sempre não
# bastam.
AZUL, VERMELHO, VERDE, ROXO, CIANO, LARANJA = "#4F81BD", "#C0504D", "#9BBB59", "#8064A2", "#4BACC6", "#F79646"
AZUL_ESCURO, VINHO, OLIVA, AMARELO, BRANCO = "#3B6FA0", "#8C3B38", "#77933C", "#FFFF00", "#FFFFFF"
CINZA, AREIA, PETROLEO = "#95A5A6", "#D9B382", "#2E6E7E"
ROSA, LILAS, MENTA, DOURADO, MARROM, AZUL_CLARO = "#E07AB1", "#B39DDB", "#45C4A0", "#C9A227", "#A9746E", "#8CB4E2"

# Moedas, na ordem em que entram na pilha: o ouro é a última, então fica no
# topo. A cor olha para a vizinha na pilha — a sequência troca de família
# (verde, azul, vermelho, roxo, petróleo, rosa, laranja, ciano, cinza, amarelo)
# em vez de seguir o espectro, senão duas faixas coladas viram uma só.
# (coluna da planilha, rótulo no gráfico, cor) — a coluna do franco vem com
# "suíco" na planilha.
MOEDAS = [
    ("Dólar americano", "Dólar americano", VERDE),
    ("Euro", "Euro", AZUL),
    ("Iene japonês", "Iene japonês", VERMELHO),
    ("Libra esterlina", "Libra esterlina", ROXO),
    ("Dólar canadense", "Dólar canadense", PETROLEO),
    ("Dólar australiano", "Dólar australiano", ROSA),
    ("Yuan chinês", "Yuan chinês", LARANJA),
    ("Franco suíco", "Franco suíço", CIANO),
    ("Outras moedas", "Outras moedas", CINZA),
    ("Ouro", "Ouro", AMARELO),
]
PRECO_OURO = "Preço do Ouro"

# As economias do primeiro gráfico de variação, na ordem que ele pediu.
ECONOMIAS = [
    ("United States", "Estados Unidos", BRANCO),
    ("China, P.R.: Mainland", "China", VERMELHO),
    ("Russian Federation", "Rússia", AMARELO),
    ("Brazil", "Brasil", VERDE),
    ("Japan", "Japão", LARANJA),
    ("Euro Area", "Zona do Euro", AZUL),
    ("United Kingdom", "Reino Unido", CIANO),
]

# O G20 do gráfico de participação, da maior fatia de ouro para a menor (é a
# ordem em que a legenda fica legível ao lado do gráfico). A União Europeia tem
# cadeira no G20 e aqui entra como Zona do Euro, que é o que a planilha traz —
# e que já contém Alemanha, França e Itália.
#
# Vinte linhas não cabem num espectro: o que decide a cor é em que altura a
# linha anda. Os oito primeiros passam de 30% e vivem embolados no alto do
# gráfico — levam as cores mais separadas que existem (branco, vermelho, azul,
# amarelo, rosa, laranja, verde, roxo). Os doze de baixo se cruzam num feixe
# abaixo de 25%, onde o que separa é a posição, não o tom; ali entram as
# famílias repetidas, e para esses é que serve o botão de tirar da tela.
G20 = [
    ("United States", "Estados Unidos", BRANCO),
    ("Italy", "Itália", VERMELHO),
    ("France", "França", AZUL),
    ("Germany", "Alemanha", AMARELO),
    ("Euro Area", "Zona do Euro", ROSA),
    ("Türkiye, Rep of5", "Türkiye", LARANJA),
    ("Russian Federation", "Rússia", VERDE),
    ("Saudi Arabia", "Arábia Saudita", ROXO),
    ("South Africa", "África do Sul", CIANO),
    ("Argentina", "Argentina", MENTA),
    ("United Kingdom", "Reino Unido", PETROLEO),
    ("India", "Índia", LILAS),
    ("Australia", "Austrália", AREIA),
    ("China, P.R.: Mainland", "China", VINHO),
    ("Japan", "Japão", AZUL_CLARO),
    ("Indonesia", "Indonésia", MARROM),
    ("Brazil", "Brasil", DOURADO),
    ("Mexico", "México", OLIVA),
    ("Korea, Rep. of", "Coreia do Sul", AZUL_ESCURO),
    ("Canada", "Canadá", CINZA),
]

TRIMESTRES = ["1º", "2º", "3º", "4º"]


# --------------------------------------------------------------------------
# leitura
# --------------------------------------------------------------------------

def trimestre(txt):
    """"1999-Q1" e "Q1 2000", os dois jeitos que a planilha escreve, viram a
    chave do eixo: "1999-Q1"."""
    m = re.match(r"\s*(\d{4})\D*Q([1-4])\s*$", str(txt)) or re.match(r"\s*Q([1-4])\D+(\d{4})\s*$", str(txt))
    if not m:
        return None
    a, q = m.groups() if len(m.group(1)) == 4 else (m.group(2), m.group(1))
    return "%s-Q%s" % (a, q)


def painel(pl, aba, linha_nomes, col_nomes, col_data):
    """Aba em pé (um trimestre por linha, um país por coluna) → {nome: {trim: v}}.

    Célula de texto (a planilha guarda "#VALUE!" onde o país não reportou) é
    buraco, não zero."""
    grade = pl.grade(aba)
    nomes = {grade[linha_nomes][c]: c for c in sorted(grade[linha_nomes]) if c >= col_nomes}
    fora = {nome: {} for nome in nomes}
    for r in sorted(grade):
        chave = trimestre(grade[r].get(col_data))
        if not chave:
            continue
        for nome, c in nomes.items():
            v = grade[r].get(c)
            if isinstance(v, float):
                fora[nome][chave] = v
    return fora


def exige(painel_, nomes, aba):
    faltam = [n for n in nomes if not painel_.get(n)]
    if faltam:
        raise RuntimeError("a aba %r não tem %s" % (aba, ", ".join(faltam)))


# --------------------------------------------------------------------------
# montagem
# --------------------------------------------------------------------------

def serie(nome, cor, dados, casas=2, **extra):
    pares = [[t, round(v, casas)] for t, v in sorted(dados.items())]
    return dict(nome=nome, cor=cor, dados=pares, **extra)


def variante(rot, series, **extra):
    return dict(rot=rot, series=series, **extra)


def grafico_moedas(moedas, preco):
    """Colunas empilhadas com o estoque de cada moeda (o ouro a preço de
    mercado) e o preço do ouro na escala da direita."""
    colunas = [serie(rot, cor, {t: v / 1e6 for t, v in moedas[nome].items()}, 3, tipo="barra")
               for nome, rot, cor in MOEDAS]
    linha = serie("Preço do ouro (eixo da direita)", BRANCO, preco, 2, dir=True, largura=5)
    return dict(
        id="reservas-moedas",
        titulo="Reservas internacionais por moeda",
        subtitulo="Estoque em US$ trilhões, no fim de cada trimestre; o ouro a preço de mercado",
        unidade="usd-tri", unidade2="usd-oz",
        trimestral=True,
        selecao=True,
        eixo=dict(alvo=10),
        series=colunas + [linha],
        nota="São as reservas **alocadas** — a parte que os bancos centrais informam ao FMI moeda "
             "por moeda — mais o ouro, avaliado ao preço do fim do trimestre. A altura de cada cor "
             "é o estoque daquela moeda e a linha branca é o preço do ouro, que corre na escala da "
             "direita. A série começa em 2000, o primeiro trimestre em que a planilha traz o ouro. "
             "Dólar canadense e dólar australiano só ganham coluna própria em 2012 e o yuan em "
             "2016: antes disso estavam dentro de \"outras moedas\".")


def grafico_participacao(moedas):
    """A mesma composição em participação: cada moeda sobre a soma de todas."""
    totais = {}
    for nome, _, _ in MOEDAS:
        for t, v in moedas[nome].items():
            totais[t] = totais.get(t, 0.0) + v
    series = [serie(rot, cor, {t: v / totais[t] * 100 for t, v in moedas[nome].items()}, 2, rotulo=True)
              for nome, rot, cor in MOEDAS]
    return dict(
        id="reservas-participacao",
        titulo="Participação de cada moeda nas reservas",
        subtitulo="Em % do total das reservas alocadas mais o ouro",
        unidade="%",
        trimestral=True,
        selecao=True,
        series=series,
        nota="É o gráfico anterior dividido pelo total de cada trimestre — o denominador é a soma "
             "das dez faixas, ouro incluído. Em 2012 e 2016 o dólar canadense, o australiano e o "
             "yuan saem de \"outras moedas\" e passam a ter faixa própria: o degrau naquelas três "
             "linhas é mudança de classificação, não de composição.")


def grafico_variacao(acum, anual, qual):
    """Variação das reservas de ouro em toneladas, nas duas janelas (acumulada
    desde 2000 e em quatro trimestres), com dois recortes cada: as principais
    economias e o total do mundo."""
    base, titulo, comeco = (acum, "Variação acumulada das reservas de ouro", "desde 2000") \
        if qual == "acum" else (anual, "Variação anual das reservas de ouro", "em quatro trimestres")
    paises = [serie(pt, cor, base[en], 1, rotulo=True) for en, pt, cor in ECONOMIAS]
    mundo = [serie("Total mundial", AMARELO, base[TOTAL], 1, rotulo=True, largura=9)]
    return dict(
        id="reservas-ouro-" + qual,
        titulo=titulo,
        subtitulo="Em toneladas, " + comeco,
        unidade="t",
        trimestral=True,
        variantes=[
            variante("Países selecionados", paises, selecao=True),
            variante("Total mundial", mundo),
        ],
        nota="Variação da tonelagem de metal: o preço do ouro não entra nesta conta. O total "
             "mundial é o agregado do próprio FMI — a outra coluna de total da planilha soma as "
             "colunas de país e quebra nos trimestres recentes, em que a maioria ainda não "
             "reportou, e por isso não é usada aqui. Ela também não fecha com a soma dos países, "
             "que varia com quem reportou em cada trimestre.")


def grafico_pct(pct):
    """Ouro como fatia das reservas, no G20."""
    # linha mais fina que o padrão: com vinte delas no mesmo gráfico, o traço
    # de sempre engrossa o feixe de baixo até virar uma mancha só
    series = [serie(pt, cor, {t: v * 100 for t, v in pct[en].items()}, 2, largura=5)
              for en, pt, cor in G20]
    return dict(
        id="reservas-ouro-pct",
        titulo="Ouro nas reservas internacionais",
        subtitulo="Em % das reservas de cada país, no fim de cada trimestre",
        unidade="%",
        trimestral=True,
        selecao=True,
        series=series,
        eixo=dict(alvo=10),
        nota="A conta é o ouro a preço de mercado sobre o total das reservas do país: a fatia "
             "sobe tanto quando ele compra metal quanto quando o ouro se valoriza. São os vinte "
             "membros do G20, do que tem mais ouro para o que tem menos. A União Europeia, que tem "
             "cadeira no G20, entra como Zona do Euro, o agregado que a planilha traz — ele já "
             "contém Alemanha, França e Itália, que aparecem à parte por serem membros também.")


def main():
    caminho = sys.argv[1] if len(sys.argv) > 1 else None
    if not caminho:
        achados = glob.glob(os.path.join(RAIZ, "dados", "*reserva*.xlsx"))
        if not achados:
            raise SystemExit("nenhuma planilha de reservas em dados/")
        caminho = max(achados, key=os.path.getmtime)
    print("Lendo %s" % os.path.basename(caminho))
    pl = Planilha(caminho)

    moedas = painel(pl, ABA_MOEDAS, 1, 2, 1)
    exige(moedas, [n for n, _, _ in MOEDAS] + [PRECO_OURO], ABA_MOEDAS)
    acum = painel(pl, ABA_ACUM, 2, 2, 1)
    anual = painel(pl, ABA_ANUAL, 2, 2, 1)
    pct = painel(pl, ABA_PCT, 1, 3, 2)
    for p, aba in ((acum, ABA_ACUM), (anual, ABA_ANUAL)):
        exige(p, [en for en, _, _ in ECONOMIAS] + [TOTAL], aba)
    exige(pct, [en for en, _, _ in G20], ABA_PCT)

    # A planilha abre em 1999-Q1, mas a coluna do ouro só começa em 2000-Q1 —
    # e sem o ouro o total é outro (o dólar daria 71% em 1999 contra 61% em
    # 2000, só porque o denominador não tem a faixa amarela). Os dois gráficos
    # de moeda começam onde o ouro começa.
    inicio = min(moedas["Ouro"])
    moedas = {nome: {t: v for t, v in d.items() if t >= inicio} for nome, d in moedas.items()}
    preco = moedas[PRECO_OURO]
    ref = max(moedas["Dólar americano"])
    print("  moedas: %d trimestres, %s a %s; ouro a US$ %.2f/oz em %s"
          % (len(moedas["Dólar americano"]), inicio, ref, preco[ref], ref))
    soma = sum(moedas[n][ref] for n, _, _ in MOEDAS) / 1e6
    print("  total em %s: US$ %.3f tri (dólar %.1f%%, ouro %.1f%%)"
          % (ref, soma, moedas["Dólar americano"][ref] / 1e4 / soma, moedas["Ouro"][ref] / 1e4 / soma))
    print("  ouro: total mundial %+.0f t desde 2000 e %+.0f t no último ano (%s)"
          % (acum[TOTAL][max(acum[TOTAL])], anual[TOTAL][max(anual[TOTAL])], max(acum[TOTAL])))

    secoes = [
        dict(titulo="Composição por moeda",
             graficos=[grafico_moedas(moedas, preco), grafico_participacao(moedas)]),
        dict(titulo="Reservas de ouro",
             graficos=[grafico_variacao(acum, anual, "acum"), grafico_variacao(acum, anual, "anual"),
                       grafico_pct(pct)]),
    ]
    doc = dict(
        atualizado=datetime.date.today().isoformat(),
        referencia="%s-%02d" % (ref[:4], int(ref[-1]) * 3),
        fonte="FMI (IFS e COFER), World Gold Council, ICE Benchmark Administration e bancos centrais",
        categoria="Reservas internacionais",
        secoes=secoes,
    )
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print("gravado %s (%.0f KB), referência %s"
          % (SAIDA, os.path.getsize(SAIDA) / 1024, doc["referencia"]))
    for sec in secoes:
        print("  %-24s %s" % (sec["titulo"] + ":", ", ".join(g["id"] for g in sec["graficos"])))


if __name__ == "__main__":
    main()
