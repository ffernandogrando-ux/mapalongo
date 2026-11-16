#!/usr/bin/env python3
"""Prancha 16:9 do vídeo longo do El Niño: um quadro por bloco, com o tempo e a frase.

Usa o motor do canal curto (mapas/docs/estilo_cinema/gerar_quadros.py) sem alterar nada nele:
só troca o tamanho do quadro para 1920x1080 neste processo.
    VISUAL_DADOS=/home/user/mapas/proto/data python3 -I prancha.py [1,2,...]
"""
import os, sys, math
MAPAS = os.environ.get("MAPAS_ROOT", "/home/user/mapas")
sys.path.insert(0, MAPAS + "/docs/estilo_cinema")
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFilter
from shapely.affinity import translate
from shapely.geometry import box, Polygon
import gerar_quadros as G

W, H = G.W, G.H = 1920, 1080
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, "quadros"); os.makedirs(OUT, exist_ok=True)
P = dict(G.PALETAS[G.PADRAO]); T = G.TEMAS

# países do outro lado da linha de data, deslocados 360° (Pacífico inteiro num quadro só)
_p = G.paises()
if not any(n.endswith("#w") for n, _ in _p):
    _p += [(n + "#w", translate(g, -360)) for n, g in _p if g.bounds[2] > 60]
BR = G.pais("Brazil")
NORTE = G.estados("Amazonas", "Pará", "Roraima", "Amapá", "Acre", "Rondônia", "Tocantins")
NORDESTE = G.estados("Maranhão", "Piauí", "Ceará", "Rio Grande do Norte", "Paraíba", "Pernambuco", "Alagoas", "Sergipe", "Bahia")
SUL = G.estados("Rio Grande do Sul", "Santa Catarina", "Paraná")
RS = G.estados("Rio Grande do Sul")


def chip(lay, txt, xy, size=40, cor=None): G.cola(lay, G.chip_img(txt, size, cor), xy)
def nome(lay, txt, xy, size=46): G.cola(lay, G.nome_img(txt, size), xy)


def seta(lay, pts, cor=(255, 255, 255), larg=14, cab=34):
    """Seta grossa com borda escura (caminho do vento ou da água)."""
    d = ImageDraw.Draw(lay); pts = [tuple(map(float, p)) for p in pts]
    for c, w in (((20, 24, 40, 230), larg + 8), (cor + (255,), larg)):
        d.line(pts, fill=c, width=int(w), joint="curve")
    (x0, y0), (x1, y1) = pts[-2], pts[-1]; a = math.atan2(y1 - y0, x1 - x0)
    tri = lambda k: [(x1 + math.cos(a) * cab * k, y1 + math.sin(a) * cab * k),
                     (x1 + math.cos(a + 2.5) * cab * k, y1 + math.sin(a + 2.5) * cab * k),
                     (x1 + math.cos(a - 2.5) * cab * k, y1 + math.sin(a - 2.5) * cab * k)]
    d.polygon(tri(1.25), fill=(20, 24, 40, 230)); d.polygon(tri(1.0), fill=cor + (255,))


def minimapa(lay, foco, canto=(1700, 150), larg=300):
    """Mapa pequeno de localização (só no 16:9): América do Sul em vetor, com o quadro do lugar."""
    x0, x1, y0, y1 = -82, -34, -56, 13; esc = larg / (x1 - x0); alt = int((y1 - y0) * esc)
    im = Image.new("RGBA", (larg + 24, alt + 24), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, larg + 23, alt + 23], 18, fill=(12, 30, 48, 210), outline=(255, 255, 255, 200), width=2)
    pt = lambda lo, la: (12 + (lo - x0) * esc, 12 + (y1 - la) * esc)
    for n, g in G.paises():
        if not g.intersects(box(x0, y0, x1, y1)): continue
        for p in (g.geoms if g.geom_type == "MultiPolygon" else [g]):
            d.polygon([pt(*c) for c in p.simplify(0.15).exterior.coords],
                      fill=(232, 214, 164, 255) if n == "Brazil" else (120, 130, 110, 255))
    bx = foco.bounds; d.rectangle([*pt(bx[0], bx[3]), *pt(bx[2], bx[1])], outline=(255, 70, 50, 255), width=4)
    G.cola(lay, G.com_sombra(im, 8, 0.5, (4, 6)), canto)


