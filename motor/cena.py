"""Parte comum de toda cena do canal longo: tempos da fala, prancha, linha de comando e render com cache por plano.

Antes, isso ficava dentro do scene_elnino.py e o próximo vídeo teria de copiar. Uso numa cena nova:

    import cena as C
    TP = C.Tempos(os.path.join(HERE, "audio"))          # linha.json da narração
    FR, PAUSAS, CAPS, DUR = TP.FR, TP.PAUSAS, TP.CAPS, TP.DUR
    S, E, T, PA, CAP = TP.S, TP.E, TP.T, TP.PA, TP.CAP     # T(frase, "palavra") = tempo da palavra
    def montar(): ... return Filme(planos, trocas, DUR)
    if __name__ == "__main__":
        C.rodar(montar, __file__, titulo="Tema — vídeo longo 16:9", placas=todas_placas)

Comandos: checar [v] | som | placas | prancha | quadro t [arq] | trecho a b | render [procs]
O render guarda cada plano em <pasta>/cache_planos/ com uma impressão digital (o que o plano desenha, a troca de
entrada, os tempos, o motor e o resto da cena). Corrigiu um plano? `render` de novo refaz só esse plano (e o
seguinte, se a troca usa o anterior) e junta tudo sem recomprimir.
"""
import os, sys, re, json, math, hashlib, inspect, subprocess, unicodedata
import numpy as np, cv2
from PIL import Image, ImageDraw

AQUI = os.path.dirname(os.path.abspath(__file__)); RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, AQUI); sys.path.insert(0, os.path.join(RAIZ, "voz"))
import longo as L  # noqa: E402
from longo import G, W, H, FPS, Figura  # noqa: E402


# ------------------------------------------------------------------------------------------- tempos da fala
def _n(s): return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn" and c.isalnum())


class Tempos:
    """linha.json (voz/narrar.py + qc): frases com palavras, pausas e capítulos."""
    def __init__(self, audio_dir, dur_padrao=600):
        f = os.path.join(audio_dir, "linha.json")
        self.LINHA = json.load(open(f)) if os.path.exists(f) else None
        it = self.LINHA["itens"] if self.LINHA else []
        self.FR = {i["n"]: i for i in it if i["tipo"] == "frase"}
        self.PAUSAS = [i for i in it if i["tipo"] == "pausa"]
        self.CAPS = [i for i in it if i["tipo"] == "capitulo"]
        self.DUR = self.LINHA["dur"] if self.LINHA else dur_padrao

    def S(self, n): return self.FR[n]["t"]
    def E(self, n): return self.FR[n]["fim"]
    def PA(self, i): return self.PAUSAS[i]["t"]          # início da i-ésima pausa do roteiro
    def CAP(self, i): return self.CAPS[i]["t"]

    @staticmethod
    def _np(w):
        from qc import extenso
        w = _n(w); return "".join(extenso(int(x)).replace(" ", "") if x.isdigit() else x for x in re.findall(r"\d+|\D+", w)) if w else w

    def T(self, n, w, k=0):
        """tempo da k-ésima palavra da frase n que começa com w (junta palavras vizinhas: "de baixo" = "debaixo";
        números em algarismos viram extenso: "16" = "dezesseis")."""
        _np = self._np
        ps = self.FR[n]["palavras"]; alvo = _n(w); achou = []
        for i in range(len(ps)):
            cat = ""
            for j in range(i, min(i + 4, len(ps))):
                cat += _np(ps[j]["w"])
                if cat.startswith(alvo):
                    achou.append(ps[i]["a"]); break
                if not alvo.startswith(cat): break
        achou = sorted(set(achou))
        if len(achou) <= k:                       # grafia diferente do Whisper ("laninha"): a palavra mais parecida
            import difflib
            sc = [(difflib.SequenceMatcher(None, alvo, _np(p["w"])[:len(alvo) + 3]).ratio(), p["a"]) for p in ps]
            achou = sorted(a for r, a in sc if r >= 0.6)
        if len(achou) <= k: raise KeyError(f"'{w}' não está na frase {n}: {[p['w'] for p in ps]}")
        return achou[k]


