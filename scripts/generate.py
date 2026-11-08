"""Gera os SVGs do README de perfil no estilo do quadro do portfólio.

Cada gráfico sai em duas versões: claro (papel pontilhado) e escuro (lousa).
As fontes (JetBrains Mono e Caveat) vão embutidas e recortadas só com os
caracteres usados, porque o GitHub não carrega fontes externas em <img>.

Uso: python scripts/generate.py  (precisa de fonttools + brotli)
"""
import base64
import io
import os
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "scripts", "fonts")
OUT = os.path.join(ROOT, "assets")

# Mesmos tokens do theme.css do portfólio.
THEMES = {
    "light": dict(bg="#f7f5f0", dot="#d6d2c8", ink="#1f1f1f", paper="#ffffff",
                  accent="#2563eb", muted="#6b6b6b", yellow="#fde68a",
                  blue="#bfdbfe", green="#bbf7d0", shadow="#1f1f1f", shadow_op="1",
                  sticky_ink="#1f1f1f"),
    "dark": dict(bg="#1f2b27", dot="#3b4a45", ink="#ecebe4", paper="#263631",
                 accent="#7fb0ff", muted="#a7b0aa", yellow="#e8d27a",
                 blue="#a9c9ec", green="#a3d9b1", shadow="#000000", shadow_op="0.45",
                 sticky_ink="#1f1f1f"),
}

FONT_FILES = {
    "mono": ("JetBrains Mono", "jetbrains-mono-latin-400-normal.woff2", 400),
    "monob": ("JetBrains Mono", "jetbrains-mono-latin-700-normal.woff2", 700),
    "hand": ("Caveat", "caveat-latin-700-normal.woff2", 700),
}


def font_face(key, text):
    """Recorta a fonte só com os glifos usados e devolve um @font-face."""
    family, file, weight = FONT_FILES[key]
    font = TTFont(os.path.join(FONTS, file))
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["kern", "liga", "calt"]
    sub = subset.Subsetter(opts)
    sub.populate(text=text + " ")
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    data = base64.b64encode(buf.getvalue()).decode()
    return (f"@font-face{{font-family:'{family}';font-weight:{weight};"
            f"src:url(data:font/woff2;base64,{data}) format('woff2');}}")


class Svg:
    """Acumula elementos e o texto de cada fonte, para recortar no final."""

    def __init__(self, w, h, t, title):
        self.w, self.h, self.t, self.title = w, h, t, title
        self.parts = []
        self.used = {"mono": "", "monob": "", "hand": ""}

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, s, font="mono", size=14, fill=None, anchor="start",
             rotate=0, extra=""):
        self.used[font] += s
        fam = "Caveat" if font == "hand" else "JetBrains Mono"
        weight = 400 if font == "mono" else 700
        rot = f' transform="rotate({rotate} {x} {y})"' if rotate else ""
        self.add(f'<text x="{x}" y="{y}" font-family="{fam}, monospace" '
                 f'font-weight="{weight}" font-size="{size}" '
                 f'fill="{fill or self.t["ink"]}" text-anchor="{anchor}"{rot}{extra}>'
                 f'{escape(s)}</text>')

    def card(self, x, y, w, h, fill=None, rotate=0, sw=2):
        """Caixa do quadro: borda de tinta e sombra dura deslocada 4px."""
        t = self.t
        rot = f' transform="rotate({rotate} {x + w / 2} {y + h / 2})"' if rotate else ""
        self.add(f'<g{rot}><rect x="{x + 4}" y="{y + 4}" width="{w}" height="{h}" rx="6" '
                 f'fill="{t["shadow"]}" fill-opacity="{t["shadow_op"]}"/>'
                 f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" '
                 f'fill="{fill or t["paper"]}" stroke="{t["ink"]}" stroke-width="{sw}"/></g>')

    def arrow(self, d, color=None, dashed=False, sw=2):
        dash = ' stroke-dasharray="6 5"' if dashed else ""
        self.add(f'<path d="{d}" fill="none" stroke="{color or self.t["ink"]}" '
                 f'stroke-width="{sw}" stroke-linecap="round"{dash} marker-end="url(#head)"/>')

    def render(self, background=True):
        t = self.t
        faces = "".join(font_face(k, v) for k, v in self.used.items() if v)
        bg = ""
        if background:
            bg = (f'<rect width="{self.w}" height="{self.h}" rx="10" fill="{t["bg"]}"/>'
                  f'<rect width="{self.w}" height="{self.h}" rx="10" fill="url(#dots)"/>')
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                f'viewBox="0 0 {self.w} {self.h}" role="img"><title>{escape(self.title)}</title>'
                f'<defs><style>{faces}</style>'
                f'<pattern id="dots" width="20" height="20" patternUnits="userSpaceOnUse">'
                f'<circle cx="2" cy="2" r="1.2" fill="{t["dot"]}"/></pattern>'
                f'<marker id="head" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" '
                f'markerHeight="8" orient="auto-start-reverse">'
                f'<path d="M1 1 L9 5 L1 9" fill="none" stroke="context-stroke" stroke-width="1.6" '
                f'stroke-linecap="round" stroke-linejoin="round"/></marker></defs>'
                f'{bg}{"".join(self.parts)}</svg>')


