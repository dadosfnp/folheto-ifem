"""
Registro de temas disponíveis.

Para adicionar um folheto novo:
  1. Crie `temas/<nome>.py` com uma classe que estende FolhetoFNP.
  2. Registre abaixo no dict TEMAS.
  3. Crie `data/<nome>/<municipio>.json` com a estrutura esperada.
"""
from .ifem import FolhetoIFEM
from .cosip import FolhetoCOSIP

TEMAS = {
    "ifem":  FolhetoIFEM,
    "cosip": FolhetoCOSIP,
}
