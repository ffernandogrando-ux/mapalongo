"""Motor do canal longo (16:9, 1920x1080, 30 fps).

Ideia: cada plano é uma PLACA estática renderizada uma vez pelo motor do canal curto (textura autoral,
territórios levantados, 3D com horizonte), um pouco maior que a tela. Por quadro, a câmera só faz uma
deriva lenta (zoom, giro e deslocamento: nunca parada) e as CAMADAS animadas (etiquetas, setas, contornos
que se desenham, números contando, figuras) vão por cima, presas ao mapa. Isso deixa 10 minutos de vídeo
baratos de renderizar e com o mesmo visual do curto.

O motor do curto (mapas/docs/estilo_cinema/gerar_quadros.py) não é alterado: só trocamos W e H dele
enquanto a placa é renderizada.
"""
import os, sys, math, subprocess
MAPAS = os.environ.get("MAPAS_ROOT", "/home/user/mapas")
sys.path.insert(0, MAPAS + "/docs/estilo_cinema")
os.environ.setdefault("VISUAL_DADOS", MAPAS + "/proto/data")
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFilter
from shapely.affinity import translate
import gerar_quadros as G

W, H, FPS = 1920, 1080, 30
G.W, G.H = W, H

# Países do outro lado da linha de data, deslocados 360° (Pacífico inteiro num quadro só).
_p = G.paises()
if not any(n.endswith("#w") for n, _ in _p):
    _p += [(n + "#w", translate(g, -360)) for n, g in _p if g.bounds[2] > 60]


# ------------------------------------------------------------------------------------------- curvas
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def suave(x): x = clamp(x); return x * x * (3 - 2 * x)
def sai(x): x = clamp(x); return 1 - (1 - x) ** 3
def volta(x, s=1.7):
    x = clamp(x); x -= 1; return 1 + x * x * ((s + 1) * x + s)
def lerp(a, b, k): return a + (b - a) * k


# ------------------------------------------------------------------------------------------- placa
class Placa:
    """Mapa renderizado uma vez, `escala` vezes maior que a tela. geo(lon, lat) -> px da placa."""
    def __init__(self, cam_kw, focos=(), paleta=None, escala=1.3, linhas_estados=True, cache=None):
        self.PW, self.PH = int(W * escala) // 2 * 2, int(H * escala) // 2 * 2
        P = dict(G.PALETAS[paleta or G.PADRAO])
        G.W, G.H = self.PW, self.PH
        try:
            self.cam = G.Camera(**cam_kw)
            if cache and os.path.exists(cache):
                self.img = cv2.imread(cache).astype(np.float32) / 255
            else:
                im = G.render_quadro(P, cam_kw, list(focos), None, linhas_estados)
                self.img = cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR).astype(np.float32) / 255
                if cache:   # a pasta das placas não vai para o Git: sem criá-la, o imwrite falhava calado e TODA execução refazia as placas (~13 min)
                    os.makedirs(os.path.dirname(os.path.abspath(cache)), exist_ok=True)
                    if not cv2.imwrite(cache, (self.img * 255).astype(np.uint8)): raise IOError('placa não salva: ' + cache)
        finally:
            G.W, G.H = W, H
        self.P = P

    def geo(self, lon, lat):
        G.W, G.H = self.PW, self.PH
        try: return self.cam.tela(lon, lat)
        finally: G.W, G.H = W, H

    def contorno(self, g, tol=0.02):
        """Anéis da geometria em px da placa (para desenhar o contorno que se desenha)."""
        gs = g.simplify(tol)
        polys = [gs] if gs.geom_type == "Polygon" else [p for p in getattr(gs, "geoms", []) if p.geom_type == "Polygon"]
        out = []
        for p in polys:
            c = np.array(p.exterior.coords)
            if len(c) < 8: continue
            out.append(np.array([self.geo(lo, la) for lo, la in c], np.float32))
        return out


