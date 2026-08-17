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