def faixa_quente():
    """Língua de água quente no Pacífico equatorial (mais larga perto da América do Sul)."""
    xs = np.linspace(-200, -81, 40); w = np.interp(xs, [-200, -150, -100, -81], [3, 6, 9, 7])
    return Polygon(list(zip(xs, w)) + list(zip(xs[::-1], -w[::-1] - 1))).buffer(1.5)


def oni():
    s, v = [], []
    for l in open(os.path.join(HERE, "oni.txt")).read().split("\n")[1:]:
        p = l.split()
        if len(p) == 4: s.append(int(p[1]) + ["DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ"].index(p[0]) / 12); v.append(float(p[3]))
    return np.array(s), np.array(v)


def grafico(fundo):
    """Bloco 'gráfico de série' sobre o mapa desfocado: índice do El Niño (NOAA/ONI), 1950 até hoje."""
    im = fundo.filter(ImageFilter.GaussianBlur(14)); im = Image.blend(im, Image.new("RGB", im.size, (8, 20, 34)), 0.45)
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    X0, X1, Y0, Y1 = 170, 1750, 230, 900
    d.rounded_rectangle([X0 - 70, Y0 - 120, X1 + 70, Y1 + 90], 34, fill=(255, 255, 255, 246))
    d.text((X0, Y0 - 70), "Quanto o Pacífico ficou mais quente que o normal", font=G.fonte(G.FONT_X, 44), fill=(20, 22, 28), anchor="lm")
    a, v = oni(); vmin, vmax = -2.2, 2.8
    px = lambda t: X0 + (t - 1950) / (2027 - 1950) * (X1 - X0)
    py = lambda y: Y1 - (y - vmin) / (vmax - vmin) * (Y1 - Y0)
    for y in (-2, -1, 0, 1, 2):
        d.line([(X0, py(y)), (X1, py(y))], fill=(200, 205, 214) if y else (90, 95, 110), width=2 if y else 3)
        d.text((X0 - 16, py(y)), f"{y:+d} °C".replace("+0", "0").replace("-", "−"), font=G.fonte(G.FONT_SB, 26), fill=(90, 95, 110), anchor="rm")
    for ano in range(1950, 2030, 10): d.text((px(ano), Y1 + 34), str(ano), font=G.fonte(G.FONT_SB, 28), fill=(90, 95, 110), anchor="mm")
    for i in range(len(a) - 1):
        c = (230, 72, 15) if v[i] >= 0.5 else (42, 143, 214) if v[i] <= -0.5 else (150, 155, 165)
        d.line([(px(a[i]), py(v[i])), (px(a[i + 1]), py(v[i + 1]))], fill=c, width=5)
    for ano, rot in ((1983.0, "1982–83"), (1997.9, "1997–98"), (2015.9, "2015–16"), (2023.9, "2023–24"), (a[-1], "agora")):
        i = int(np.argmin(np.abs(a - ano))); x, y = px(a[i]), py(v[i])
        d.ellipse([x - 11, y - 11, x + 11, y + 11], fill=(230, 72, 15), outline=(255, 255, 255), width=4)
        chip(lay, rot, (x - 70 if rot == "agora" else x, y - 58), 30, "#FF7A1A" if rot == "agora" else None)
    im = im.convert("RGBA"); im.alpha_composite(lay); return im.convert("RGB")


def lista(fundo, titulo, itens):
    im = fundo.filter(ImageFilter.GaussianBlur(10)); im = Image.blend(im, Image.new("RGB", im.size, (8, 20, 34)), 0.35).convert("RGBA")
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.rounded_rectangle([1010, 170, 1820, 910], 34, fill=(255, 255, 255, 246))
    d.text((1070, 250), titulo, font=G.fonte(G.FONT_X, 44), fill=(20, 22, 28), anchor="lm")
    for k, (cor, txt) in enumerate(itens):
        y = 370 + k * 125
        d.ellipse([1070, y - 22, 1114, y + 22], fill=G.rgb(cor)); d.text((1092, y), str(k + 1), font=G.fonte(G.FONT_X, 28), fill=(255, 255, 255), anchor="mm")
        d.text((1140, y), txt, font=G.fonte(G.FONT_SB, 36), fill=(30, 34, 44), anchor="lm")
    im.alpha_composite(lay); return im.convert("RGB")


