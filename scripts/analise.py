# -*- coding: utf-8 -*-
"""
Analisador de Dependências PowerBuilder - Lazarus IA
Analisa arquivos .srw, .srd, .sru, .srf e gera fluxo de dependências.

Uso (via analise.bat, de qualquer pasta):
    analise w_tab_fnc                 # por NOME, em todas as PBLs
    analise w_tab_fnc.srw             # extensao opcional
    analise deivide\\w_tab_fnc        # caminho: forcar uma PBL especifica
    analise w_tab_*                   # curinga no NOME do objeto
    analise *telemetria* --tipo srd   # curinga + filtro de tipo

    analise --buscar "texto"          # busca de CONTEUDO dentro dos .sr*
    analise --buscar "teq_id_seq" --tipo srw  # conteudo + filtro de tipo
    analise --buscar "teq_id_seq" --em "deivide\\w_tab_teq" --tipo srw
                                      # conteudo restrito a um objeto/PBL
    analise --buscar "teq_id_seq" --em deivide
                                      # PBL inteira pelo nome da pasta (sem *)
    analise --buscar "teq_id_seq" --em "deivide/w_tab_teq"
                                      # barra "/" também é aceita como separador
    analise --buscar "vinculacao de soltura"
                                      # padrão: ignora acento e case
                                      # ("vinculacao" acha "vinculação")
    analise --buscar "Vinculação" --acentos
                                      # respeita ACENTOS, mantém case-insensitive
    Flags (--tipo, --em, --acentos) podem vir em qualquer ordem:
    analise --em deivide --tipo srd --buscar "texto"

Modos:
  - NOME/CAMINHO/CURINGA: resolve o objeto pelo nome do arquivo.
  - --buscar: procura um texto DENTRO do conteudo dos arquivos .sr* e
    devolve onde ele aparece (tipo, caminho, linha). Aceita --em para
    restringir a busca a um objeto, caminho, PBL (nome da pasta, sem
    precisar de "*") ou padrao especifico.
O diretório .git é ignorado na varredura e só arquivos .sr* são lidos.
"""

import re
import sys
import os
import unicodedata
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comum

RAIZ = Path(comum.CODIGO_FONTE)

EXTENSOES = (".srw", ".srd", ".srf", ".sru", ".srm", ".sra")
NOME_TIPO = {
    ".srw": "Window",
    ".srd": "DataWindow",
    ".srf": "Function",
    ".sru": "UserObject",
    ".srm": "Menu",
    ".sra": "Application",
}

_MAPA_MENUS_CACHE = None


def obter_mapa_menus():
    """Varre todos os arquivos .srm e mapeia: nome_janela (lowercase) -> lista de caminhos de menu."""
    global _MAPA_MENUS_CACHE
    if _MAPA_MENUS_CACHE is not None:
        return _MAPA_MENUS_CACHE

    mapa = {}
    for arq in RAIZ.rglob("*.srm"):
        if ".git" in arq.parts:
            continue
        conteudo = ler_arquivo(arq)
        if not conteudo or conteudo.startswith("ERRO:"):
            continue

        menu_principal = arq.stem

        # 1. Mapear hierarquia pai-filho: type <item> from menu within <pai>
        pais = {}
        for m in re.finditer(r'type\s+(\w+)\s+from\s+(?:menu|[\w`]+)\s+within\s+(\w+)', conteudo):
            filho, pai = m.group(1), m.group(2)
            pais[filho] = pai

        # 2. Mapear rotulos (text): on <item>.create ... this.text = "..." ... end on
        titulos = {}
        for m in re.finditer(r'on\s+(\w+)\.create(.*?)end\s+on', conteudo, re.DOTALL):
            item, bloco = m.group(1), m.group(2)
            m_text = re.search(r'this\.text\s*=\s*"([^"]*)"', bloco)
            if m_text:
                txt = m_text.group(1).replace("&", "").strip()
                if txt and txt != "-":
                    titulos[item] = txt

        # 3. Mapear chamadas de abertura de janela
        for m in re.finditer(r'type\s+(\w+)\s+from.*?(?:event\s+clicked;|(?:on\s+\1\.create))(.*?)end\s+(?:event|on)', conteudo, re.DOTALL):
            item, bloco = m.group(1), m.group(2)
            for m_open in re.finditer(r'Open(?:Sheet)?(?:WithParm|WithPop)?\s*\(\s*["\']?(\w+)', bloco):
                janela = m_open.group(1)

                caminho_itens = [item]
                curr = item
                while curr in pais and pais[curr] != menu_principal:
                    curr = pais[curr]
                    caminho_itens.append(curr)

                caminho_itens.reverse()

                caminho_legivel = []
                for node in caminho_itens:
                    lbl = titulos.get(node, node)
                    caminho_legivel.append(lbl)

                path_str = f"{menu_principal} -> " + " > ".join(caminho_legivel)
                if path_str not in mapa.setdefault(janela.lower(), []):
                    mapa[janela.lower()].append(path_str)

    _MAPA_MENUS_CACHE = mapa
    return _MAPA_MENUS_CACHE


