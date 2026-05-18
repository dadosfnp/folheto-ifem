"""
Classe-base FolhetoFNP.

Cada tema (COSIP, IFEM, …) cria uma subclasse e implementa apenas
`construir_paginas()` — uma lista de callables que recebem (canvas, n_pagina)
e desenham uma página. Toda a infraestrutura (PDF, fontes, output) fica aqui.
"""
from pathlib import Path
from typing import Callable
from reportlab.pdfgen import canvas as rl_canvas

from .tokens import PAGE_SIZE, OUTPUT_DIR
from .fonts import register_fonts


PageFn = Callable[[rl_canvas.Canvas, int], None]


class FolhetoFNP:
    """
    Classe-base para todos os folhetos FNP.

    Subclasses devem definir:
      - `titulo_publicacao`: ex. "IFEM · ÍNDICE DE FINANCIAMENTO DE EQUIDADE MUNICIPAL"
      - método `construir_paginas() -> list[PageFn]`: ordem das páginas.

    Subclasses NÃO devem reescrever `gerar()`.
    """

    titulo_publicacao: str = "FNP — FOLHETO INSTITUCIONAL"

    def __init__(self, dados: dict, output_path: Path | None = None):
        self.d = dados
        self.W, self.H = PAGE_SIZE
        self.output_path = output_path or self._default_output()
        register_fonts()

    def _output_name(self) -> tuple[str, str]:
        """Subclasse pode sobrescrever pra adaptar ao seu schema. Default lê (nome, uf) da raiz."""
        return self.d.get("nome", "folheto"), self.d.get("uf", "")

    def _default_output(self) -> Path:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        nome, uf = self._output_name()
        nome = (nome or "folheto").replace(" ", "_")
        sufixo = f"_{uf}" if uf else ""
        return OUTPUT_DIR / f"{self.__class__.__name__}_{nome}{sufixo}.pdf"

    def construir_paginas(self) -> list[PageFn]:
        """Subclasse implementa. Retorna lista ordenada de funções de página."""
        raise NotImplementedError("Subclasses devem implementar construir_paginas()")

    def gerar(self) -> Path:
        """Gera o PDF completo. Retorna o caminho do arquivo."""
        c = rl_canvas.Canvas(str(self.output_path), pagesize=PAGE_SIZE)

        for n, page_fn in enumerate(self.construir_paginas(), start=1):
            page_fn(c, n)
            c.showPage()

        c.save()
        return self.output_path
