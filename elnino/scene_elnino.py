#!/usr/bin/env python3
"""El Niño 2026: vídeo longo 16:9.

    python3 -I scene_elnino.py placas            # renderiza (e guarda) as placas de mapa
    python3 -I scene_elnino.py prancha           # um quadro por plano, com o tempo e a frase
    python3 -I scene_elnino.py trecho 0 60       # trecho em vídeo (com a voz)
    python3 -I scene_elnino.py render 4          # vídeo inteiro em 4 processos
"""
import os, sys, json, math, re, unicodedata, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); RAIZ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(RAIZ, "motor"))
import numpy as np, cv2, shapefile
from PIL import Image, ImageDraw, ImageFilter
from shapely.geometry import box, Polygon, shape
import longo as L
from longo import G, W, H, Placa, Plano, Filme, Caminho, Chip, Nome, Seta, Linha, Contorno, Figura, Minimapa, Painel, clamp, sai, suave, lerp, volta

AUDIO = os.path.join(HERE, "audio"); PL = os.path.join(HERE, "placas")
T_ = G.TEMAS

# ------------------------------------------------------------------------------------------- tempo
import cena as C  # noqa: E402  parte comum: tempos da fala, prancha, linha de comando, render com cache por plano
TP = C.Tempos(AUDIO)
LINHA, FR, PAUSAS, CAPS, DUR = TP.LINHA, TP.FR, TP.PAUSAS, TP.CAPS, TP.DUR
S, E, T, PA, CAP = TP.S, TP.E, TP.T, TP.PA, TP.CAP


# ------------------------------------------------------------------------------------------- geografia
BR = G.pais("Brazil")
E_ = G.estados
NORTE = E_("Amazonas", "Pará", "Roraima", "Amapá", "Acre", "Rondônia", "Tocantins")
NORDESTE = E_("Maranhão", "Piauí", "Ceará", "Rio Grande do Norte", "Paraíba", "Pernambuco", "Alagoas", "Sergipe", "Bahia")
NNE = E_("Amazonas", "Pará", "Roraima", "Amapá", "Maranhão", "Piauí", "Ceará", "Rio Grande do Norte")
SUL = E_("Rio Grande do Sul", "Santa Catarina", "Paraná")
RS, RR, AM = E_("Rio Grande do Sul"), E_("Roraima"), E_("Amazonas")
SECO = E_("São Paulo", "Rio de Janeiro", "Minas Gerais", "Espírito Santo", "Goiás", "Mato Grosso", "Mato Grosso do Sul", "Distrito Federal")


def faixa(x0=-200, x1=-81, larg=(3, 6, 9, 7)):
    xs = np.linspace(x0, x1, 40); w = np.interp(xs, [x0, lerp(x0, x1, 0.4), lerp(x0, x1, 0.85), x1], larg)
    return Polygon(list(zip(xs, w)) + list(zip(xs[::-1], -w[::-1] - 1))).buffer(1.5)


from shapely.ops import unary_union
_TERRA = unary_union([g for n, g in G.paises() if g.intersects(box(-250, -30, -60, 30))]).buffer(0.15)
_faixa = faixa
def faixa(*a, **k): return _faixa(*a, **k).difference(_TERRA)     # a água quente não pinta a terra
QUENTE = faixa()                                     # El Niño: língua quente até o Peru
PISCINA = faixa(-235, -160, (8, 11, 10, 6))          # ano normal: água quente acumulada no oeste
FRIA_PERU = faixa(-120, -81, (2, 3, 5, 6))           # ano normal / La Niña: água fria perto do Peru
FRIA = faixa(-190, -81, (3, 5, 7, 6))                # La Niña
N34 = box(-170, -5, -120, 5)


def rio(nome, bbox=None):
    r = shapefile.Reader(os.path.join(os.environ["VISUAL_DADOS"], "ne", "ne_10m_rivers_lake_centerlines"))
    out = []
    for s in r.iterShapeRecords():
        if s.record.as_dict()["name"] != nome: continue
        g = shape(s.shape.__geo_interface__)
        if bbox and not g.intersects(box(*bbox)): continue
        for ln in (g.geoms if g.geom_type == "MultiLineString" else [g]): out.append(list(ln.coords))
    return out


# ------------------------------------------------------------------------------------------- placas
_cache = {}
def placa(nome, cam, focos=(), paleta=None, escala=1.3, divisas=True):
    if nome not in _cache:
        _cache[nome] = Placa(cam, focos, paleta, escala, divisas, cache=os.path.join(PL, nome + ".png"))
    return _cache[nome]

seca = lambda g, lift=22: dict(g=g, lift=lift, tema="seca", divisas=False)
cheia = lambda g, lift=22: dict(g=g, lift=lift, tema="cheia", divisas=False)
quente = lambda g: dict(g=g, lift=0, tema="calor", divisas=False)
fria = lambda g: dict(g=g, lift=0, tema="frio", divisas=False)
br0 = dict(g=BR, lift=0, sec=True)

CAM = dict(
    abre=dict(lon=-52, lat=-12, wdeg=42, rot=-4, persp=True, horizonte=0.11),
    brasil=dict(lon=-54, lat=-15, wdeg=46, rot=-3, tilt=0.22),
    pac=dict(lon=-150, lat=-4, wdeg=150, rot=0, tilt=0.18),
    pac3d=dict(lon=-140, lat=10, wdeg=72, rot=4, persp=True, horizonte=0.15),
    peru=dict(lon=-79.5, lat=-9, wdeg=9, rot=90, persp=True, horizonte=0.18),
    sul3d=dict(lon=-54, lat=-24, wdeg=26, rot=-8, persp=True, horizonte=0.16),
    ne=dict(lon=-41, lat=-9, wdeg=20, rot=-6, tilt=0.3),
    amz=dict(lon=-62, lat=-0.5, wdeg=16, rot=8, tilt=0.3),
    rs=dict(lon=-53.3, lat=-29.8, wdeg=13, rot=-10, tilt=0.3),
    poa=dict(lon=-51.18, lat=-30.12, wdeg=1.5, rot=0, tilt=0.1),
    energia=dict(lon=-50, lat=-17, wdeg=30, rot=4, tilt=0.25),
    agro=dict(lon=-52.5, lat=-27, wdeg=13, rot=-6, tilt=0.3),
    asia=dict(lon=120, lat=0, wdeg=95, rot=0, tilt=0.15),
    mundo=dict(lon=-60, lat=0, wdeg=230, rot=0, tilt=0.0),
    lista=dict(lon=-42, lat=-15, wdeg=48, rot=0, tilt=0.18),
)


