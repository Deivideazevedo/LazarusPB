# -*- coding: latin-1 -*-
r"""Lazarus IA - Mapa de correspondencia entre PBLs (origem).

Mapa: para cada objeto de uma PBL "origem" (ex.: deivide), procura o mesmo
objeto nas DEMAIS PBLs extraidas em codigo_fonte. Cria a pasta oculta
"codigo_fonte\.origem\\" e, dentro dela, uma pasta com o nome da PBL origem.
Nessa subpasta, gera uma pasta por PBL que possui correspondencia (copiando
os objetos para la) e uma pasta "novos objetos" com os objetos que NAO
existem em nenhuma outra PBL. Varias PBLs origem podem coexistir (uma pasta
por PBL origem); a cada execucao so a subpasta da PBL origem e recriada.

Nao altera nenhum .sr* nem recompila: apenas LE e COPIA. A pasta ".origem\"
e ignorada no .gitignore do repo de codigo_fonte.

Uso (via origem.bat, de qualquer pasta):
    origem deivide        # mapa de correspondencia da PBL deivide
"""

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comum

FONTE = comum.CODIGO_FONTE
ORIGEM = os.path.join(FONTE, '.origem')
NOVOS = 'novos objetos'

TIPOS = comum.TIPOS


def _ignorado(nome):
    return nome in ('.git',) or nome.startswith('.')


def listar_pbls():
    """Devolve o nome de cada subpasta de codigo_fonte que e uma PBL."""
    if not os.path.isdir(FONTE):
        return []
    return sorted(
        d for d in os.listdir(FONTE)
        if os.path.isdir(os.path.join(FONTE, d)) and not _ignorado(d)
    )


def objetos_da_pbl(pbl):
    """Devolve {nome_arquivo: caminho} dos objetos .sr* de uma PBL."""
    pasta = os.path.join(FONTE, pbl)
    if not os.path.isdir(pasta):
        return {}
    objetos = {}
    for f in sorted(os.listdir(pasta)):
        caminho = os.path.join(pasta, f)
        if os.path.isfile(caminho) and os.path.splitext(f)[1].lower() in TIPOS:
            objetos[f] = caminho
    return objetos


def onde_existe(pbl_origem, nome_arquivo):
    """Em quais outras PBLs existe um arquivo de mesmo nome."""
    alvos = []
    for pbl in listar_pbls():
        if pbl == pbl_origem:
            continue
        if os.path.isfile(os.path.join(FONTE, pbl, nome_arquivo)):
            alvos.append(pbl)
    return alvos


def gerar_mapa(pbl_origem):
    """Cria a arvore de origem com as correspondencias e 'novos objetos'."""
    pbl_origem = pbl_origem.strip()
    if not pbl_origem:
        print("Informe a PBL origem: origem <nome>")
        sys.exit(1)
    dest_pbl = os.path.join(ORIGEM, pbl_origem)
    dest_novo = os.path.join(dest_pbl, NOVOS)

    objetos = objetos_da_pbl(pbl_origem)
    if not objetos:
        print(f"PBL '{pbl_origem}' nao encontrada ou sem objetos em codigo_fonte.")
        sys.exit(1)

    # Limpa destino para refletir sempre o estado atual
    if os.path.isdir(dest_pbl):
        shutil.rmtree(dest_pbl)
    os.makedirs(dest_novo, exist_ok=True)

    por_pbl = {}      # pbl_destino -> [arquivos]
    novos = []

    for nome_arquivo, caminho_orig in sorted(objetos.items()):
        alvos = onde_existe(pbl_origem, nome_arquivo)
        if alvos:
            for pbl_alvo in alvos:
                por_pbl.setdefault(pbl_alvo, []).append(nome_arquivo)
                dest_dir = os.path.join(dest_pbl, pbl_alvo)
                os.makedirs(dest_dir, exist_ok=True)
                shutil.copy2(caminho_orig, os.path.join(dest_dir, nome_arquivo))
        else:
            novos.append(nome_arquivo)
            shutil.copy2(caminho_orig, os.path.join(dest_novo, nome_arquivo))

    # Relatorio
    linhas = []
    linhas.append(f"Mapa de correspondencia - PBL origem: {pbl_origem}")
    linhas.append(f"Gerado em: {comum.agora()}")
    linhas.append("")
    linhas.append("Objetos da PBL origem:")
    for f in sorted(objetos):
        linhas.append(f"  - {f}")
    linhas.append("")

    if por_pbl:
        linhas.append("Correspondencias (pasta por PBL):")
        for pbl_alvo in sorted(por_pbl):
            arq = sorted(por_pbl[pbl_alvo])
            linhas.append(f"  [{pbl_alvo}] {len(arq)} objeto(s):")
            for f in arq:
                linhas.append(f"    - {f}")
        linhas.append("")
    else:
        linhas.append("Correspondencias: nenhuma em outras PBLs.")
        linhas.append("")

    if novos:
        linhas.append(f"NOVO - sem correspondencia ({len(novos)}):")
        for f in sorted(novos):
            linhas.append(f"  - {f}")
    else:
        linhas.append("NOVO: nenhum objeto sem correspondencia.")

    relatorio = os.path.join(dest_pbl, 'relatorio.txt')
    with open(relatorio, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(linhas) + '\n')

    # Saida no console
    print(f"\nPBL origem: {pbl_origem}")
    print(f"  {len(objetos)} objeto(s) mapeado(s)")
    for pbl_alvo in sorted(por_pbl):
        print(f"  -> {pbl_alvo}: {len(por_pbl[pbl_alvo])} correspondencia(s)")
    print(f"  -> {NOVOS}: {len(novos)} objeto(s) sem correspondencia")
    print(f"\nArvore criada em: {dest_pbl}")
    print(f"Relatorio: {relatorio}")


def main():
    if len(sys.argv) < 2:
        print("Uso: origem <pbl>   (ex.: origem deivide)")
        sys.exit(1)
    gerar_mapa(sys.argv[1])
    sys.exit(0)


if __name__ == "__main__":
    main()