# ------------------------------------------------------------------------------------------- câmera
class Deriva:
    """Câmera lenta: zoom z0->z1, giro r0->r1 (graus), centro c0->c1 (em fração da placa, 0..1).
    O plano nasce um pouco mais aberto ou fechado (entrada) e nunca para."""
    def __init__(self, z=(1.0, 1.07), rot=(0.0, 1.2), c0=(0.5, 0.5), c1=None, curva=None):
        self.z, self.rot, self.c0, self.c1 = z, rot, c0, c1 or c0
        self.curva = curva or (lambda k: k)

    def matriz(self, placa, k, extra_z=1.0, extra_rot=0.0):
        k = self.curva(clamp(k))
        z = lerp(*self.z, k) * extra_z; r = lerp(*self.rot, k) + extra_rot
        cx = lerp(self.c0[0], self.c1[0], k) * placa.PW; cy = lerp(self.c0[1], self.c1[1], k) * placa.PH
        base = W / placa.PW * 1.06          # margem para o giro não mostrar a borda
        M = cv2.getRotationMatrix2D((cx, cy), r, base * z)
        M[0, 2] += W / 2 - cx; M[1, 2] += H / 2 - cy
        return M


class Caminho:
    """Câmera por chaves: [(t, dict(geo=(lon,lat) ou c=(fx,fy), z=1.0, rot=0.0)), ...]. Entre chaves, move com
    suavidade (o enquadramento muda sem corte); depois da última, continua derivando devagar (nunca para)."""
    def __init__(self, chaves, dur_mov=1.6, deriva_z=0.012, deriva_rot=0.35):
        self.chaves = sorted(chaves, key=lambda c: c[0]); self.dur_mov = dur_mov
        self.dz, self.drot = deriva_z, deriva_rot

    def _estado(self, placa, c):
        if "geo" in c: x, y = placa.geo(*c["geo"])
        else: x, y = c.get("c", (0.5, 0.5))[0] * placa.PW, c.get("c", (0.5, 0.5))[1] * placa.PH
        return np.array([x, y, c.get("z", 1.0), c.get("rot", 0.0)], float)

    def _chaves_px(self, placa):
        """Estados das chaves em px da placa, já presos dentro dela (calculado uma vez por placa)."""
        k = id(placa)
        if getattr(self, "_cache_k", None) != k:
            base = W / placa.PW * 1.06; est = []
            for _, c in self.chaves:
                e = self._estado(placa, c); e[0], e[1] = _dentro(placa, e[0], e[1], base * e[2] * 0.97, e[3]); est.append(e)
            self._cache_k, self._cache = k, est
        return self._cache

    def matriz_t(self, placa, t, extra_z=1.0, extra_rot=0.0):
        """Sem trancos: cada movimento entre chaves começa e termina com velocidade zero (curva suave), as chaves já
        vêm presas dentro da placa e a deriva é uma função contínua do tempo (não muda de sentido de uma vez)."""
        ks = self.chaves; est = self._chaves_px(placa)
        i = max([j for j, (tk, _) in enumerate(ks) if tk <= t] or [0])
        e = est[i].copy()
        if i + 1 < len(ks):
            t1 = ks[i + 1][0]; d = min(self.dur_mov, max(0.6, t1 - ks[i][0]))
            if t > t1 - d:
                u = clamp((t - (t1 - d)) / d); k = u * u * u * (u * (u * 6 - 15) + 10)     # smootherstep
                e = est[i] * (1 - k) + est[i + 1] * k
        dt = t - ks[0][0]
        z = e[2] * (1 + self.dz * dt) * extra_z
        r = e[3] + self.drot * 3 * math.sin(dt / 4.0) + extra_rot
        base = W / placa.PW * 1.06
        x, y = _dentro(placa, e[0], e[1], base * z, r)
        M = cv2.getRotationMatrix2D((x, y), r, base * z)
        M[0, 2] += W / 2 - x; M[1, 2] += H / 2 - y
        return M