def todas_placas():
    P = {}
    P["abre"] = placa("abre", CAM["abre"], [br0], divisas=False)
    P["abre_n"] = placa("abre_n", CAM["abre"], [br0, seca(NORTE, 26)], divisas=False)
    P["abre_ns"] = placa("abre_ns", CAM["abre"], [br0, seca(NORTE, 26), cheia(SUL, 26)], divisas=False)
    P["fecho"] = placa("fecho", CAM["abre"], [br0, seca(NNE, 26), cheia(SUL, 26)], divisas=False)
    P["pac"] = placa("pac", CAM["pac"], [], divisas=False)
    P["pac_q"] = placa("pac_q", CAM["pac"], [quente(QUENTE)], divisas=False)
    P["pac_f"] = placa("pac_f", CAM["pac"], [fria(FRIA)], divisas=False)
    P["brasil"] = placa("brasil", CAM["brasil"], [br0])
    P["brasil_rr_rs"] = placa("brasil_rr_rs", CAM["brasil"], [br0, seca(RR), cheia(RS)])
    P["brasil_ns"] = placa("brasil_ns", CAM["brasil"], [br0, seca(NNE), cheia(SUL)], divisas=False)
    P["brasil_inv"] = placa("brasil_inv", CAM["brasil"], [br0, cheia(NNE), seca(SUL)], divisas=False)
    P["pac3d"] = placa("pac3d", CAM["pac3d"], [br0], divisas=False, escala=1.25)
    P["pac3d_normal"] = placa("pac3d_normal", CAM["pac3d"], [quente(PISCINA), fria(FRIA_PERU), br0], divisas=False, escala=1.25)
    P["pac3d_nino"] = placa("pac3d_nino", CAM["pac3d"], [quente(QUENTE), quente(PISCINA), br0], divisas=False, escala=1.25)
    P["peru"] = placa("peru", CAM["peru"], [], divisas=False)
    P["peru_q"] = placa("peru_q", CAM["peru"], [quente(faixa(-95, -79.5, (2, 3, 5, 7)))], divisas=False)
    P["sul3d"] = placa("sul3d", CAM["sul3d"], [br0], divisas=False)
    P["sul3d_c"] = placa("sul3d_c", CAM["sul3d"], [br0, cheia(SUL, 26)], divisas=False)
    P["ne"] = placa("ne", CAM["ne"], [br0])
    P["ne_s"] = placa("ne_s", CAM["ne"], [br0, seca(NORDESTE, 20)])
    P["amz"] = placa("amz", CAM["amz"], [br0])
    P["amz_s"] = placa("amz_s", CAM["amz"], [br0, seca(RR, 18)])
    P["rs"] = placa("rs", CAM["rs"], [br0])
    P["rs_c"] = placa("rs_c", CAM["rs"], [br0, cheia(RS, 22)])
    P["poa"] = placa("poa", CAM["poa"], [], paleta="relevo", divisas=False)
    P["energia"] = placa("energia", CAM["energia"], [br0])
    P["energia_r"] = placa("energia_r", CAM["energia"], [br0, dict(g=E_("São Paulo", "Minas Gerais", "Goiás", "Paraná", "Mato Grosso do Sul", "Distrito Federal"), lift=18, tema="cheia", divisas=True)])
    P["agro"] = placa("agro", CAM["agro"], [br0])
    P["asia"] = placa("asia", CAM["asia"], [], divisas=False)
    P["mundo"] = placa("mundo", CAM["mundo"], [], divisas=False, escala=1.15)
    P["lista"] = placa("lista", CAM["lista"], [br0])
    P["lista_s"] = placa("lista_s", CAM["lista"], [br0, cheia(SUL)])
    P["lista_se"] = placa("lista_se", CAM["lista"], [br0, dict(g=SECO, lift=22, tema="calor", divisas=False)])
    P["lista_n"] = placa("lista_n", CAM["lista"], [br0, seca(NNE)])
    return P


# ------------------------------------------------------------------------------------------- painéis desenhados
F_X, F_SB, F_B = G.FONT_X, G.FONT_SB, G.FONT_BLACK
def fonte(f, s): return G.fonte(f, s)
def cartao(d, xy, r=34, a=246): d.rounded_rectangle(xy, r, fill=(255, 255, 255, a))


def oni():
    s, v = [], []
    meses = ["DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ"]
    for l in open(os.path.join(HERE, "oni.txt")).read().split("\n")[1:]:
        p = l.split()
        if len(p) == 4: s.append(int(p[1]) + meses.index(p[0]) / 12); v.append(float(p[3]))
    return np.array(s), np.array(v)
ONI_A, ONI_V = oni()


def grafico(t_draw, marcas):
    """marcas: [(ano, rótulo, t_aparece)]."""
    X0, X1, Y0, Y1 = 230, 1690, 250, 880; vmin, vmax = -2.2, 2.8
    px = lambda a: X0 + (a - 1950) / (2027 - 1950) * (X1 - X0)
    py = lambda y: Y1 - (y - vmin) / (vmax - vmin) * (Y1 - Y0)
    fundo = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(fundo)
    cartao(d, [X0 - 120, Y0 - 140, X1 + 90, Y1 + 100])
    d.text((X0 - 40, Y0 - 96), "Quanto o Pacífico ficou mais quente (ou mais frio) que o normal", font=fonte(F_X, 40), fill=(20, 22, 28), anchor="lm")
    d.text((X0 - 40, Y0 - 50), "índice ONI da NOAA, média de 3 meses, °C", font=fonte(F_SB, 30), fill=(90, 95, 110), anchor="lm")
    for y in (-2, -1, 0, 1, 2):
        d.line([(X0, py(y)), (X1, py(y))], fill=(200, 205, 214) if y else (90, 95, 110), width=2 if y else 3)
        d.text((X0 - 16, py(y)), (f"{y:+d} °C" if y else "0").replace("-", "−"), font=fonte(F_SB, 32), fill=(70, 75, 90), anchor="rm")
    for a in range(1950, 2030, 10): d.text((px(a), Y1 + 40), str(a), font=fonte(F_SB, 32), fill=(90, 95, 110), anchor="mm")
    seg = [(px(ONI_A[i]), py(ONI_V[i]), ONI_V[i]) for i in range(len(ONI_A))]
    def f(lay, k, t):
        lay.alpha_composite(fundo); dd = ImageDraw.Draw(lay)
        m = int((len(seg) - 1) * sai(clamp((t - t_draw) / 7.0)))
        for i in range(m):
            v = seg[i][2]; c = (230, 72, 15) if v >= 0.5 else (42, 143, 214) if v <= -0.5 else (150, 155, 165)
            dd.line([seg[i][:2], seg[i + 1][:2]], fill=c, width=5)
        if m > 0:
            x, y = seg[m][:2]; dd.ellipse([x - 8, y - 8, x + 8, y + 8], fill=(230, 72, 15))
        for ano, rot, ta in marcas:
            if t < ta: continue
            j = np.where(np.abs(ONI_A - ano) <= 0.7)[0]; i = int(j[np.argmax(ONI_V[j])]) if len(j) else int(np.argmin(np.abs(ONI_A - ano)))
            x, y = px(ONI_A[i]), py(ONI_V[i]); s_ = volta((t - ta) / 0.3)
            r = 12 * s_; dd.ellipse([x - r, y - r, x + r, y + r], fill=(230, 72, 15), outline=(255, 255, 255), width=4)
            rot2 = f"{rot}: +{ONI_V[i]:.1f}".replace(".", ",")
            L._cola(lay, G.chip_img(rot2, 34, "#FF7A1A" if rot == "agora" else None), (x - 150, y + 70) if rot == "agora" else (x, y - 64), 0.6 + 0.4 * s_, clamp((t - ta) / 0.15))
    return f