_MAPA_DW_USOS_CACHE = None


def obter_mapa_dw_usos():
    """Varre todos os arquivos .srw, .sru e .srd e mapeia:
    datawindow_lower -> {'janelas': [...], 'objetos': [...], 'datawindows': [...]}"""
    global _MAPA_DW_USOS_CACHE
    if _MAPA_DW_USOS_CACHE is not None:
        return _MAPA_DW_USOS_CACHE

    mapa = {}

    def registrar(dw_nome, item_nome, chave):
        if not dw_nome:
            return
        dw_key = dw_nome.strip().lower()
        if dw_key not in mapa:
            mapa[dw_key] = {"janelas": [], "objetos": [], "datawindows": []}
        if item_nome not in mapa[dw_key][chave]:
            mapa[dw_key][chave].append(item_nome)

    padrao_dw = re.compile(r'(?:[Dd]ata[Oo]bject|is_nm_dataobject)\s*=\s*["\'](\w+)["\']')
    padrao_report = re.compile(r'report\([^)]*dataobject\s*=\s*["\'](\w+)["\']', re.IGNORECASE)

    for arq in RAIZ.rglob("*"):
        if ".git" in arq.parts or not arq.is_file():
            continue
        ext = arq.suffix.lower()
        if ext not in (".srw", ".sru", ".srd"):
            continue

        conteudo = ler_arquivo(arq)
        if not conteudo or conteudo.startswith("ERRO:"):
            continue

        nome = arq.stem
        if ext == ".srw":
            for m in padrao_dw.finditer(conteudo):
                registrar(m.group(1), nome, "janelas")
        elif ext == ".sru":
            for m in padrao_dw.finditer(conteudo):
                registrar(m.group(1), nome, "objetos")
        elif ext == ".srd":
            for m in padrao_report.finditer(conteudo):
                registrar(m.group(1), nome, "datawindows")

    _MAPA_DW_USOS_CACHE = mapa
    return _MAPA_DW_USOS_CACHE


def ler_arquivo(caminho):
    """Lê arquivo com encoding cp1252 (padrão PowerBuilder)."""
    try:
        return Path(caminho).read_text(encoding="cp1252", errors="replace")
    except Exception as e:
        return f"ERRO: {e}"


