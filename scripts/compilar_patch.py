# -*- coding: latin-1 -*-
r"""Lazarus IA - Compilador de PATCH (somente os alterados)

Compara o conteudo atual de codigo_fonte\ com a baseline de hashes.json
(gerada pelo extrair.py) e importa SOMENTE os objetos novos ou alterados
em um unico patch.pbl, junto com todos os .sr* que vierem a mudar
(windows, datawindows, funcoes, user objects etc.).

Fluxo de trabalho:
    1) extrair.bat            -> gera codigo_fonte\*.sr* + hashes.json (baseline)
    2) edite os .sr* em codigo_fonte\
    3) compilar_patch.bat     -> gera compilacao\patch.pbl com so os alterados

Observacoes:
    - O patch.pbl eh recriado do zero a cada execucao e contem TODOS os
      objetos alterados desde a ultima extracao (patch cumulativo).
    - A baseline so volta ao zero quando voce rodar extrair.bat de novo.
    - Este script precisa do Python 32-bit (scripts\python32\python.exe),
      pois usa a pborc90.dll de 32 bits.

Saida:
    LazarusIA\compilacao\patch.pbl
    LazarusIA\logs\patch.import.txt
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import comum
from compilar import (
    DLL_PADRAO,
    OK,
    OBJEXISTS,
    ORDEM,
    TIPO,
    TIPO_BINARY,
    MARCADOR_BINARIO,
    OrcaSession,
    extrair_comentario,
)

OUT_PATCH = os.path.join(comum.COMPILACAO, 'patch.pbl')


def coletar_fonte():
    r"""Todos os .sr* de codigo_fonte\ (uma subpasta por PBL), ordenados."""
    arquivos = []
    if not os.path.isdir(comum.CODIGO_FONTE):
        return arquivos
    for raiz, _, fnames in os.walk(comum.CODIGO_FONTE):
        for f in fnames:
            if os.path.splitext(f)[1].lower() in comum.TIPOS:
                arquivos.append(os.path.join(raiz, f))
    arquivos.sort(key=lambda p: (
        ORDEM.index(os.path.splitext(p)[1].lower()),
        os.path.basename(p).lower()))
    return arquivos


def detectar_alterados(arquivos):
    r"""Devolve (alterados, removidos).

    alterados: arquivos cujo hash difere da baseline ou que sao novos.
    removidos: chaves presentes na baseline mas sem arquivo em disco.
    A chave da baseline eh o caminho relativo "pbl\nome.ext".
    """
    dados = comum.carregar_hashes()
    baseline = dados.get('objetos', {})
    vistos = set()
    alterados = []
    for arquivo in arquivos:
        chave = os.path.relpath(arquivo, comum.CODIGO_FONTE)
        vistos.add(chave)
        atual = comum.hash_arquivo(arquivo)
        reg = baseline.get(chave)
        if reg is None or reg.get('hash') != atual:
            alterados.append(arquivo)
    removidos = sorted(set(baseline) - vistos)
    return alterados, removidos


def importar_patch(sess, itens, cfg, lf):
    """Cria patch.pbl e importa cada objeto; retorna (ok, falhas)."""
    rc = sess.criar_biblioteca(OUT_PATCH)
    lf.write('Criar biblioteca %s -> rc=%d\n' % (OUT_PATCH, rc))
    print('==> Criando biblioteca %s (rc=%d)' % (OUT_PATCH, rc))

    libs = [OUT_PATCH]
    for lib in list(cfg.get('pbls', [])) + list(cfg.get('lib_list', [])):
        if os.path.isfile(lib) and lib not in libs:
            libs.append(lib)
    rc = sess.set_library_list(libs)
    lf.write('Library list (%d) -> rc=%d\n' % (len(libs), rc))
    if rc != OK:
        print('!! Falha ao definir library list (rc=%d)' % rc)
        return [], list(itens)

    app_name = cfg.get('app_name', '')
    app_lib = cfg.get('app_lib', '')
    if app_name and app_lib and os.path.isfile(app_lib):
        rc = sess.set_current_appl(app_lib, app_name)
        lf.write('Application atual (%s em %s) -> rc=%d\n'
                 % (app_name, app_lib, rc))
        if rc != OK:
            print('!! Falha ao definir application atual (rc=%d)' % rc)
            return [], list(itens)
    else:
        print('!! ATENCAO: app_name/app_lib invalidos no config.json.')
        return [], list(itens)

    ok, falhas = [], []
    pendentes = list(itens)
    for tentativa in range(6):
        if not pendentes:
            break
        restantes = []
        for arquivo in pendentes:
            basename = os.path.basename(arquivo)
            ext = os.path.splitext(basename)[1].lower()
            entry = os.path.splitext(basename)[0]
            with open(arquivo, 'rb') as fh:
                sintaxe = fh.read()

            marca = sintaxe.find(MARCADOR_BINARIO)
            if marca >= 0:
                parte_fonte = sintaxe[:marca]
                parte_bin = sintaxe[marca:]
            else:
                parte_fonte = sintaxe
                parte_bin = None

            comentario = extrair_comentario(parte_fonte)

            rc1, erros = sess.importar(
                OUT_PATCH, entry, TIPO[ext], parte_fonte, comentario)
            rc2 = OK
            if parte_bin is not None and rc1 == OK:
                rc2, _ = sess.importar(
                    OUT_PATCH, entry, TIPO_BINARY, parte_bin)

            if rc1 == OK and rc2 == OK:
                ok.append(arquivo)
                lf.write('OK   %s\n' % basename)
                print('  OK  %s' % basename)
            elif rc1 == OBJEXISTS:
                ok.append(arquivo)
                lf.write('OK   %s (ja existia)\n' % basename)
                print('  OK  %s (ja existia)' % basename)
            else:
                restantes.append(arquivo)
                for nivel, num, msg, linha in erros:
                    texto = (msg or b'').decode('latin-1', 'replace')
                    lf.write('ERR  %s [%s] %s (linha %s)\n'
                             % (basename, rc1, texto.strip(), linha))
                lf.write('FALHOU %s (rc=%d)\n' % (basename, rc1))
        pendentes = restantes
        if pendentes:
            print('    retentando %d objeto(s)...' % len(pendentes))

    return ok, pendentes


def main():
    if not os.path.isfile(comum.HASHES):
        print('ERRO: hashes.json nao encontrado em scripts\\.')
        print('Rode antes o extrair.bat para gerar a baseline de hashes.')
        return 1

    cfg = comum.carregar_config()
    orca_dll = cfg.get('orca_dll', DLL_PADRAO)
    if not os.path.isfile(orca_dll):
        print('ERRO: pborc90.dll nao encontrado em', orca_dll)
        return 1

    arquivos = coletar_fonte()
    if not arquivos:
        print('Nenhum .sr* encontrado em', comum.CODIGO_FONTE)
        return 1

    alterados, removidos = detectar_alterados(arquivos)

    if removidos:
        print('Info: %d objeto(s) da baseline nao estao mais em disco '
              '(ignorados):' % len(removidos))
        for nome in removidos[:20]:
            print('    -', nome)
        if len(removidos) > 20:
            print('    ... e mais %d' % (len(removidos) - 20))

    if not alterados:
        print('\nNenhum objeto alterado desde a ultima extracao. '
              'Nada a compilar.')
        return 0

    itens = alterados
    print('\nObjetos alterados/novos desde a ultima extracao: %d' % len(itens))
    for a in itens:
        print('    *', os.path.relpath(a, comum.CODIGO_FONTE))

    import integridade_fontes
    pular_checagem = '--ignorar-checagem' in sys.argv
    if not pular_checagem:
        print('== Checando integridade e encoding dos alterados (CP1252 / Git)...')
        ok = integridade_fontes.processar_integridade(itens, interativo=True)
        if not ok:
            print('\n!! COMPILACAO DO PATCH ABORTADA.')
            return 1

    sess = OrcaSession(orca_dll)
    if not sess.abrir():
        print('ERRO: nao foi possivel abrir sessao ORCA.')
        return 1

    os.makedirs(comum.COMPILACAO, exist_ok=True)
    os.makedirs(comum.LOGS, exist_ok=True)
    log = os.path.join(comum.LOGS, 'patch.import.txt')
    try:
        with open(log, 'w', encoding='utf-8') as lf:
            lf.write('Log de patch  [%s]\n' % comum.agora())
            lf.write('Baseline: %s\n' % comum.HASHES)
            lf.write('Alterados/novos: %d\n\n' % len(itens))
            ok, falhas = importar_patch(sess, itens, cfg, lf)
            if falhas:
                lf.write('\nNAO IMPORTADOS: %s\n'
                         % ', '.join(os.path.basename(f) for f in falhas))
            resultado = ('SUCESSO (%d objeto(s))' % len(ok)) if not falhas \
                else 'FALHOU (%d objeto(s))' % len(falhas)
            lf.write('\nFim: %s  [%s]\n' % (resultado, comum.agora()))
    finally:
        sess.fechar()

    if falhas:
        print('\n==> %d objeto(s) NAO importado(s):' % len(falhas))
        for f in falhas:
            print('    -', os.path.basename(f))
        print('Patch parcial em:', OUT_PATCH)
        return 2

    print('\n==> Patch gerado com %d objeto(s) em:' % len(ok))
    print('   ', OUT_PATCH)
    return 0


if __name__ == '__main__':
    sys.exit(main())
