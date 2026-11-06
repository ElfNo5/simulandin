"""
Simulado ENEM 2026 — 1º dia (Linguagens, Redação e Ciências Humanas)
Rode com:  streamlit run app.py
"""
from __future__ import annotations

import json
import math
import time
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st

BASE = Path(__file__).parent
DATA = BASE / "data"
SAVE_DIR = BASE / "progresso"
SAVE_DIR.mkdir(exist_ok=True)


def slug(nome: str) -> str:
    import re, unicodedata
    n = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")[:40] or "anon"


def arquivo_usuario() -> Path | None:
    u = st.session_state.get("usuario")
    return SAVE_DIR / f"{u}.json" if u else None

DURACAO_PROVA = 5 * 3600 + 30 * 60      # 5h30 (edital 2026)
PERMANENCIA_MINIMA = 2 * 3600            # 2h
SAIDA_COM_CADERNO = DURACAO_PROVA - 30 * 60  # só nos últimos 30 min
LETRAS = ["A", "B", "C", "D", "E"]
CORES_CADERNO = ["Azul", "Amarelo", "Branco", "Rosa"]


# --------------------------------------------------------------------------- #
# Dados
# --------------------------------------------------------------------------- #
@st.cache_data
def carregar_questoes() -> dict:
    ling = json.loads((DATA / "linguagens_a.json").read_text("utf-8")) + \
        json.loads((DATA / "linguagens_b.json").read_text("utf-8"))
    hum = json.loads((DATA / "humanas_a.json").read_text("utf-8")) + \
        json.loads((DATA / "humanas_b.json").read_text("utf-8"))
    ingles = [q for q in ling if q["disciplina"] == "Inglês"]
    espanhol = [q for q in ling if q["disciplina"] == "Espanhol"]
    comuns = [q for q in ling if q["disciplina"] not in ("Inglês", "Espanhol")]
    return {"ingles": ingles, "espanhol": espanhol, "ling_comum": comuns, "humanas": hum}


@st.cache_data
def carregar_redacao() -> dict:
    return json.loads((DATA / "redacao.json").read_text("utf-8"))


def montar_caderno(lingua: str) -> list[dict]:
    d = carregar_questoes()
    le = d["ingles"] if lingua == "Inglês" else d["espanhol"]
    return sorted(le, key=lambda q: q["numero"]) + \
        sorted(d["ling_comum"], key=lambda q: q["numero"]) + \
        sorted(d["humanas"], key=lambda q: q["numero"])


# --------------------------------------------------------------------------- #
# Estado / persistência
# --------------------------------------------------------------------------- #
CAMPOS_SALVOS = ["fase", "inicio", "fim", "lingua", "cor", "respostas", "marcadas",
                 "redacao", "atual", "autoavaliacao"]


def init_state():
    defaults = dict(fase="inicio", inicio=None, fim=None, lingua="Inglês", cor="Azul",
                    respostas={}, marcadas=[], redacao="", atual=1, autoavaliacao={})
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)
    if not st.session_state.get("_carregado"):
        # cada participante tem sessão própria, identificada por ?u=<nome> na URL
        u = st.query_params.get("u")
        if u:
            carregar_usuario(u)
    st.session_state["_carregado"] = True


def carregar_usuario(u: str) -> bool:
    """Carrega a prova salva de <u> e retoma o cronômetro de onde parou."""
    st.session_state["usuario"] = slug(u)
    arq = arquivo_usuario()
    if not arq or not arq.exists():
        return False
    try:
        dados = json.loads(arq.read_text("utf-8"))
    except Exception:
        return False
    for k in CAMPOS_SALVOS:
        if k in dados:
            st.session_state[k] = dados[k]
    if st.session_state.fase == "prova":
        # retoma o tempo de onde parou (pausa), em vez do relógio de parede
        st.session_state.inicio = time.time() - dados.get("decorrido", 0)
    st.query_params["u"] = st.session_state["usuario"]
    return True


