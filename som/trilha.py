#!/usr/bin/env python3
"""Trilha própria (sem licença de terceiros): pad ambiente lento, sintetizado aqui.
Acordes suaves em lá menor com ataque e queda longos, filtrados, para ficar BEM baixo por baixo da voz.
    python3 trilha.py SEGUNDOS saida.wav
"""
import sys, numpy as np, soundfile as sf
from scipy.signal import butter, sosfilt
SR = 44100
def nota(f, dur, sr=SR):
    t = np.arange(int(dur * sr)) / sr
    s = sum(np.sin(2 * np.pi * f * k * t + k) / k ** 1.6 for k in (1, 2, 3)) * 0.5
    s += 0.35 * np.sin(2 * np.pi * f * 1.003 * t)              # leve batimento (calor)
    env = np.minimum(1, t / (dur * 0.35)) * np.minimum(1, (dur - t) / (dur * 0.45))
    return s * env ** 1.5
def trilha(dur):
    acordes = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (196.0, 246.94, 293.66), (164.81, 207.65, 246.94)]  # Am F G E
    passo = 9.0; out = np.zeros(int((dur + passo * 2) * SR))
    for i, t0 in enumerate(np.arange(0, dur + passo, passo)):
        ac = acordes[i % 4]; d = passo * 1.8
        seg = sum(nota(f, d) for f in ac) + 0.6 * nota(ac[0] / 2, d)
        a = int(t0 * SR); out[a:a + len(seg)] += seg[:len(out) - a]
    out = sosfilt(butter(4, 1400, "lp", fs=SR, output="sos"), out)
    out = sosfilt(butter(2, 70, "hp", fs=SR, output="sos"), out)
    out = out[:int(dur * SR)]; out /= np.abs(out).max() + 1e-9
    fade = np.minimum(1, np.arange(len(out)) / (3 * SR)) * np.minimum(1, (len(out) - np.arange(len(out))) / (4 * SR))
    return (out * fade * 0.5).astype(np.float32)
if __name__ == "__main__":
    sf.write(sys.argv[2], trilha(float(sys.argv[1])), SR)