# ------------------------------------------------------------------------------------------- impressão digital
def _fp(o, prof=0, vistos=None):
    """Texto estável que muda quando muda o que o objeto desenha. Atributos com _ (caches) ficam de fora."""
    vistos = vistos if vistos is not None else set()
    if prof > 8: return "…"
    if o is None or isinstance(o, (bool, int, str)): return repr(o)
    if isinstance(o, float): return repr(round(o, 6))
    if isinstance(o, np.ndarray):
        a = o[(slice(None, None, 5),) * min(o.ndim, 2)] if o.ndim >= 2 else o
        return f"nd{o.shape}{o.dtype}:" + hashlib.sha1(np.ascontiguousarray(a).tobytes()).hexdigest()[:12]
    if isinstance(o, Image.Image): return "img:" + hashlib.sha1(o.tobytes()).hexdigest()[:12]
    if hasattr(o, "wkb") and hasattr(o, "geom_type"): return "geo:" + hashlib.sha1(o.wkb).hexdigest()[:12]
    if id(o) in vistos: return "↺"
    vistos = vistos | {id(o)}
    if isinstance(o, (list, tuple, set, frozenset)):
        it = sorted(o, key=repr) if isinstance(o, (set, frozenset)) else o
        return "[" + ",".join(_fp(x, prof + 1, vistos) for x in it) + "]"
    if isinstance(o, dict): return "{" + ",".join(f"{k}:{_fp(v, prof + 1, vistos)}" for k, v in sorted(o.items(), key=lambda kv: repr(kv[0]))) + "}"
    if callable(o) and hasattr(o, "__code__"):
        try: src = inspect.getsource(o)
        except Exception: src = o.__code__.co_code.hex()
        cel = [c.cell_contents for c in (o.__closure__ or ()) if _tem(c)]
        return "fn:" + src + _fp(cel, prof + 1, vistos) + _fp(o.__defaults__, prof + 1, vistos)
    if hasattr(o, "__dict__"):
        return type(o).__name__ + _fp({k: v for k, v in vars(o).items() if not k.startswith("_")}, prof + 1, vistos)
    return repr(o)


def _tem(c):
    try: c.cell_contents; return True
    except ValueError: return False


def _comum(cena):
    """Tudo o que vale para todos os planos: motor e a cena SEM o corpo de montar() (os planos entram um a um)."""
    src = open(cena, encoding="utf-8").read()
    src = re.sub(r"\ndef montar\(\):.*?(?=\n\S)", "\n", src, flags=re.S)
    partes = [src] + [open(os.path.join(AQUI, f), encoding="utf-8").read() for f in ("longo.py", "cena.py")]
    return hashlib.sha1("\0".join(partes + [str((W, H, FPS))]).encode()).hexdigest()[:16]


def segmentos(F):
    """Um trecho por plano: do início do plano (com a troca de entrada) até o início do seguinte."""
    n = len(F.planos); out = []
    for i, p in enumerate(F.planos):
        a = 0.0 if i == 0 else p.t0; b = F.planos[i + 1].t0 if i + 1 < n else F.dur
        out.append((i, a, b))
    return out


_F = None
def _parte(arg):
    i, a, b, out = arg
    tmp = out + ".tmp.mp4"; _F.render(tmp, a, b); os.replace(tmp, out)
    return i


def render_planos(F, cena, saida, procs=4):
    """Render com cache por plano (ver o topo do arquivo). Devolve o caminho do vídeo mudo."""
    global _F
    pasta = os.path.dirname(os.path.abspath(cena)); cache = os.path.join(pasta, "cache_planos"); os.makedirs(cache, exist_ok=True)
    comum = _comum(cena); faz, partes = [], []
    for i, a, b in segmentos(F):
        p = F.planos[i]; ant = F.planos[i - 1] if i else None
        chave = hashlib.sha1("\0".join([comum, _fp(p), F.trocas[i], _fp(ant) if ant else "", f"{a:.4f}-{b:.4f}"]).encode()).hexdigest()[:16]
        out = os.path.join(cache, f"{i:03d}_{chave}.mp4"); partes.append(out)
        if not os.path.exists(out): faz.append((i, a, b, out))
    vivos = {os.path.basename(x) for x in partes}
    for f in os.listdir(cache):
        if f.endswith(".mp4") and f not in vivos: os.remove(os.path.join(cache, f))   # libera o disco
    print(f"render: {len(partes) - len(faz)} planos do cache, {len(faz)} a renderizar"
          + (f" ({', '.join(str(x[0]) for x in faz)})" if 0 < len(faz) < 40 else ""), flush=True)
    if faz:
        _F = F
        from multiprocessing import Pool
        with Pool(procs) as pool:
            for k, i in enumerate(pool.imap_unordered(_parte, sorted(faz, key=lambda x: x[1] - x[2]))):
                print(f"  plano {i} pronto ({k + 1}/{len(faz)})", flush=True)
    lst = os.path.join(cache, "lista.txt"); open(lst, "w").write("".join(f"file '{p}'\n" for p in partes))
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", saida], check=True)
    return saida


