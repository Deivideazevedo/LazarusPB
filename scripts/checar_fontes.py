# -*- coding: latin-1 -*-
r"""Lazarus IA - Checador de integridade dos fontes .sr*

Os fontes .sr* sao ANSI/Windows-1252 (padrao do PowerBuilder 9). Uma sessao
de edicao que os leia como UTF-8/ASCII e grave de volta DELETA todo caractere
acentuado ("Observacao" vira "Observao") sem deixar nenhum byte invalido -
o arquivo corrompido decoda limpo em qualquer encoding. Por isso a checagem
tem duas camadas:

  A) ENCODING - BOM UTF-8, bytes fora da tabela cp1252 ou conteudo que
                so decoda como UTF-8 (re-encode).
  B) GIT      - compara com a versao no HEAD: linha que tinha acentos e
                voltou sem nenhum = strip na edicao. Nao cobre arquivo
                novo/nao versionado (sem baseline no git).

Uso (chame sempre com o caminho completo):

    "...\python32\python.exe" "...\checar_fontes.py" [nome_pbl ...]
        # Checa codigo_fonte\<pbl>\ dos PBLs indicados (ou todos do config).

Retorna rc=0 se nao ha erros bloqueantes; rc=1 caso contrario.
compilar.py roda esta checagem automaticamente antes de importar qualquer
objeto; para forcar a compilacao mesmo assim use --ignorar-checagem.
"""
import difflib
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comum

CODIGO_FONTE = comum.CODIGO_FONTE

BOM = b'\xef\xbb\xbf'
ILEGAIS_CP1252 = {0x81, 0x8D, 0x8F, 0x90, 0x9D}
EXT_FONTE = ('.sra', '.srd', '.srf', '.srm', '.srq', '.srs', '.sru', '.srw')


def _alto(b):
    return sum(1 for x in b if x > 0x7F)


# --------------------------------------------------------------- camada A
def checar_encoding(caminho):
    b = open(caminho, 'rb').read()
    erros = []
    if b.startswith(BOM):
        erros.append('possui BOM UTF-8')
    ilegais = sorted(set(x for x in b if x in ILEGAIS_CP1252))
    if ilegais:
        erros.append('bytes fora da tabela cp1252: '
                     + ', '.join('0x%02X' % x for x in ilegais))
    if any(x > 0x7F for x in b):
        try:
            b.decode('utf-8')
            erros.append('conteudo decoda como UTF-8 mas o padrao do projeto '
                         'e cp1252 (possivel re-encode)')
        except UnicodeDecodeError:
            pass
    return erros


# --------------------------------------------------------------- camada B
def _git(args):
    return subprocess.run(['git', '-C', CODIGO_FONTE] + args,
                          capture_output=True)


def _conteudo_head(rel):
    r = _git(['show', 'HEAD:' + rel])
    return r.stdout if r.returncode == 0 else None


def _linhas_alto(conteudo):
    txt = conteudo.decode('cp1252', 'replace')
    return [(i, ln, _alto(ln.encode('cp1252', 'replace')))
            for i, ln in enumerate(txt.splitlines(), 1)]


def checar_git(rel, novo_b):
    """Compara com HEAD. Retorna (erros, avisos)."""
    velho_b = _conteudo_head(rel)
    if velho_b is None:
        return [], []
    erros, avisos = [], []
    velho = _linhas_alto(velho_b)
    novo = _linhas_alto(novo_b)
    tot_v = sum(x[2] for x in velho)
    tot_n = sum(x[2] for x in novo)
    if tot_v > 0 and tot_n == 0:
        erros.append('arquivo tinha %d byte(s) acentuado(s) no HEAD e ficou '
                     '100%% sem acentos (strip na edicao)' % tot_v)
        return erros, avisos
    sm = difflib.SequenceMatcher(None,
                                 [x[1] for x in velho],
                                 [x[1] for x in novo], autojunk=False)
    exemplos = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag not in ('replace',):
            continue
        for k in range(min(i2 - i1, j2 - j1)):
            _, lo, av = velho[i1 + k]
            _, ln, nv = novo[j1 + k]
            if av > 0 and nv == 0:
                razao = difflib.SequenceMatcher(None, lo, ln).ratio()
                if razao >= 0.5:
                    exemplos.append((lo[:70], ln[:70]))
    if exemplos:
        avisos.append('%d linha(s) aparentam ter perdido acentos na edicao; '
                      'exemplos:' % len(exemplos))
        for lo, ln in exemplos[:5]:
            avisos.append('   HEAD : %s' % lo)
            avisos.append('   atual: %s' % ln)
    return erros, avisos


# ------------------------------------------------------------------ nucleo
def pastas_dos_pbls(pbls):
    cfg = comum.carregar_config()
    nomes = [os.path.splitext(os.path.basename(p))[0] for p in pbls]
    if not nomes:
        nomes = [os.path.splitext(os.path.basename(p))[0]
                 for p in cfg.get('pbls', [])]
    return nomes


def verificar(pbls=None, verbose=True):
    """Roda as camadas A e B nas pastas indicadas.
    Retorna (erros, avisos); erros bloqueiam a compilacao."""
    nomes = pastas_dos_pbls(pbls or [])
    erros, avisos = [], []
    for nome in nomes:
        pasta = os.path.join(CODIGO_FONTE, nome)
        if not os.path.isdir(pasta):
            continue
        alvos = []
        for raiz, _, arqs in os.walk(pasta):
            for a in arqs:
                if os.path.splitext(a)[1].lower() in EXT_FONTE:
                    rel = os.path.relpath(os.path.join(raiz, a),
                                          CODIGO_FONTE).replace('\\', '/')
                    alvos.append((rel, os.path.join(raiz, a)))
        for rel, caminho in sorted(alvos):
            for e in checar_encoding(caminho):
                erros.append('[A] %s: %s' % (rel, e))
            eb, ab = checar_git(rel, open(caminho, 'rb').read())
            for e in eb:
                erros.append('[B] %s: %s' % (rel, e))
            for a in ab:
                avisos.append('[B] %s: %s' % (rel, a))
    if verbose:
        vistos, unicos = set(), []
        for a in avisos:
            if a not in vistos:
                vistos.add(a)
                unicos.append(a)
        for a in unicos[:30]:
            print('AVISO %s' % a)
        if len(unicos) > 30:
            print('AVISO ... (+%d aviso(s) demais)' % (len(unicos) - 30))
        for e in erros:
            print('ERRO  %s' % e)
        if not erros and not unicos:
            print('OK: nenhum problema de encoding/acento detectado.')
        else:
            print('== resumo: %d erro(s) bloqueante(s), %d aviso(s)'
                  % (len(erros), len(unicos)))
    return erros, avisos


def main(argv):
    erros, _ = verificar(argv, verbose=True)
    return 1 if erros else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
