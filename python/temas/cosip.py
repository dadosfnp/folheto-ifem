"""
Tema COSIP — Contribuição para Custeio do Serviço de Iluminação Pública.

Esqueleto inicial. Reproduz a estrutura do folheto COSIP impresso (16 pp.)
adaptada ao gerador unificado. Páginas marcadas TODO ainda precisam ser
implementadas — uso como referência para próximos folhetos.
"""
from core.base_folheto import FolhetoFNP
from core.tokens import (
    PAPER, BLUE, BLUE_DARK, BLUE_MID, YELLOW, YELLOW_DARK,
    MUTED, INK, WHITE,
    STRIPE_W, MARGIN, CONTENT_W, ASSETS_DIR,
    FS_EYEBROW, FS_TITLE_SECAO, FS_BODY,
)
from core.fonts import F
from core.components import (
    draw_stripe, draw_page_number, draw_header, draw_footer,
    draw_eyebrow, draw_titulo, draw_body, draw_caption,
    draw_destaque_box, draw_card_topbar, draw_table,
    draw_section_divider, draw_qr_page,
)


class FolhetoCOSIP(FolhetoFNP):
    titulo_publicacao = "COSIP · O FUTURO DA CONTRIBUIÇÃO MUNICIPAL"

    def construir_paginas(self):
        return [
            self._pag_capa,
            self._pag_novo_papel,
            self._pag_o_que_mudou,
            self._pag_protagonismo_fnp,
            self._pag_por_que_essencial,
            self._pag_dados_arrecadacao,
            self._pag_ranking_oportunidade,
            self._pag_qr,
        ]

    # ─── Páginas ─────────────────────────────────────────────────────────────

    def _pag_capa(self, c, n):
        d = self.d

        capa_img = ASSETS_DIR / "capa-cosip.png"
        if capa_img.exists():
            c.drawImage(
                str(capa_img), 0, 0,
                width=self.W - STRIPE_W, height=self.H,
                preserveAspectRatio=False, mask="auto",
            )
        else:
            c.setFillColor(BLUE)
            c.rect(0, 0, self.W - STRIPE_W, self.H, fill=1, stroke=0)

        draw_stripe(c, self.W, self.H, "dir")
        draw_page_number(c, self.W, n, "dir")

        BAND_H = 220
        c.setFillColor(BLUE)
        c.rect(0, 0, self.W - STRIPE_W, BAND_H, fill=1, stroke=0)

        c.setFillColor(WHITE)
        c.setFont(F("BarlowCondensed-Bold"), 30)
        c.drawString(44, BAND_H - 80, "Transformar,")
        c.drawString(44, BAND_H - 110, "Monitorar")
        c.drawString(44, BAND_H - 140, "e Conectar")

        c.setFillColor(YELLOW)
        c.setFont(F("BarlowCondensed-SemiBold"), 12)
        c.drawString(44, BAND_H - 165,
                     f"O Futuro da COSIP em {d.get('nome', 'seu município')}/{d.get('uf', '')}")

        fnp_path = ASSETS_DIR / "logos" / "fnp-logo.png"
        if fnp_path.exists():
            c.drawImage(str(fnp_path), self.W - STRIPE_W - 130, 30, width=110, height=42,
                        preserveAspectRatio=True, mask="auto")

    def _pag_novo_papel(self, c, n):
        c.setFillColor(PAPER)
        c.rect(0, 0, self.W, self.H, fill=1, stroke=0)
        draw_stripe(c, self.W, self.H, "dir")
        draw_page_number(c, self.W, n, "dir")
        draw_header(c, self.H, self.titulo_publicacao)
        draw_footer(c, self.W, "O Novo Papel da COSIP")

        x, y = MARGIN, self.H - 55
        draw_eyebrow(c, "Capítulo 01", x, y); y -= 10
        draw_titulo(c, "O novo papel\nda COSIP", x, y, size=38, color=YELLOW_DARK); y -= 80

        draw_destaque_box(
            c, "A CONTRIBUIÇÃO QUE FINANCIA…",
            "A COSIP evoluiu para financiar tecnologias de monitoramento, segurança, "
            "trânsito, prevenção de desastres e eficiência urbana.",
            x, y - 80, CONTENT_W, h=80,
        )

    def _pag_o_que_mudou(self, c, n):
        # Comparativo "antes × depois" da Reforma Tributária (PEC 132/2023).
        c.setFillColor(PAPER)
        c.rect(0, 0, self.W, self.H, fill=1, stroke=0)
        draw_stripe(c, self.W, self.H, "esq")
        draw_page_number(c, self.W, n, "esq")
        draw_header(c, self.H, self.titulo_publicacao)
        draw_footer(c, self.W, "O que mudou")

        x = STRIPE_W + MARGIN
        y = self.H - 55
        draw_eyebrow(c, "Reforma Tributária · Art. 149-A", x, y); y -= 8
        draw_titulo(c, "O que mudou?", x, y, size=FS_TITLE_SECAO); y -= 34

        half = (CONTENT_W - 12) / 2
        draw_card_topbar(
            c, "ANTES",
            "Tributo com destinação exclusiva ao custeio da iluminação pública.",
            x, y - 140, half, 138, top_color=YELLOW_DARK,
        )
        draw_card_topbar(
            c, "DEPOIS",
            "Custeio, expansão e melhoria da iluminação pública E de sistemas de "
            "monitoramento para segurança e preservação de logradouros.",
            x + half + 12, y - 140, half, 138, top_color=BLUE,
        )

    def _pag_protagonismo_fnp(self, c, n):
        # TODO: cards das defesas FNP + autonomia financeira + voz dos municípios.
        draw_section_divider(
            c, self.W, self.H,
            capitulo="Capítulo 02",
            titulo="A FNP e a\nNova COSIP",
            subtitulo="Protagonismo da Frente Nacional de Prefeitas e Prefeitos.",
            n_pagina=n, lado="dir",
        )

    def _pag_por_que_essencial(self, c, n):
        # TODO: 3 pilares (autonomia / cidades inteligentes / segurança e valorização).
        c.setFillColor(PAPER)
        c.rect(0, 0, self.W, self.H, fill=1, stroke=0)
        draw_stripe(c, self.W, self.H, "esq")
        draw_page_number(c, self.W, n, "esq")
        draw_header(c, self.H, self.titulo_publicacao)
        draw_footer(c, self.W, "Por que é essencial")

        x = STRIPE_W + MARGIN
        y = self.H - 55
        draw_eyebrow(c, "Capítulo 03", x, y); y -= 8
        draw_titulo(c, "Por que a Nova COSIP\né essencial?", x, y, size=FS_TITLE_SECAO); y -= 60

        draw_body(
            c,
            "Autonomia financeira · Cidades inteligentes · Segurança e valorização. "
            "(Conteúdo detalhado a implementar na próxima iteração.)",
            x, y, CONTENT_W, size=FS_BODY,
        )

    def _pag_dados_arrecadacao(self, c, n):
        d = self.d

        c.setFillColor(PAPER)
        c.rect(0, 0, self.W, self.H, fill=1, stroke=0)
        draw_stripe(c, self.W, self.H, "dir")
        draw_page_number(c, self.W, n, "dir")
        draw_header(c, self.H, self.titulo_publicacao)
        draw_footer(c, self.W, "Arrecadação COSIP")

        x, y = MARGIN, self.H - 55
        draw_eyebrow(c, f"COSIP · {d.get('nome','Município')}/{d.get('uf','')}", x, y); y -= 8
        draw_titulo(c, "Arrecadação histórica", x, y, size=FS_TITLE_SECAO); y -= 34

        # Tabela: ano × arrecadação total × per capita.
        serie = d.get("arrecadacao_serie", [])
        if not serie:
            draw_body(c, "Série histórica indisponível para este município.",
                      x, y, CONTENT_W, size=FS_BODY)
            return

        col_w = [CONTENT_W * 0.25, CONTENT_W * 0.40, CONTENT_W * 0.35]
        headers = ["Ano", "Arrecadação (R$ mi)", "Per capita (R$)"]
        rows = [
            [str(r["ano"]), f"{r['total_mi']:,.1f}", f"{r['per_capita']:,.2f}"]
            for r in serie
        ]
        y = draw_table(c, headers, rows, col_w, x, y, highlight_col=1)

        y -= 16
        draw_caption(c, "Fonte: STN/Siconfi. Elaboração: FNP. Valores deflacionados (base 2024).", x, y)

    def _pag_ranking_oportunidade(self, c, n):
        d = self.d
        r = d.get("rankings", {})
        opp = d.get("oportunidades", {})

        c.setFillColor(PAPER)
        c.rect(0, 0, self.W, self.H, fill=1, stroke=0)
        draw_stripe(c, self.W, self.H, "esq")
        draw_page_number(c, self.W, n, "esq")
        draw_header(c, self.H, self.titulo_publicacao)
        draw_footer(c, self.W, "Ranking e Oportunidades")

        x = STRIPE_W + MARGIN
        y = self.H - 55
        draw_eyebrow(c, "Capítulo 04", x, y); y -= 8
        draw_titulo(c, "Ranking e oportunidades", x, y, size=FS_TITLE_SECAO); y -= 40

        # Mostra oportunidades de arrecadação como destaque + cards.
        cards = [
            ("Comparado à média nacional", opp.get("vs_nacional", "—")),
            ("Comparado ao mesmo porte",   opp.get("vs_porte",    "—")),
            ("Comparado à UF",             opp.get("vs_uf",       "—")),
        ]
        cw = (CONTENT_W - 16) / 3
        ch = 100
        for i, (titulo, valor) in enumerate(cards):
            cx = x + i * (cw + 8)
            cy = y - ch
            c.setFillColor(WHITE)
            c.roundRect(cx, cy, cw, ch, 3, fill=1, stroke=0)
            c.setFillColor(BLUE_MID)
            c.rect(cx, cy + ch - 4, cw, 4, fill=1, stroke=0)
            c.setFillColor(MUTED)
            c.setFont(F("Inter-Regular"), 7)
            c.drawString(cx + 10, cy + ch - 22, titulo.upper())
            c.setFillColor(BLUE_DARK)
            c.setFont(F("BarlowCondensed-Bold"), 22)
            c.drawString(cx + 10, cy + 30, str(valor))

    def _pag_qr(self, c, n):
        ultima = ASSETS_DIR / "ultima-cosip.png"
        draw_qr_page(
            c, self.W, self.H,
            url=self.d.get("url", "https://radarppp.com/fnp"),
            n_pagina=n, lado="dir",
            imagem_fundo=str(ultima) if ultima.exists() else None,
        )
