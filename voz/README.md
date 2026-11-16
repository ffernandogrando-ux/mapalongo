# Voz do canal (Fish Audio, clonagem instantânea)

A voz é a do dono do canal. Ela é clonada em cada pedido a partir de `ref30.wav`, os primeiros ~31 s da gravação dele. O Fish Audio não guarda modelo de voz: a conta não tem crédito para criar um.
Os áudios da voz ficam fora do Git (`.gitignore`).

## Como usar
Coloque `ref30.wav` nesta pasta e escreva um arquivo de frases, uma por linha. Depois rode:

    python3 qc.py frases.txt 2 narracao.wav

O número `2` é quantas versões gerar por frase.

## O que o `qc.py` faz
- Gera N versões de cada frase.
- Confere cada versão:
  - **Palavra errada:** o Whisper transcreve o áudio e compara com o roteiro (qualquer diferença reprova).
  - **Pausa:** acima de 0,7 s dentro da frase.
  - **Velocidade:** precisa ficar entre 11 e 19 caracteres por segundo.
  - **Tom monótono:** variação de tom abaixo de 1,5 semitom.
  - **Estouro de volume.**
- Escolhe a melhor versão de cada frase e junta tudo com 0,35 s de respiro entre as frases.
- Grava `relatorio_qc.json`. As frases marcadas com `ouvir: true` precisam de escuta humana.

## Tags de emoção
As tags vão no começo da frase, em inglês: `[serious]`, `[excited]`, `[curious]`, `[thoughtful]`, `[confident]`, `[pause]`.
Elas não são faladas: o QC confere isso.
Escreva os números por extenso no roteiro.

## Dependências

    pip install msgpack librosa soundfile faster-whisper
