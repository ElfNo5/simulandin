# Simulado ENEM 2026 — 1º dia (Streamlit)

Simulado do primeiro dia (domingo, 8/11/2026): Linguagens, Códigos e suas Tecnologias (Q01–45, com 5 de língua estrangeira), Proposta de Redação e Ciências Humanas e suas Tecnologias (Q46–90). Formato e regras seguem o Edital Inep nº 64/2026.

## Como rodar

```bash
pip install -r requirements.txt
streamlit run app.py
```

Abre em `http://localhost:8501`.

## O que tem

- Cronômetro real de **5h30** (encerra e recolhe a prova sozinho), avisos de permanência mínima (2h) e de saída com o caderno (últimos 30 min).
- Escolha de inglês ou espanhol (Q01–05) e cor do caderno.
- Cartão-resposta na lateral, marcação de questões para revisar, navegação livre entre as seções.
- Folha de redação com contagem de palavras e **linhas estimadas** (≈62 caracteres/linha; limite 30; ≤7 = zero).
- Progresso salvo em `progresso.json` (se fechar o navegador, reabra e continue).
- Ao entregar: acertos por área e por disciplina, estimativa grosseira de nota, gabarito comentado, autoavaliação da redação pelas 5 competências e download de tudo em `.md`.

## Para treinar de verdade

1. Comece **às 13h30** do dia em que for treinar, com água e lanche como no dia da prova.
2. Faça o rascunho da redação **à mão** e depois digite (ou cronometre também a passagem a limpo).
3. Não pause. Não consulte nada. Só veja o gabarito no fim.
4. Na prova real a correção é por TRI: chutar não ajuda, e acertar as fáceis vale mais do que acertar aleatoriamente as difíceis.

## Sobre o conteúdo

- As 95 questões (45 + 5 de espanhol + 45) são **originais**, escritas no estilo, nos comandos e na distribuição aproximada das últimas edições (crônica com 4 questões em bloco, Machado, Modernismo, Simbolismo, vozes negras e indígenas, variação linguística, charges e textos digitais; Vargas, Colônia, ditadura, Guerra Fria, Antiguidade, geografia ambiental/agrária/energética, contratualismo, Foucault, Arendt, Durkheim, Weber, Marx...).
- O tema da redação (**proteção de crianças e adolescentes no ambiente digital**) é a aposta mais convergente de 14 listas de cursinhos e professores (ago–nov/2026), ancorada no ECA Digital (Lei 15.211/2025). Veja o relatório `Simulado ENEM 2026 primeiro dia.md` para o ranking completo e os dados dos temas alternativos.
- Os textos motivadores são elaborados com dados reais (TIC Kids Online 2025, Lei 15.211/2025), mas redigidos para este simulado.

## Estrutura

```
app.py                 # aplicação Streamlit
data/linguagens_a.json # Q01–05 (inglês e espanhol) + Q06–25
data/linguagens_b.json # Q26–45
data/humanas_a.json    # Q46–68
data/humanas_b.json    # Q69–90
data/redacao.json      # proposta, textos motivadores, competências
```
