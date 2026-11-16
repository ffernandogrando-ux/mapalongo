"""Conferência automática da narração: gera N versões por frase, confere com Whisper e escolhe a melhor."""
import json, re, subprocess, sys, unicodedata, numpy as np, librosa
from faster_whisper import WhisperModel
from tts import tts
M = WhisperModel("small", compute_type="int8")
_U = "zero um dois tres quatro cinco seis sete oito nove dez onze doze treze quatorze quinze dezesseis dezessete dezoito dezenove".split()
_D = "_ _ vinte trinta quarenta cinquenta sessenta setenta oitenta noventa".split()
_C = "_ cento duzentos trezentos quatrocentos quinhentos seiscentos setecentos oitocentos novecentos".split()
def extenso(n):
    """inteiro (0..999999) por extenso em português, sem acento (para comparar com a fala)."""
    if n < 20: return _U[n]
    if n < 100: return _D[n // 10] + ("" if n % 10 == 0 else " e " + _U[n % 10])
    if n == 100: return "cem"
    if n < 1000: return _C[n // 100] + ("" if n % 100 == 0 else " e " + extenso(n % 100))
    m, r = divmod(n, 1000)
    s = "mil" if m == 1 else extenso(m) + " mil"
    if r == 0: return s
    return s + (" e " if r < 100 or r % 100 == 0 else " ") + extenso(r)
def _num(m):
    v = int(m.group(0)); return " " + extenso(v) + " " if v < 1000000 else m.group(0)
def norm(s):
    s = re.sub(r"\[[^\]]*\]", " ", s)  # tags de emoção não são faladas
    s = s.replace("%", " por cento")
    s = re.sub(r"\d+", _num, s)        # o Whisper escreve números em algarismos
    s = unicodedata.normalize("NFD", s.lower()); s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r" +", " ", re.sub(r"[^a-z0-9 ]", " ", s))
    s = re.sub(r"\bel ?(ninio|nineo|ninyo|nino|minio|ninho)\b|\belminio\b|\belninho\b", "el nino", s)  # grafias do Whisper para El Niño
    s = re.sub(r"\bla ?(ninia|ninha|ninya)\b|\blaninha\b", "la nina", s)
    s = s.replace(" e ", " e ").replace(" todo o mundo", " todo mundo")
    return s.split()
def wer(ref, hyp):
    d = np.arange(len(hyp) + 1)
    for i, r in enumerate(ref, 1):
        nd = d.copy(); nd[0] = i
        for j, h in enumerate(hyp, 1): nd[j] = min(d[j] + 1, nd[j-1] + 1, d[j-1] + (r != h))
        d = nd
    return d[-1] / max(1, len(ref))
NUM = {"0":"zero","1":"um","2":"dois","3":"tres","4":"quatro","5":"cinco","6":"seis","7":"sete","8":"oito","9":"nove","10":"dez"}
def avalia(wav, texto):
    a, sr = librosa.load(wav, sr=16000)
    segs, _ = M.transcribe(a, language="pt", word_timestamps=True)
    ws = [w for s in segs for w in s.words]
    hyp = norm(" ".join(w.word for w in ws))
    ref = norm(texto)
    e = 0.0 if "".join(ref) == "".join(hyp) else wer(ref, hyp)  # "debaixo" = "de baixo"
    gaps = [ws[i+1].start - ws[i].end for i in range(len(ws) - 1)]
    pausa = max(gaps, default=0)
    dur = len(a) / sr; cps = len(re.sub(r"\[[^\]]*\]", "", texto)) / max(dur, .1)
    f0, vo, _ = librosa.pyin(a, fmin=70, fmax=350, sr=sr)
    f0 = f0[~np.isnan(f0)]; st = 12 * np.log2(f0 / np.median(f0)) if len(f0) else np.zeros(1)
    var = float(np.std(st))
    fim = float(np.median(st[-15:]) - np.median(st[-60:-15])) if len(st) > 80 else 0.0
    pico = float(np.abs(a).max())
    avisos = []
    if e > 0: avisos.append(f"palavra errada ({' '.join(hyp)})")
    if pausa > 0.7: avisos.append(f"pausa {pausa:.1f}s")
    if not 11 <= cps <= 19: avisos.append(f"velocidade {cps:.0f} car/s")
    if var < 1.5: avisos.append(f"tom monótono ({var:.1f} st)")
    if pico > 0.99: avisos.append("estouro")
    nota = e * 10 + max(0, pausa - .7) + abs(cps - 15) / 4 + max(0, 2.2 - var)
    pal = [dict(w=w.word.strip(), a=round(w.start, 3), b=round(w.end, 3)) for w in ws]
    return dict(palavras=pal, wer=round(e, 3), pausa=round(pausa, 2), cps=round(cps, 1), tom_st=round(var, 2), fim_st=round(fim, 2), nota=round(nota, 2), avisos=avisos, ouvido=" ".join(hyp))
if __name__ == "__main__":
    frases = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    rel, escolhidas = [], []
    for i, f in enumerate(frases, 1):
        vs = []
        for k in range(n):
            out = f"f{i:02d}_v{k+1}.wav"
            if tts(f, out, "s2.1-pro-free"): vs.append(dict(arq=out, **avalia(out, f)))
        melhor = min(vs, key=lambda v: v["nota"])
        rel.append(dict(frase=f, versoes=vs, escolhida=melhor["arq"], ouvir=bool(melhor["avisos"])))
        escolhidas.append(melhor["arq"])
        print(i, melhor["arq"], melhor["avisos"] or "ok", flush=True)
    json.dump(rel, open("relatorio_qc.json", "w"), ensure_ascii=False, indent=1)
    # junta com 0,35 s de respiro entre frases
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "0.35", "resp.wav"])
    lst = "".join(f"file '{e}'\nfile 'resp.wav'\n" for e in escolhidas)
    open("lista.txt", "w").write(lst)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", "lista.txt", "-ar", "44100", "-ac", "1", sys.argv[3]])