def analisar_srw(caminho):
    """Analisa um arquivo Window (.srw)."""
    conteudo = ler_arquivo(caminho)
    nome = Path(caminho).stem
    relativo = str(Path(caminho).relative_to(RAIZ))
    pasta = Path(caminho).parent.name

    resultado = {
        "arquivo": nome,
        "caminho": relativo,
        "pbl": pasta,
        "tipo": "Window",
        "heranca": [],
        "menus": obter_mapa_menus().get(nome.lower(), []),
        "datawindows": [],
        "funcoes": [],
        "janelas": [],
        "objetos": [],
        "procedures": [],
        "sql": [],
    }

    # Herança: global type w_X from w_parent (apenas a primeira ocorrência)
    heranca_match = re.search(r'global\s+type\s+\w+\s+from\s+(\w+)', conteudo)
    if heranca_match:
        resultado["heranca"].append(heranca_match.group(1))

    # DataObjects: dataobject = "d_xxx" ou DataObject = 'd_xxx'
    for m in re.finditer(r'[Dd]ata[Oo]bject\s*=\s*["\'](\w+)["\']', conteudo):
        resultado["datawindows"].append(m.group(1))

    # Funções: f_xxx( ou of_xxx(
    for m in re.finditer(r'\b(f_\w+|of_\w+)\s*\(', conteudo):
        func = m.group(1)
        if func not in resultado["funcoes"]:
            resultado["funcoes"].append(func)

    # Janelas: Open/OpenWithParm(w_xxx, ...)
    for m in re.finditer(r'Open(?:WithParm|WithPop)\s*\(\s*["\']?(\w+)', conteudo):
        janela = m.group(1)
        if janela not in resultado["janelas"]:
            resultado["janelas"].append(janela)

    # CREATE de objetos: id_xxx = create xxx  ou  CREATE xxx (exclui keywords PB)
    pb_keywords = {"call", "end", "if", "then", "else", "for", "next", "do", "loop", "while", "return", "choose", "case", "try", "catch", "throw", "set", "get", "is", "this", "parent", "super", "create", "destroy", "open", "close", "post", "trigger", "halt", "return", "continue", "exit", "select", "insert", "update", "delete", "declare", "cursor", "fetch", "execute", "commit", "rollback", "disconnect", "connect"}
    for m in re.finditer(r'(?i:create)\s+(\w+)', conteudo):
        obj = m.group(1)
        if obj.lower() not in pb_keywords and obj not in resultado["objetos"]:
            resultado["objetos"].append(obj)

    # SQL inline: SELECT ... FROM
    for m in re.finditer(r'SELECT\s+.+?\s+FROM\s+(\w+)', conteudo, re.IGNORECASE):
        tabela = m.group(1)
        if tabela not in resultado["sql"]:
            resultado["sql"].append(tabela)

    # Procedures: declare alias procedure for sp_xxx
    for m in re.finditer(r'declare\s+\w+\s+procedure\s+for\s+(\w+)', conteudo, re.IGNORECASE):
        proc = m.group(1)
        if proc not in resultado["procedures"]:
            resultado["procedures"].append(proc)

    return resultado


def analisar_srd(caminho):
    """Analisa um arquivo DataWindow (.srd)."""
    conteudo = ler_arquivo(caminho)
    nome = Path(caminho).stem
    relativo = str(Path(caminho).relative_to(RAIZ))
    pasta = Path(caminho).parent.name

    usos = obter_mapa_dw_usos().get(nome.lower(), {})
    resultado = {
        "arquivo": nome,
        "caminho": relativo,
        "pbl": pasta,
        "tipo": "DataWindow",
        "janelas": usos.get("janelas", []),
        "objetos": usos.get("objetos", []),
        "datawindows": usos.get("datawindows", []),
        "tabelas": [],
        "colunas": [],
        "procedures": [],
        "code_tables": [],
    }

    # Tabelas: FROM table ou table = no retrieve
    for m in re.finditer(r'FROM\s+(\w+)', conteudo, re.IGNORECASE):
        tabela = m.group(1)
        if tabela not in resultado["tabelas"] and not tabela.startswith("("):
            resultado["tabelas"].append(tabela)

    # Tabelas no retrieve: retrieve="SELECT ... FROM table"
    for m in re.finditer(r'retrieve\s*=\s*"(SELECT\s+.+?\s+FROM\s+(\w+))"', conteudo, re.IGNORECASE):
        tabela = m.group(2)
        if tabela not in resultado["tabelas"]:
            resultado["tabelas"].append(tabela)

    # Tabelas no update: update="table"
    for m in re.finditer(r'update\s*=\s*"(\w+)"', conteudo, re.IGNORECASE):
        tabela = m.group(1)
        if tabela not in resultado["tabelas"]:
            resultado["tabelas"].append(tabela)

    # Colunas: type=... name=xxx
    for m in re.finditer(r'type=\w+\s+name=(\w+)', conteudo):
        col = m.group(1)
        if col not in resultado["colunas"]:
            resultado["colunas"].append(col)

    # Code Tables: values=("x" / "y" ...)
    for m in re.finditer(r'values\s*=\s*\("([^"]+)"', conteudo):
        resultado["code_tables"].append(m.group(1))

    # Procedures: procedure="1 execute [dbo.]sp_xxx;1 ...
    for m in re.finditer(r'procedure="1\s+(?:execute|exec)\s+(?:(?:dbo|vetorh)\.{1,2})?([a-zA-Z_]\w*)\s*;1', conteudo, re.IGNORECASE):
        proc = m.group(1)
        if proc not in resultado["procedures"]:
            resultado["procedures"].append(proc)

    return resultado


