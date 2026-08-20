# Lições — Folhetos FNP

## 2026-08-17 — Nunca propor comando destrutivo em banco como passo de rotina

**O que aconteceu:** recomendei `python manage.py recriar_banco --confirmar` como
um passo numerado dentro de uma lista de instruções, para popular o SQLite local
a partir das planilhas. O comando dropa todas as tabelas do database conectado.
O Pedro interrompeu, alarmado — com razão.

**Por que foi errado**, mesmo apontando para um SQLite local vazio:

- O cluster PostgreSQL da FNP hospeda vários bancos (`ifem`, `fnp_sistema`,
  financeiro). Um erro de configuração de `DATABASE_URL` transforma um comando
  "local" em perda de dados de produção de outras aplicações.
- Segurança que depende de uma variável de ambiente estar comentada é frágil:
  basta alguém descomentar, ou uma env var do sistema ter precedência.
- Apresentar um `drop` como item de checklist esconde o risco. O usuário lê a
  lista inteira como "passos normais" e executa sem avaliar cada um.

**Regra daqui em diante:**

1. Qualquer comando que apague, dropa, trunque ou sobrescreva dados — em banco,
   disco ou remoto — vai numa mensagem **isolada**, com o risco declarado antes
   do comando, e só depois de confirmação explícita. Nunca dentro de uma lista.
2. Antes de sugerir, verificar o alvo real: qual database, quantos registros,
   o que mais vive naquele servidor.
3. Preferir sempre a alternativa aditiva: banco novo em arquivo separado em vez
   de recriar o existente; `--out` para diretório novo em vez de sobrescrever.
4. Se a operação destrutiva for mesmo necessária, explicar por que nenhuma
   alternativa aditiva serve — e deixar a decisão com o Pedro.

**Contexto que motivou:** o repo Subfinanciados é read-only nesta tarefa (o Pedro
foi explícito: "lá tá funcionando tudo com os dados 2025 atualizados"). Escrever
qualquer coisa lá dentro, inclusive na pasta `export_folheto/`, é violar isso —
usar `--out` apontando para fora.

---

## 2026-08-20 — Conteúdo editorial dentro de pasta gitignorada sai vazio em toda máquina nova

**O que aconteceu:** um colega clonou o repo, seguiu o `PASSO_A_PASSO.md` à risca
e a página "Metodologia" saiu em branco — só a imagem à direita, sem texto. O
gerador avisava (`[aviso] _metodologia.json não encontrado`), mas o arquivo
existia e funcionava na minha máquina.

**Por que:** `_metodologia.json` só existia dentro de
`data/ifem/dados-ifem/export_folheto/` — pasta inteira no `.gitignore`, e com
razão (5.4k arquivos, ~94 MB, regeneráveis). Só que o conteúdo dela **não é
homogêneo**: os JSONs municipais são dado calculado, regenerável a partir das
planilhas; `_metodologia.json` é texto editorial que nenhuma planilha origina.
Ignorar a pasta por causa do volume levou o texto embora junto. O
`_problema.json` tinha o mesmo risco e alguém já havia resolvido — o
`_metodologia.json` nunca ganhou o mesmo tratamento, e o defeito ficou invisível
em qualquer máquina que já tivesse um lote antigo em disco.

**Regra daqui em diante:**

1. Antes de concluir que um arquivo "está no projeto", checar com
   `git ls-files <arquivo>` — não com `ls`. O que existe em disco na máquina de
   quem desenvolveu não é o que o repo entrega.
2. Pasta ignorada por **volume** precisa ser auditada por **tipo de conteúdo**:
   dado calculado pode ficar fora; texto redacional, nunca. Se um script não
   consegue regenerar o arquivo, ele tem que estar versionado.
3. Quando um arquivo ganha fallback versionado, verificar se existe algum
   **irmão na mesma categoria** sem o mesmo tratamento. O fix do `_problema.json`
   apontava exatamente para o buraco do `_metodologia.json`.
4. Fechar o buraco no **script de setup**, não só no fallback: o gerador prefere
   a cópia ao lado dos dados à versionada, então um lote velho em disco continua
   vencendo em silêncio. O `planilhas_para_json.py` e o `sync_dados.py` agora
   copiam a versão do repo por cima, sempre.
5. Aviso em `stderr` não é rede de proteção suficiente para conteúdo ausente —
   ninguém lê `stderr` num lote de 400 PDFs. Só percebemos porque o colega abriu
   o PDF e viu a página vazia.

**Contexto e uma segunda lição:** o texto nasceu como dict hardcoded em ASCII
puro no `export_folheto_municipios.py` do Subfinanciados, então a página imprime
"metodo" e "populacao" sem acento. Cheguei a versionar a cópia já acentuada — o
Pedro reverteu. **Corrigir um defeito de conteúdo não é parte de destravar o
build.** Eram duas mudanças com consequências diferentes: uma faz a página deixar
de sair vazia, a outra altera o que já foi impresso e distribuído, e ainda cria
duas fontes divergentes (repo acentuado vs. export ASCII) onde antes havia uma.
A correção de acento existe como pendência para ser feita nos dois lados de uma
vez, não de carona.