def _dentro(placa, x, y, esc, rot):
    """Segura o centro da câmera para a tela nunca sair da placa (fora dela o mapa espelharia)."""
    a = math.radians(abs(rot)); hw = (W / 2 * math.cos(a) + H / 2 * math.sin(a)) / esc; hh = (W / 2 * math.sin(a) + H / 2 * math.cos(a)) / esc
    x = placa.PW / 2 if hw * 2 >= placa.PW else min(max(x, hw), placa.PW - hw)
    y = placa.PH / 2 if hh * 2 >= placa.PH else min(max(y, hh), placa.PH - hh)
    return x, y


def aplica(M, xy):
    x, y = xy; return (M[0, 0] * x + M[0, 1] * y + M[0, 2], M[1, 0] * x + M[1, 1] * y + M[1, 2])


# ------------------------------------------------------------------------------------------- camadas
class Camada:
    t_in, t_out = 0.0, 1e9
    def vivo(self, t): return self.t_in - 0.01 <= t <= self.t_out + 0.35
    def desenha(self, lay, t, M, placa): ...


def _pop(t, t_in, t_out, dur=0.28):
    """escala e opacidade de entrada com mola e saída rápida."""
    if t < t_in: return 0, 0
    e = volta((t - t_in) / dur); s = 0.55 + 0.45 * e
    a = clamp((t - t_in) / 0.12)
    if t > t_out: k = clamp((t - t_out) / 0.25); s *= 1 - 0.3 * k; a *= 1 - k
    return s, a


MARGEM = 0.06      # área segura: nenhuma etiqueta encosta na borda (6 % de cada lado)


def seguro(xy, im):
    mx, my = W * MARGEM, H * MARGEM
    return (min(max(xy[0], mx + im.width / 2), W - mx - im.width / 2), min(max(xy[1], my + im.height / 2), H - my - im.height / 2))


def _cola(lay, im, xy, s=1.0, a=1.0):
    if a <= 0.01 or s <= 0.02: return
    if abs(s - 1) > 0.01: im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BILINEAR)
    if a < 0.99:
        im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    x, y = xy[0] - im.width / 2, xy[1] - im.height / 2; ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    if fx > 0.02 or fy > 0.02:     # desloca a fração de pixel com interpolação: a etiqueta anda junto com o mapa, sem tremer
        im = im.transform((im.width + 1, im.height + 1), Image.AFFINE, (1, 0, -fx, 0, 1, -fy), resample=Image.BILINEAR)
    lay.alpha_composite(im, (ix, iy))


class Chip(Camada):
    """Etiqueta branca presa a um lugar (geo=(lon,lat)) ou à tela (tela=(x,y)). Com conta=(de, até, formato, dur)
    o número conta dentro da etiqueta."""
    def __init__(self, texto, t_in, t_out, geo=None, tela=None, size=40, cor=None, dy=0, conta=None):
        self.texto, self.t_in, self.t_out, self.geo, self.tela, self.size, self.cor, self.dy, self.conta = texto, t_in, t_out, geo, tela, size, cor, dy, conta
        self._cache = {}
    def img(self, txt):
        if txt not in self._cache: self._cache[txt] = G.chip_img(txt, self.size, self.cor)
        return self._cache[txt]
    def desenha(self, lay, t, M, placa):
        s, a = _pop(t, self.t_in, self.t_out)
        txt = self.texto
        if self.conta:
            de, ate, fmt, dur = self.conta; k = sai((t - self.t_in) / dur)
            txt = fmt(lerp(de, ate, k))
        xy = self.tela or aplica(M, placa.geo(*self.geo)); xy = (xy[0], xy[1] + self.dy)
        im = self.img(txt); _cola(lay, im, seguro(xy, im), s, a)