# ------------------------------------------------------------------- quadros (um por bloco do roteiro)
def q1():
    def pc(lay, cam, P, L):
        x, y = cam.tela(-62, -4); chip(lay, "Norte: menos chuva", (x, y - 120), 42, T["seca"]["acento"])
        x, y = cam.tela(-52, -27); chip(lay, "Sul: mais chuva", (x + 40, y - 110), 42, T["cheia"]["acento"])
    return G.render_quadro(P, dict(lon=-54, lat=-24, wdeg=26, rot=-8, persp=True, horizonte=0.16),
                           [dict(g=BR, lift=0, sec=True), dict(g=NORTE, lift=26, tema="seca", divisas=False), dict(g=SUL, lift=26, tema="cheia", divisas=False)], pc, False)


def q2():
    N34 = box(-170, -5, -120, 5)
    def pc(lay, cam, P, L):
        x, y = cam.tela(-145, 0); chip(lay, "+2,5 °C acima do normal", (x, y - 150), 44, "#FF7A1A")
        nome(lay, "OCEANO PACÍFICO", cam.tela(-150, -22), 50)
        x, y = cam.tela(-60, -12); nome(lay, "BRASIL", (x, y), 40)
    return G.render_quadro(P, dict(lon=-150, lat=-4, wdeg=150, rot=0, tilt=0.18),
                           [dict(g=faixa_quente(), lift=0, tema="calor", divisas=False), dict(g=BR, lift=10, divisas=False)], pc, False)


def q3():
    def pc(lay, cam, P, L):
        a = [cam.tela(lo, 9) for lo in (-95, -130, -165)]; seta(lay, a, (235, 240, 250))
        chip(lay, "ventos enfraquecem", (a[1][0], a[1][1] - 80), 36, "#9BB3C8")
        b = [cam.tela(lo, -6) for lo in (-185, -150, -110, -88)]; seta(lay, b, (255, 122, 26))
        chip(lay, "a água quente volta", (b[2][0], b[2][1] + 85), 36, "#FF7A1A")
        x, y = cam.tela(-76, -10); chip(lay, "Peru", (x + 20, y), 32)
    return G.render_quadro(P, dict(lon=-128, lat=-26, wdeg=58, rot=12, persp=True, horizonte=0.18),
                           [dict(g=faixa_quente(), lift=0, tema="calor", divisas=False), dict(g=BR, lift=0, sec=True)], pc, False)


def q4(): return grafico(Image.open(os.path.join(OUT, "02.png")))


def q5():
    """Satélite como prova (no vídeo final: imagem Copernicus da data do evento)."""
    Pr = dict(G.PALETAS["relevo"])
    def pc(lay, cam, P, L):
        chip(lay, "imagem de satélite", (250, 90), 38, "#FFFFFF"); x, y = cam.tela(-51.23, -30.03); chip(lay, "Porto Alegre", (x + 40, y - 70), 34)
        x, y = cam.tela(-51.25, -30.35); nome(lay, "GUAÍBA", (x - 120, y), 34)
    return G.render_quadro(Pr, dict(lon=-51.15, lat=-30.15, wdeg=1.6, rot=0, tilt=0.1), [], pc, False)


def q6():
    def pc(lay, cam, P, L):
        x, y = cam.tela(-53.2, -29.6); y -= L[-1]
        G.peca(lay, "obj_casa_alagada", (x - 60, y + 40), 210, P["boneco"])
        chip(lay, "risco alto de cheia", (x + 210, y - 170), 40, T["cheia"]["acento"])
        nome(lay, "RIO GRANDE DO SUL", (W / 2 - 160, 90), 44); minimapa(lay, RS)
    return G.render_quadro(P, dict(lon=-53.3, lat=-29.6, wdeg=14, rot=-10, tilt=0.30), [dict(g=BR, lift=0, sec=True), dict(g=RS, lift=22, tema="cheia")], pc)


