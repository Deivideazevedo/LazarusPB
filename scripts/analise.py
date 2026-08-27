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

Modos:
  - NOME/CAMINHO/CURINGA: resolve o objeto pelo nome do arquivo.
  - --buscar: procura um texto DENTRO do conteudo dos arquivos .sr* e
    devolve onde ele aparece (tipo, caminho, linha). Aceita --em para
    restringir a busca a um objeto, caminho ou padrao especifico.
O diretório .git é ignorado na varredura e só arquivos .sr* são lidos.
"""

import re
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comum

RAIZ = Path(comum.CODIGO_FONTE)

EXTENSOES = (".srw", ".srd", ".srf", ".sru")
NOME_TIPO = {
    ".srw": "Window",
    ".srd": "DataWindow",
    ".srf": "Function",
    ".sru": "UserObject",
}


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
        "datawindows": [],
        "funcoes": [],
        "janelas": [],
        "objetos": [],
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

    return resultado


def analisar_srd(caminho):
    """Analisa um arquivo DataWindow (.srd)."""
    conteudo = ler_arquivo(caminho)
    nome = Path(caminho).stem
    relativo = str(Path(caminho).relative_to(RAIZ))
    pasta = Path(caminho).parent.name

    resultado = {
        "arquivo": nome,
        "caminho": relativo,
        "pbl": pasta,
        "tipo": "DataWindow",
        "tabelas": [],
        "colunas": [],
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
    else:
        return {"arquivo": Path(caminho).stem, "tipo": f"Não suportado ({ext})"}


def formatar_saida(resultado):
    """Formata a saída da análise para impressão."""
    linhas = []
    linhas.append(f"=== {resultado['arquivo']}.{resultado.get('tipo', '?').lower()} ===")
    linhas.append(f"Tipo: {resultado['tipo']}")
    linhas.append(f"PBL: {resultado.get('pbl', '?')}")
    linhas.append(f"Caminho: {resultado.get('caminho', '?')}")
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
        if resultado["sql"]:
            linhas.append(f"Tabelas SQL: {', '.join(resultado['sql'])}")

    elif resultado["tipo"] == "DataWindow":
        if resultado["tabelas"]:
            linhas.append(f"Tabelas: {', '.join(resultado['tabelas'])}")
        if resultado["colunas"]:
            cols = resultado["colunas"][:15]
            linhas.append(f"Colunas ({len(resultado['colunas'])} total): {', '.join(cols)}")
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
    ('deivide\\w_tab_fnc') e padrão/curinga ('w_tab_*').
    Se houver mais de um objeto com o mesmo nome, retorna todos."""
    termo = termo.strip()
    if not termo:
        return []
    p = Path(termo)

    if p.is_file():
        return [p]

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


def buscar_conteudo(texto, tipo_filtro=None, alvos=None):
    """Procura um texto dentro do conteúdo dos .sr* (case-insensitive).
    alvos: lista opcional de arquivos a pesquisar (escopo/--em). Se vazio,
    varre todos os .sr*. Retorna lista de (caminho, linhas)."""
    alvo = texto.lower()
    resultados = []
    arquivos = alvos if alvos else _varrer("*")
    for arq in arquivos:
        if tipo_filtro and arq.suffix.lower() != "." + tipo_filtro.lower():
            continue
        conteudo = ler_arquivo(arq)
        if alvo not in conteudo.lower():
            continue
        linhas = []
        for i, linha in enumerate(conteudo.splitlines(), start=1):
            if alvo in linha.lower():
                linhas.append(i)
        resultados.append((arq, linhas))
    return resultados


def _extrair_flag(sysv, flag):
    """Lê o valor da flag (--tipo, --em) da linha de comando, se houver."""
    if flag in sysv:
        idx = sysv.index(flag)
        if idx + 1 < len(sysv):
            return sysv[idx + 1]
    return None


def main():
    if len(sys.argv) < 2:
        print("Uso (via analise.bat, de qualquer pasta):")
        print("  analise w_tab_fnc              # por NOME, em todas as PBLs")
        print("  analise deivide\\w_tab_fnc     # caminho: forcar uma PBL")
        print("  analise w_tab_*                # curinga no NOME do objeto")
        print("  analise *telemetria* --tipo srd  # curinga + filtro de tipo")
        print("  analise --buscar \"texto\"      # busca de CONTEUDO nos .sr*")
        print("  analise --buscar \"txt\" --em \"deivide\\w_tab_teq\" --tipo srw")
        sys.exit(1)

    tipo_filtro = _extrair_flag(sys.argv, "--tipo")

    # Modo --buscar: busca por CONTEÚDO (com escopo opcional via --em)
    if sys.argv[1] == "--buscar":
        texto = sys.argv[2] if len(sys.argv) > 2 else ""
        if not texto:
            print("Informe o texto a buscar: analise --buscar \"texto\"")
            sys.exit(1)
        # Escopo: --em resolve um objeto/caminho/padrão; sem ele, varre tudo
        em = _extrair_flag(sys.argv, "--em")
        alvos = resolver(em) if em else None
        if em and not alvos:
            print(f"--em: nenhum objeto encontrado para: {em}")
            sys.exit(0)
        resultados = buscar_conteudo(texto, tipo_filtro, alvos)
        if not resultados:
            print(f"Nenhum .sr* contém: {texto}")
            sys.exit(0)
        print(f"{len(resultados)} objeto(s) contêm '{texto}':\n")
        for arq, linhas in resultados:
            rel = arq.relative_to(RAIZ)
            tipo = NOME_TIPO.get(arq.suffix.lower(), arq.suffix.lower())
            linhas_txt = ", ".join(str(n) for n in linhas[:10])
            extra = "..." if len(linhas) > 10 else ""
            print(f"  {rel}  [{tipo}]  (linha(s): {linhas_txt}{extra})")
        sys.exit(0)

    # Modo padrão: por nome/caminho/curinga
    termo = sys.argv[1]
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