class Lugar(Camada):
    """Lugar citado na fala: pino branco com aro no ponto exato do mapa + etiqueta logo acima, na palavra."""
    def __init__(self, texto, geo, t_in, t_out, size=38, cor="#E0461A", lado="cima"):
        self.texto, self.geo, self.t_in, self.t_out, self.lado = texto, geo, t_in, t_out, lado
        self.chip = G.chip_img(texto, size, None)
        r = 16; im = Image.new("RGBA", (r * 4, r * 4), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.ellipse([r, r, r * 3, r * 3], fill=(255, 255, 255, 255)); d.ellipse([r + 6, r + 6, r * 3 - 6, r * 3 - 6], fill=G.rgb(cor) + (255,))
        self.pino = G.com_sombra(im, 5, 0.5, (2, 4))
    def desenha(self, lay, t, M, placa):
        s, a = _pop(t, self.t_in, self.t_out)
        x, y = aplica(M, placa.geo(*self.geo))
        _cola(lay, self.pino, (x, y), s, a)
        dy = -(self.chip.height / 2 + 14) if self.lado == "cima" else (self.chip.height / 2 + 14)
        _cola(lay, self.chip, seguro((x, y + dy * (0.7 + 0.3 * s)), self.chip), s, a)


class Nome(Camada):
    """Nome de lugar em caixa-alta, entra subindo e com o espaçamento abrindo."""
    def __init__(self, texto, t_in, t_out, geo=None, tela=None, size=46):
        self.texto, self.t_in, self.t_out, self.geo, self.tela, self.size = texto, t_in, t_out, geo, tela, size
        self.im = G.nome_img(texto, size)
    def desenha(self, lay, t, M, placa):
        a = clamp((t - self.t_in) / 0.4) * (1 - clamp((t - self.t_out) / 0.3))
        xy = self.tela or aplica(M, placa.geo(*self.geo))
        _cola(lay, self.im, (xy[0], xy[1] + 18 * (1 - sai((t - self.t_in) / 0.5))), 1.0, a)


class Seta(Camada):
    """Seta grossa que se desenha ao longo de um caminho geográfico (vento, corrente, água quente)."""
    def __init__(self, pts_geo, t_in, t_out, dur=1.2, cor=(255, 255, 255), larg=14, n=60):
        self.pts_geo, self.t_in, self.t_out, self.dur, self.cor, self.larg = pts_geo, t_in, t_out, dur, cor, larg
        g = np.array(pts_geo, float); u = np.linspace(0, 1, len(g)); uu = np.linspace(0, 1, n)
        self.den = np.column_stack([np.interp(uu, u, g[:, 0]), np.interp(uu, u, g[:, 1])])
        self._px = None
    def desenha(self, lay, t, M, placa):
        if self._px is None: self._px = np.array([placa.geo(lo, la) for lo, la in self.den])
        k = sai((t - self.t_in) / self.dur); a = 1 - clamp((t - self.t_out) / 0.3)
        m = max(2, int(len(self._px) * k))
        pts = [aplica(M, p) for p in self._px[:m]]
        if len(pts) < 2 or a <= 0: return
        d = ImageDraw.Draw(lay); A = int(255 * a)
        for c, w in (((20, 24, 40, int(200 * a)), self.larg + 8), (self.cor + (A,), self.larg)):
            d.line(pts, fill=c, width=int(w), joint="curve")
        (x0, y0), (x1, y1) = pts[-2], pts[-1]; ang = math.atan2(y1 - y0, x1 - x0); cab = self.larg * 2.4
        tri = lambda q: [(x1 + math.cos(ang) * cab * q, y1 + math.sin(ang) * cab * q),
                         (x1 + math.cos(ang + 2.5) * cab * q, y1 + math.sin(ang + 2.5) * cab * q),
                         (x1 + math.cos(ang - 2.5) * cab * q, y1 + math.sin(ang - 2.5) * cab * q)]
        d.polygon(tri(1.25), fill=(20, 24, 40, int(200 * a))); d.polygon(tri(1.0), fill=self.cor + (A,))


class Linha(Camada):
    """Linha geográfica que se desenha (rio, estrada): lista de trechos [(lon, lat), ...]."""
    def __init__(self, trechos, t_in, dur=1.5, t_out=1e9, cor=(90, 200, 255), larg=7):
        self.trechos, self.t_in, self.dur, self.t_out, self.cor, self.larg = trechos, t_in, dur, t_out, cor, larg
        self._px = None
    def desenha(self, lay, t, M, placa):
        if self._px is None: self._px = [np.array([placa.geo(lo, la) for lo, la in tr]) for tr in self.trechos]
        k = sai((t - self.t_in) / self.dur); a = 1 - clamp((t - self.t_out) / 0.4)
        if k <= 0 or a <= 0: return
        tot = sum(len(p) for p in self._px); m = int(tot * k)
        d = ImageDraw.Draw(lay)
        for p in self._px:
            if m <= 1: break
            pts = [aplica(M, q) for q in p[:m]]; m -= len(p)
            if len(pts) > 1:
                d.line(pts, fill=(10, 30, 60, int(180 * a)), width=self.larg + 6, joint="curve")
                d.line(pts, fill=self.cor + (int(255 * a),), width=self.larg, joint="curve")


class Contorno(Camada):
    """Linha brilhante que se desenha em volta de um território (a assinatura do canal)."""
    def __init__(self, g, t_in, dur=1.1, t_out=1e9, cor=(255, 255, 255), larg=5):
        self.g, self.t_in, self.dur, self.t_out, self.cor, self.larg = g, t_in, dur, t_out, cor, larg
        self._an = None
    def desenha(self, lay, t, M, placa):
        if self._an is None: self._an = placa.contorno(self.g)
        k = sai((t - self.t_in) / self.dur); a = 1 - clamp((t - self.t_out) / 0.4)
        if k <= 0 or a <= 0: return
        brilho = Image.new("RGBA", lay.size, (0, 0, 0, 0)); d = ImageDraw.Draw(brilho)
        for an in self._an:
            m = max(2, int(len(an) * k)); pts = [aplica(M, p) for p in an[:m]]
            d.line(pts, fill=self.cor + (int(255 * a),), width=self.larg, joint="curve")
        glow = brilho.filter(ImageFilter.GaussianBlur(7))
        lay.alpha_composite(glow); lay.alpha_composite(glow); lay.alpha_composite(brilho)


class Figura(Camada):
    """Ilustração da biblioteca (boneco/objeto) em pé num lugar, com sombra."""
    def __init__(self, nome, geo, t_in, t_out, larg=200, dy=0):
        self.nome, self.geo, self.t_in, self.t_out, self.larg, self.dy = nome, geo, t_in, t_out, larg, dy
        im = G.acabamento(Image.open(os.path.join(G.PNG, nome + ".png")).convert("RGBA"), "cinema")
        im = im.resize((larg, int(im.height * larg / im.width)), Image.LANCZOS)
        self.im = G.com_sombra(im, 10, 0.45, (8, 12))
    def desenha(self, lay, t, M, placa):
        s, a = _pop(t, self.t_in, self.t_out, 0.35)
        x, y = aplica(M, placa.geo(*self.geo))
        _cola(lay, self.im, (x, y - self.im.height * 0.45 * s + self.dy), s, a)


class Minimapa(Camada):
    """Mapa pequeno de localização no canto (só cabe no 16:9)."""
    def __init__(self, foco, t_in, t_out, canto=(1730, 160), larg=280):
        self.t_in, self.t_out, self.canto = t_in, t_out, canto
        from shapely.geometry import box
        x0, x1, y0, y1 = -82, -34, -56, 13; esc = larg / (x1 - x0); alt = int((y1 - y0) * esc)
        im = Image.new("RGBA", (larg + 24, alt + 24), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, larg + 23, alt + 23], 18, fill=(12, 30, 48, 215), outline=(255, 255, 255, 210), width=2)
        pt = lambda lo, la: (12 + (lo - x0) * esc, 12 + (y1 - la) * esc)
        for n, g in G.paises():
            if n.endswith("#w") or not g.intersects(box(x0, y0, x1, y1)): continue
            for p in (g.geoms if g.geom_type == "MultiPolygon" else [g]):
                d.polygon([pt(*c) for c in p.simplify(0.15).exterior.coords], fill=(232, 214, 164, 255) if n == "Brazil" else (118, 128, 108, 255))
        for p in (foco.geoms if foco.geom_type == "MultiPolygon" else [foco]):
            d.polygon([pt(*c) for c in p.simplify(0.1).exterior.coords], fill=(255, 90, 50, 255))
        self.im = G.com_sombra(im, 8, 0.5, (4, 6))
    def desenha(self, lay, t, M, placa):
        a = clamp((t - self.t_in) / 0.4) * (1 - clamp((t - self.t_out) / 0.3))
        _cola(lay, self.im, (self.canto[0] + 40 * (1 - sai((t - self.t_in) / 0.5)), self.canto[1]), 1.0, a)


