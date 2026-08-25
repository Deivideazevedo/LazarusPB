# -*- coding: latin-1 -*-
r"""Lazarus IA - Extrator de PBLs
Extrai o codigo-fonte (.sr*) de bibliotecas PowerBuilder (.pbl) usando PblDump.

Uso (chame sempre com o caminho completo, de qualquer pasta):

    "C:\Users\Elton\Desktop\LazarusIA\scripts\python32\python.exe" "C:\Users\Elton\Desktop\LazarusIA\scripts\extrair.py"
        # Sem argumentos: extrai os PBLs da lista "pbls" do config.json (raiz).

    ...\extrair.py "F:\sdo\programa\elton.pbl"
        # Extrai tambem/apenas este PBL informado na linha de comando.

Saida:
    LazarusIA\codigo_fonte\<nome_da_pbl>\*.sr*
    LazarusIA\scripts\hashes.json   <- hash SHA-256 de cada objeto (chave = pbl\nome)
    LazarusIA\logs\<nome_da_pbl>.extracao.txt

O hashes.json gerado aqui eh consumido pelo compilar_patch.py para detectar
somente os objetos alterados desde a ultima extracao.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comum


def carregar_pbls(args):
    cfg = comum.carregar_config()
    if not args:
        return cfg.get('pbls', [])
    origem = cfg.get('origem', '')
    pbls = []
    for a in args:
        if os.path.isfile(a):
            pbls.append(a)
        elif comum.eh_nome_simples(a):
            nome = a if a.lower().endswith('.pbl') else a + '.pbl'
            candidato = comum.resolver(nome, origem)
            if os.path.isfile(candidato):
                pbls.append(candidato)
            else:
                print('ERRO: PBL "%s" nao encontrado na origem (%s).' % (nome, origem or 'config sem "origem"'))
                return []
    return pbls


def extrair_pbl(pbl):
    nome = os.path.splitext(os.path.basename(pbl))[0]
    destino = os.path.join(comum.CODIGO_FONTE, nome)
    os.makedirs(destino, exist_ok=True)
    os.makedirs(comum.LOGS, exist_ok=True)
    log = os.path.join(comum.LOGS, nome + '.extracao.txt')
    print('==> Extraindo [%s] -> %s' % (pbl, destino))
    proc = subprocess.run(
        [comum.PBLDUMP, '-es', pbl, '*.*'],
        cwd=destino,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    saida = proc.stdout.decode('latin-1', errors='replace')
    saida = saida.replace('\r\n', '\n').replace('\r', '\n')
    print(saida.strip())
    arquivos = [a for a in os.listdir(destino)
                if os.path.splitext(a)[1].lower() in comum.TIPOS]
    print('    Objetos de fonte extraidos: %d' % len(arquivos))

    com_hash = comum.atualizar_hashes_pbl(nome, destino)
    print('    Hashes atualizados em hashes.json: %d' % com_hash)

    with open(log, 'w', encoding='utf-8') as lf:
        lf.write('Log de extracao de %s  [%s]\n' % (pbl, comum.agora()))
        lf.write('Destino: %s\n' % destino)
        lf.write(saida)
        lf.write('\nObjetos de fonte extraidos: %d\n' % len(arquivos))
        lf.write('Hashes atualizados em hashes.json: %d\n' % com_hash)
        lf.write('Fim: [%s]\n' % comum.agora())
    return len(arquivos)


def main():
    if not os.path.isfile(comum.PBLDUMP):
        print('ERRO: PblDump.exe nao encontrado em', comum.PBLDUMP)
        return 1
    pbls = carregar_pbls(sys.argv[1:])
    if not pbls:
        print('Nenhum PBL informado. Edite config.json ou passe caminhos como argumento.')
        return 1
    os.makedirs(comum.CODIGO_FONTE, exist_ok=True)
    total = 0
    for pbl in pbls:
        total += extrair_pbl(pbl)
    print('\nExtracao concluida: %d objeto(s) em %d PBL(s).' % (total, len(pbls)))
    print('Baseline de hashes gravada em:', comum.HASHES)
    return 0


if __name__ == '__main__':
    sys.exit(main())
