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

---

## Travessão no folheto: convenção da publicação, não gosto do autor

**O que aconteceu:** escrevi as páginas de Risco Climático usando travessão (—)
em texto corrido, do jeito que escrevo em qualquer outro lugar. Na revisão o Pedro
cortou: *"tire todas as barras do texto, nunca é para aparecer"*.

**Por que passou:** olhei o DESIGN_SYSTEM.md atrás de cor, fonte e grid — e não
havia nada sobre pontuação, então assumi que não havia regra. Havia: estava na
cabeça de quem revisa, e o folheto anterior só não a contrariava por acaso. Pior:
o caractere já existia em texto que eu não escrevi (`_problema.json`, título do
quadro da UF, placeholders de valor ausente), então "só arrumar a minha página"
deixaria o defeito vivo em outras três.

**Regra daqui em diante:**

1. Convenção tipográfica de uma publicação é regra do projeto. Ao escrever copy
   nova, imitar a pontuação que **já está impressa** nas páginas aprovadas em vez
   de importar o próprio estilo.
2. Quando o cliente enuncia uma regra ("nunca é para aparecer"), ela vale para o
   **documento inteiro**: copy nova, texto editorial nos JSONs e placeholders de
   dado ausente. Auditar tudo antes de responder, não só a página que ele estava
   olhando.
3. Regra recém-descoberta vira **linha no DESIGN_SYSTEM.md + item de checklist
   verificável**, senão volta no próximo folheto. A verificação aqui é objetiva:
   varrer `page.get_text()` de todas as páginas do PDF atrás do caractere.
4. Placeholder de valor ausente nunca é um traço solto: num KPI ele se confunde
   com sinal de menos. `n/d` diz o que aconteceu.

---

## Decoração não pode cobrir dado: quem desenha por último precisa medir

**O que aconteceu:** o Pedro mandou o print da página de Risco Climático com a
arte do rodapé por cima da tabela — a última linha ("Integridade da
biodiversidade") ficava escondida atrás dos quartos de círculo. Auditando o lote
inteiro, o defeito não era daquele município nem daquela página: **424 de 424
folhetos publicados** tinham a arte cobrindo conteúdo, em três páginas cada
(receita nível 1-2, primeira do nível 3 e a tabela de risco).

**Por que passou:** `_decorar_rodape` tinha dois caminhos de encaixe. No caminho
"largura total" (o da arte1, e o usado por toda chamada com `forcar_fina`) a
altura saía de `w_disp / ratio` e **nunca era comparada com o espaço livre** — o
clamp existia só no outro ramo. Uma arte1 de 87pt entrava num rodapé de 30pt e
apagava 24pt de tabela. Como PDF não tem colisão nem erro, nada avisou: o
arquivo abre, o texto continua extraível pelo `get_text()`, e só quem olha a
página vê.

Pior: cada chamador fazia a própria conta antes de chamar
(`if y - arte1_h_estim - 4 >= SAFE_BOTTOM`, `if y_after > SAFE_BOTTOM + 8`,
`if y > SAFE_BOTTOM + 50`), com pisos diferentes entre si e diferentes do que a
função usava por dentro. Três contas paralelas para uma regra só, e duas delas
erradas.

**Regra daqui em diante:**

1. Quem desenha por último é quem tem que medir. Se um elemento é aplicado por
   cima de uma página já montada, o cálculo de "cabe?" mora **dentro** dele, e o
   chamador só informa onde o conteúdo terminou. Guarda no call site é convite a
   divergência.
2. Toda decoração degrada em cascata explícita — encolhe, troca por uma variante
   menor, ou não aparece. **Rodapé branco é aceitável; dado coberto, não.**
   Quando o design pede o inverso, é o layout que está apertado demais, não a
   decoração que merece prioridade.
3. Defeito visual em PDF não aparece em `stderr` nem em teste de conteúdo. A
   verificação tem que medir **geometria do arquivo gerado**: `tools/verificar_arte.py`
   compara o retângulo real da imagem com o de cada texto e vetor da página, e
   sai com código 1 se houver interseção. Entrou no checklist do DESIGN_SYSTEM.md.
4. Print de uma página é amostra, não escopo. Antes de responder "corrigi",
   rodar a verificação no lote inteiro — aqui, o que parecia um município virou
   1.272 páginas defeituosas em produção.

---

## Fallback que depende de pasta ignorada não é fallback

**O que aconteceu:** o Phillip não conseguiu gerar o folheto de Almirante
Tamandaré. O município não declarou receita de 2025, e `planilhas_para_json.py`
descarta quem não tem receita do ano — 130 municípios, 7 deles no recorte
publicado. Existia solução para isso desde sempre (`gerar_sem_declaracao.py`,
que publica o dado de 2024 com tarja de ressalva), mas na máquina dele o script
não tinha como funcionar.

**Por que não funcionava:** o script lia o dado de
`data/ifem/dados-ifem/_backup_2024/`, dentro da pasta que o `.gitignore` exclui
por volume. A justificativa da exclusão é "regenerável a qualquer momento com
`planilhas_para_json.py`" — e essa justificativa **é falsa para o ano anterior**:
em `base_datas/` só existem `receitas_correntes_2000.xlsx` e
`receitas_correntes_2025.xlsx`, e as planilhas de detalhamento e percentil não
têm recorte por ano. Rodar com `ANO_REF=2024` morre em "Planilha obrigatória
ausente". O dado de 2024 só existia como resíduo de uma execução antiga na
máquina de quem gerou o lote.

É a mesma lição do `_metodologia.json`, um nível acima: lá o arquivo não
versionado era editorial; aqui é dado — mas dado que **nenhum script recria**.

**Regra daqui em diante:**

1. Antes de aceitar "está ignorado porque é regenerável", **rodar o
   regenerador**. Se ele falha para algum recorte (um ano, um subconjunto, um
   município), aquele recorte não é regenerável e tem que estar versionado.
2. Fallback tem que funcionar num clone limpo, e a forma de saber é **testar num
   clone limpo** — aqui bastou renomear `_backup_2024/` e rodar. Nenhuma leitura
   de código tinha revelado isso: na máquina de quem escreveu, funcionava.
3. Descarte silencioso em pipeline de dados precisa dizer o que fazer, não só o
   que aconteceu. `[aviso] 130 pulados` fez concluir que aquelas cidades não têm
   folheto. O aviso agora nomeia os que estão no recorte publicado e aponta o
   script que os gera.
4. Ferramenta que existe e não está no README **não existe**. O
   `gerar_sem_declaracao.py` não era citado em lugar nenhum da documentação —
   nem no README, nem no PASSO_A_PASSO. Quem não escreveu o script não tinha
   como saber que o caminho existia.
