# -*- coding: latin-1 -*-
r"""Lazarus IA - Validador de round-trip

Extrai de novo o .pbl recriado (compilacao\<nome>.pbl) e compara os .sr*
obtidos com os de codigo_fonte\<nome>\. Se forem identicos, o ciclo
extrair -> compilar preservou o codigo sem perdas.

Uso (chame sempre com o caminho completo, de qualquer pasta):

    "...\python32\python.exe" "...\validar.py"
        # Valida os PBLs da lista "pbls" do config.json.

    "...\validar.py" "F:\sdo\programa\deivide.pbl"
        # Valida apenas este PBL.

Saida:
    LazarusIA\logs\<nome>.validacao.txt
"""
import datetime
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comum

BASE = comum.BASE
ROOT = comum.ROOT
CODIGO_FONTE = comum.CODIGO_FONTE
COMPILACAO = comum.COMPILACAO
LOGS = comum.LOGS
PBLDUMP = comum.PBLDUMP
CONFIG = comum.CONFIG

TIPOS = comum.TIPOS


def agora():
    return comum.agora()


def carregar_pbls(args):
    if not args:
        cfg = comum.carregar_config()
        return cfg.get('pbls', [])
    # Nome simples ("deivide" / "deivide.pbl") nao precisa de arquivo:
    # a validacao compara compilacao\<nome>.pbl com codigo_fonte\<nome>\.
    pbls = []
    for a in args:
        if os.path.isfile(a) or not comum.eh_nome_simples(a):
            pbls.append(a)
        else:
            pbls.append(a if a.lower().endswith('.pbl') else a + '.pbl')
    invalidos = [p for p in pbls
                 if not (os.path.isfile(p) or comum.eh_nome_simples(p))]
    if invalidos:
        print('AVISO: caminho nao encontrado, ignorado:', ', '.join(invalidos))
    return [p for p in pbls
            if os.path.isfile(p) or comum.eh_nome_simples(p)]


def comparar_bytes(orig, novo):
    with open(orig, 'rb') as f1, open(novo, 'rb') as f2:
        return f1.read() == f2.read()


def comparar_solto(orig, novo):
    """Compara ignorando espacos em branco no fim de cada linha."""
    with open(orig, 'rb') as f1, open(novo, 'rb') as f2:
        a = [l.rstrip(b' \t\r\n') for l in f1.read().splitlines() if l.strip()]
        b = [l.rstrip(b' \t\r\n') for l in f2.read().splitlines() if l.strip()]
    return a == b


def validar_pbl(pbl, lf):
    nome = os.path.splitext(os.path.basename(pbl))[0]
    dir_src = os.path.join(CODIGO_FONTE, nome)
    recreated = os.path.join(COMPILACAO, nome + '.pbl')
    print('==> Validando [%s]' % pbl)
    lf.write('==> Validando [%s]\n' % pbl)

    if not os.path.isdir(dir_src):
        print('    !! Pasta de fonte nao encontrada:', dir_src)
        lf.write('    !! Pasta de fonte nao encontrada: %s\n' % dir_src)
        return 1
    if not os.path.isfile(recreated):
        print('    !! .pbl recriado nao encontrado:', recreated)
        lf.write('    !! .pbl recriado nao encontrado: %s\n' % recreated)
        return 1

    tmp = tempfile.mkdtemp(prefix='validar_')
    proc = subprocess.run([PBLDUMP, '-es', recreated, '*.*'],
                          cwd=tmp, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    saida = proc.stdout.decode('latin-1', errors='replace')
    saida = saida.replace('\r\n', '\n').replace('\r', '\n')

    fontes = sorted(a for a in os.listdir(dir_src)
                    if os.path.splitext(a)[1].lower() in TIPOS)
    ig = diff = ausente = 0
    for f in fontes:
        novo = os.path.join(tmp, f)
        orig = os.path.join(dir_src, f)
        if not os.path.isfile(novo):
            ausente += 1
            print('    AUSENTE  %s' % f)
            lf.write('    AUSENTE  %s\n' % f)
        elif comparar_bytes(orig, novo):
            ig += 1
        elif comparar_solto(orig, novo):
            diff += 1
            print('    ~ SOLO   %s (difere so por espacos/linha final)' % f)
            lf.write('    ~ SOLO   %s (difere so por espacos/linha final)\n' % f)
        else:
            diff += 1
            print('    DIFERENTE  %s' % f)
            lf.write('    DIFERENTE  %s\n' % f)

    lf.write('    Resumo: %d identico(s), %d divergente(s), %d ausente(s)\n'
             % (ig, diff, ausente))
    print('    Resumo: %d identico(s), %d divergente(s), %d ausente(s)'
          % (ig, diff, ausente))
    return 0 if (diff == 0 and ausente == 0) else 2


def main():
    if not os.path.isfile(PBLDUMP):
        print('ERRO: PblDump.exe nao encontrado em', PBLDUMP)
        return 1
    pbls = carregar_pbls(sys.argv[1:])
    if not pbls:
        print('Nenhum PBL informado. Edite config.json ou passe caminhos.')
        return 1
    os.makedirs(LOGS, exist_ok=True)
    falhou = 0
    for pbl in pbls:
        nome = os.path.splitext(os.path.basename(pbl))[0]
        log = os.path.join(LOGS, nome + '.validacao.txt')
        with open(log, 'w', encoding='utf-8') as lf:
            lf.write('Log de validacao de %s  [%s]\n' % (pbl, agora()))
            rc = validar_pbl(pbl, lf)
            lf.write('Fim: %s  [%s]\n' % ('OK' if rc == 0 else 'FALHOU', agora()))
        falhou += rc
    print('\nValidacao concluida.')
    return 0 if falhou == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
