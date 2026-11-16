# Proposta: formato longo no YouTube (em discussão, 16/11/2026)

Canal irmão do Mapas (TikTok). Vídeos longos em 16:9, público do Brasil, sobre clima e assuntos em alta explicados pelo mapa.
O repositório do curto (`mapas`) não é alterado: este repositório usa o motor do curto numa versão fixa.

Esta proposta junta duas análises feitas separadamente (a do assistente e a de um agente independente), que chegaram quase às mesmas conclusões.
As probabilidades e os números de RPM e retenção são **estimativas**, não dados medidos.

## Decisões propostas
| Tema | Proposta | Situação |
|---|---|---|
| Duração | 8–12 min (anúncio no meio a partir de 8 min). 15–25 min só depois de ter dados de retenção. | consenso |
| Frequência | 1 longo por semana durante 12 semanas, mais 2–3 Shorts por semana | consenso |
| Pauta | ~70 % "notícia-perene" (a notícia é o gancho, e o vídeo explica um mecanismo que volta todo ano: El Niño, frente fria, ciclone, seca no Norte, enchente no Sul) e ~30 % notícia quente | sugerida pelo agente; o assistente concorda |
| Filtro de pauta | Só vira longo o tema cujo curto passou de ~50 mil views ou de 0,5 % de compartilhamentos por view | consenso |
| Voz | A voz do dono do canal é o melhor caminho (retenção e regra de monetização). Se for sintética, usar sempre a mesma voz | **decisão do dono** |
| Primeiros 3 vídeos | Pautas já validadas no curto: El Niño, frio da Antártida e BR-163 | consenso |

## Estrutura do roteiro (~10 min)
| Tempo | Bloco | O que faz |
|---|---|---|
| 0:00–0:30 | Gancho | O conflito em uma frase (regra do curto), seguido da promessa do vídeo |
| 0:30–1:30 | O que aconteceu | A notícia no mapa, com no máximo 2–3 números |
| 1:30–4:00 | Mecanismo | "Funciona assim": um caminho físico no mapa |
| ~4:00 | Gancho de meio | Um paradoxo que o bloco seguinte responde (nada de "fica até o final") |
| 4:00–6:30 | História | As outras vezes que aconteceu, com gráfico de série |
| 6:30–8:30 | Impacto | "Se você mora em...": preço, conta de luz, safra, risco por região |
| 8:30–9:45 | Utilidade | O que fazer, o que observar, quando acontece |
| 9:45–10:00 | "Ou seja" | Fecho memorável e card para o próximo vídeo |

Regra: cada bloco responde a uma pergunta que o espectador faria. Bloco sem pergunta sai. Se o vídeo der 8 min, tudo bem.
O vídeo é dividido em capítulos no YouTube, um por bloco.

## Visual: o que muda em relação ao curto
**Mantém:** a textura autoral, os contornos que se desenham, as etiquetas brancas, os números contando e os caminhos animados (setas, frentes, estradas).

**Deixa de valer no longo** (as regras fixas do curto continuam valendo no curto):
- o pêndulo constante e o soco em quase toda palavra;
- o plano novo a cada ~3 s e o zoom-through em toda troca;
- a exigência de 4 a 6 ângulos e as aberturas com "slam" a cada bloco.

**Ritmo do longo:**
- plano novo a cada 8–15 s, e algo novo na tela a cada 4–6 s;
- câmera com deriva lenta e contínua (zoom de 1–2 %/s e giro de ~1 °/s), que nunca fica parada;
- o mergulho girando do curto fica guardado para as viradas de bloco (5–8 por vídeo);
- 3D com horizonte em 2–3 momentos (gancho, virada, fecho);
- em 16:9 cabe mais: mapa pequeno de localização no canto, legenda e escala.

## Produção: blocos prontos em vez de cena escrita à mão
Uma cena do curto tem ~1.000 linhas de código para 80 s. Nesse ritmo, 10 min não cabem.
A proposta é ter um kit de **6–8 tipos de plano parametrizados**, dirigidos por um arquivo de linha do tempo (o roteiro marcado com as palavras), de modo que ~70 % do vídeo seja configuração:
1. **Mapa-lousa:** fundo autoral, câmera lenta, camadas que se desenham na palavra.
2. **Viagem:** de um lugar a outro, com o mergulho nas viradas.
3. **Caminho:** seta, frente fria, rio ou estrada que anda.
4. **Gráfico de série:** linha ou barra que cresce, no estilo das etiquetas.
5. **Comparador:** duas regiões ou dois anos lado a lado.
6. **Ficha de dado:** número grande sobre o mapa desfocado.
7. **Foto real em moldura** (Agência Brasil, Agência Senado).
8. **Lista de utilidade.**

O código feito à mão fica só para o mecanismo principal de cada vídeo.
Meta de esforço: um longo custar no máximo 3–4 vezes um curto.

