"""QH GEX-riport: GLD opciós láncból -> arany-skálázott GEX-adatok."""
import json, datetime
import numpy as np
import pandas as pd
import yfinance as yf

def arlekeres(ticker):
    t = yf.Ticker(ticker)
    try:
        p = t.fast_info.last_price
        if p: return float(p)
    except Exception: pass
    try:
        p = t.fast_info["last_price"]
        if p: return float(p)
    except Exception: pass
    h = t.history(period="2d")
    return float(h["Close"].iloc[-1])

TICKER = "GLD"
KIMENET = "docs/gex.json"

spot_gld = arlekeres(TICKER)

expiry = list(yf.Ticker(TICKER).options)[:2]
if not expiry:
    raise SystemExit("Nincs elérhető lejárat – a Yahoo most nem ad opciós adatot")

gld = yf.Ticker(TICKER)
calls_all, puts_all = [], []
for exp in expiry:
    ch = gld.option_chain(exp)
    c = ch.calls.copy(); c["expiry"] = exp
    p = ch.puts.copy();  p["expiry"] = exp
    calls_all.append(c); puts_all.append(p)
calls = pd.concat(calls_all); puts = pd.concat(puts_all)

S = spot_gld

def gex_sorok(df, tipus):
    df = df.dropna(subset=["openInterest"])
    df = df[df["openInterest"] > 0]
    tav = (df["strike"] - S).abs() / S
    df["gamma"] = np.where(tav < 0.02, 0.05, np.where(tav < 0.05, 0.02, 0.005))
    elojeles = 1 if tipus == "call" else -1
    df["gex"] = elojeles * df["gamma"] * df["openInterest"] * 100
    return df

c_gex = gex_sorok(calls, "call")
p_gex = gex_sorok(puts, "put")
ossz = pd.concat([c_gex[["strike","gex"]], p_gex[["strike","gex"]]])
gex_szint = ossz.groupby("strike")["gex"].sum()

kum = gex_szint.cumsum()
flip_gld = None
for strike, ertek in kum.items():
    if ertek < 0:
        flip_gld = strike
        break
if flip_gld is None:
    flip_gld = gex_szint.abs().idxmax()

call_wall = c_gex.groupby("strike")["gex"].sum().idxmax()
put_wall  = p_gex.groupby("strike")["gex"].sum().idxmax()

put_oi  = puts["openInterest"].sum()
call_oi = calls["openInterest"].sum()
charm_proxy = int((put_oi - call_oi) / (put_oi + call_oi) * 300000)

atm_iv_c = calls.iloc[(calls["strike"]-S).abs().argsort()[:3]]["impliedVolatility"].mean()
atm_iv_p = puts.iloc[(puts["strike"]-S).abs().argsort()[:3]]["impliedVolatility"].mean()
skew_proxy = round(float((atm_iv_p - atm_iv_c) * 100), 1)

xau = arlekeres("GC=F")
arany_ratio = xau / spot_gld
f = lambda s: round(float(s) * arany_ratio, 1)

riport = {
    "datum": datetime.date.today().isoformat(),
    "ido":   datetime.datetime.utcnow().strftime("%H:%M") + " UTC",
    "cw":  f(call_wall),
    "pw":  f(put_wall),
    "zg":  f(flip_gld),
    "ch":  charm_proxy,
    "sk":  skew_proxy,
    "spot_xau": round(float(xau), 1),
    "forras": "GLD opcios lanc, GitHub Actions"
}

with open(KIMENET, "w") as fh:
    json.dump(riport, fh, indent=2)

print("GEX riport elkészült:", riport)