# ------------------------------------------------------------------------------------------- prancha
def prancha(F, FR, titulo, saida):
    fonte = G.fonte; F_X, F_SB = G.FONT_X, G.FONT_SB
    larg = 480; hq = int(larg * H / W); gap = 14; cols = 4
    rows = math.ceil(len(F.planos) / cols)
    pr = Image.new("RGB", (cols * (larg + gap) + gap, rows * (hq + 92 + gap) + 80), (14, 15, 18)); d = ImageDraw.Draw(pr)
    d.text((gap, 40), titulo + " — prancha (um quadro por plano: tempo e frase)", font=fonte(F_X, 28), fill=(240, 240, 240), anchor="lm")
    for k, p in enumerate(F.planos):
        tm = min(p.t1 - 0.5, p.t0 + max(2.5, (p.t1 - p.t0) * 0.6))
        im = Image.fromarray(cv2.cvtColor((np.clip(F.quadro(tm), 0, 1) * 255).astype(np.uint8), cv2.COLOR_BGR2RGB))
        x = gap + (k % cols) * (larg + gap); y = 80 + (k // cols) * (hq + 92 + gap)
        pr.paste(im.resize((larg, hq), Image.LANCZOS), (x, y))
        fr = [i for i in FR.values() if p.t0 - 0.5 <= i["t"] < p.t1]
        txt = fr[0]["texto"] if fr else ""; txt = re.sub(r"\[[a-z]+\] ", "", txt)
        d.text((x, y + hq + 18), f"{int(p.t0 // 60)}:{p.t0 % 60:04.1f} · {p.nome} · {F.trocas[k]}", font=fonte(F_X, 18), fill=(255, 196, 80), anchor="lm")
        ls, l = [], ""
        for w_ in txt.split():
            if fonte(F_SB, 15).getlength(l + " " + w_) > larg: ls.append(l); l = w_
            else: l = (l + " " + w_).strip()
        d.multiline_text((x, y + hq + 32), "\n".join((ls + [l])[:3]), font=fonte(F_SB, 15), fill=(215, 215, 215), spacing=3)
    pr.save(saida, quality=88); print(saida, len(F.planos), "planos")


# ------------------------------------------------------------------------------------------- linha de comando
def rodar(montar, cena, titulo, placas=None, tempos=None):
    HERE = os.path.dirname(os.path.abspath(cena)); AUDIO = os.path.join(HERE, "audio")
    TP = tempos or Tempos(AUDIO)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "prancha"
    if cmd == "checar":
        F = montar(); print("ok", len(F.planos), "planos", round(TP.DUR, 1), "s")
        for p in F.planos:
            print(f"{p.t0:7.2f} {p.t1 - p.t0:5.1f}s {p.nome}")
            if len(sys.argv) > 2:
                for c in p.camadas:
                    bad = " <<< fora do plano" if c.t_in > p.t1 or c.t_in < p.t0 - 0.5 else ""
                    print(f"          {type(c).__name__:9s} {getattr(c, 'texto', '')[:34]:34s} {c.t_in:7.2f} {min(c.t_out, 9999):7.2f}{bad}")
        r = L.checar_camera(F)
        print(f"câmera: {len(r)} tranco(s) acima do limite" + "".join(f"\n  {x}" for x in r[:15]) if r else "câmera: sem trancos")
    elif cmd == "som":
        F = montar(); ev = []
        for p, tr in zip(F.planos, F.trocas):
            if tr == "mergulho": ev.append(dict(t=p.t0, som="whoosh"))
            for c in p.camadas:
                if isinstance(c, Figura) and c.t_in > 0.5: ev.append(dict(t=c.t_in, som="pop"))
        ev.sort(key=lambda e: e["t"]); ev2 = []
        for e in ev:                                     # nada de pops amontoados: no máximo um a cada 0,6 s
            if e["som"] == "pop" and ev2 and e["t"] - ev2[-1]["t"] < 0.6: continue
            ev2.append(e)
        json.dump(ev2, open(os.path.join(AUDIO, "eventos.json"), "w"), indent=0)
        subprocess.run([sys.executable, os.path.join(RAIZ, "som", "mix.py"), os.path.join(AUDIO, "narracao.wav"), os.path.join(AUDIO, "eventos.json"), os.path.join(AUDIO, "mix.wav")], check=True)
        print(len(ev2), "efeitos;", os.path.join(AUDIO, "mix.wav"))
    elif cmd == "placas":
        placas(); print("ok")
    elif cmd == "prancha":
        prancha(montar(), TP.FR, titulo, os.path.join(HERE, "prancha.jpg"))
    elif cmd == "quadro":
        F = montar(); t = float(sys.argv[2])
        cv2.imwrite(sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, f"q_{t:.1f}.png"), (np.clip(F.quadro(t), 0, 1) * 255).astype(np.uint8))
    elif cmd == "trecho":
        F = montar(); a, b = float(sys.argv[2]), float(sys.argv[3])
        mix = os.path.join(AUDIO, "mix.wav")
        print(F.render(os.path.join(HERE, f"trecho_{a:.0f}_{b:.0f}.mp4"), a, b, audio=mix if os.path.exists(mix) else os.path.join(AUDIO, "narracao.wav")))
    elif cmd == "render":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 4
        print(render_planos(montar(), cena, os.path.join(HERE, "video_mudo.mp4"), n))
    else:
        sys.exit(__doc__)
