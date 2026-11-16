#!/usr/bin/env python3
"""Mixagem do vídeo longo: voz (já nivelada) + efeitos sutis + trilha bem baixa, com a trilha abaixando
quando a voz fala (sidechain simples). Efeitos: whoosh suave nos mergulhos de capítulo, pop leve nas figuras,
marcação na cartela de capítulo.
    python3 mix.py VOZ.wav EVENTOS.json SAIDA.wav
EVENTOS.json: [{"t": s, "som": "whoosh"|"pop"|"marca"|"tique"}]
"""
import sys, json, subprocess, os, numpy as np, soundfile as sf
from scipy.signal import butter, sosfilt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trilha import trilha
SR = 44100; MIX = "/home/user/mapas/sfxlib/mixkit"
SONS = {"whoosh": ["swoosh/1469", "wh2/1458", "swoosh/1340", "wh2/3161"], "pop": ["pop/2925", "pop/2365"], "marca": ["mark/3005"]}
GANHO = {"whoosh": 0.16, "pop": 0.10, "marca": 0.12, "tique": 0.05}

def carrega(p):
    a = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", p, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True).stdout
    a = np.frombuffer(a, np.float32).copy()
    a = sosfilt(butter(2, [220, 7000], "bp", fs=SR, output="sos"), a)   # tira grave e chiado (padrão do canal)
    return a / (np.abs(a).max() + 1e-9)

def tique():
    t = np.arange(int(0.03 * SR)) / SR; return (np.sin(2 * np.pi * 2200 * t) * np.exp(-t * 180)).astype(np.float32)

def main(voz, ev, out):
    v, sr = sf.read(voz, dtype="float32"); v = v if v.ndim == 1 else v.mean(1)
    n = len(v); fx = np.zeros(n, np.float32); cache = {}; cont = {}
    for e in json.load(open(ev)):
        s = e["som"]
        if s == "tique": a = tique()
        else:
            lst = SONS[s]; k = cont.get(s, 0); cont[s] = k + 1
            p = os.path.join(MIX, lst[k % len(lst)] + "-preview.mp3")
            if p not in cache: cache[p] = carrega(p)
            a = cache[p]
        a = a * GANHO[s]; i = int(max(0, e["t"] - (0.35 if s == "whoosh" else 0)) * SR)
        j = min(n, i + len(a)); fx[i:j] += a[:j - i]
    m = trilha(n / SR)[:n]
    # sidechain: envelope da voz -> abaixa a trilha onde há fala
    env = np.convolve(np.abs(v), np.ones(int(0.3 * SR)) / int(0.3 * SR), "same")
    env = np.clip(env / (np.percentile(env, 95) + 1e-9), 0, 1)
    m = m * (0.085 - 0.045 * env)                       # ~ -22 dB sem voz, ~ -28 dB com voz
    mix = v + fx + m
    sf.write(out + ".tmp.wav", mix.astype(np.float32), SR)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", out + ".tmp.wav", "-af", "alimiter=limit=0.89", out]); os.remove(out + ".tmp.wav")

if __name__ == "__main__":
    main(*sys.argv[1:4])
