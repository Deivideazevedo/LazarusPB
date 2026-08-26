# Lazarus IA — Guia de Uso

Pipeline para extrair código-fonte de bibliotecas **PowerBuilder 9** (.pbl) em
arquivos de texto (`.sr*`), versionar com Git, editar com IA e recompilar de
volta para `.pbl`.

---

## Índice

1. [O que cada pasta faz](#1-o-que-cada-pasta-faz)
2. [O que cada campo do config.json significa](#2-o-que-cada-campo-do-configjson-significa)
3. [Pré-requisitos](#3-pré-requisitos)
4. [Como configurar (passo a passo)](#4-como-configurar-passo-a-passo)
5. [Como extrair](#5-como-extrair)
6. [Como compilar (recriar o .pbl)](#6-como-compilar-recriar-o-pbl)
7. [Atalhos (.bat)](#7-atalhos-bat)
8. [Fluxo completo com Git e IA](#8-fluxo-completo-com-git-e-ia)
9. [Como validar que nada quebrou](#9-como-validar-que-nada-quebrou)
10. [Logs gerados](#10-logs-gerados)
11. [Solução de problemas](#11-solução-de-problemas)

---

## 1. O que cada pasta faz

```
C:\Users\Elton\Desktop\LazarusIA\
│
├── extrair.bat           ⭐ ATALHOS (duplo clique)
├── compilar.bat              extrair / compilar / validar
├── validar.bat
│
├── codigo_fonte\        ← ARQUIVOS DE TEXTO (.sr*) extraídos dos .pbl
│   │                       É aqui que o Git e a IA trabalham.
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
    ├── pbldump\            PblDump.exe (extrator)
    └── python32\           Python 32-bit (para usar a DLL do PowerBuilder)
```

---

## 2. O que cada campo do config.json significa

Este é o arquivo que você edita. Ele fica na **raiz** do projeto:
`C:\Users\Elton\Desktop\LazarusIA\config.json`.

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

## 3. Pré-requisitos

- **PowerBuilder 9 instalado** (para compilar; usa `pborc90.dll`).
- **Python** (qualquer versão) — só para o passo de extração.
- Git (opcional, para versionar).

---

## 4. Como configurar (passo a passo)

### Passo 4.1 — Abra o config.json
Abra `C:\Users\Elton\Desktop\LazarusIA\config.json` no Bloco de Notas.

### Passo 4.2 — Liste as bibliotecas que você quer processar
Em `"pbls"`, coloque o caminho completo de CADA `.pbl` que você quer
extrair e recriar. Separe por vírgula. Use o caminho do **original**
(na `origem`, ex.: `G:\sdo\programa`) — ele é lido, não modificado.

Exemplo para processar `deivide.pbl` e `elton.pbl`:

```json
"pbls": [
  "G:\\sdo\\programa\\deivide.pbl",
  "G:\\sdo\\programa\\elton.pbl"
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

## 5. Como extrair

Extrai o código-fonte dos `.pbl` da lista `pbls` para `codigo_fonte\<pbl>\`.

> **Atalho:** dê dois cliques em `extrair.bat` — faz a mesma coisa sem
> digitar comando.
>
> Os comandos abaixo usam caminhos completos — rode de **qualquer pasta**, sem
> precisar de `cd`. (Isso vale para todas as seções deste guia.)

### Opção A — Linha de comando (usa o config.json)
Abra o Prompt de Comando (cmd) e rode:

```bat
python "C:\Users\Elton\Desktop\LazarusIA\scripts\extrair.py"
```

### Opção B — Informar o caminho direto (sem editar config.json)
```bat
python "C:\Users\Elton\Desktop\LazarusIA\scripts\extrair.py" "G:\sdo\programa\elton.pbl"
```

> Atalho: como o `config.json` já tem a `"origem"`, basta o **nome** do PBL:
> ```bat
> python "C:\Users\Elton\Desktop\LazarusIA\scripts\extrair.py" elton
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
"C:\Users\Elton\Desktop\LazarusIA\extrair.bat" --nao-limpar deivide
```

> Arquivos que não são `.sr*` (`.txt`, `.md`, notas) não são afetados pela limpeza.

### Resultado esperado
```
    Limpando 3 .sr* antigo(s) em C:\...\codigo_fonte\deivide
      - w_tab_oso_pref.srw
      - d_tab_obo_antigo.srd
      - f_unused.srf
==> Extraindo [G:\sdo\programa\deivide.pbl] -> C:\Users\Elton\Desktop\LazarusIA\codigo_fonte\deivide
    Objetos de fonte extraidos: 20
Extracao concluida: 20 objeto(s) em 1 PBL(s).
```

Se aparecer `Objetos de fonte extraidos: 0`, veja a
[seção de problemas](#10-solução-de-problemas).

---

## 6. Como compilar (recriar o .pbl)

Reconstrói o `.pbl` em `compilacao\<pbl>.pbl` a partir dos `.sr*` que estão em
`codigo_fonte\<pbl>\`, importando e compilando cada objeto com o PowerBuilder.

> **Qual a origem dos objetos?** Para cada `.pbl` da lista `pbls`, a origem é
> **somente** a pasta `codigo_fonte\<nome do pbl>\` que corresponde a ele.
> Cada PBL é processado separado e vira um `.pbl` próprio em `compilacao\`.
> Nada é misturado entre bibliotecas. O PBL original (de `pbls`) entra na
> library list **apenas para leitura** (resolver referências) — os objetos
> importados no `.pbl` novo vêm exclusivamente da pasta de fonte dele.

> **Atalho:** dê dois cliques em `compilar.bat` — faz a mesma coisa sem
> digitar comando.
>
> **IMPORTANTE:** este comando usa o Python 32-bit (`python32\`), porque a DLL
> do PowerBuilder é 32-bit. Não use `python` comum aqui.
>
> Os comandos usam caminhos completos — rode de **qualquer pasta**, sem
> precisar de `cd`.

### Travas automáticas de encoding/acento

Os fontes `.sr*` são **ANSI/Windows-1252**. Antes de importar qualquer objeto,
o `compilar.py` roda `checar_fontes.py`, que bloqueia a compilação se detectar
perda de encoding/acentos — o dano clássico é uma sessão de edição que lê os
arquivos como UTF-8 e salva de volta apagando todo caractere acentuado
(`Observação` vira `Observao`). As duas camadas:

| Camada | O que pega | Como |
|---|---|---|
| A — Encoding | BOM UTF-8, re-encode, bytes inválidos | leitura byte a byte |
| B — Git diff | arquivo versionado que **perdeu** acentos na edição | compara com `HEAD` |

> Limitação conhecida: arquivo **novo** (ainda sem commit) não tem baseline no
> git, então a camada B não o cobre. Por isso: **faça commit logo após a
> extração/criação** — a partir daí qualquer edição que stripar acentos é
> bloqueada.

Saída: `ERRO` bloqueia; `AVISO` só informa. Para rodar avulso:

```bat
"...\scripts\python32\python.exe" "...\scripts\checar_fontes.py" deivide
```

Se um erro for falso positivo confirmado (raro), contorne com
`--ignorar-checagem` — mas confira cada ponto antes.

### Opção A — Linha de comando (usa o config.json)
Compila os PBLs listados em `"pbls"` do config.json. Cada um é compilado a
partir da sua própria pasta `codigo_fonte\<nome do pbl>\`.

```bat
"C:\Users\Elton\Desktop\LazarusIA\scripts\python32\python.exe" "C:\Users\Elton\Desktop\LazarusIA\scripts\compilar.py"
```

> O script **não varre** a pasta `codigo_fonte` sozinho. Quem define o que
> compilar é a lista de PBLs (config.json ou argumentos). Se a pasta
> `codigo_fonte\<nome>` do PBL não existir, ele avisa e para nesse PBL.

### Opção B — Informar o caminho direto
Compila **apenas** os PBLs passados (ignora `"pbls"` do config.json, mas ainda
usa `lib_list`/`app_name`/`app_lib` dele):

```bat
"C:\Users\Elton\Desktop\LazarusIA\scripts\python32\python.exe" "C:\Users\Elton\Desktop\LazarusIA\scripts\compilar.py" deivide
```

O argumento pode ser só o **nome** do PBL (`deivide` ou `deivide.pbl`), pois a
compilação **não lê a origem**: os objetos vêm sempre de
`codigo_fonte\<nome>\` e o resultado vai para `compilacao\<nome>.pbl`.
Caminho completo do original (`G:\sdo\programa\deivide.pbl`) também é aceito,
por compatibilidade — mas não é obrigatório.

### Resultado esperado
```
==> Criando biblioteca C:\Users\Elton\Desktop\LazarusIA\compilacao\deivide.pbl (rc=0)
  OK  f_converte_min_duracao.srf
  OK  d_ope_his_eqp_hec.srd
  ...
==> Todos os 20 objetos foram importados/compilados.
```

Cada `OK` é um objeto importado e compilado. Se algum `FALHOU`, leia o log
`logs\<pbl>.import.txt` para ver o erro.

---

## 7. Atalhos (.bat)

Há dois arquivos prontos na pasta `scripts\`. Basta dar **dois cliques**:

| Atalho | O que faz | Quando usar |
|---|---|---|
| Atalho | O que faz | Quando usar |
|---|---|---|
| `extrair.bat` | Extrai os `.sr*` para `codigo_fonte\` | Quando quiser atualizar os fontes a partir das `.pbl` originais |
| `compilar.bat` | Recria os `.pbl` em `compilacao\` | **Depois** de editar os `.sr*` com a IA |
| `validar.bat` | Compara o `.pbl` recriado com a fonte | Para conferir que nada quebrou |

**Fluxo típico:**

1. Duplo clique em `extrair.bat` → atualiza os fontes.
2. IA edita os arquivos em `codigo_fonte\<pbl>\`.
3. Duplo clique em `compilar.bat` → gera o `.pbl` novo.
4. Duplo clique em `validar.bat` → confirma que o round-trip preservou tudo.
5. Copie `compilacao\<pbl>.pbl` para o lugar do original.

Os dois atalhos aceitam nomes ou caminhos para processar só alguns PBLs:

```bat
"C:\Users\Elton\Desktop\LazarusIA\extrair.bat"  elton
"C:\Users\Elton\Desktop\LazarusIA\compilar.bat" elton
```

> No `extrair`, o nome é resolvido contra a `"origem"` do config.json.
> O `validar.bat` aceita o mesmo: `validar.bat deivide`.
>
> Para extrair **sem** limpar órfãos anteriores:
> ```bat
> "C:\Users\Elton\Desktop\LazarusIA\extrair.bat" --nao-limpar deivide
> ```

> `extrair.bat` só **lê** as `.pbl` originais. `compilar.bat` só **escreve** em
> `compilacao\`. Nenhum dos dois modifica as bibliotecas originais.

---

## 8. Fluxo completo com Git e IA

### Passo 1 — Extraia a base
Dê dois cliques em `extrair.bat` (ou rode a seção 5).

### Passo 2 — Crie o repositório Git (uma vez)
```bat
cd C:\Users\Elton\Desktop\LazarusIA\codigo_fonte
git init
git add .
git commit -m "base extraida"
```

> Versionar **só** o texto (`.sr*`). Não versionar `.pbl` nem `compilacao\`.

### Passo 3 — Peça para a IA editar
A IA edita os arquivos `.sr*` dentro de `codigo_fonte\<pbl>\`.
Eles são texto puro — o mesmo conteúdo que você vê no EditSource do PowerBuilder.

### Passo 4 — Veja o que mudou
```bat
git -C C:\Users\Elton\Desktop\LazarusIA\codigo_fonte diff
```

### Passo 5 — Recompile após a edição
Dê dois cliques em `compilar.bat` (ou rode a seção 6).

### Passo 6 — Commit da alteração
```bat
cd C:\Users\Elton\Desktop\LazarusIA\codigo_fonte
git add .
git commit -m "ajuste da janela w_ope_hec"
```

### Passo 7 — Use o .pbl recriado
Copie `compilacao\<pbl>.pbl` para o lugar da biblioteca original
(faça backup do original antes).

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
cd C:\Users\Elton\AppData\Local\Temp
mkdir verificacao
cd verificacao
"C:\Users\Elton\Desktop\LazarusIA\scripts\pbldump\PblDump.exe" -es "C:\Users\Elton\Desktop\LazarusIA\compilacao\deivide.pbl" *.*
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

## 10. Logs gerados

Todos os logs têm **data e hora** no cabeçalho e no rodapé:

| Log | Local | Conteúdo |
|---|---|---|
| Extração | `logs\<pbl>.extracao.txt` | Saída do PblDump + contagem de objetos |
| Compilação | `logs\<pbl>.import.txt` | Cada objeto importado, erros, resumo e status final |
| Validação | `logs\<pbl>.validacao.txt` | Comparação arquivo a arquivo + resumo |

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