## Riscos
- **Monetização e conteúdo de IA:** a regra do YouTube (hoje "Generic or Repetitive Content", segundo a imprensa de julho de 2026) mira conteúdo em massa sem valor original, não o uso de IA em si. A defesa é ter pesquisa visível, fontes na descrição, mapa autoral, ritmo humano (1 por semana) e, de preferência, a voz do dono do canal. Evitar pautas de finanças narradas por voz sintética.
- **Concorrência:** Climatempo e MetSul fazem previsão do tempo. A explicação com mapa autoral parece um espaço pouco ocupado em pt-BR (impressão, sem levantamento). Não competir com "vai chover amanhã".
- **Tempo:** o longo não pode tirar o curto do ar nos dias de notícia quente.

## Metas e critérios no dia 90
| Mês | Entregas | Metas |
|---|---|---|
| 1 | Kit de blocos e 3 longos | Esforço ≤ 4× o curto, retenção média ≥ 35 %, CTR ≥ 4 % |
| 2 | 4 longos, testando uma variável por vez (duração, miniatura, quente × perene) | ≥ 300 inscritos, 1 vídeo acima de 10 mil views, ≥ 20 % das views de busca ou sugeridos |
| 3 | 4–5 longos e 1 teste de boletim semanal | 1.000 inscritos, ≥ 1.500 h assistidas, 1 vídeo perene ainda crescendo 30 dias depois |

**Decisão no dia 90:**
- **Continuar:** retenção ≥ 35 %, 1 vídeo acima de 20 mil views e esforço ≤ 4× o curto.
- **Mudar** (primeiro a voz, depois a duração): retenção abaixo de 30 % ou nenhum vídeo acima de 5 mil views.
- **Pausar:** esforço acima de 6× o curto, ou o curto perdendo mais de 40 % das views por falta de tempo.

## Rodada 2 (16/11/2026): voz, frequência e satélite

### Voz
- **Não clonar o Henry nem o Nathan no Fish Audio.**
  - As vozes do ElevenLabs com esse nome parecem ser da Voice Library, que são vozes de pessoas reais. A ficha da voz no app mostra o autor.
  - Os termos do Fish Audio proíbem usar a voz de outra pessoa sem autorização.
  - Os termos do ElevenLabs proíbem usar a saída do serviço para criar modelos concorrentes.
  - Se der problema, o canal perde a voz que é a identidade dele.
- **Caminhos para ganhar emoção:**
  1. Eleven v3 com audio tags (`[empolgado]`, `[pausa]`), na mesma voz Henry.
  2. Fish Audio com a voz do dono do canal ou de um locutor contratado, com cessão de direitos por escrito.
  3. Voice Design (uma voz nova, sem pessoa real por trás).
- **Controle de qualidade automático, em todo vídeo:**
  - gerar 2–3 versões por frase;
  - Whisper compara o que foi falado com o roteiro, e qualquer palavra errada reprova a frase;
  - medir pausas, velocidade, tom monótono ou final subindo, e nível;
  - escolher sozinho a melhor versão de cada frase;
  - só as frases reprovadas em todas as versões vão para escuta.

### Frequência
- Mix de cerca de **50 % notícia quente e 50 % perene**. Assunto em alta sem notícia só entra se houver um mecanismo que o mapa explique.
- **Semanas 1–4:** 1 perene de 10–12 min + 1 quente de 6–8 min, publicado em até 36 h.
- **Semanas 5–8:** 2 por semana fixos, medindo as horas gastas.
- **Semanas 9–12:** 3 por semana (2 quentes + 1 perene), se a retenção ficar em pelo menos 35 %, o quente custar até 2× um curto e o curto não cair.
- **1 por dia, agora, não:** o risco estimado na regra de conteúdo genérico do YouTube sobe de menos de 10 % (2 por semana) para 25–40 % (1 por dia).

### Satélite (em aberto: A/B na prancha)
- **Licença:**
  - Sentinel-2 cloudless **2016** (EOX) é CC BY 4.0: pode usar comercialmente, com crédito na descrição.
  - Os mosaicos de 2018–2021 são NC (não comerciais).
  - Os de 2023 em diante precisam de licença paga.
- **Risco de "reused content" no YouTube:** baixo, porque há animação, roteiro e narração próprios.
- **Assistente:** satélite como base em 16:9, com tratamento de cor próprio. As camadas simples (contornos, setas, etiquetas) vão por cima.
- **Agente:** base autoral (marca visual que liga TikTok e YouTube, mais legível em 10 min) e satélite só como "prova" em 1–3 momentos, com imagem Copernicus da data do evento. O mosaico de 2016 é velho e não mostra o evento.
- **Próximo passo:** prancha 16:9 com o mesmo plano em três versões (autoral, satélite com tratamento, satélite cru) para o dono escolher.