def analisar_srf(caminho):
    """Analisa um arquivo Function (.srf)."""
    conteudo = ler_arquivo(caminho)
    nome = Path(caminho).stem
    relativo = str(Path(caminho).relative_to(RAIZ))
    pasta = Path(caminho).parent.name

    resultado = {
        "arquivo": nome,
        "caminho": relativo,
        "pbl": pasta,
        "tipo": "Function",
        "heranca": [],
        "parametros": [],
        "chama": [],
        "sql": [],
    }

    # Herança: global type f_X from function_object
    for m in re.finditer(r'global\s+type\s+\w+\s+from\s+(\w+)', conteudo):
        resultado["heranca"].append(m.group(1))

    # Parâmetros: na declaração da função
    for m in re.finditer(r'global\s+function\s+\w+\s+\w+\s*\(([^)]*)\)', conteudo):
        params = m.group(1).strip()
        if params:
            resultado["parametros"] = [p.strip() for p in params.split(",") if p.strip()]

    # Chamadas de outras funções
    for m in re.finditer(r'\b(f_\w+|of_\w+)\s*\(', conteudo):
        func = m.group(1)
        if func != nome and func not in resultado["chama"]:
            resultado["chama"].append(func)

    # SQL: SELECT ... FROM
    for m in re.finditer(r'SELECT\s+.+?\s+FROM\s+(\w+)', conteudo, re.IGNORECASE):
        tabela = m.group(1)
        if tabela not in resultado["sql"]:
            resultado["sql"].append(tabela)

    return resultado


def analisar_sru(caminho):
    """Analisa um arquivo User Object (.sru)."""
    conteudo = ler_arquivo(caminho)
    nome = Path(caminho).stem
    relativo = str(Path(caminho).relative_to(RAIZ))
    pasta = Path(caminho).parent.name

    resultado = {
        "arquivo": nome,
        "caminho": relativo,
        "pbl": pasta,
        "tipo": "UserObject",
        "heranca": [],
        "metodos": [],
        "datawindows": [],
        "sql": [],
    }

    # Herança: global type u_X from parent
    for m in re.finditer(r'global\s+type\s+\w+\s+from\s+(\w+)', conteudo):
        resultado["heranca"].append(m.group(1))

    # Métodos: public function/subroutine of_xxx(...)  ou  protected function/subroutine of_xxx(...)
    for m in re.finditer(r'(public|protected|private)\s+(function|subroutine)\s+\w+\s+(of_\w+)\s*\(', conteudo):
        metodo = m.group(3)
        if metodo not in resultado["metodos"]:
            resultado["metodos"].append(metodo)

    # DataObjects
    for m in re.finditer(r'[Dd]ata[Oo]bject\s*=\s*["\'](\w+)["\']', conteudo):
        resultado["datawindows"].append(m.group(1))

    # SQL
    for m in re.finditer(r'SELECT\s+.+?\s+FROM\s+(\w+)', conteudo, re.IGNORECASE):
        tabela = m.group(1)
        if tabela not in resultado["sql"]:
            resultado["sql"].append(tabela)

    return resultado


def analisar_srm(caminho):
    """Analisa um arquivo Menu (.srm)."""
    conteudo = ler_arquivo(caminho)
    nome = Path(caminho).stem
    relativo = str(Path(caminho).relative_to(RAIZ))
    pasta = Path(caminho).parent.name

    resultado = {
        "arquivo": nome,
        "caminho": relativo,
        "pbl": pasta,
        "tipo": "Menu",
        "janelas": [],
    }

    for m in re.finditer(r'Open(?:Sheet)?(?:WithParm|WithPop)?\s*\(\s*["\']?(\w+)', conteudo):
        janela = m.group(1)
        if janela not in resultado["janelas"]:
            resultado["janelas"].append(janela)

    return resultado


