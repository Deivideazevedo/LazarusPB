# Lazarus IA — Guia de Uso

Pipeline para extrair código-fonte de bibliotecas **PowerBuilder 9** (.pbl) em
arquivos de texto (`.sr*`), versionar com Git, editar com IA e recompilar de
volta para `.pbl`.

---

## Índice

1. [O que cada pasta faz](#1-o-que-cada-pasta-faz)
2. [O que cada campo do config.json significa](#2-o-que-cada-campo-do-config-json-significa)
3. [Pré-requisitos](#3-pré-requisitos)
4. [Como configurar (passo a passo)](#4-como-configurar-passo-a-passo)
5. [Como extrair](#5-como-extrair)
6. [Como compilar (recriar o .pbl)](#6-como-compilar-recriar-o-pbl)
7. [Atalhos (.bat)](#7-atalhos-bat)
8. [Fluxo completo com Git e IA](#8-fluxo-completo-com-git-e-ia)
9. [Como validar que nada quebrou](#9-como-validar-que-nada-quebrou)
10. [Logs gerados](#10-logs-gerados)
11. [Solução de problemas](#11-solução-de-problemas)
12. [Como analisar dependências (`analise`)](#12-como-analisar-dependências-analise)
13. [Mapa de correspondência entre PBLs (`origem`)](#13-mapa-de-correspondência-entre-pbls-origem)

---

## 1. O que cada pasta faz

```
LazarusIA\
│
├── extrair.bat           ⭐ ATALHOS (duplo clique)
├── compilar.bat              extrair / compilar / validar / analise / origem
├── compilar_patch.bat        compila apenas alterados/novos em patch.pbl
├── integridade.bat           verifica integridade e encoding (CP1252)
├── validar.bat
├── analise.bat
├── origem.bat
│
├── codigo_fonte\        ← ARQUIVOS DE TEXTO (.sr*) extraídos dos .pbl
│   │                       É aqui que o Git e a IA trabalham.
│   ├── .origem\             Mapa de correspondência (gerado por origem.bat)
│   └── deivide\             Subpasta criada automaticamente para cada .pbl
│       ├── w_ope_hec.srw    window
│       ├── d_tab_oso_pref.srd   datawindow
│       └── f_converte_min_duracao.srf   function
│
├── compilacao\          ← .pbl RECRIADOS
│   └── deivide.pbl         PBL novo, gerado a partir dos .sr*
│
├── logs\                ← Logs com data/hora
│   ├── deivide.extracao.txt
│   ├── deivide.import.txt
│   └── deivide.validacao.txt
│
└── scripts\             ← Programas (não mexa a não ser para configurar)
    ├── config.json         ⭐ CONFIGURAÇÃO — edite este arquivo
    ├── extrair.py          Extrai .sr* dos .pbl
    ├── compilar.py         Reconstrói .pbl a partir dos .sr*
    ├── validar.py          Compara .pbl recriado com a fonte
    ├── analise.py          Mapeia dependências .sr* (nome/curinga/conteúdo)
    ├── origem.py           Mapa de correspondência entre PBLs
    ├── pbldump\            PblDump.exe (extrator)
    └── python32\           Python 32-bit (para usar a DLL do PowerBuilder)
```

---

---

## 2. O que cada campo do config.json significa

Este é o arquivo que você edita. Ele fica na **raiz** do projeto:
`config.json`.

> **Conceito importante:** os `.pbl` listados no config vivem no servidor/disco
> de origem (`G:\sdo\programa`). Eles são **somente leitura** para este
> pipeline: a extração copia o código para `codigo_fonte\` e é lá — e somente
> lá — que se trabalha. Nada é gravado de volta na `origem`; o `.pbl` novo sai
> em `compilacao\`, e só depois de validar você o copia por cima do original.

| Campo | O que é | Papel |
|---|---|---|
| `origem` | Pasta onde ficam os PBLs do projeto | Base para resolver nomes simples de `pbls`, `lib_list` e `app_lib` |
| `origem_pfc` | Pasta onde ficam as PFC (ex.: `G:\ni_pfc`) | Segunda base da `lib_list`: nomes simples não encontrados em `origem` são procurados aqui |
| `pbls` | Bibliotecas que VOCÊ quer processar | **São extraídas** para `codigo_fonte\` e **são recriadas** em `compilacao\` |
| `lib_list` | Outras bibliotecas do projeto | **Somente leitura.** Usadas na compilação para resolver referências (ancestrais PFC, datawindows de outras libs). **Nunca são extraídas, modificadas ou recriadas**. Aceita nome simples (resolvido contra `origem` e depois `origem_pfc`) ou caminho completo |
| `app_name` | Nome do application object | Obrigatório. O ORCA só importa com um application definido |
| `app_lib` | Biblioteca onde está o application | Obrigatório. Ex.: `sdo01.pbl` |
| `orca_dll` | DLL do PowerBuilder 9 | Mantenha o caminho padrão |

> **Regra de bolso:** `pbls` = o que você quer extrair/recriar.
> `lib_list` = só "ajuda" na compilação, fica intocada.
> Com `origem_pfc` definida, a `lib_list` pode listar as PFC só pelo nome:
> `"ni_pfc_base.pbl"` em vez de `"G:\ni_pfc\ni_pfc_base.pbl"`.

---

---

## 3. Pré-requisitos

- **PowerBuilder 9 instalado** (para compilar; usa `pborc90.dll`).
- **Python** (qualquer versão) — só para o passo de extração.
- Git (opcional, para versionar).

---

---

## 4. Como configurar (passo a passo)

### Passo 4.1 — Abra o config.json
Abra `config.json` (na raiz do projeto) no seu editor.

### Passo 4.2 — Liste as bibliotecas que você quer processar
Em `"pbls"`, coloque o nome ou caminho de CADA `.pbl` que você quer
extrair e recriar. Separe por vírgula.

Exemplo para processar `deivide.pbl` e `sdo01.pbl`:

```json
"pbls": [
  "deivide.pbl",
  "sdo01.pbl"
],
```

> Atenção: no JSON as barras invertidas são escritas em dobro (`\\`).
> Nunca inclua `.pbd` aqui — `.pbd` não tem código-fonte.

### Passo 4.3 — Confira a library list

**Para que serve (por quê):** quando o PowerBuilder **compila** um objeto
(ex.: a janela `w_ope_hec`), ele precisa **encontrar as definições** dos
objetos que essa janela referencia — o ancestre `w_ni_cadastro`, um datawindow
que ela usa, funções globais etc. Esses objetos moram em **outras** bibliotecas
(`sdo01`...`sdo09`, PFC). O compilador ORCA procura essas definições na
"library list", igual ao IDE faz pelo Library List da aplicação. Se não achar,
a compilação falha com `Illegal data type`.

**O que ela faz (e o que NÃO faz):**
- **NÃO copia** nada: o `.pbl` recriado em `compilacao\` contém **somente** os
  objetos do `.pbl` que está em `pbls`. Nenhum objeto de outra biblioteca é
  copiado para dentro dele.
- **NÃO altera** nada: os `.sr*` mantêm os nomes de referência originais. A
  `lib_list` é apenas um **caminho de busca de leitura** durante a compilação;
  essas bibliotecas são abertas para **ler** definições e **nunca são
  modificadas**.
- Em runtime, a aplicação acha os objetos pelo Library List do `.pbt` (que
  aponta para as libs originais). O `.pbl` recriado **substitui apenas a si
  mesmo** — as referências continuam apontando para os mesmos nomes.

**Como preencher:** em `"lib_list"`, mantenha as bibliotecas do projeto que
resolvem essas referências (ex.: `sdo01.pbl`...`sdo09.pbl` e as libs PFC, que
podem ser listadas só pelo nome se você definir `"origem_pfc"`). O config.json
já vem preenchido com a lista do projeto `a_sdo`.

**Se o seu .pbl pertence a outro projeto**, substitua a `lib_list` pelas
bibliotecas desse projeto.

### Passo 4.4 — Confira o application
- `"app_name"` = nome do application object (ex.: `a_sdo`).
- `"app_lib"` = biblioteca onde ele mora (ex.: `G:\sdo\programa\sdo01.pbl`).

Se for outro projeto, use o application desse projeto.

### Passo 4.5 — Salve o arquivo

---

---

## 5. Como extrair

Extrai o código-fonte dos `.pbl` da lista `pbls` para `codigo_fonte\<pbl>\`.

> **Atalho:** dê dois cliques em `extrair.bat` — faz a mesma coisa sem
> digitar comando.
>
> Os comandos abaixo usam caminhos completos — rode de **qualquer pasta**, sem
> precisar de `cd`. (Isso vale para todas as seções deste guia.)

### Opção A — Linha de comando ou dois cliques
Dê dois cliques em `extrair.bat` ou rode pelo terminal:

```bat
extrair.bat
```

### Opção B — Informar o PBL diretamente (sem editar config.json)
```bat
extrair.bat deivide.pbl
```

> Atalho: como o `config.json` já tem a `"origem"`, basta o **nome** simples do PBL:
> ```bat
> extrair.bat deivide
> ```
> O nome é resolvido contra a `"origem"` (com ou sem `.pbl`). Caminho completo
> também funciona.

### Limpeza automática de órfãos (padrão)

Antes de extrair, o script **remove todos os `.sr*` existentes** na pasta
destino. Isso garante que arquivos removidos do PBL original não fiquem como
"órfãos" — objetos que não existem mais mas continuam sendo compilados,
gerando falsos positivos no `compilar.py` e no `validar.py`.

Para **desativar** a limpeza (manter comportamento anterior), use `--nao-limpar`:

```bat
extrair.bat --nao-limpar deivide
```

> Arquivos que não são `.sr*` (`.txt`, `.md`, notas) não são afetados pela limpeza.

### Resultado esperado
```
    Limpando 3 .sr* antigo(s) em codigo_fonte\deivide
      - w_tab_oso_pref.srw
      - d_tab_obo_antigo.srd
      - f_unused.srf
==> Extraindo [G:\sdo\programa\deivide.pbl] -> codigo_fonte\deivide
    Objetos de fonte extraidos: 20
Extracao concluida: 20 objeto(s) em 1 PBL(s).
```

Se aparecer `Objetos de fonte extraidos: 0`, veja a
[seção de problemas](#11-solução-de-problemas).

---

---

## 6. Como compilar (recriar o .pbl)

O comando **`compilar.bat <nome>`** reconstrói o `.pbl` em
`compilacao\<pbl>.pbl` a partir do código-fonte que está em
`codigo_fonte\<pbl>\`, importando e compilando cada objeto com o PowerBuilder.
De **qualquer pasta**, dê dois cliques ou chame o atalho:

```bat
compilar.bat                # compila TODOS os PBLs do config.json (pbls)
compilar.bat deivide        # compila só o deivide
compilar.bat deivide sdo09  # compila vários escolhidos (um por argumento)
```

> **De onde vêm os objetos?** Sempre da pasta `codigo_fonte\<nome do pbl>\`
> correspondente — a compilação **não lê a origem** (`G:\sdo\programa`). Cada
> PBL é processado separado e vira um `.pbl` próprio em `compilacao\`. O PBL
> original (de `pbls`) entra na library list **apenas para leitura** (resolver
> referências); nada é misturado entre bibliotecas.

> Também aceita caminho completo do original
> (`compilar.bat G:\sdo\programa\deivide.pbl`) por compatibilidade, mas o nome
> simples basta: os objetos saem de `codigo_fonte\<nome>\` e o `.pbl` novo vai
> para `compilacao\<nome>.pbl`.

### Linha de comando via Python (sem atalho)

**Opção A — Compilar todos do config.json:**
```bat
"...\scripts\python32\python.exe" "...\scripts\compilar.py"
```

**Opção B — Compilar PBLs específicos** (ignora `pbls`, mas ainda usa
`lib_list`/`app_name`/`app_lib` do config):
```bat
"...\scripts\python32\python.exe" "...\scripts\compilar.py" deivide
"...\scripts\python32\python.exe" "...\scripts\compilar.py" deivide sdo09
```

> **IMPORTANTE:** use o Python 32-bit (`python32\`), pois a DLL do PowerBuilder
> é 32-bit. Não use o `python` comum aqui.
>
> O script **não varre** `codigo_fonte` sozinho: quem define o que compilar é a
> lista de PBLs (config.json ou argumentos). Se a pasta `codigo_fonte\<nome>`
> do PBL não existir, ele avisa e para nesse PBL.

### Travas automáticas de encoding/acento

Antes de importar cada objeto, o `compilar.py` roda `checar_fontes.py`, que
**bloqueia** a compilação se detectar perda de encoding/acentos — o dano clássico
é uma sessão de edição que lê os `.sr*` como UTF-8 e salva apagando os acentos
(`Observação` vira `Observao`). As duas camadas:

| Camada | O que pega | Como |
|---|---|---|
| A — Encoding | BOM UTF-8, re-encode, bytes inválidos | leitura byte a byte |
| B — Git diff | arquivo versionado que **perdeu** acentos na edição | compara com `HEAD` |

> Limitação conhecida: arquivo **novo** (ainda sem commit) não tem baseline no
> git, então a camada B não o cobre. Por isso: **faça commit logo após a
> extração/criação** — a partir daí qualquer edição que stripar acentos é
> bloqueada.
>
> Saída: `ERRO` bloqueia; `AVISO` só informa. Para rodar avulso:
> ```bat
> "...\scripts\python32\python.exe" "...\scripts\checar_fontes.py" deivide
> ```
> Falso positivo confirmado (raro): contorne com `--ignorar-checagem`, mas
> confira cada ponto antes.

### Resultado esperado
```
==> Criando biblioteca compilacao\deivide.pbl (rc=0)
  OK  f_converte_min_duracao.srf
  OK  d_ope_his_eqp_hec.srd
  ...
==> Todos os 20 objetos foram importados/compilados.
```

Cada `OK` é um objeto importado e compilado. Se algum `FALHOU`, leia o log
`logs\<pbl>.import.txt` para ver o erro.

---

---

## 7. Atalhos (.bat)

Todos os comandos têm um `.bat` pronto para **dois cliques**, na raiz do
Lazarus IA. Eles são a porta de entrada dos fluxos do pipeline:

| Atalho | O que faz | Detalhes |
|---|---|---|
| `extrair.bat` | Extrai os `.sr*` para `codigo_fonte\` | [seção 5](#5-como-extrair) |
| `compilar.bat` | Recria os `.pbl` em `compilacao\` | [seção 6](#6-como-compilar-recriar-o-pbl) |
| `compilar_patch.bat` | Compila somente objetos alterados/novos em `patch.pbl` | Compilação incremental |
| `integridade.bat` | Verifica integridade e encoding (CP1252 / Git) | Proteção preventiva |
| `validar.bat` | Compara o `.pbl` recriado com a fonte | [seção 9](#9-como-validar-que-nada-quebrou) |
| `analise.bat` | Mapeia dependências e busca conteúdo nos `.sr*` | [seção 12](#12-como-analisar-dependências-analise) |
| `origem.bat` | Mapa de correspondência: onde cada objeto da origem existe | [seção 13](#13-mapa-de-correspondência-entre-pbls-origem) |

**Fluxo típico:**

1. Duplo clique em `extrair.bat` → atualiza os fontes.
2. IA edita os arquivos em `codigo_fonte\<pbl>\`.
3. Duplo clique em `compilar.bat` (ou `compilar_patch.bat`) → gera o `.pbl` novo.
4. Duplo clique em `validar.bat` → confirma que o round-trip preservou tudo.
5. Copie `compilacao\<pbl>.pbl` para o lugar do original.

> `analise.bat` e `origem.bat` são **opcionais** (não fazem parte do ciclo
> extrair → compilar → validar): ajudam a entender o código antes de editar e a
> decidir onde colar objetos. Veja os links Acima para o uso detalhado.

`extrair` e `compilar` aceitam nomes ou caminhos para processar só alguns PBLs:

```bat
extrair.bat  sdo01
compilar.bat sdo01
```

> No `extrair`, o nome é resolvido contra a `"origem"` do config.json.
> O `validar.bat` aceita o mesmo: `validar.bat deivide`.
>
> Para extrair **sem** limpar órfãos anteriores:
> ```bat
> extrair.bat --nao-limpar deivide
> ```

> `extrair.bat` só **lê** as `.pbl` originais. `compilar.bat` só **escreve** em
> `compilacao\`. Nenhum dos dois modifica as bibliotecas originais.

---

## 8. Fluxo completo com Git e IA

### Passo 1 — Extraia a base
Dê dois cliques em `extrair.bat` (ou rode a seção 5).

### Passo 2 — Crie o repositório Git (uma vez)
```bat
cd codigo_fonte
git init
git add .
git commit -m "base extraida"
```

> Versionar **só** o texto (`.sr*`). Não versionar `.pbl` nem `compilacao\`.

### Passo 3 — Peça para a IA editar
A IA edita os arquivos `.sr*` dentro de `codigo_fonte\<pbl>\`.
Eles são texto puro — o mesmo conteúdo que você vê no EditSource do PowerBuilder.
Utilize o **LazarusCode** (`lazaruscode.exe`) como agente do OpenCode, pois ele suporta nativamente a codificação **CP1252**.

### Passo 4 — Veja o que mudou
```bat
git -C codigo_fonte diff
```

### Passo 5 — Recompile após a edição
Dê dois cliques em `compilar.bat` (ou rode a seção 6).

### Passo 6 — Commit da alteração
```bat
cd codigo_fonte
git add .
git commit -m "ajuste da janela w_ope_hec"
```

### Passo 7 — Use o .pbl recriado
Copie `compilacao\<pbl>.pbl` para o lugar da biblioteca original
(faça backup do original antes).

---

---

## 9. Como validar que nada quebrou

### Modo fácil — `validar.bat`
Dê dois cliques em `validar.bat`. Ele:
1. Extrai de novo o `.pbl` recriado (`compilacao\<pbl>.pbl`) com o PblDump.
2. Compara arquivo por arquivo com `codigo_fonte\<pbl>\`.
3. Mostra: `identicos`, `divergentes` (e se a diferença é só espaço/linha
   final) e `ausentes`. Gera `logs\<pbl>.validacao.txt`.

Se todos forem `identicos`, o ciclo extrair → compilar → extrair **preservou o
código**: nada quebrou.

### Entendendo o comando manual
O que aquele comando fazia, passo a passo:

```bat
cd %TEMP%
mkdir verificacao
cd verificacao
scripts\pbldump\PblDump.exe -es ..\compilacao\deivide.pbl *.*
```

1. `cd`/`mkdir`/`cd` — cria uma pasta vazia de trabalho em `Temp`.
2. `PblDump.exe -es ...compilacao\deivide.pbl *.*` — extrai o **código-fonte
   do PBL recriado** para essa pasta (o `-es` é o mesmo modo de extração do
   `extrair.py`).

O resultado é comparado com `codigo_fonte\deivide`: se os `.sr*` forem
idênticos (ou só divergirem por espaço no fim de linha / linha em branco
final), o round-trip preservou o código — o compilador não "perdeu" nada.

> Diferença real = objeto mudou de conteúdo entre o fonte e o que o
> compilador gravou. Isso aponta um problema no processo ou um código
> "reformatado" pelo PB — investigue o arquivo apontado.

---

---

## 10. Logs gerados

Todos os logs têm **data e hora** no cabeçalho e no rodapé:

| Log | Local | Conteúdo |
|---|---|---|
| Extração | `logs\<pbl>.extracao.txt` | Saída do PblDump + contagem de objetos |
| Compilação | `logs\<pbl>.import.txt` | Cada objeto importado, erros, resumo e status final |
| Validação | `logs\<pbl>.validacao.txt` | Comparação arquivo a arquivo + resumo |

---

---

## 11. Solução de problemas

**"Objetos de fonte extraidos: 0"**
- Confirme que o caminho no `pbls` existe e é um `.pbl` (não `.pbd`).
- Confirme que você está executando o `extrair.py` na pasta certa ou com caminho completo.

**"Current appl not set" / `rc=-13`**
- `app_name` e `app_lib` não estão configurados ou apontam para o application errado.
- Configure no `config.json` e rode `compilar.py` de novo.

**"Illegal data type: xxx" / objeto FALHOU na compilação**
- O objeto referencia algo que não está em lugar nenhum da `lib_list`.
- Adicione a biblioteca que define esse objeto à `lib_list` e rode de novo.
- O nome do objeto problemático aparece no log `logs\<pbl>.import.txt`.

**"Não é um aplicativo Win32 válido" ao carregar pborc90.dll**
- Você usou o Python 64-bit. Use o `python32\python.exe` (item 6).

**Erro de sintaxe no config.json**
- Confira aspas e vírgulas. Toda linha de caminho termina com vírgula, menos a última.
- Barras invertidas sempre em dobro: `G:\\sdo\\programa\\deivide.pbl`.

**Quero processar várias bibliotecas de uma vez**
- Liste todas em `pbls` no config.json e rode `extrair.py` / `compilar.py` uma vez só.

**A lib_list copia objetos para dentro do meu .pbl?**
Não. O `.pbl` recriado contém apenas os objetos do `.pbl` que está em `pbls`.
As bibliotecas da `lib_list` são usadas somente como leitura para resolver
referências durante a compilação — nada é copiado nem alterado nelas.

**A compilação muda os nomes/referências no código?**
Não. Os arquivos `.sr*` ficam intactos com os mesmos nomes de objetos e
referências. O `lib_list` é apenas o caminho de busca que o compilador usa.

---

---

## 12. Como analisar dependências (`analise`)

O `analise.bat` consulta o código-fonte extraído em `codigo_fonte\` para mapear
**dependências** de um objeto (herança, DataWindows, funções, janelas, tabelas
SQL) e para **localizar** onde um texto aparece dentro dos `.sr*`. É uma
ferramenta de leitura: não modifica nada.

> Use sempre **antes** de editar um objeto — ele mostra de um só golpe o que
> o objeto usa e onde ele é citado, evitando abrir arquivo por arquivo.

### Modo 1 — Por nome do objeto (todas as PBLs)

Busca o objeto pelo nome em **toda** a árvore de `codigo_fonte\`. Se o mesmo
nome existir em mais de uma PBL (ex.: `w_tab_fnc` em `deivide` e `ni_pfc_tab`),
analisa **todas** e mostra o caminho de cada uma.

```bat
analise w_tab_fnc
analise w_tab_fnc.srw        # extensão é opcional
```

### Modo 2 — Por caminho (forçar uma PBL específica)

```bat
analise deivide\w_tab_fnc
```

### Modo 3 — Por curinga no nome (padrão)

Encontra todos os objetos cujo nome casa com o padrão. Combinável com
`--tipo srw|srd|srf|sru` para restringir por tipo.

```bat
analise w_tab_*                  # todos que começam com w_tab_
analise *telemetria* --tipo srd  # só datawindows com "telemetria"
```

### Modo 4 — Por conteúdo (`--buscar`)

Procura um **texto dentro do conteúdo** dos `.sr*` e devolve **onde** ele
aparece: tipo do objeto, caminho e o(s) número(s) da(s) linha(s). Use para
descobrir onde um campo, função, janela ou tabela é usado.

**Por padrão a busca é case-insensitive e ignora acentos** (independente da
codificação cp1252 dos arquivos — a comparação é normalizada em memória, sem
alterar nada no disco). Assim `--buscar "situacao"` acha também `Situação`,
`SITUAÇÃO`, etc. Se quiser **respeitar os acentos** (mas continuar
case-insensitive), use `--acentos`.

```bat
analise --buscar "ll_teq_id_seq"
analise --buscar "ll_teq_id_seq" --tipo srw          # só windows
analise --buscar "het_historico_equip_telemetria"
analise --buscar "vinculacao de soltura"             # padrão: acha "Vinculação de soltura"
analise --buscar "Vinculação" --acentos             # respeita acentos (case-insensitive)
```

> As flags `--tipo`, `--em` e `--acentos` podem vir em **qualquer ordem**,
> antes ou depois do `--buscar` e do texto — o resultado é o mesmo.

**Restringir o escopo com `--em`:** por padrão a busca varre todos os `.sr*`.
Use `--em "alvo"` para pesquisar **somente** num objeto, caminho, PBL ou padrão
específico. O alvo aceita nome (`w_tab_fnc`), `pbl\objeto` (`deivide\w_tab_fnc`),
**o nome da PBL sozinho** (`deivide`) e curinga (`w_tab_*`). A barra `/` também
é aceita como separador de caminho, igual a `\`. Para escopar uma PBL inteira,
basta passar o nome da pasta, **sem precisar de `*`**:

```bat
analise --buscar "teq_cd_equipamento" --em "deivide\w_tab_teq" --tipo srw
analise --buscar "teq_cd_equipamento" --em "deivide/w_tab_teq" --tipo srw   # barra "/" também vale
analise --buscar "teq_cd_equipamento" --em deivide                          # PBL inteira, sem "*"
analise --buscar "teq_cd_equipamento" --em "deivide\w_tab_*" --tipo srw    # curinga (opcional)
```

Saída do `--buscar` (exemplo):
```
2 objeto(s) contêm 'll_teq_id_seq':

  deivide\w_tab_teq.srw  [Window]  (linha(s): 287, 293, 308)
  sdo09\w_ope_his_eqp_ccusto.srw  [Window]  (linha(s): 257, 271, 313, 321)
```

> A varredura ignora a pasta `.git` e só lê arquivos `.sr*` reais.

---

---

## 13. Mapa de correspondência entre PBLs (`origem`)

O `origem.bat` mapeia uma PBL de trabalho (ex.: `deivide`) contra **todas as
outras** PBLs extraídas em `codigo_fonte`, para você saber de uma vez **onde**
cada objeto da origem já existe — ou se é objeto novo.

É uma ferramenta de **leitura e cópia apenas**: não altera nenhum `.sr*` e não
recompila nada. Onde você vai colar os arquivos é decidido por você depois.

```bat
origem deivide        # mapa de correspondência da PBL deivide
```

### O que ele gera

Cria (se não existir) a pasta oculta `.origem\` **dentro de `codigo_fonte\`** —
fica no topo da listagem, fora do versionamento (`.gitignore` do repo de
fontes) — e, dentro dela, uma pasta com o nome da PBL origem. As PBLs origem
podem coexistir (uma pasta por PBL origem):

```
codigo_fonte\
└── .origem\
    └── deivide\        <- isolado por PBL origem
        ├── relatorio.txt
        ├── sdo09\        <- objetos da origem que JÁ existem em sdo09
        │     d_lst_teq.srd
        │     w_tab_teq.srw
        ├── ni_pfc_tab\   <- objetos da origem que existem em ni_pfc_tab
        │     w_tab_fnc.srw
        └── novos objetos\   <- objetos da origem sem correspondência em nenhuma PBL
              w_ope_his_eqp_telemetria.srw
              ...
```

A cada execução só a subpasta da PBL origem informada é recriada do zero
(ex.: rodar `origem deivide` regenera apenas `.origem\deivide\`, sem mexer em
`.origem\sdo01\`).

- **Uma pasta por PBL correspondente**: cada arquivo é copiado para a pasta da
  PBL onde existe um objeto de mesmo nome. Se existir em várias PBLs, vai para
  todas (a pasta mostra todas as opções).
- **`novos objetos\`**: objetos da origem que não existem em **nenhuma** outra PBL.
- **`relatorio.txt`**: resumo com a contagem por PBL e a lista de `novos objetos`.
