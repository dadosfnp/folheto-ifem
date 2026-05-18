# Fontes

Baixar e colocar nesta pasta os arquivos `.ttf` (não versionados no git):

| Arquivo                              | Origem                                                  |
|--------------------------------------|---------------------------------------------------------|
| `BarlowCondensed-Bold.ttf`           | https://fonts.google.com/specimen/Barlow+Condensed      |
| `BarlowCondensed-SemiBold.ttf`       | https://fonts.google.com/specimen/Barlow+Condensed      |
| `BarlowCondensed-Regular.ttf`        | https://fonts.google.com/specimen/Barlow+Condensed      |
| `Inter-Regular.ttf`                  | https://fonts.google.com/specimen/Inter                 |
| `Inter-SemiBold.ttf`                 | https://fonts.google.com/specimen/Inter                 |
| `Inter-Bold.ttf`                     | https://fonts.google.com/specimen/Inter                 |

Se algum arquivo não existir, o gerador usa **Helvetica** como fallback automático
(implementado em `python/core/fonts.py`). Os PDFs continuam sendo gerados, mas sem
o tratamento tipográfico oficial FNP.