def walker(t_sobe, t_desce, t_seco):
    """Perfil da circulação: o ar sobe no Pacífico quente, anda lá em cima e desce sobre a Amazônia."""
    X0, X1, YM = 160, 1760, 820
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(base)
    cartao(d, [X0 - 60, 150, X1 + 60, 960], a=240)
    d.text((X0, 205), "O ar visto de lado", font=fonte(F_X, 46), fill=(20, 22, 28), anchor="lm")
    d.rectangle([X0, YM, 1180, 900], fill=(30, 110, 170)); d.rectangle([X0 + 500, YM, 1180, 840], fill=(240, 120, 40))
    d.polygon([(1180, YM + 10), (1260, 760), (1330, 700), (1400, 690), (1760, 700), (1760, 900), (1180, 900)], fill=(96, 140, 72))
    d.text((640, 868), "Pacífico quente", font=fonte(F_X, 36), fill=(255, 255, 255), anchor="mm")
    d.text((1500, 790), "Amazônia", font=fonte(F_X, 40), fill=(255, 255, 255), anchor="mm")
    d.text((1185, 935), "América do Sul", font=fonte(F_SB, 32), fill=(80, 85, 95), anchor="lm")
    nuvem = L.Figura("obj_nuvem_chuva", (0, 0), 0, 1).im; sol = L.Figura("obj_sol", (0, 0), 0, 1).im
    def seta(dd, pts, k, cor):
        m = max(2, int(len(pts) * k)); p = pts[:m]
        dd.line(p, fill=(20, 24, 40), width=24, joint="curve"); dd.line(p, fill=cor, width=16, joint="curve")
        (x0, y0), (x1, y1) = p[-2], p[-1]; a = math.atan2(y1 - y0, x1 - x0); c = 38
        dd.polygon([(x1 + math.cos(a) * c, y1 + math.sin(a) * c), (x1 + math.cos(a + 2.5) * c, y1 + math.sin(a + 2.5) * c), (x1 + math.cos(a - 2.5) * c, y1 + math.sin(a - 2.5) * c)], fill=cor)
    sobe = [(880, 760 - i * 9) for i in range(46)]
    cima = [(880 + 20 * math.sin(i / 50 * math.pi) + i * 11, 330 - 60 * math.sin(i / 50 * math.pi)) for i in range(51)]
    desce = [(1450, 340 + i * 7) for i in range(45)]
    def f(lay, k, t):
        lay.alpha_composite(base); dd = ImageDraw.Draw(lay)
        if t > t_sobe:
            seta(dd, sobe, sai((t - t_sobe) / 1.2), (255, 150, 60))
            L._cola(lay, nuvem.resize((220, int(220 * nuvem.height / nuvem.width))), (760, 420), volta((t - t_sobe - 0.8) / 0.4) if t > t_sobe + 0.8 else 0, 1)
            if t > t_sobe + 1.0: seta(dd, cima, sai((t - t_sobe - 1.0) / 1.4), (235, 240, 250))
        if t > t_desce: seta(dd, desce, sai((t - t_desce) / 1.2), (120, 190, 255))
        if t > t_seco:
            L._cola(lay, sol.resize((170, int(170 * sol.height / sol.width))), (1620, 470), volta((t - t_seco) / 0.4), 1)
            L._cola(lay, G.chip_img("céu limpo, sem chuva", 34, T_["seca"]["acento"]), (1450, 620), volta((t - t_seco - 0.2) / 0.3), clamp((t - t_seco - 0.2) / 0.15))
    return f


def conta_luz(t_in, t_amarela, t_vermelha):
    def f(lay, k, t):
        d = ImageDraw.Draw(lay); x0, y0 = 1200, 300
        a = clamp((t - t_in) / 0.3)
        if a <= 0: return
        card = Image.new("RGBA", (560, 520), (0, 0, 0, 0)); dc = ImageDraw.Draw(card)
        dc.rounded_rectangle([0, 0, 559, 519], 30, fill=(255, 255, 255, 248))
        dc.text((40, 60), "Conta de luz", font=fonte(F_X, 44), fill=(20, 22, 28), anchor="lm")
        for i in range(4): dc.rounded_rectangle([40, 120 + i * 46, 520 - i * 70, 140 + i * 46], 8, fill=(220, 224, 230))
        cor = (46, 170, 80); nome = "bandeira verde"
        if t > t_amarela: cor, nome = (240, 190, 30), "bandeira amarela"
        if t > t_vermelha: cor, nome = (225, 60, 50), "bandeira vermelha"
        dc.rounded_rectangle([40, 340, 520, 470], 22, fill=cor)
        dc.text((280, 405), nome, font=fonte(F_X, 40), fill=(255, 255, 255), anchor="mm")
        card = G.com_sombra(card, 12, 0.5, (6, 10))
        L._cola(lay, card, (x0 + 270, y0 + 260), volta((t - t_in) / 0.35), a)
    return f