class Painel(Camada):
    """Camada de tela cheia desenhada por uma função f(lay, k, t) com k = progresso 0..1 desde t_in."""
    def __init__(self, f, t_in, t_out, dur=1.0):
        self.f, self.t_in, self.t_out, self.dur = f, t_in, t_out, dur
    def desenha(self, lay, t, M, placa):
        self.f(lay, clamp((t - self.t_in) / self.dur), t)


# ------------------------------------------------------------------------------------------- plano
class Plano:
    """Um enquadramento: placa (mapa sem destaque), placa acesa opcional (território levantado, revelado
    em t_acende por um fade), deriva de câmera e camadas. fundo: 'mapa' ou função f(t)->float BGR (gráfico etc.)."""
    def __init__(self, nome, t0, t1, placa=None, acesas=(), deriva=None, camadas=(), desfoque=0.0, escurece=0.0):
        """acesas: [(t, placa, 'fade' | 'cortina' | 'cortina_esq'), ...]: a partir de t a placa troca para essa
        (território aceso, cor nova), com fusão de 0,6 s ou cortina da esquerda para a direita (ou ao contrário) em 1,6 s."""
        self.nome, self.t0, self.t1, self.placa = nome, t0, t1, placa
        self.acesas = sorted(acesas, key=lambda a: a[0])
        self.deriva = deriva or Deriva(); self.camadas = list(camadas); self.desfoque, self.escurece = desfoque, escurece

    def quadro(self, t, extra_z=1.0, extra_rot=0.0):
        if isinstance(self.deriva, Caminho): M = self.deriva.matriz_t(self.placa, t, extra_z, extra_rot)
        else: M = self.deriva.matriz(self.placa, (t - self.t0) / max(self.t1 - self.t0, 0.1), extra_z, extra_rot)
        wa = lambda im: cv2.warpAffine(im, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        atual, f = self.placa, None
        ativas = [a for a in self.acesas if a[0] <= t]
        if not ativas: f = wa(self.placa.img)
        else:
            ta, pa, modo = ativas[-1]
            ant = ativas[-2][1] if len(ativas) > 1 else self.placa
            if modo.startswith("cortina"):
                k = suave((t - ta) / 1.6)
                if k >= 1: f = wa(pa.img)
                else:
                    a_, b_ = wa(ant.img), wa(pa.img)
                    x = np.linspace(0, 1, W, dtype=np.float32)
                    if modo == "cortina_esq": x = 1 - x
                    m = np.clip((k * 1.25 - x) / 0.25, 0, 1)[None, :, None]
                    f = a_ * (1 - m) + b_ * m
            else:
                k = suave((t - ta) / 0.6)
                f = wa(pa.img) if k >= 1 else wa(ant.img) * (1 - k) + wa(pa.img) * k
        if self.desfoque: f = cv2.GaussianBlur(f, (0, 0), self.desfoque)
        if self.escurece: f = f * (1 - self.escurece) + np.array([0.13, 0.08, 0.03], np.float32) * self.escurece
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for c in self.camadas:
            if c.vivo(t): c.desenha(lay, t, M, self.placa)
        rgba = np.asarray(lay).astype(np.float32) / 255
        a = rgba[..., 3:4]; f = f * (1 - a) + rgba[..., 2::-1] * a
        return f


class Filme:
    """Sequência de planos. Troca: 'fusao' (dissolve 0,5 s) ou 'mergulho' (o plano que sai mergulha
    girando e acelerando com desfoque, o novo continua o mergulho)."""
    def __init__(self, planos, trocas, dur):
        self.planos, self.trocas, self.dur = planos, trocas, dur

    def plano_em(self, t):
        for i, p in enumerate(self.planos):
            if p.t0 <= t < p.t1: return i
        return len(self.planos) - 1

    def quadro(self, t):
        i = self.plano_em(t); p = self.planos[i]
        # entrada do plano i (troca com o anterior)
        if i > 0:
            tipo = self.trocas[i]; d = 0.9 if tipo == "mergulho" else 0.5
            k = (t - p.t0) / d
            if k < 1:
                q = self.planos[i - 1]
                if tipo == "mergulho":
                    e = k ** 2
                    a = q.quadro(t, extra_z=1 + 1.4 * e, extra_rot=-18 * e)
                    b = p.quadro(t, extra_z=0.72 + 0.28 * sai(k), extra_rot=10 * (1 - sai(k)))
                    m = suave((k - 0.25) / 0.5)
                    f = a * (1 - m) + b * m
                    blur = 6 * math.sin(math.pi * k)
                    return cv2.GaussianBlur(f, (0, 0), blur) if blur > 0.5 else f
                m = suave(k)
                return q.quadro(t) * (1 - m) + p.quadro(t) * m
        return p.quadro(t)

    def render(self, saida, t_ini=0.0, t_fim=None, audio=None, crf=18):
        t_fim = t_fim or self.dur
        cmd = ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
        if audio: cmd += ["-ss", f"{t_ini:.3f}", "-t", f"{t_fim - t_ini:.3f}", "-i", audio, "-c:a", "aac", "-b:a", "192k", "-shortest"]
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p", saida]
        pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        n0, n1 = int(round(t_ini * FPS)), int(round(t_fim * FPS))
        for n in range(n0, n1):
            f = self.quadro(n / FPS)
            pr.stdin.write((np.clip(f, 0, 1) * 255).astype(np.uint8).tobytes())
        pr.stdin.close(); pr.wait()
        return saida


# ------------------------------------------------------------------------------------------- conferência da câmera
def checar_camera(filme, passo=1):
    """Mede, quadro a quadro, quanto a tela anda (pontos de uma grade levados pela câmera) e acusa TRANCOS:
    quadros em que a velocidade muda de repente (aceleração acima do limite). Ignora as trocas de plano."""
    g = np.array([[x, y] for x in (W * 0.2, W * 0.5, W * 0.8) for y in (H * 0.2, H * 0.5, H * 0.8)])
    def pos(p, t):
        if isinstance(p.deriva, Caminho): M = p.deriva.matriz_t(p.placa, t)
        else: M = p.deriva.matriz(p.placa, (t - p.t0) / max(p.t1 - p.t0, 0.1))
        Mi = cv2.invertAffineTransform(M); M2 = M                          # ponto fixo do mapa (o do centro em t)
        return M
    trancos = []
    for p in filme.planos:
        n0, n1 = int(math.ceil(p.t0 * FPS)) + 1, int(p.t1 * FPS) - 1
        pts_mapa = None; prev = None; vprev = None
        for n in range(n0, n1, passo):
            t = n / FPS; M = pos(p, t)
            if pts_mapa is None:
                Mi = cv2.invertAffineTransform(M); pts_mapa = np.array([aplica(Mi, q) for q in g])
            tela = np.array([aplica(M, q) for q in pts_mapa])
            if prev is not None:
                v = tela - prev
                if vprev is not None:
                    a = np.abs(v - vprev).max()
                    if a > 1.5: trancos.append((round(t, 2), p.nome, round(float(a), 1)))
                vprev = v
            prev = tela
    return trancos