def analisar_sra(caminho):
    """Analisa um arquivo Application (.sra)."""
    conteudo = ler_arquivo(caminho)
    nome = Path(caminho).stem
    relativo = str(Path(caminho).relative_to(RAIZ))
    pasta = Path(caminho).parent.name

    resultado = {
        "arquivo": nome,
        "caminho": relativo,
        "pbl": pasta,
        "tipo": "Application",
        "janelas": [],
    }

    for m in re.finditer(r'Open(?:Sheet)?(?:WithParm|WithPop)?\s*\(\s*["\']?(\w+)', conteudo):
        janela = m.group(1)
        if janela not in resultado["janelas"]:
            resultado["janelas"].append(janela)

    return resultado


def analisar_arquivo(caminho):
    """Roteia para o analisador correto baseado na extensão."""
    ext = Path(caminho).suffix.lower()
    if ext == ".srw":
        return analisar_srw(caminho)
    elif ext == ".srd":
        return analisar_srd(caminho)
    elif ext == ".srf":
        return analisar_srf(caminho)
    elif ext == ".sru":
        return analisar_sru(caminho)
    elif ext == ".srm":
        return analisar_srm(caminho)
    elif ext == ".sra":
        return analisar_sra(caminho)
    else:
        return {"arquivo": Path(caminho).stem, "tipo": f"Não suportado ({ext})"}


def formatar_saida(resultado):
    """Formata a saída da análise para impressão."""
    linhas = []
    linhas.append(f"=== {resultado['arquivo']}.{resultado.get('tipo', '?').lower()} ===")
    linhas.append(f"Tipo: {resultado['tipo']}")
    linhas.append(f"PBL: {resultado.get('pbl', '?')}")
    linhas.append(f"Caminho: {resultado.get('caminho', '?')}")
    if resultado.get("menus"):
        if len(resultado["menus"]) == 1:
            linhas.append(f"Menu: {resultado['menus'][0]}")
        else:
            linhas.append("Menu:")
            for m in resultado["menus"]:
                linhas.append(f"  - {m}")
    linhas.append("")

    if resultado["tipo"] == "Window":
        if resultado["heranca"]:
            linhas.append(f"Herança: {', '.join(resultado['heranca'])}")
        if resultado["datawindows"]:
            linhas.append(f"DataWindows: {', '.join(resultado['datawindows'])}")
        if resultado["funcoes"]:
            linhas.append(f"Funções: {', '.join(resultado['funcoes'])}")
        if resultado["janelas"]:
            linhas.append(f"Janelas que abre: {', '.join(resultado['janelas'])}")
        if resultado["objetos"]:
            linhas.append(f"Objetos: {', '.join(resultado['objetos'])}")
        if resultado["procedures"]:
            linhas.append(f"Procedures: {', '.join(resultado['procedures'])}")
        if resultado["sql"]:
            linhas.append(f"Tabelas SQL: {', '.join(resultado['sql'])}")

    elif resultado["tipo"] == "DataWindow":
        if resultado.get("janelas"):
            linhas.append(f"Usada nas janelas: {', '.join(resultado['janelas'])}")
        if resultado.get("objetos"):
            linhas.append(f"Usada nos objetos: {', '.join(resultado['objetos'])}")
        if resultado.get("datawindows"):
            linhas.append(f"Usada em DataWindows (sub-reports): {', '.join(resultado['datawindows'])}")
        if resultado["tabelas"]:
            linhas.append(f"Tabelas: {', '.join(resultado['tabelas'])}")
        if resultado["colunas"]:
            cols = resultado["colunas"][:15]
            linhas.append(f"Colunas ({len(resultado['colunas'])} total): {', '.join(cols)}")
        if resultado["procedures"]:
            linhas.append(f"Procedures: {', '.join(resultado['procedures'])}")
        if resultado["code_tables"]:
            linhas.append(f"Code Tables: {', '.join(resultado['code_tables'][:5])}")

    elif resultado["tipo"] == "Function":
        if resultado["heranca"]:
            linhas.append(f"Herança: {', '.join(resultado['heranca'])}")
        if resultado["parametros"]:
            linhas.append(f"Parâmetros: {', '.join(resultado['parametros'])}")
        if resultado["chama"]:
            linhas.append(f"Chama: {', '.join(resultado['chama'])}")
        if resultado["sql"]:
            linhas.append(f"Tabelas SQL: {', '.join(resultado['sql'])}")

    elif resultado["tipo"] == "UserObject":
        if resultado["heranca"]:
            linhas.append(f"Herança: {', '.join(resultado['heranca'])}")
        if resultado["metodos"]:
            linhas.append(f"Métodos: {', '.join(resultado['metodos'])}")
        if resultado["datawindows"]:
            linhas.append(f"DataWindows: {', '.join(resultado['datawindows'])}")
        if resultado["sql"]:
            linhas.append(f"Tabelas SQL: {', '.join(resultado['sql'])}")

    elif resultado["tipo"] == "Menu":
        if resultado.get("janelas"):
            linhas.append(f"Janelas que abre ({len(resultado['janelas'])} total): {', '.join(resultado['janelas'][:20])}")

    elif resultado["tipo"] == "Application":
        if resultado.get("janelas"):
            linhas.append(f"Janelas que abre: {', '.join(resultado['janelas'])}")

    return "\n".join(linhas)