def q7():
    AM = G.estados("Amazonas")
    def pc(lay, cam, P, L):
        x, y = cam.tela(-63, -4.5); y -= L[-1]
        G.peca(lay, "obj_navio", (x, y + 40), 220, P["boneco"]); chip(lay, "rios mais baixos", (x + 240, y - 130), 40, T["seca"]["acento"])
        nome(lay, "AMAZÔNIA", (W / 2 - 200, 90), 46); minimapa(lay, AM)
    return G.render_quadro(P, dict(lon=-62, lat=-4.5, wdeg=20, rot=14, tilt=0.30), [dict(g=BR, lift=0, sec=True), dict(g=AM, lift=22, tema="seca")], pc)


def q8():
    return lista(Image.open(os.path.join(OUT, "06.png")), "O que observar no seu estado",
                 [("#19B5E0", "Alertas da Defesa Civil"), ("#19B5E0", "Nível dos rios perto de você"), ("#D9A441", "Previsão de chuva do mês"), ("#D9A441", "Kit de emergência pronto")])


def q9():
    def pc(lay, cam, P, L): chip(lay, "o Brasil dividido ao meio", (W / 2, 120), 44, "#FFFFFF")
    return G.render_quadro(P, dict(lon=-50, lat=-30, wdeg=30, rot=6, persp=True, horizonte=0.2),
                           [dict(g=BR, lift=0, sec=True), dict(g=NORTE.union(NORDESTE), lift=26, tema="seca", divisas=False), dict(g=SUL, lift=26, tema="cheia", divisas=False)], pc, False)


QUADROS = [  # (tempo, bloco, frase, função)
    ("0:00", "Gancho", "O mesmo fenômeno vai deixar o Norte sem chuva e o Sul debaixo d'água.", q1),
    ("0:40", "O que aconteceu", "A água do Pacífico está dois graus e meio acima do normal.", q2),
    ("1:40", "Mecanismo", "Quando os ventos enfraquecem, a água quente volta para a América do Sul.", q3),
    ("4:00", "História", "Já aconteceu antes: 82, 97, 2015, 2023. E agora.", q4),
    ("5:20", "Prova (satélite)", "Em 2024, o Guaíba invadiu Porto Alegre.", q5),
    ("6:30", "Impacto: Sul", "No Sul, o risco de cheia nos rios é considerado alto.", q6),
    ("7:40", "Impacto: Norte", "Na Amazônia, rios como o Negro e o Branco já estão baixos.", q7),
    ("8:40", "Utilidade", "O que observar no seu estado nos próximos meses.", q8),
    ("9:45", "Ou seja", "Quando a água esquenta do outro lado do Pacífico, o Brasil inteiro sente.", q9),
]


def prancha(larg=600):
    hq = int(larg * H / W); gap, cab = 18, 96
    cols = 3; rows = math.ceil(len(QUADROS) / cols)
    pr = Image.new("RGB", (cols * (larg + gap) + gap, rows * (hq + cab + gap) + gap + 70), (14, 15, 18)); d = ImageDraw.Draw(pr)
    d.text((gap, 40), "El Niño (vídeo longo, 16:9): prancha de estilo, um quadro por bloco", font=G.fonte(G.FONT_X, 30), fill=(240, 240, 240), anchor="lm")
    for k, (tm, bl, fr, _) in enumerate(QUADROS):
        x = gap + (k % cols) * (larg + gap); y = 70 + gap + (k // cols) * (hq + cab + gap)
        f = os.path.join(OUT, f"{k + 1:02d}.png")
        if os.path.exists(f): pr.paste(Image.open(f).resize((larg, hq), Image.LANCZOS), (x, y))
        d.text((x, y + hq + 22), f"{tm} · {bl}", font=G.fonte(G.FONT_X, 22), fill=(255, 196, 80), anchor="lm")
        linhas, l = [], ""
        for w_ in fr.split():
            if G.fonte(G.FONT_SB, 19).getlength(l + " " + w_) > larg: linhas.append(l); l = w_
            else: l = (l + " " + w_).strip()
        d.multiline_text((x, y + hq + 40), "\n".join(linhas + [l]), font=G.fonte(G.FONT_SB, 19), fill=(220, 220, 220), spacing=4)
    p = os.path.join(HERE, "prancha.jpg"); pr.save(p, quality=90); return p


if __name__ == "__main__":
    qs = [int(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else range(1, len(QUADROS) + 1)
    for k in qs:
        im = QUADROS[k - 1][3](); p = os.path.join(OUT, f"{k:02d}.png"); im.save(p); print(p, flush=True)
    print(prancha())
