# Mapa Longo: canal de vídeos longos de geografia e clima (YouTube, pt-BR, 16:9)

Canal irmão do Mapas, o canal de curtos do TikTok. O repositório `mapas` **não é alterado** por este projeto: o motor dele é usado numa versão fixa.
Antes de qualquer roteiro, leia `docs/PROPOSTA_FORMATO_LONGO.md`. Responda ao usuário em português.

## Decisões tomadas (16/11/2026)
- **Formato:** 16:9, de 8 a 12 min, dividido em capítulos. A estrutura dos blocos está na proposta.
- **Cadência:**
  - mês 1: 2 vídeos por semana (1 perene + 1 quente publicado em até 36 h);
  - mês 3: até 3 vídeos por semana, se as metas forem batidas;
  - 1 vídeo por dia não entra agora.
- **Pauta:** cerca de 50 % notícia quente e 50 % assunto que volta todo ano. Sempre com um mecanismo que o mapa explica.
- **Mapa:**
  - a **base é a textura autoral** (a mesma marca do TikTok, simplificada para 16:9);
  - o **satélite entra como "prova"** em 1 a 3 momentos por vídeo, de preferência com imagem Copernicus da data do evento;
  - o mosaico Sentinel-2 cloudless **2016** (EOX, CC BY 4.0) é a única versão da EOX liberada; as de 2018 em diante não podem ser usadas;
  - créditos só na descrição, nunca na tela.
- **Câmera calma:**
  - plano novo a cada 8–15 s e algo novo na tela a cada 4–6 s;
  - deriva lenta e contínua, sem nunca parar;
  - o mergulho girando só nas viradas de bloco;
  - 3D com horizonte em 2–3 momentos por vídeo.
  - As regras fixas de câmera do curto não valem aqui.
  - **Sem trancos (feedback do El Niño, 16/11/2026: "a câmera ficou dando umas travadinhas"):** a câmera sai de `motor/longo.py` (`Caminho`), que move entre as chaves com curva suave, prende as chaves dentro da placa e deriva sem mudar de sentido de uma vez. Antes do render, `longo.checar_camera(filme)` tem de voltar sem tranco acima de 3 px/quadro².
- **Textos na tela (feedback do El Niño):**
  - todo lugar citado na fala ganha um `Lugar` (pino no ponto exato do mapa + nome logo acima) **na palavra**. Ex.: "Peru" marcado no Peru, nunca uma etiqueta solta num canto;
  - a etiqueta fica perto do que ela nomeia, sem cobrir o assunto, dentro da área segura (6 % de margem, o motor já segura);
  - no máximo 2–3 etiquetas ao mesmo tempo, cada uma por pelo menos 2,5 s, sem sobrepor outra; letra de no mínimo 36 px;
  - etiquetas em subpixel (o motor já faz), para andarem junto com o mapa sem tremer.
- **Produção por blocos:** usar planos parametrizados (mapa-lousa, viagem, caminho, gráfico, comparador, ficha de dado, foto, lista). O código à mão fica só para o mecanismo principal.
- **Roteiro:** todo roteiro passa por **dois revisores independentes** (agentes) antes da voz: um checa os dados na web, o outro a narrativa e a retenção. O texto final incorpora as duas revisões.
- **Voz:**
  - a voz é a do dono do canal, clonada no Fish Audio (`voz/`), com tags de emoção (aprovada em 16/11/2026);
  - pausas na narração são permitidas quando fazem sentido e o vídeo mostra algo durante a pausa (número contando, contorno se desenhando, seta andando, imagem de satélite);
  - sempre a mesma voz;
  - nunca clonar a voz de uma pessoa real sem autorização por escrito;
  - controle de qualidade automático em toda narração: Whisper × roteiro, pausas, velocidade, tom e nível, com 2 a 3 versões por frase.
- **Antes do render final:** mandar a prancha (um quadro por plano, com o tempo e a frase) e um trecho em vídeo, e esperar o ok. Quando o dono estiver ausente e pedir, as dúvidas e o ok da prancha vão para um agente independente (consultor), e o dono vê tudo quando voltar.
- **Som:** efeitos sutis nas trocas de bloco e nas entradas importantes; música opcional, só se fizer sentido e bem baixa, por baixo da voz.
- **Herdado do curto:**
  - dados conferidos na web;
  - créditos na descrição;
  - arquivo de imagens de IA (`roteiros/<video>_imagens.txt`).

## Produção eficiente (16/11/2026)
- **Parte comum em `motor/cena.py`:** tempos da fala (`Tempos`: `S`, `E`, `T`, `PA`, `CAP`), prancha, linha de comando e render. A cena de um vídeo novo tem só a geografia, as placas, os componentes do tema e `montar()`, e termina com `C.rodar(montar, __file__, titulo=..., placas=...)`. Modelo: começo e fim de `elnino/scene_elnino.py`. **Não copie** a parte comum para a cena; componente que servir para outro vídeo (gráfico, lista, cartela) vai para `motor/`.
- **Render com cache por plano:** `python3 -I <cena> render 4` guarda cada plano em `<video>/cache_planos/` com uma impressão digital. Corrigiu um plano? Rode `render` de novo: só esse plano (e o seguinte, se a troca usa o anterior) é refeito, e tudo é juntado sem recomprimir. Antes, o vídeo inteiro era refeito.
- **Placas guardadas:** as placas ficam em `<video>/placas/` (fora do Git) e são feitas uma vez só por sessão (~13 min no El Niño). Até 16/11 a pasta não era criada e toda execução refazia as placas.
