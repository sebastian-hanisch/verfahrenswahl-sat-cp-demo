"""Plotly-Abbildungen. Alle Achsen sind gesperrt (fixedrange), damit Touch-Geräte beim Scrollen nicht am Diagramm hängen bleiben."""

import plotly.graph_objects as go

import vsw_constants as C


def lock_axes(fig):
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def _base(fig, height=360):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", y=-0.25), plot_bgcolor="rgba(0,0,0,0)")
    return lock_axes(fig)


def build_balken(namen: list, werte: list, farben: list, titel: str, einheiten: list, log: bool = True):
    """Balken je Verfahren; Beschriftung mit der Einheit (Konflikte, Knoten, Branches). Werte 0 werden als 0,5 gezeichnet, damit die logarithmische Achse sie zeigt."""
    xs = [f"{n}<br>({e})" for n, e in zip(namen, einheiten)]
    ys = [max(w, 0.5) if log else w for w in werte]
    fig = go.Figure(go.Bar(x=xs, y=ys, marker_color=farben, text=[f"{w:g}" for w in werte], textposition="outside", cliponaxis=False,
                           hovertemplate="%{x}: %{text}<extra></extra>"))
    fig.update_yaxes(title_text=titel, type="log" if log else "linear")
    return _base(fig, 340)


def build_zellen(n: int, dom: list, titel: str, vorbelegt: dict | None = None):
    """Gitter n x n: Farbe nach Zahl der noch möglichen Schichten (festgelegt grün, vorbelegt hellgrün, offen grau), Beschriftung = die möglichen Schichten."""
    vorbelegt = vorbelegt or {}
    z, text = [], []
    for r in range(n):
        zeile, tzeile = [], []
        for c in range(n):
            d = dom[r * n + c]
            if (r, c) in vorbelegt:
                zeile.append(0.0)
            elif len(d) == 1:
                zeile.append(1.0)
            else:
                zeile.append(2.0)
            tzeile.append(str(d[0]) if len(d) == 1 else ("{" + " ".join(map(str, d)) + "}" if len(d) <= 4 else f"{len(d)} Schichten"))
        z.append(zeile)
        text.append(tzeile)
    fig = go.Figure(go.Heatmap(z=z, text=text, texttemplate="%{text}", x=[f"T{c + 1}" for c in range(n)], y=[f"M{r + 1}" for r in range(n)],
                               colorscale=[[0.0, C.COLOR_PRE], [0.5, C.COLOR_FIXED], [1.0, C.COLOR_OPEN]], zmin=0, zmax=2, showscale=False,
                               xgap=2, ygap=2, hoverinfo="skip"))
    fig.update_yaxes(autorange="reversed", title_text=None)
    fig.update_layout(title=dict(text=titel, font=dict(size=14)))
    return _base(fig, 300)


def build_raster(ordnungen: list, luecken: list, anteile: dict, titel: str):
    """Heatmap: Anteil der Instanzen, in denen die paarweise Vorwärtsprüfung am Budget abbrach, je (Ordnung, Lücken)."""
    z = [[anteile.get((o, l)) for l in luecken] for o in ordnungen]
    text = [[("–" if v is None else f"{round(v * 10)} von 10") for v in zeile] for zeile in z]
    fig = go.Figure(go.Heatmap(z=z, text=text, texttemplate="%{text}", x=[f"{l} %" for l in luecken], y=[f"Ordnung {o}" for o in ordnungen], colorscale="Oranges", zmin=0, zmax=1,
                               showscale=False, xgap=2, ygap=2, hoverinfo="skip"))
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(title=dict(text=titel, font=dict(size=14)))
    return _base(fig, 280)


def build_wachstum(groessen: list, reihen: list, titel: str):
    """Linien über den Job-Shop-Größen auf logarithmischer Achse. `reihen`: [(Name, Einheit, Werte oder None je Größe, Farbe)]; die Einheit steht im Namen der Linie."""
    fig = go.Figure()
    for name, einheit, werte, farbe in reihen:
        xs = [f"{g} × {g}" for g, w in zip(groessen, werte) if w is not None]
        ys = [max(w, 0.5) for w in werte if w is not None]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name=f"{name} ({einheit})", line=dict(color=farbe, width=3),
                                 hovertemplate=f"{name}: %{{y:g}} {einheit}<extra></extra>"))
    fig.update_yaxes(title_text=titel, type="log")
    fig.update_xaxes(title_text="Aufträge × Maschinen")
    return _base(fig, 380)