def wrap(s, chars):
    """Quebra de linha simples; a fonte é monoespaçada, então conta caracteres."""
    lines, cur = [], ""
    for word in s.split():
        if cur and len(cur) + 1 + len(word) > chars:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        lines.append(cur)
    return lines


def sticky(svg, x, y, w, h, color, lines, rotate, size=24):
    t = svg.t
    cx, cy = x + w / 2, y + h / 2
    svg.add(f'<g transform="rotate({rotate} {cx} {cy})">'
            f'<rect x="{x + 3}" y="{y + 4}" width="{w}" height="{h}" fill="#000" fill-opacity="0.12"/>'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{t[color]}"/>'
            f'<rect x="{x + w / 2 - 22}" y="{y - 7}" width="44" height="14" fill="{t["paper"]}" '
            f'fill-opacity="0.55" transform="rotate(-3 {x + w / 2} {y})"/></g>')
    start = cy - (len(lines) - 1) * size * 0.55
    for i, line in enumerate(lines):
        svg.text(cx, start + i * size * 1.1 + size * 0.3, line, font="hand", size=size,
                 fill=t["sticky_ink"], anchor="middle", rotate=rotate)


# ---------------------------------------------------------------- gráficos

def header(t):
    s = Svg(880, 300, t, "Luiz Kirsch, desenvolvedor fullstack pleno")
    s.card(40, 46, 470, 200)
    s.text(68, 96, "$ whoami", size=15, fill=t["muted"])
    s.text(68, 146, "luiz kirsch", font="monob", size=40)
    s.text(68, 182, "desenvolvedor fullstack · pleno", size=17)
    s.text(68, 216, "campo bom, rs", size=15, fill=t["muted"])
    s.add(f'<rect x="200" y="204" width="10" height="16" fill="{t["accent"]}"/>')

    sticky(s, 560, 42, 150, 104, "yellow", ["laravel", "+ react"], -4)
    sticky(s, 700, 118, 150, 104, "blue", ["erp de", "consórcios"], 3)
    sticky(s, 556, 172, 140, 96, "green", ["ads · ienh", "2027"], -2)

    s.text(258, 284, "desenho antes de codar", font="hand", size=27, fill=t["accent"], rotate=-2)
    s.arrow("M250 278 C 210 278, 190 268, 182 252", color=t["accent"])
    return s


def trajetoria(t):
    s = Svg(880, 230, t, "Trajetória: QA automatizado em 2022, desenvolvimento em 2023, "
                         "dev júnior em 2024, dev pleno em 2026")
    boxes = [
        ("2022", "qa automatizado", ["cypress, selenium,", "codeceptjs"]),
        ("2023", "dev fullstack", ["php puro pra", "laravel multi-tenant"]),
        ("2024", "dev júnior", ["laravel, livewire,", "rpa em python"]),
        ("2026", "dev pleno", ["arquitetura dos", "módulos e dados"]),
    ]
    labels = ["migrei pro código", "", "promoção"]
    w, h, gap, y = 176, 120, 40, 60
    x0 = (880 - (4 * w + 3 * gap)) / 2
    for i, (year, title, desc) in enumerate(boxes):
        x = x0 + i * (w + gap)
        last = i == len(boxes) - 1
        s.card(x, y, w, h, fill=t["blue"] if last else None)
        ink = t["sticky_ink"] if last else t["ink"]
        mut = t["sticky_ink"] if last else t["muted"]
        s.text(x + 16, y + 30, year, size=13, fill=mut)
        s.text(x + 16, y + 58, title, font="monob", size=15, fill=ink)
        for j, line in enumerate(desc):
            s.text(x + 16, y + 84 + j * 18, line, size=12, fill=mut)
        if i < len(labels):
            ax = x + w + 6
            s.arrow(f"M{ax} {y + h / 2} L{ax + gap - 14} {y + h / 2}")
            if labels[i]:
                s.text(ax + (gap - 8) / 2, y - 14 if i % 2 == 0 else y + h + 32, labels[i],
                       font="hand", size=21, fill=t["accent"], anchor="middle",
                       rotate=-3 if i % 2 == 0 else 2)
    return s


