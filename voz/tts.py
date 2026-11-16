import sys, msgpack, requests
# Referência: os primeiros ~31 s de voz/ref30.wav (trecho da voz do dono, fora do Git) e o texto falado nele.
REF_TXT = ("A Petrobras lucrou quase quarenta bilhões de reais em só três meses e vai pagar quinze vírgula três bilhões aos acionistas. "
 "Mas para onde vai esse dinheiro? E de onde sai esse petróleo? O mapa responde. Tudo começa aqui, no meio do mar, a cerca de duzentos quilômetros "
 "da costa de São Paulo e do Rio de Janeiro. É o pré-sal. As plataformas atravessam mais de dois mil metros de água, depois, camadas de rocha e de sal, "
 "até chegar ao petróleo, a até sete quilômetros de profundidade.")
# Modelo gratuito da API; os pagos (s1, s2-pro) pedem crédito. O Fish não guarda modelo: a voz vai em cada pedido (clonagem instantânea).
def tts(text, out, model="s2.1-pro-free", ref="ref30.wav"):
    body = dict(text=text, format="wav", references=[dict(audio=open(ref,"rb").read(), text=REF_TXT)], normalize=False, latency="normal")
    r = requests.post("https://api.fish.audio/v1/tts", data=msgpack.packb(body),
        headers={"Authorization": "Bearer dummy", "content-type": "application/msgpack", "model": model}, timeout=300)
    if r.status_code != 200: print(out, r.status_code, r.text[:300]); return False
    open(out, "wb").write(r.content); print(out, len(r.content)); return True
if __name__ == "__main__":
    tts(sys.argv[1], sys.argv[2], *(sys.argv[3:4] or ["s1"]))
