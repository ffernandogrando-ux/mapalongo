#!/usr/bin/env python3
"""Narração de um roteiro inteiro com a voz do canal.

    python3 narrar.py ../roteiros/elnino_longo.txt ../elnino/audio

Lê o roteiro (## capítulo, > plano, {pausa N: ...}, [tag] frase), gera até 3 versões por frase com o
controle de qualidade do qc.py (para na primeira sem aviso a partir da 2ª) e monta:
  narracao.wav   a voz inteira, com respiro entre frases e as pausas pedidas no roteiro;
  linha.json     a linha do tempo: cada frase (início, fim, palavras com tempo), pausas, planos e capítulos;
  qc.json        o relatório (frases que precisam de escuta humana têm "ouvir": true).
"""
import json, os, re, subprocess, sys, shutil
import numpy as np, soundfile as sf
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.chdir(HERE)
from qc import avalia
from tts import tts

SR = 44100; RESPIRO, ENTRE_CAP = 0.38, 0.85


def le(path):
    itens = []
    for l in open(path, encoding="utf-8"):
        l = l.strip()
        if not l or l.startswith("# "): continue
        if l.startswith("## "): itens.append(dict(tipo="capitulo", nome=l[3:]))
        elif l.startswith(">"): itens.append(dict(tipo="plano", nota=l[1:].strip()))
        elif l.startswith("{pausa"):
            m = re.match(r"\{pausa ([\d.]+):\s*(.*)\}", l); itens.append(dict(tipo="pausa", dur=float(m.group(1)), nota=m.group(2)))
        else: itens.append(dict(tipo="frase", texto=l))
    return itens


def wav(path):
    a, sr = sf.read(path, dtype="float32")
    if a.ndim > 1: a = a.mean(1)
    if sr != SR:
        import librosa; a = librosa.resample(a, orig_sr=sr, target_sr=SR)
    # tira silêncio das pontas (deixa 40 ms)
    nz = np.where(np.abs(a) > 0.01)[0]
    if len(nz): a = a[max(0, nz[0] - int(0.04 * SR)): nz[-1] + int(0.06 * SR)]
    return a


def main(rot, saida):
    os.makedirs(os.path.join(saida, "frases"), exist_ok=True)
    itens = le(rot); partes, t, linha, rel = [], 0.0, [], []
    n = 0; cap_ant = False
    for it in itens:
        if it["tipo"] == "capitulo":
            if t > 0: partes.append(np.zeros(int(ENTRE_CAP * SR), np.float32)); t += ENTRE_CAP
            linha.append(dict(it, t=round(t, 3))); cap_ant = True; continue
        if it["tipo"] == "plano": linha.append(dict(it, t=round(t, 3))); continue
        if it["tipo"] == "pausa":
            partes.append(np.zeros(int(it["dur"] * SR), np.float32)); linha.append(dict(it, t=round(t, 3))); t += it["dur"]; continue
        n += 1; texto = it["texto"]; vs = []
        for k in range(3):
            out = os.path.join(saida, "frases", f"{n:03d}_v{k + 1}.wav")
            if not os.path.exists(out) and not tts(texto, out, "s2.1-pro-free"): continue
            v = dict(arq=out, **avalia(out, texto)); vs.append(v)
            if k >= 1 and not min(vs, key=lambda x: x["nota"])["avisos"]: break
        m = min(vs, key=lambda x: x["nota"])
        a = wav(m["arq"]); d = len(a) / SR
        # tempos das palavras: o whisper mede no arquivo original; corrige pelo corte da ponta
        a0, _ = sf.read(m["arq"], dtype="float32"); a0 = a0 if a0.ndim == 1 else a0.mean(1)
        sr0 = sf.info(m["arq"]).samplerate; nz = np.where(np.abs(a0) > 0.01)[0]
        corte = max(0, nz[0] / sr0 - 0.04) if len(nz) else 0
        pal = [dict(w=p["w"], a=round(t + p["a"] - corte, 3), b=round(t + p["b"] - corte, 3)) for p in m["palavras"]]
        linha.append(dict(tipo="frase", n=n, texto=texto, t=round(t, 3), fim=round(t + d, 3), palavras=pal))
        rel.append(dict(n=n, texto=texto, escolhida=os.path.basename(m["arq"]), avisos=m["avisos"], ouvir=bool(m["avisos"]),
                        versoes=[{k: v[k] for k in ("arq", "wer", "pausa", "cps", "tom_st", "nota", "avisos")} for v in vs]))
        print(f"{n:3d} {t:7.2f}s {os.path.basename(m['arq'])} {m['avisos'] or 'ok'}", flush=True)
        partes.append(a); t += d
        partes.append(np.zeros(int(RESPIRO * SR), np.float32)); t += RESPIRO
    partes.append(np.zeros(int(1.5 * SR), np.float32)); t += 1.5
    sf.write(os.path.join(saida, "narracao_bruta.wav"), np.concatenate(partes), SR)
    json.dump(dict(dur=round(t, 3), itens=linha), open(os.path.join(saida, "linha.json"), "w"), ensure_ascii=False, indent=1)
    json.dump(rel, open(os.path.join(saida, "qc.json"), "w"), ensure_ascii=False, indent=1)
    # nível: loudnorm em etapa separada (padrão do canal)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", os.path.join(saida, "narracao_bruta.wav"),
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", str(SR), os.path.join(saida, "narracao.wav")])
    print("duração", round(t, 1), "s;", sum(r["ouvir"] for r in rel), "frases para ouvir")


if __name__ == "__main__":
    main(sys.argv[1], os.path.abspath(sys.argv[2]))