def _varrer(padrao):
    """Varrer a árvore de fontes ignorando .git e retornando só .sr*."""
    out = []
    for arq in RAIZ.rglob(padrao):
        rel = Path(arq)
        if ".git" in rel.parts:
            continue
        if rel.is_file() and rel.suffix.lower() in EXTENSOES:
            out.append(rel)
    return out


def resolver(termo):
    """Resolve um termo para caminhos .sr*.
    Aceita nome simples ('w_tab_fnc' ou 'w_tab_fnc.srw'), caminho
    ('deivide\\w_tab_fnc' ou 'deivide/w_tab_fnc'), pasta/PBL completa
    ('deivide') e padrão/curinga ('w_tab_*').
    Se houver mais de um objeto com o mesmo nome, retorna todos."""
    termo = termo.strip()
    if not termo:
        return []
    termo = termo.replace("/", os.sep)
    p = Path(termo)
    alvo_raiz = RAIZ / p  # resolvido contra a raiz dos fontes (indep. do cwd)

    if p.is_file() or alvo_raiz.is_file():
        alvo = p if p.is_file() else alvo_raiz
        return [alvo]

    # Pasta/PBL: termo é um diretório → todos os .sr* dentro dela
    if alvo_raiz.is_dir():
        return sorted(set(_varrer(str(p) + os.sep + "**" + os.sep + "*.sr*")))

    # Curinga no nome
    if any(c in termo for c in "*?"):
        return sorted(set(_varrer(termo) + _varrer(termo + ".sr*")))

    # Nome simples (com ou sem extensão)
    if p.suffix.lower() in EXTENSOES:
        nome_base = p.stem
    else:
        nome_base = termo
    return sorted(set(
        arq for ext in EXTENSOES for arq in _varrer(nome_base + ext)
    ))


def _normalizar(texto):
    """Remove acentos e lower-case, via unicodedata (robusto para qualquer
    acento latino). Usada na busca --buscar padrão (independente de case e
    acentos). Não altera o encoding dos .sr*: só cria a forma normalizada em
    memória."""
    n = unicodedata.normalize("NFD", texto)
    return "".join(c for c in n if not unicodedata.combining(c)).lower()


def _buscar_worker(args):
    """Worker paralelo: procura o alvo num único arquivo.
    args = (caminho, tipo_filtro, texto, respeitar_acentos).
    Devolve (caminho, [nº das linhas]) ou None se não houver match."""
    caminho, tipo_filtro, texto, respeitar_acentos = args
    arq = Path(caminho)
    if tipo_filtro and arq.suffix.lower() != "." + tipo_filtro.lower():
        return None
    conteudo = ler_arquivo(arq)
    if respeitar_acentos:
        alvo = texto.lower()
        conteudo_lc = conteudo.lower()
        if alvo not in conteudo_lc:
            return None
        linhas = [i for i, linha in enumerate(conteudo_lc.splitlines(), start=1)
                  if alvo in linha]
    else:
        alvo = _normalizar(texto)
        conteudo_norm = _normalizar(conteudo)
        if alvo not in conteudo_norm:
            return None
        linhas = [i for i, linha in enumerate(conteudo_norm.splitlines(), start=1)
                  if alvo in linha]
    return (caminho, linhas)