def copo(t_in, t_cheio):
    def f(lay, k, t):
        if t < t_in: return
        im = Image.new("RGBA", (520, 640), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, 519, 639], 30, fill=(255, 255, 255, 246))
        gx0, gx1, gy0, gy1 = 150, 370, 110, 560
        nivel = lerp(0.62, 0.86, sai((t - t_cheio) / 1.5)) if t > t_cheio else 0.62
        y = gy1 - (gy1 - gy0) * nivel
        d.polygon([(gx0 + 8, y), (gx1 - 8, y), (gx1 - 18, gy1), (gx0 + 18, gy1)], fill=(42, 143, 214))
        if t > t_cheio: 
            yy = gy1 - (gy1 - gy0) * 0.62; d.polygon([(gx0 + 8, y), (gx1 - 8, y), (gx1 - 10, yy), (gx0 + 10, yy)], fill=(240, 120, 40))
        d.line([(gx0, gy0), (gx0 + 18, gy1), (gx1 - 18, gy1), (gx1, gy0)], fill=(30, 34, 44), width=8, joint="curve")
        d.text((260, 60), "oceanos", font=fonte(F_X, 38), fill=(20, 22, 28), anchor="mm")
        d.text((260, 600), "+ El Niño" if t > t_cheio else "", font=fonte(F_X, 34), fill=(230, 72, 15), anchor="mm")
        L._cola(lay, G.com_sombra(im, 12, 0.5, (6, 10)), (1500, 560), volta((t - t_in) / 0.35), clamp((t - t_in) / 0.2))
    return f


def lista(itens):
    """itens: [(t, cor, texto)]. Cartão à direita, um item por frase."""
    def f(lay, k, t):
        if t < itens[0][0] - 0.3: return
        d = ImageDraw.Draw(lay); a = clamp((t - itens[0][0] + 0.3) / 0.3)
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dd = ImageDraw.Draw(ov)
        dd.rounded_rectangle([1040, 210, 1860, 900], 34, fill=(255, 255, 255, int(246 * a)))
        dd.text((1100, 285), "O que esperar", font=fonte(F_X, 46), fill=(20, 22, 28, int(255 * a)), anchor="lm")
        for i, (ti, cor, txt) in enumerate(itens):
            if t < ti: continue
            b = clamp((t - ti) / 0.3); y = 400 + i * 120; x = 1100 + 30 * (1 - sai((t - ti) / 0.4))
            dd.ellipse([x, y - 26, x + 52, y + 26], fill=G.rgb(cor) + (int(255 * b),))
            dd.text((x + 26, y), str(i + 1), font=fonte(F_X, 30), fill=(255, 255, 255, int(255 * b)), anchor="mm")
            for j, linha in enumerate(txt.split("\n")):
                dd.text((x + 80, y - 18 + j * 40 - (18 if "\n" not in txt else 0) + (18 if "\n" not in txt else 0)), linha, font=fonte(F_SB, 38 if j == 0 else 32), fill=(30, 34, 44, int(255 * b)) if j == 0 else (90, 95, 110, int(255 * b)), anchor="lm")
        lay.alpha_composite(ov)
    return f


def cartela(texto, sub, t_in, t_out):
    """Cartela de capítulo (canto inferior esquerdo, discreta)."""
    def f(lay, k, t):
        a = clamp((t - t_in) / 0.4) * (1 - clamp((t - t_out) / 0.4))
        if a <= 0: return
        im = Image.new("RGBA", (900, 150), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 20, 10, 130], 5, fill=(255, 196, 80, 255))
        d.text((34, 52), sub, font=fonte(F_SB, 28), fill=(255, 220, 150, 255), anchor="lm")
        d.text((34, 100), texto, font=fonte(F_X, 46), fill=(255, 255, 255, 255), anchor="lm")
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); sh.putalpha(im.getchannel("A").filter(ImageFilter.MaxFilter(7)).point(lambda v: int(v * 0.6)))
        out = Image.new("RGBA", im.size, (0, 0, 0, 0)); out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10))); out.alpha_composite(im)
        L._cola(lay, out, (80 + 450 + 30 * (1 - sai((t - t_in) / 0.5)), 940), 1, a)
    return f