def agenda(t):
    """Projeto em destaque: arquitetura do agenda-eletricista como diagrama."""
    s = Svg(880, 330, t, "agenda-eletricista: React, API Express com Sequelize e MySQL, "
                         "com a análise documentada num vault do Obsidian")
    s.text(40, 52, "agenda-eletricista", font="monob", size=24)
    s.text(40, 80, "agenda e ordens de serviço para eletricista autônomo", size=14,
           fill=t["muted"])

    nodes = [
        (40, "react", ["agenda semanal", "drag-and-drop"]),
        (250, "api express", ["conflito de horário", "perfis de acesso"]),
        (460, "sequelize", ["models e", "migrations"]),
        (670, "mysql", ["clientes, serviços,", "agendamentos"]),
    ]
    y, w, h = 120, 166, 96
    for x, title, desc in nodes:
        s.card(x, y, w, h)
        s.text(x + 14, y + 30, title, font="monob", size=15)
        for j, line in enumerate(desc):
            s.text(x + 14, y + 56 + j * 18, line, size=11.5, fill=t["muted"])
    for x in (206, 416, 626):
        s.arrow(f"M{x + 8} {y + h / 2} L{x + 38} {y + h / 2}")
    s.text(229, y - 10, "http", font="hand", size=20, fill=t["accent"], anchor="middle")
    s.text(649, y - 10, "sql", font="hand", size=20, fill=t["accent"], anchor="middle")

    sticky(s, 300, 250, 300, 58, "yellow", ["vault do obsidian: requisitos,",
                                            "regras de negócio e diagramas"], -1.5, size=21)
    s.arrow("M296 272 C 200 276, 130 262, 123 226", dashed=True, color=t["accent"])
    s.arrow("M606 270 C 690 272, 748 258, 753 226", dashed=True, color=t["accent"])
    s.text(40, 306, "escrito antes do código", font="hand", size=21, fill=t["accent"],
           rotate=-2)
    return s


def tile(t, name, tag, tag_color, desc, stack):
    s = Svg(430, 200, t, f"{name}: {desc}")
    s.card(8, 8, 410, 180)
    s.text(28, 48, name, font="monob", size=19)
    tw = len(tag) * 7.2 + 20
    s.add(f'<rect x="{408 - tw - 8}" y="26" width="{tw}" height="24" rx="12" '
          f'fill="{t[tag_color]}" stroke="{t["ink"]}" stroke-width="1.5"/>')
    s.text(408 - 8 - tw / 2, 42, tag, size=12, fill=t["sticky_ink"], anchor="middle")
    for i, line in enumerate(wrap(desc, 44)[:4]):
        s.text(28, 80 + i * 20, line, size=13)
    s.add(f'<line x1="28" y1="152" x2="398" y2="152" stroke="{t["dot"]}" stroke-width="1.5" '
          f'stroke-dasharray="4 4"/>')
    s.text(28, 174, stack, size=11.5, fill=t["muted"])
    return s


TILES = {
    "tako": ("tako", "em construção", "yellow",
             "cli que liga um board do github projects a um agente de ia: escolhe o card no "
             "terminal e a ferramenta cria a branch, abre o agente e entrega o pr",
             "typescript · node · ink · gh cli"),
    "tenancy": ("tenancy-laravel", "estudo", "green",
                "aplicação multi-tenant com banco isolado por tenant, identificado pelo "
                "subdomínio e provisionado na criação",
                "laravel · stancl/tenancy · livewire · mysql"),
    "oraculo": ("oraculo", "poc", "blue",
                "assistente que responde perguntas sobre documentos internos (pdfs e imagens "
                "com ocr) usando rag com filtro por categoria",
                "python · fastapi · langchain · chromadb"),
    "barnout": ("barnout", "código privado", "yellow",
                "gamificação do bar congress, evento universitário: pontuação, ranking e "
                "integração com o app. dev e organização do time",
                "laravel · mysql · next.js"),
}


def stack(t):
    s = Svg(880, 250, t, "Stack: PHP, Laravel, Livewire, Node.js, Express, Python; TypeScript, "
                         "React, Next.js, Tailwind; MySQL, Redis, Docker, Linux; "
                         "Cypress, Selenium, PHPUnit, Playwright")
    cols = [
        ("back-end", "yellow", ["php · laravel", "livewire", "node · express", "python · fastapi"]),
        ("front-end", "blue", ["typescript", "react · next.js", "vite", "tailwind · alpine"]),
        ("dados e infra", "green", ["mysql · sqlite", "redis", "docker · linux", "github actions"]),
        ("qualidade", "yellow", ["cypress", "selenium", "phpunit", "playwright"]),
    ]
    w, gap = 190, 20
    x0 = (880 - (4 * w + 3 * gap)) / 2
    for i, (title, color, items) in enumerate(cols):
        x = x0 + i * (w + gap)
        s.card(x, 40, w, 180)
        s.add(f'<rect x="{x}" y="40" width="{w}" height="40" rx="6" fill="{t[color]}" '
              f'stroke="{t["ink"]}" stroke-width="2"/>')
        s.text(x + 16, 66, title, font="monob", size=14, fill=t["sticky_ink"])
        for j, item in enumerate(items):
            s.text(x + 16, 112 + j * 28, item, size=13)
    return s


def main():
    os.makedirs(OUT, exist_ok=True)
    jobs = {"header": header, "trajetoria": trajetoria, "agenda": agenda, "stack": stack}
    for mode, t in THEMES.items():
        for name, fn in jobs.items():
            write(f"{name}-{mode}.svg", fn(t).render())
        for key, args in TILES.items():
            write(f"tile-{key}-{mode}.svg", tile(t, *args).render())


def write(name, content):
    with open(os.path.join(OUT, name), "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print(f"{name:28} {len(content) / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