def buscar_conteudo(texto, tipo_filtro=None, alvos=None, respeitar_acentos=False,
                    paralelo=True):
    """Procura um texto dentro do conteúdo dos .sr*.
    alvos: lista opcional de arquivos a pesquisar (escopo/--em). Se vazio,
    varre todos os .sr*. Com respeitar_acentos=True a busca ignora case mas
    respeita acentos; padrão é case-insensitive e ignora acentos.
    Processa os arquivos em paralelo (multiprocessing) quando há muitos.
    Retorna lista de (caminho, linhas)."""
    arquivos = [a for a in (alvos if alvos is not None else _varrer("*"))]
    if tipo_filtro:
        arquivos = [a for a in arquivos
                    if a.suffix.lower() == "." + tipo_filtro.lower()]
    if not arquivos:
        return []
    args = [(str(a), tipo_filtro, texto, respeitar_acentos) for a in arquivos]
    if paralelo and len(args) > 1:
        from multiprocessing import Pool, cpu_count
        nprocs = min(cpu_count(), len(args))
        if nprocs > 1:
            with Pool(processes=nprocs) as pool:
                chunksize = max(1, (len(args) + nprocs * 4 - 1) // (nprocs * 4))
                parcial = pool.map(_buscar_worker, args, chunksize=chunksize)
        else:
            parcial = [_buscar_worker(a) for a in args]
    else:
        parcial = [_buscar_worker(a) for a in args]
    return [(Path(c), linhas)
            for c, linhas in [x for x in parcial if x is not None]]


def _extrair_flag(sysv, flag):
    """Lê o valor da flag (--tipo, --em) da linha de comando, se houver."""
    if flag in sysv:
        idx = sysv.index(flag)
        if idx + 1 < len(sysv):
            return sysv[idx + 1]
    return None


# Flags aceitas, breve explicação e exemplo de uso (exibidos no erro de flag
# desconhecida). O exemplo com '{t}' usa o termo digitado no --buscar (quando
# existir); o exemplo fixo serve quando não há --buscar na linha de comando.
_FLAGS_DISPONIVEIS = [
    ("--buscar", "Busca o texto dentro do conteúdo dos .sr*.",
     '--buscar "{t}"', '--buscar "ll_teq_id_seq"'),
    ("--acentos", "Na busca, respeita os acentos (mantém case-insensitive).",
     '--buscar "{t}" --acentos', '--buscar "ll_teq_id_seq" --acentos'),
    ("--tipo", "Filtra por tipo de objeto: srw | srd | srf | sru.",
     '--buscar "{t}" --tipo srd', '*telemetria* --tipo srd'),
    ("--em", "Restringe a busca a um objeto/caminho/PBL/padrão.",
     '--buscar "{t}" --em deivide\\w_tab_teq',
     '--buscar "ll_teq_id_seq" --em deivide\\w_tab_teq'),
]
_FLAGS_CONHECIDAS = {f for f, _, _, _ in _FLAGS_DISPONIVEIS}


def _validar_flags(argv):
    """Devolve a lista de flags desconhecidas digitadas (começam com '--'.
    mas não são --tipo/--em/--buscar/--acentos). Se houver, imprime o erro
    com a lista das flags válidas (explicação alinhada com o exemplo) e
    devolve True (para interromper)."""
    desconhecidas = [a for a in argv if a.startswith("--") and a not in _FLAGS_CONHECIDAS]
    if not desconhecidas:
        return False
    termo = _extrair_flag(argv, "--buscar")
    print("Flag desconhecida:", ", ".join(f"'{a}'" for a in desconhecidas))
    print("\nFlags válidas:")
    ident = " " * 15  # alinha o exemplo com o início da explicação
    for f, d, ex_com, ex_sem in _FLAGS_DISPONIVEIS:
        ex = ex_com.format(t=termo) if termo else ex_sem
        print(f"  {f:<12} {d}")
        print(f"{ident}ex.: {ex}")
    return True


def _montar_args(argv):
    """Normaliza a linha de comando: devolve (termo, tipo, em, acess).
    aceitando as flags em qualquer ordem. 'termo' é o --buscar (texto a
    procurar) ou o nome/caminho/curinga do modo padrão. 'acess' (--acentos)
    indica que a busca respeita os acentos (mantendo case-insensitive)."""
    resto = list(argv)
    acess = "--acentos" in resto
    tipo = _extrair_flag(resto, "--tipo")
    em = _extrair_flag(resto, "--em")
    for flag in ("--acentos", "--buscar"):
        if flag in resto:
            resto.remove(flag)
    for flag in ("--tipo", "--em"):
        while flag in resto:
            idx = resto.index(flag)
            resto = resto[:idx] + resto[idx + 2:]
    resto = [a for a in resto if a]
    termo = resto[0] if resto else ""
    return termo, tipo, em, acess


def main():
    if len(sys.argv) < 2:
        print("Uso (via analise.bat, de qualquer pasta):")
        print("  analise w_tab_fnc              # por NOME, em todas as PBLs")
        print("  analise deivide\\w_tab_fnc     # caminho: forcar uma PBL")
        print("  analise w_tab_*                # curinga no NOME do objeto")
        print("  analise *telemetria* --tipo srd  # curinga + filtro de tipo")
        print("  analise --buscar \"texto\"      # busca de CONTEUDO nos .sr*")
        print("  analise --buscar \"txt\" --em \"deivide\\w_tab_teq\" --tipo srw")
        print("  analise --buscar \"txt\" --em deivide     # PBL inteira, sem *")
        print("  analise --buscar \"txt\" --em \"sdo09/w_obj\"  # barra \"/\" vale")
        print("  analise --buscar \"txt\" --acentos  # respeita ACENTOS (case-insensitive)")
        print("  Flags (--tipo, --em, --acentos) valem em qualquer ordem.")
        sys.exit(1)

    if _validar_flags(sys.argv[1:]):
        sys.exit(1)

    buscar_mode = "--buscar" in sys.argv
    termo, tipo_filtro, em, acess = _montar_args(sys.argv[1:])

    # Modo --buscar: busca por CONTEÚDO (com escopo opcional via --em)
    if buscar_mode:
        texto = termo
        if not texto:
            print("Informe o texto a buscar: analise --buscar \"texto\"")
            sys.exit(1)
        # Escopo: --em resolve um objeto/caminho/padrão; sem ele, varre tudo
        alvos = resolver(em) if em else None
        if em and not alvos:
            print(f"--em: nenhum objeto encontrado para: {em}")
            sys.exit(0)
        resultados = buscar_conteudo(texto, tipo_filtro, alvos, acess)
        modo = "case-insensitive / respeita acentos" if acess else "case-insensitive / ignora acentos"
        if not resultados:
            print(f"Nenhum .sr* contém: {texto}  (busca {modo})")
            sys.exit(0)
        print(f"{len(resultados)} objeto(s) contêm '{texto}' ({modo}):\n")
        for arq, linhas in resultados:
            rel = arq.relative_to(RAIZ)
            tipo = NOME_TIPO.get(arq.suffix.lower(), arq.suffix.lower())
            linhas_txt = ", ".join(str(n) for n in linhas[:10])
            extra = "..." if len(linhas) > 10 else ""
            print(f"  {rel}  [{tipo}]  (linha(s): {linhas_txt}{extra})")
        sys.exit(0)

    # Modo padrão: por nome/caminho/curinga
    arquivos = resolver(termo)
    if not arquivos:
        print(f"Nenhum objeto encontrado para: {termo}")
        sys.exit(0)
    if tipo_filtro:
        arquivos = [a for a in arquivos if a.suffix.lower() == "." + tipo_filtro.lower()]
        if not arquivos:
            print(f"Nenhum objeto {tipo_filtro} encontrado para: {termo}")
            sys.exit(0)
    for arq in arquivos:
        print(formatar_saida(analisar_arquivo(arq)))
        print()


if __name__ == "__main__":
    main()