# ------------------------------------------------------------------------------------------- planos
def montar():
    P = todas_placas(); planos, trocas = [], []
    def add(pl, troca="fusao"): planos.append(pl); trocas.append(troca)
    def cap(i, sub="Capítulo"):  # cartela do capítulo i (1..13)
        c = CAPS[i]; return Painel(cartela(c["nome"], f"{i:02d}" if i else "", c["t"] + 0.5, c["t"] + 4.0), c["t"], c["t"] + 4.6)
    A, Nn, Sn = T_["seca"]["acento"], T_["cheia"]["acento"], "#FF7A1A"

    # 1 — gancho
    add(Plano("abertura", 0, S(3) - 0.3, P["abre"], acesas=[(T(1, "norte") - 0.1, P["abre_n"], "fade"), (T(1, "sul") - 0.1, P["abre_ns"], "fade")],
              deriva=Caminho([(0, dict(c=(0.5, 0.42), z=1.18, rot=-6)), (T(1, "norte"), dict(c=(0.5, 0.36), z=1.08, rot=-2)),
                              (T(1, "sul"), dict(c=(0.55, 0.62), z=1.05, rot=2)), (S(2), dict(c=(0.5, 0.5), z=0.98, rot=0))]),
              camadas=[Chip("menos chuva", T(1, "sem"), S(3), geo=(-60, -5), size=40, cor=A, dy=-110),
                       Chip("mais chuva", T(1, "debaixo"), S(3), geo=(-52, -27), size=40, cor=Nn, dy=-120)]), "-")
    add(Plano("pacifico", S(3) - 0.3, S(5) - 0.3, P["pac"], acesas=[(S(4), P["pac_q"], "cortina")],
              deriva=Caminho([(S(3) - 0.3, dict(geo=(-120, -2), z=1.0)), (S(4), dict(geo=(-130, 0), z=1.12))]),
              camadas=[Nome("OCEANO PACÍFICO", T(3, "pacifico") - 0.2, S(5), geo=(-150, -24), size=52),
                       Chip("o mais forte para a época", T(4, "forte"), S(5), geo=(-140, 4), size=42, cor=Sn, dy=-120)]), "mergulho")
    add(Plano("promessa", S(5) - 0.3, CAP(1), P["brasil"],
              deriva=Caminho([(S(5) - 0.3, dict(geo=(-62, -12), z=1.0)), (T(5, "porto"), dict(geo=(-53, -24), z=1.15)), (T(5, "amazonia"), dict(geo=(-60, -6), z=1.1)), (S(6), dict(geo=(-52, -14), z=0.98))]),
              camadas=[Chip("Peru", T(5, "peru"), S(6), tela=(250, 520), size=38),
                       Chip("Porto Alegre", T(5, "porto"), S(6) + 1, geo=(-51.2, -30.0), size=38, cor=Nn, dy=-60),
                       Chip("rios da Amazônia", T(5, "amazonia"), S(6) + 1, geo=(-62, -3.5), size=38, cor=A, dy=-60),
                       Figura("obj_raio", (-47.9, -15.8), T(6, "luz"), CAP(1), 150), Chip("conta de luz", T(6, "luz"), CAP(1), geo=(-47.9, -15.8), size=36, dy=60),
                       Figura("obj_prato", (-44, -20), T(6, "comida"), CAP(1), 160), Chip("comida", T(6, "comida"), CAP(1), geo=(-44, -20), size=36, dy=60)]))

    # 2 — o mais forte para a época
    add(Plano("medicao", CAP(1), S(10) - 0.2, P["pac"], acesas=[],
              deriva=Caminho([(CAP(1), dict(geo=(-150, -4), z=1.0)), (S(8), dict(geo=(-145, 0), z=1.25)), (S(9), dict(geo=(-145, 0), z=1.35, rot=-2))]),
              camadas=[cap(1), Nome("EL NIÑO", T(7, "el"), S(9), tela=(W / 2, 240), size=86),
                       Linha([[(-180, 0), (-80, 0)]], T(8, "equador") - 0.3, 1.2, cor=(255, 255, 255), larg=4),
                       Chip("linha do Equador", T(8, "equador"), S(9), geo=(-100, 0), size=36, dy=-45),
                       Contorno(N34, PA(0) - 0.1, 1.2, cor=(255, 210, 90), larg=6),
                       Chip("região de medição", PA(0) + 0.3, S(10), geo=(-145, -5), size=36, cor="#FFD25A", dy=60),
                       Chip("+0,5 °C por meses = El Niño", T(9, "meio"), S(10), geo=(-145, 5), size=38, cor=Sn, dy=-70)]), "mergulho")
    add(Plano("recorde", S(10) - 0.2, S(12) - 0.3, P["pac"], acesas=[(T(10, "outubro"), P["pac_q"], "cortina")],
              deriva=Caminho([(S(10) - 0.2, dict(geo=(-140, -2), z=1.2, rot=-2)), (S(11), dict(geo=(-135, -2), z=1.08, rot=1))]),
              camadas=[Contorno(N34, S(10) - 0.2, 0.01, t_out=S(11), cor=(255, 210, 90), larg=6),
                       Chip("", T(10, "dois"), S(12), geo=(-145, 5), size=52, cor=Sn, dy=-90, conta=(0, 2.47, lambda v: f"+{v:.1f} °C".replace(".", ","), 1.8)),
                       Chip("recorde para outubro", T(11, "maior"), S(12), geo=(-145, -5), size=40, cor="#FFFFFF", dy=80)]))
    add(Plano("inmet", S(12) - 0.3, CAP(2), P["brasil_ns"],
              deriva=Caminho([(S(12) - 0.3, dict(geo=(-52, -15), z=1.05, rot=2)), (T(12, "novembro"), dict(geo=(-50, -16), z=1.12, rot=-1))]),
              camadas=[Chip("Inmet", T(12, "inmet"), CAP(2), tela=(W / 2, 170), size=42),
                       Chip("auge: novembro a janeiro", T(12, "novembro"), CAP(2), tela=(W / 2, 270), size=40, cor=Sn),
                       Chip("categoria: muito forte", T(12, "muito"), CAP(2), tela=(W / 2, 370), size=40, cor="#E0461A")]))

    # 3 — de onde veio o nome
    add(Plano("peru", CAP(2), S(17) - 0.3, P["peru"], acesas=[(T(15, "demais"), P["peru_q"], "fade")],
              deriva=Caminho([(CAP(2), dict(c=(0.5, 0.55), z=1.05)), (S(14), dict(c=(0.45, 0.6), z=1.15, rot=-2)), (S(16), dict(c=(0.5, 0.55), z=1.0, rot=2))]),
              camadas=[cap(2), Nome("PERU", T(13, "peru"), S(15), geo=(-76.5, -10), size=50),
                       Figura("obj_navio", (-81, -8), T(13, "pescadores"), S(17), 230), Chip("pescadores", T(13, "pescadores") + 0.2, S(14) + 1, geo=(-81, -8), size=36, dy=60),
                       Figura("obj_calendario", (-84, -12), T(14, "natal"), S(15) + 1, 150), Chip("perto do Natal", T(14, "natal"), S(15) + 1, geo=(-84, -12), size=36, dy=60),
                       Chip("os peixes sumiam", T(15, "peixes"), S(17), geo=(-82, -6), size=38, cor=Sn, dy=-80),
                       Chip("El Niño = o Menino Jesus", T(16, "menino"), S(17), tela=(W / 2, 180), size=46, cor="#FFD25A")]))
    add(Plano("pesca", S(17) - 0.3, CAP(3), P["peru_q"],
              deriva=Caminho([(S(17) - 0.3, dict(c=(0.5, 0.55), z=1.0, rot=2)), (S(18), dict(c=(0.5, 0.4), z=0.9, rot=-4))]),
              camadas=[Chip("ano ruim de pesca", T(17, "ruim"), S(18), geo=(-81, -8), size=38, dy=-90),
                       Seta([(-79, -14), (-84, -13), (-90, -12)], T(18, "vento"), CAP(3), 1.0, cor=(235, 240, 250))]))

    # 4 — como funciona
    vento_n = [(-85, 6), (-110, 7), (-140, 8), (-170, 8), (-200, 7)]
    add(Plano("vento", CAP(3), S(24) - 0.3, P["pac3d"], acesas=[(T(22, "acumula") - 0.3, P["pac3d_normal"], "cortina_esq")],
              deriva=Caminho([(CAP(3), dict(c=(0.55, 0.55), z=1.0)), (S(21), dict(c=(0.45, 0.55), z=1.05, rot=-2)), (S(23), dict(c=(0.7, 0.55), z=1.2, rot=3))]),
              camadas=[cap(3), Chip("ano normal", S(20), S(24), tela=(W / 2, 140), size=44),
                       Seta(vento_n, T(20, "leste") - 0.2, S(24), 2.2, cor=(235, 240, 250)),
                       Seta([(-90, -3), (-125, -2), (-160, -1), (-195, -1)], PA(1), S(24), 1.8, cor=(235, 240, 250), larg=11),
                       Seta([(-95, -10), (-130, -9), (-165, -8), (-195, -7)], PA(1) + 0.4, S(24), 1.8, cor=(235, 240, 250), larg=11),
                       Chip("vento", T(20, "vento"), S(22), geo=(-130, 8), size=36, dy=-60),
                       Chip("Austrália e Indonésia", T(21, "indonesia"), S(23), geo=(-215, -10), size=36, dy=-50),
                       Chip("água quente acumulada", T(22, "acumula"), S(24), geo=(-205, 0), size=38, cor=Sn, dy=-90),
                       Chip("sobe água fria", T(23, "fria"), S(24), geo=(-92, -6), size=38, cor="#3FB4FF", dy=-90)]), "mergulho")
    add(Plano("escorre", S(24) - 0.3, S(28) - 0.3, P["pac3d_normal"], acesas=[(PA(2) - 0.6, P["pac3d_nino"], "cortina")],
              deriva=Caminho([(S(24) - 0.3, dict(c=(0.5, 0.55), z=1.0, rot=2)), (PA(2), dict(c=(0.55, 0.55), z=1.04, rot=-1)), (S(26), dict(c=(0.62, 0.55), z=1.18, rot=-3))]),
              camadas=[Chip("ano de El Niño", S(24), S(28), tela=(W / 2, 140), size=44, cor=Sn),
                       Seta(vento_n[:3], T(24, "enfraquece"), S(26), 1.4, cor=(170, 180, 195), larg=7),
                       Chip("o vento enfraquece", T(24, "enfraquece") + 0.2, S(26), geo=(-115, 7), size=36, dy=-60),
                       Seta([(-200, -2), (-160, -3), (-120, -3), (-88, -4)], T(25, "escorre"), S(27), 2.4, cor=(255, 122, 26)),
                       Figura("obj_nuvem_chuva", (-115, 0), T(26, "nuvens"), S(28), 220),
                       Figura("obj_nuvem_chuva", (-140, -1), T(26, "nuvens") + 0.4, S(28), 180),
                       Chip("a chuva muda de lugar", T(27, "chuva"), S(28), tela=(W / 2, 250), size=40)]))
    add(Plano("estranho", S(28) - 0.3, CAP(4), P["brasil"], acesas=[(T(29, "rio"), P["brasil_rr_rs"], "fade")],
              deriva=Caminho([(S(28) - 0.3, dict(geo=(-56, -15), z=1.0)), (T(29, "rio"), dict(geo=(-54, -22), z=1.12, rot=-2)), (T(29, "roraima"), dict(geo=(-58, -8), z=1.1, rot=2))]),
              camadas=[Chip("10 mil km", T(29, "dez"), CAP(4), tela=(300, 300), size=44, cor=Sn),
                       Seta([(-79, -2), (-74, -5), (-70, -8)], T(29, "dez"), CAP(4), 1.0, cor=(255, 122, 26), larg=10),
                       Chip("alaga", T(29, "alaga"), CAP(4), geo=(-53.5, -29.5), size=40, cor=Nn, dy=-80),
                       Chip("seca", T(29, "seca"), CAP(4), geo=(-61, 2), size=40, cor=A, dy=-80),
                       ]))

    # 5 — o Brasil dividido
    add(Plano("walker", CAP(4), S(33) - 0.3, P["pac"], desfoque=10, escurece=0.35,
              deriva=Caminho([(CAP(4), dict(geo=(-110, -5), z=1.0)), (S(32), dict(geo=(-105, -5), z=1.04))]),
              camadas=[cap(4), Painel(walker(T(31, "sobe"), T(31, "desce"), S(32)), CAP(4), S(33))]), "mergulho")
    jato = [(-75, -20), (-62, -26), (-52, -29), (-42, -28), (-32, -25)]
    add(Plano("jato", S(33) - 0.3, CAP(5), P["sul3d"], acesas=[(T(35, "chuva"), P["sul3d_c"], "fade")],
              deriva=Caminho([(S(33) - 0.3, dict(c=(0.5, 0.5), z=1.0, rot=-2)), (PA(4), dict(c=(0.5, 0.55), z=1.08, rot=2)), (S(36), dict(c=(0.5, 0.5), z=0.95, rot=-1))]),
              camadas=[Seta(jato, T(34, "jato") - 0.3, CAP(5), 2.0, cor=(140, 200, 255), larg=22),
                       Chip("jato subtropical", T(34, "jato"), CAP(5), geo=(-62, -26), size=38, cor="#8CC8FF", dy=-80),
                       Seta([(-60, -38), (-56, -34), (-54, -31.5)], T(34, "frentes"), S(36), 1.0, cor=(63, 140, 255), larg=10),
                       Chip("frente fria parada", PA(4), S(36), geo=(-56, -33), size=36, cor="#3FB4FF", dy=50),
                       Figura("obj_nuvem_chuva", (-53, -28), T(35, "chuva"), CAP(5), 200), Figura("obj_nuvem_chuva", (-50, -26), T(35, "dia"), CAP(5), 170),
                       Chip("menos chuva em cima, mais chuva embaixo", T(36, "resultado"), CAP(5), tela=(W / 2, 170), size=40)]))

    # 6 — Norte e Nordeste
    add(Plano("nordeste", CAP(5), S(39) - 0.3, P["ne"], acesas=[(T(37, "seca"), P["ne_s"], "fade")],
              deriva=Caminho([(CAP(5), dict(geo=(-41, -8), z=1.0, rot=2)), (PA(5), dict(geo=(-40, -9), z=1.12, rot=-2)), (S(38), dict(geo=(-41, -8), z=1.0, rot=1))]),
              camadas=[cap(5), Minimapa(NORDESTE, CAP(5) + 0.5, S(39)), Nome("NORDESTE", T(37, "nordeste"), S(39), tela=(W / 2 - 200, 110), size=48),
                       Chip("", T(37, "dezesseis"), S(39), geo=(-40.5, -8), size=48, cor=A, dy=-40, conta=(16, 28, lambda v: f"seca grave: {v:.0f} %", 2.5)),
                       Chip("quase toda a região com seca", T(38, "quase"), S(39), geo=(-40.5, -8), size=36, dy=60)]), "mergulho")
    add(Plano("rios", S(39) - 0.3, S(42) - 0.3, P["amz"], acesas=[(T(39, "roraima"), P["amz_s"], "fade")],
              deriva=Caminho([(S(39) - 0.3, dict(geo=(-61, 2), z=1.05)), (S(40), dict(geo=(-62, -2), z=1.1, rot=-3)), (S(41), dict(geo=(-60, -3), z=1.2, rot=2))]),
              camadas=[Minimapa(AM.union(RR), S(39), S(42)), Nome("RORAIMA", T(39, "roraima"), S(40), geo=(-61.5, 3.2), size=40),
                       Linha(rio("Branco"), T(39, "branco"), 1.6, cor=(110, 205, 255), larg=8),
                       Chip("rio Branco: muito abaixo do normal", T(39, "muito"), S(42), geo=(-61.2, 1.2), size=36, cor=A, dy=-60),
                       Linha(rio("Rio Negro"), T(40, "negro"), 1.8, cor=(110, 205, 255), larg=8),
                       Chip("rio Negro: navegação difícil", T(40, "navegacao"), S(42), geo=(-63.5, -1), size=36, cor=A, dy=60),
                       Figura("obj_navio", (-60.1, -3.2), T(41, "barco"), S(42), 200),
                       Chip("comida e combustível não chegam", T(41, "comida"), S(42), geo=(-60.1, -3.2), size=36, dy=60)]))
    add(Plano("fogo", S(42) - 0.3, CAP(6), P["amz_s"],
              deriva=Caminho([(S(42) - 0.3, dict(geo=(-61, -1), z=1.1, rot=2)), (T(42, "centenas"), dict(geo=(-62, -1), z=0.95, rot=-2))]),
              camadas=[Figura("obj_fogo", (-64, -2), T(42, "fogo"), CAP(6), 140), Figura("obj_fogo", (-59, -4), T(42, "fogo") + 0.3, CAP(6), 120),
                       Figura("obj_fogo", (-61.5, 1), T(42, "fogo") + 0.6, CAP(6), 110),
                       Chip("centenas de municípios em alerta de incêndio", T(42, "centenas"), CAP(6), tela=(W / 2, 170), size=40, cor="#F2381A")]))

    # 7 — Sul e 2024
    add(Plano("rs", CAP(6), PA(6) - 0.2, P["rs"], acesas=[(T(43, "sul"), P["rs_c"], "fade")],
              deriva=Caminho([(CAP(6), dict(geo=(-53, -29.5), z=1.0, rot=-2)), (S(44), dict(geo=(-52, -30), z=1.15, rot=2))]),
              camadas=[cap(6), Minimapa(RS, CAP(6) + 0.5, PA(6)), Nome("RIO GRANDE DO SUL", T(43, "sul"), PA(6), tela=(W / 2 - 160, 110), size=44),
                       Figura("obj_nuvem_chuva", (-53.5, -29), T(43, "chuva"), PA(6), 220), Chip("chuva acima da média", T(43, "acima"), PA(6), geo=(-53.5, -29), size=38, cor=Nn, dy=80),
                       Linha(rio("Uruguay"), T(44, "historia") - 0.6, 1.6, cor=(110, 205, 255), larg=7)]), "mergulho")
    add(Plano("poa", PA(6) - 0.2, S(47) - 0.3, P["poa"],
              deriva=Caminho([(PA(6) - 0.2, dict(geo=(-51.2, -30.1), z=1.0, rot=0)), (S(46), dict(geo=(-51.22, -30.04), z=1.25, rot=2))], deriva_z=0.01),
              camadas=[Chip("Porto Alegre", PA(6) + 0.4, S(47), geo=(-51.2, -30.03), size=36, dy=-150),
                       Nome("GUAÍBA", PA(6) + 0.8, S(47), geo=(-51.27, -30.25), size=40),
                       Chip("", T(45, "enchente"), S(47), geo=(-51.25, -30.12), size=46, cor=Nn, dy=-140, conta=(0, 5.35, lambda v: f"cheia de 2024: Guaíba a {v:.2f} m".replace(".", ","), 2.2)),
                       Figura("obj_casa_alagada", (-51.14, -30.0), T(45, "enchente"), S(47), 200)]))
    add(Plano("nao_e", S(47) - 0.3, CAP(7), P["brasil_ns"],
              deriva=Caminho([(S(47) - 0.3, dict(geo=(-55, -15), z=1.0)), (T(47, "nao", 0) if False else E(47) - 0.9, dict(geo=(-50, -18), z=1.2, rot=-3))]),
              camadas=[Chip("Sul", T(47, "sul"), CAP(7), geo=(-52, -27), size=40, cor=Nn, dy=-90), Chip("Norte", T(47, "norte"), CAP(7), geo=(-60, -4), size=40, cor=A, dy=-90)]))

    # 8 — o seu bolso
    usinas = [("Itaipu", -54.59, -25.41), ("Tucuruí", -49.65, -3.83), ("Belo Monte", -51.77, -3.12), ("Furnas", -46.32, -20.67), ("Sobradinho", -40.83, -9.43), ("Ilha Solteira", -51.36, -20.38)]
    cam_e = []
    for i, (nm, lo, la) in enumerate(usinas):
        cam_e.append(Chip(nm, T(49, "represados") + i * 0.25, S(51), geo=(lo, la), size=36, cor="#19B5E0"))
    add(Plano("energia", CAP(7), S(52) - 0.3, P["energia"], acesas=[(T(49, "represados") - 0.3, P["energia_r"], "fade")],
              deriva=Caminho([(CAP(7), dict(geo=(-50, -15), z=1.0)), (S(50), dict(geo=(-49, -18), z=1.08, rot=2)), (S(51), dict(geo=(-60, -16), z=1.1, rot=-1))]),
              camadas=[cap(7)] + cam_e + [Figura("obj_fabrica", (-43.2, -22.9), T(50, "termicas"), S(52), 170),
                       Chip("onde ficam as grandes represas", T(49, "represados"), S(51), tela=(W / 2, 150), size=40, cor="#19B5E0"),
                       Chip("térmicas: energia mais cara", T(50, "caras"), S(52), geo=(-43.2, -22.9), size=36, cor="#E0461A", dy=60),
                       Painel(conta_luz(T(51, "bandeira") - 0.4, T(51, "bandeira") + 0.3, T(51, "luz")), T(51, "bandeira") - 0.4, S(52))]), "mergulho")
    add(Plano("agro", S(52) - 0.3, S(55) - 0.3, P["agro"],
              deriva=Caminho([(S(52) - 0.3, dict(geo=(-52, -27), z=1.0, rot=-2)), (S(53), dict(geo=(-52.5, -28), z=1.12, rot=1)), (S(54), dict(geo=(-53, -29), z=1.2, rot=3))]),
              camadas=[Chip("na comida, o efeito é misto", T(52, "comida"), S(53), tela=(W / 2, 160), size=42),
                       Figura("obj_soja", (-52.5, -25.3), T(53, "soja"), S(55), 150), Figura("obj_trator", (-53.8, -28.6), T(53, "milho"), S(55), 190),
                       Chip("soja e milho: chuva ajuda", T(53, "ajudar"), S(54), geo=(-52.5, -25.3), size=36, cor="#22C46A", dy=60),
                       Figura("obj_casa_alagada", (-51.5, -29.6), T(54, "alagada"), S(55), 170),
                       Chip("colheita alagada perde", T(54, "perde"), S(55), geo=(-51.5, -29.6), size=36, cor=Nn, dy=60),
                       Chip("Semiárido: quem planta para comer", T(54, "semiarido"), S(55), tela=(W / 2, 250), size=36, cor=A)]))
    add(Plano("asia", S(55) - 0.3, CAP(8), P["asia"],
              deriva=Caminho([(S(55) - 0.3, dict(geo=(110, 10), z=1.0)), (T(55, "australia"), dict(geo=(125, -10), z=1.1, rot=2)), (T(55, "arroz"), dict(geo=(118, 2), z=1.0, rot=-2))]),
              camadas=[Nome("ÁSIA", T(55, "asia"), CAP(8), geo=(100, 22), size=46), Nome("AUSTRÁLIA", T(55, "australia"), CAP(8), geo=(134, -24), size=44),
                       Chip("arroz", T(55, "arroz"), CAP(8), tela=(1450, 320), size=40, cor="#D9A441"),
                       Chip("açúcar", T(55, "acucar"), CAP(8), tela=(1450, 420), size=40, cor="#D9A441"),
                       Chip("trigo", T(55, "trigo"), CAP(8), tela=(1450, 520), size=40, cor="#D9A441"),
                       Figura("obj_prato", (100, 8), T(55, "arroz"), CAP(8), 170)]))

    # 9 — as outras vezes
    add(Plano("grafico", CAP(8), CAP(9), P["pac"], desfoque=12, escurece=0.4,
              deriva=Caminho([(CAP(8), dict(geo=(-140, 0), z=1.0)), (S(58), dict(geo=(-135, 0), z=1.05))]),
              camadas=[cap(8), Painel(grafico(PA(7) - 0.3, [(1997.9, "1997–98", T(58, "noventa")), (2015.9, "2015–16", T(58, "dois")), (ONI_A[-1], "agora", T(59, "agora"))]), CAP(8), CAP(9))]), "mergulho")

    # 10 — por que agora é diferente
    add(Plano("diferente", CAP(9), CAP(10), P["mundo"],
              deriva=Caminho([(CAP(9), dict(c=(0.5, 0.5), z=1.0)), (S(62), dict(c=(0.5, 0.5), z=1.08, rot=1)), (S(63), dict(c=(0.42, 0.5), z=1.1, rot=-1))]),
              camadas=[cap(9), Chip("último El Niño forte: 2023–24", T(61, "ultimo"), S(62), tela=(W / 2, 170), size=42, cor=Sn),
                       Chip("oceanos mais quentes que em 1982 e 1997", T(62, "oceanos"), S(63) + 1, tela=(W / 2, 260), size=40, cor="#E0461A"),
                       Painel(copo(T(63, "copo") - 0.2, T(63, "mesmo")), T(63, "copo") - 0.2, CAP(10))]), "mergulho")

    # 11 — La Niña
    add(Plano("lanina", CAP(10), S(66) - 0.3, P["pac_q"], acesas=[(PA(8) - 0.5, P["pac_f"], "cortina_esq")],
              deriva=Caminho([(CAP(10), dict(geo=(-130, -2), z=1.0)), (S(65), dict(geo=(-120, -2), z=1.12, rot=-2))]),
              camadas=[cap(10), Seta([(-85, 6), (-120, 7), (-160, 8), (-200, 7)], T(65, "vento"), S(66), 1.6, cor=(235, 240, 250), larg=20),
                       Chip("vento mais forte", T(65, "forte"), S(66), geo=(-125, 7), size=36, dy=-70),
                       Nome("LA NIÑA", T(65, "nina"), S(66), tela=(W / 2, 220), size=80)]), "mergulho")
    add(Plano("inverte", S(66) - 0.3, CAP(11), P["brasil_ns"], acesas=[(T(66, "inverte"), P["brasil_inv"], "fade")],
              deriva=Caminho([(S(66) - 0.3, dict(geo=(-54, -15), z=1.0, rot=2)), (S(67), dict(geo=(-53, -26), z=1.2, rot=-2))]),
              camadas=[Chip("mais chuva", T(66, "chuva"), S(67), geo=(-60, -4), size=40, cor=Nn, dy=-90), Chip("seca", T(66, "seca"), S(67), geo=(-52, -27), size=40, cor=A, dy=-90),
                       Chip("estiagem e enchente em anos seguidos", T(67, "estiagem"), CAP(11), tela=(W / 2, 170), size=40)]))

    # 12 — se você mora em...
    add(Plano("lista", CAP(11), CAP(12), P["lista"], acesas=[(S(69), P["lista_s"], "fade"), (S(70), P["lista_se"], "fade"), (S(71), P["lista_n"], "fade"), (S(72), P["lista"], "fade")],
              deriva=Caminho([(CAP(11), dict(geo=(-42, -15), z=1.0)), (S(69), dict(geo=(-44, -20), z=1.08)), (S(70), dict(geo=(-43, -15), z=1.05)), (S(71), dict(geo=(-44, -8), z=1.06)), (S(72), dict(geo=(-42, -15), z=1.0))]),
              camadas=[cap(11), Painel(lista([(S(69), Nn, "Sul\nalertas da Defesa Civil e o rio mais perto"), (S(70), "#FF7A1A", "Sudeste e Centro-Oeste\nmais calor, chuva irregular"),
                                               (S(71), A, "Norte e norte do Nordeste\nguarde água, nada de queimadas"), (S(72), "#E0461A", "Em qualquer lugar\nkit de emergência pronto")]), S(69) - 0.5, CAP(12)),
                       Figura("obj_mochila", (-47, -16), T(72, "kit"), S(73), 200),
                       Chip("perde força no início de 2027", T(73, "perder"), CAP(12), tela=(560, 170), size=38, cor="#FFD25A")]), "mergulho")

    # 13 — ou seja
    add(Plano("fecho", CAP(12), DUR, P["fecho"],
              deriva=Caminho([(CAP(12), dict(c=(0.5, 0.5), z=1.2, rot=-4)), (S(75), dict(c=(0.5, 0.45), z=1.05, rot=0)), (S(76), dict(c=(0.5, 0.5), z=0.95, rot=3))], deriva_z=-0.01),
              camadas=[Chip("menos chuva", T(76, "dividir"), DUR, geo=(-58, -4), size=40, cor=A, dy=-110),
                       Chip("mais chuva", T(76, "dividir") + 0.3, DUR, geo=(-52, -27), size=40, cor=Nn, dy=-120)]), "mergulho")
    for a, b in zip(planos, planos[1:]): a.t1 = b.t0
    caps = [c["t"] for c in CAPS]
    trocas = ["-"] + ["mergulho" if any(abs(p.t0 - c) < 0.05 for c in caps) else "fusao" for p in planos[1:]]
    return Filme(planos, trocas, DUR)


# ------------------------------------------------------------------------------------------- CLI
if __name__ == "__main__":
    C.rodar(montar, __file__, titulo="El Niño — vídeo longo 16:9", placas=todas_placas, tempos=TP)