def salvar():
    arq = arquivo_usuario()
    if not arq:
        return
    dados = {k: st.session_state.get(k) for k in CAMPOS_SALVOS}
    dados["decorrido"] = tempo_decorrido()
    arq.write_text(json.dumps(dados, ensure_ascii=False, indent=1), "utf-8")


def tempo_restante() -> int:
    if st.session_state.inicio is None:
        return DURACAO_PROVA
    return max(0, int(st.session_state.inicio + DURACAO_PROVA - time.time()))


def tempo_decorrido() -> int:
    if st.session_state.inicio is None:
        return 0
    return int(time.time() - st.session_state.inicio)


def md(texto: str) -> str:
    """Converte quebras de linha simples em quebras duras (versos/parágrafos)."""
    return "\n".join(l.rstrip() + ("  " if l.strip() else "") for l in texto.split("\n"))


def fmt(seg: int) -> str:
    h, r = divmod(seg, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def encerrar(motivo: str = "manual"):
    st.session_state.fase = "encerrada"
    st.session_state.fim = time.time()
    st.session_state.motivo_fim = motivo
    salvar()


# --------------------------------------------------------------------------- #
# Estimativa de nota (ESTIMATIVA GROSSEIRA — a nota real é TRI)
# --------------------------------------------------------------------------- #
CURVA = {
    "LC": [(0, 300), (10, 400), (20, 500), (30, 600), (38, 700), (43, 780), (45, 830)],
    "CH": [(0, 310), (10, 420), (20, 520), (30, 630), (38, 720), (44, 820), (45, 850)],
}


def estimar_nota(area: str, acertos: int) -> int:
    pts = CURVA[area]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= acertos <= x1:
            return int(y0 + (y1 - y0) * (acertos - x0) / (x1 - x0))
    return pts[-1][1]


# --------------------------------------------------------------------------- #
# Redação — métricas
# --------------------------------------------------------------------------- #
CHARS_POR_LINHA = 62   # média aproximada da folha de redação manuscrita


def metricas_redacao(txt: str) -> tuple[int, int]:
    palavras = len(txt.split())
    linhas = 0
    for par in txt.split("\n"):
        par = par.strip()
        linhas += max(1, math.ceil(len(par) / CHARS_POR_LINHA)) if par else 0
    return palavras, linhas


# --------------------------------------------------------------------------- #
# UI — componentes
# --------------------------------------------------------------------------- #
@st.fragment(run_every="1s")
def painel_tempo():
    rest = tempo_restante()
    dec = tempo_decorrido()
    if st.session_state.fase == "prova" and rest <= 0:
        encerrar("tempo")
        st.rerun()
    cor = "red" if rest < 30 * 60 else ("orange" if rest < 60 * 60 else "green")
    st.markdown(f"### :{cor}[⏱ {fmt(rest)}]")
    st.caption(f"Decorrido: {fmt(dec)} · Término às "
               f"{(datetime.fromtimestamp(st.session_state.inicio) + timedelta(seconds=DURACAO_PROVA)).strftime('%H:%M')}")
    if dec < PERMANENCIA_MINIMA:
        st.caption(f"🚪 Pode sair da sala a partir de {fmt(PERMANENCIA_MINIMA - dec)}")
    elif dec < SAIDA_COM_CADERNO:
        st.caption(f"📘 Leva o caderno em {fmt(SAIDA_COM_CADERNO - dec)}")
    else:
        st.caption("📘 Já pode sair levando o caderno")


def cartao_resposta(caderno: list[dict]):
    st.markdown("**Cartão-resposta**")
    resp = st.session_state.respostas
    marc = set(st.session_state.marcadas)
    cols = st.columns(5)
    for i, q in enumerate(caderno):
        n = q["numero"]
        idx = i + 1  # posição no caderno (Q1–Q90)
        r = resp.get(str(idx))
        label = f"{idx:02d}{r or '·'}"
        if idx in marc:
            label = "⚑" + label
        tipo = "primary" if idx == st.session_state.atual else "secondary"
        if cols[i % 5].button(label, key=f"cr{idx}", type=tipo, width="stretch"):
            st.session_state.atual = idx
            st.session_state.secao = "q1" if idx <= 45 else "q2"
            st.rerun()
    feitas = len(resp)
    st.progress(feitas / 90, text=f"{feitas}/90 respondidas · {len(marc)} marcadas p/ revisão")


def mostrar_questao(caderno: list[dict], idx: int):
    q = caderno[idx - 1]
    area = "LINGUAGENS, CÓDIGOS E SUAS TECNOLOGIAS" if q["area"] == "LC" else "CIÊNCIAS HUMANAS E SUAS TECNOLOGIAS"
    faixa = "Questões de 01 a 45" if q["area"] == "LC" else "Questões de 46 a 90"
    st.caption(f"{area} — {faixa}")
    if idx <= 5:
        st.caption(f"Questões de 01 a 05 (opção {st.session_state.lingua})")
    st.markdown(f"## QUESTÃO {idx:02d}")
    st.markdown(md(q["texto"]))
    st.caption(q["fonte"])
    st.markdown(f"**{q['comando']}**")

    key = str(idx)
    atual = st.session_state.respostas.get(key)
    opcoes = [f"{L}  {q['alternativas'][L]}" for L in LETRAS]
    sel = st.radio("Alternativas", opcoes, index=LETRAS.index(atual) if atual else None,
                   key=f"radio{idx}_{st.session_state.get('_rev', 0)}", label_visibility="collapsed")
    if sel:
        letra = sel[0]
        if st.session_state.respostas.get(key) != letra:
            st.session_state.respostas[key] = letra
            salvar()

    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
    if c1.button("◀ Anterior", disabled=idx == 1, width="stretch"):
        st.session_state.atual = idx - 1
        st.session_state.secao = "q1" if idx - 1 <= 45 else "q2"
        st.rerun()
    if c2.button("Próxima ▶", disabled=idx == 90, width="stretch"):
        st.session_state.atual = idx + 1
        st.session_state.secao = "q1" if idx + 1 <= 45 else "q2"
        st.rerun()
    marcada = idx in st.session_state.marcadas
    if c3.button("⚑ Desmarcar" if marcada else "⚑ Revisar", width="stretch"):
        if marcada:
            st.session_state.marcadas.remove(idx)
        else:
            st.session_state.marcadas.append(idx)
        salvar()
        st.rerun()
    if atual and c4.button("Apagar resposta", width="stretch"):
        st.session_state.respostas.pop(key, None)
        st.session_state["_rev"] = st.session_state.get("_rev", 0) + 1
        salvar()
        st.rerun()


def tela_redacao(resultado: bool = False):
    r = carregar_redacao()
    st.markdown("## PROPOSTA DE REDAÇÃO")
    st.markdown(r["instrucoes"])
    with st.expander("Instruções formais", expanded=False):
        for i in r["instrucoes_formais"]:
            st.markdown(f"- {i}")
    for t in r["textos_motivadores"]:
        st.markdown(f"**{t['titulo']}**")
        st.markdown(md(t["corpo"]))
        st.caption(t["fonte"])
        st.divider()
    if resultado:
        st.markdown("### Sua redação")
        st.text(st.session_state.redacao or "(em branco)")
        return
    st.markdown("### Folha de redação")
    st.caption("Na prova real a redação é manuscrita. Para treinar o tempo e o tamanho, escreva aqui; "
               "a contagem de linhas é uma estimativa (~62 caracteres por linha).")
    txt = st.text_area("Redação", value=st.session_state.redacao, height=520,
                       label_visibility="collapsed", key="ta_redacao")
    if txt != st.session_state.redacao:
        st.session_state.redacao = txt
        salvar()
    pal, lin = metricas_redacao(txt)
    cor = "red" if (lin > 30 or lin <= 7) else "green"
    st.markdown(f"**Palavras:** {pal} · **Linhas estimadas:** :{cor}[{lin}/30]")
    if lin > 30:
        st.error("Ultrapassou 30 linhas — na prova, o excedente não é lido.")
    elif 0 < lin <= 7:
        st.warning("Até 7 linhas = texto insuficiente (nota zero).")


# --------------------------------------------------------------------------- #
# Telas
# --------------------------------------------------------------------------- #
def tela_inicio():
    st.title("Simulado ENEM 2026 — 1º dia")
    st.markdown(
        """
**Domingo, 8 de novembro de 2026** · Linguagens, Códigos e suas Tecnologias · Redação · Ciências Humanas e suas Tecnologias

| | Prova real (Edital Inep 64/2026) |
|---|---|
| Portões | 12h às 13h (horário de Brasília) |
| Início | 13h30 |
| Duração | **5h30** (término às 19h) |
| Permanência mínima | 2h |
| Sair com o caderno | só nos **últimos 30 minutos** |
| Questões | 90 (5 de língua estrangeira + 40 de Linguagens + 45 de Humanas), 5 alternativas |
| Redação | dissertativo-argumentativa, até 30 linhas, ≤7 linhas = zero |

Este simulado reproduz a estrutura do caderno: **Q01–05** língua estrangeira, **Q06–45** Linguagens, **Proposta de Redação**, **Q46–90** Ciências Humanas.
As questões são originais, escritas no estilo e na distribuição das últimas edições; o tema da redação é a aposta mais fundamentada para 2026.
        """
    )
    st.info("Dica de treino real: comece exatamente às 13h30, use só caneta e papel para o rascunho da redação, "
            "não pause o cronômetro e só consulte o gabarito no fim.")

    nome = st.text_input("Seu nome (cada pessoa tem a própria prova; o progresso fica salvo no link)",
                         value=st.session_state.get("usuario", ""))
    c1, c2 = st.columns(2)
    st.session_state.lingua = c1.radio("Língua estrangeira (escolhida na inscrição)", ["Inglês", "Espanhol"],
                                       index=0 if st.session_state.lingua == "Inglês" else 1, horizontal=True)
    st.session_state.cor = c2.selectbox("Cor do caderno", CORES_CADERNO,
                                        index=CORES_CADERNO.index(st.session_state.cor))

    if nome and (SAVE_DIR / f"{slug(nome)}.json").exists():
        st.success("Encontrei uma prova salva com esse nome.")
        if st.button("↩ Continuar de onde parei", type="primary", width="stretch"):
            carregar_usuario(nome)
            st.rerun()
        st.caption("Ou inicie uma prova nova (apaga a salva):")

    if st.button("▶ Iniciar prova (5h30)", type="primary", width="stretch", disabled=not nome.strip()):
        st.session_state.usuario = slug(nome)
        st.query_params["u"] = st.session_state.usuario
        st.session_state.respostas = {}
        st.session_state.marcadas = []
        st.session_state.redacao = ""
        st.session_state.autoavaliacao = {}
        st.session_state.atual = 1
        st.session_state.inicio = time.time()
        st.session_state.fim = None
        st.session_state.fase = "prova"
        salvar()
        st.rerun()


def tela_prova():
    caderno = montar_caderno(st.session_state.lingua)
    with st.sidebar:
        st.markdown(f"**Caderno {st.session_state.cor.upper()}** · {st.session_state.lingua}")
        painel_tempo()
        st.divider()
        secao = st.radio("Ir para", ["Questões 01–45", "Redação", "Questões 46–90"],
                         index=["q1", "red", "q2"].index(st.session_state.get("secao", "q1")),
                         label_visibility="collapsed")
        novo = {"Questões 01–45": "q1", "Redação": "red", "Questões 46–90": "q2"}[secao]
        if novo != st.session_state.get("secao", "q1"):
            st.session_state.secao = novo
            if novo == "q1" and st.session_state.atual > 45:
                st.session_state.atual = 1
            if novo == "q2" and st.session_state.atual <= 45:
                st.session_state.atual = 46
            st.rerun()
        st.divider()
        cartao_resposta(caderno)
        st.divider()
        dec = tempo_decorrido()
        if dec < PERMANENCIA_MINIMA:
            st.caption("⚠ Antes de 2h de prova você não poderia sair da sala. Pode encerrar mesmo assim (treino).")
        if st.button("⏸ Salvar e sair (pausar)", width="stretch"):
            salvar()
            st.session_state["_pausada"] = True
        if st.session_state.get("_pausada"):
            st.success(f"Salvo. Para continuar, abra o app e digite **{st.session_state.usuario}** "
                       f"(ou use este mesmo link). O cronômetro retoma de {fmt(tempo_decorrido())}.")
        if st.button("✔ Entregar prova", type="primary", width="stretch"):
            st.session_state["_confirma"] = True
        if st.session_state.get("_confirma"):
            faltam = 90 - len(st.session_state.respostas)
            st.warning(f"Entregar agora? {faltam} questão(ões) em branco. Redação: "
                       f"{metricas_redacao(st.session_state.redacao)[1]} linhas.")
            a, b = st.columns(2)
            if a.button("Sim, entregar", width="stretch"):
                encerrar("manual")
                st.rerun()
            if b.button("Voltar", width="stretch"):
                st.session_state["_confirma"] = False
                st.rerun()

    secao = st.session_state.get("secao", "q1")
    if secao == "red":
        tela_redacao()
    else:
        idx = st.session_state.atual
        if secao == "q1" and idx > 45:
            idx = st.session_state.atual = 1
        if secao == "q2" and idx <= 45:
            idx = st.session_state.atual = 46
        mostrar_questao(caderno, idx)


def tela_resultado():
    caderno = montar_caderno(st.session_state.lingua)
    resp = st.session_state.respostas
    motivo = st.session_state.get("motivo_fim", "manual")
    dur = int((st.session_state.fim or time.time()) - (st.session_state.inicio or time.time()))

    st.title("Resultado do simulado")
    if motivo == "tempo":
        st.error("⏱ Tempo esgotado — prova recolhida.")
    st.caption(f"Tempo de prova: {fmt(dur)} · Caderno {st.session_state.cor} · {st.session_state.lingua}")

    # ---- objetivas
    acertos = {"LC": 0, "CH": 0}
    por_disc: dict[str, list[int]] = {}
    linhas = []
    for i, q in enumerate(caderno, start=1):
        r = resp.get(str(i))
        ok = r == q["gabarito"]
        acertos[q["area"]] += ok
        por_disc.setdefault(q["disciplina"].split(" –")[0], [0, 0])
        por_disc[q["disciplina"].split(" –")[0]][0] += ok
        por_disc[q["disciplina"].split(" –")[0]][1] += 1
        linhas.append({"Q": i, "Área": q["area"], "Disciplina": q["disciplina"], "Sua": r or "—",
                       "Gabarito": q["gabarito"], "Acertou": "✅" if ok else ("⬜" if r is None else "❌")})

    c1, c2, c3 = st.columns(3)
    c1.metric("Linguagens (Q1–45)", f"{acertos['LC']}/45", f"≈ {estimar_nota('LC', acertos['LC'])} pts")
    c2.metric("Ciências Humanas (Q46–90)", f"{acertos['CH']}/45", f"≈ {estimar_nota('CH', acertos['CH'])} pts")
    c3.metric("Total", f"{acertos['LC'] + acertos['CH']}/90", f"{90 - len(resp)} em branco")
    st.caption("As notas em pontos são uma ESTIMATIVA grosseira baseada em curvas de edições anteriores. "
               "A nota real é calculada por TRI (coerência do padrão de acertos), não pelo número bruto.")

    st.markdown("#### Por disciplina")
    disc_rows = [{"Disciplina": d, "Acertos": f"{a}/{t}", "%": round(100 * a / t)} for d, (a, t) in por_disc.items()]
    st.dataframe(disc_rows, hide_index=True, width="stretch")

    st.markdown("#### Gabarito")
    st.dataframe(linhas, hide_index=True, width="stretch", height=400)

    with st.expander("Comentários de cada questão (resolução)", expanded=False):
        for i, q in enumerate(caderno, start=1):
            r = resp.get(str(i))
            icone = "✅" if r == q["gabarito"] else "❌"
            st.markdown(f"**{icone} Q{i:02d} — {q['disciplina']}** · gabarito **{q['gabarito']}** · sua: {r or '—'}  \n"
                        f"_{q['habilidade']}_  \n{q['comentario']}")

    # ---- redação
    st.divider()
    r = carregar_redacao()
    pal, lin = metricas_redacao(st.session_state.redacao)
    st.markdown(f"## Redação — {pal} palavras, ~{lin} linhas")
    with st.expander("Ver proposta e seu texto", expanded=False):
        tela_redacao(resultado=True)
    st.markdown("#### Autoavaliação por competência (0 a 200)")
    st.caption("Seja rigoroso: compare com a cartilha do Inep. Use a tabela abaixo como guia.")
    total = 0
    for c in r["competencias"]:
        k = f"c{c['num']}"
        val = st.select_slider(f"C{c['num']} — {c['nome']}", options=[0, 40, 80, 120, 160, 200],
                               value=st.session_state.autoavaliacao.get(k, 120), key=f"sl{k}",
                               help=c["descricao"])
        st.session_state.autoavaliacao[k] = val
        total += val
    salvar()
    st.metric("Nota estimada da redação", f"{total}/1000")
    st.markdown("**Checklist da proposta de intervenção (C5):** " + " · ".join(f"☐ {x}" for x in r["checklist_proposta"]))
    if 0 < lin <= 7:
        st.error("Texto insuficiente (≤7 linhas): nota zero na prova real.")

    # ---- exportar
    st.divider()
    md = [f"# Simulado ENEM 2026 — 1º dia — {datetime.now():%d/%m/%Y %H:%M}", "",
          f"Linguagens: {acertos['LC']}/45 (≈{estimar_nota('LC', acertos['LC'])})  ",
          f"Ciências Humanas: {acertos['CH']}/45 (≈{estimar_nota('CH', acertos['CH'])})  ",
          f"Redação (autoavaliação): {total}/1000 · {pal} palavras · ~{lin} linhas", "",
          "| Q | Sua | Gabarito | Disciplina |", "|---|---|---|---|"]
    md += [f"| {l['Q']} | {l['Sua']} | {l['Gabarito']} | {l['Disciplina']} |" for l in linhas]
    md += ["", "## Redação", "", f"**Tema:** {r['tema']}", "", st.session_state.redacao or "(em branco)"]
    st.download_button("⬇ Baixar resultado + redação (.md)", "\n".join(md),
                       file_name=f"simulado_enem_dia1_{datetime.now():%Y%m%d_%H%M}.md", mime="text/markdown")

    if st.button("↺ Novo simulado", width="stretch"):
        for k in CAMPOS_SALVOS:
            st.session_state.pop(k, None)
        st.session_state.pop("_confirma", None)
        arq = arquivo_usuario()
        if arq and arq.exists():
            arq.unlink()
        st.session_state["_carregado"] = True
        init_state()
        st.rerun()


# --------------------------------------------------------------------------- #
def main():
    st.set_page_config(page_title="Simulado ENEM 2026 — 1º dia", page_icon="📝", layout="wide")
    init_state()
    fase = st.session_state.fase
    if fase == "prova" and tempo_restante() <= 0:
        encerrar("tempo")
        fase = "encerrada"
    if fase == "inicio":
        tela_inicio()
    elif fase == "prova":
        tela_prova()
    else:
        tela_resultado()


main()
