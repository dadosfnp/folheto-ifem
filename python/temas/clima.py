"""
Tema CLIMA — atalho de preview das duas páginas de Risco Climático.

O conteúdo NÃO mora aqui: as páginas foram mescladas em `temas/ifem.py`
(`_pag_risco_panorama` e `_pag_risco_municipio`), onde vivem todas as páginas do
folheto do IFEM. Este módulo só existe para iterar nelas sem regerar as outras
16 — útil ao ajustar layout, inútil para distribuir.

    python python/gerar.py --tema clima --dados data/ifem/dados-ifem/export_folheto/<arquivo>.json

O JSON precisa do bloco `risco_climatico`; sem ele o folheto sai vazio de
propósito (mesma guarda de `FolhetoIFEM.construir_paginas`). Para gravá-lo:

    python tools/adapta_para_json.py --injetar --cod-ibge <cod>

O folheto que vai para a gráfica é sempre `--tema ifem`.
"""
import sys

from .ifem import FolhetoIFEM

# Posição real do spread dentro do folheto completo. Preview fora dessas
# posições sairia com o stripe na borda errada — as páginas são um par
# (esquerda/direita) e só se leem abertas em (par, ímpar).
PAGINA_PANORAMA = 14
PAGINA_MUNICIPIO = 15


class FolhetoClima(FolhetoIFEM):
    """Só o spread de Risco Climático, numerado como no folheto completo."""

    def construir_paginas(self):
        if not self.risco_climatico:
            print("[aviso] JSON sem o bloco `risco_climatico` — nada a desenhar.\n"
                  "        Rode: python tools/adapta_para_json.py --injetar "
                  f"--cod-ibge {self.ident.get('cod_ibge', '')}",
                  file=sys.stderr)
            return []
        return [
            lambda c, _: self._pag_risco_panorama(c, PAGINA_PANORAMA),
            lambda c, _: self._pag_risco_municipio(c, PAGINA_MUNICIPIO),
        ]
