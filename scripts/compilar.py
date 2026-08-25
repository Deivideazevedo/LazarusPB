# -*- coding: latin-1 -*-
r"""Lazarus IA - Compilador de PBLs via API ORCA (pborc90.dll)

Recria um .pbl a partir dos .sr* extraidos, importando e compilando cada objeto
com o mesmo mecanismo do Library Painter do PowerBuilder.

IMPORTANTE: este script precisa do Python 32-bit para carregar pborc90.dll
(32 bits). Use o caminho completo do python32\python.exe.

Uso (o script deve ser chamado com o caminho COMPLETO, de qualquer pasta;
nao funciona rodar de outra pasta sem o caminho):

    "C:\Users\Elton\Desktop\LazarusIA\scripts\python32\python.exe" "C:\Users\Elton\Desktop\LazarusIA\scripts\compilar.py"
        # Sem argumentos: compila os PBLs da lista "pbls" do config.json (raiz).

    ...\python32\python.exe ...\scripts\compilar.py "F:\sdo\programa\deivide.pbl"
        # Compila APENAS este PBL (a origem e a pasta codigo_fonte\deivide).

    ...\python32\python.exe ...\scripts\compilar.py "F:\sdo\programa\a.pbl" "F:\sdo\programa\b.pbl"
        # Compila apenas estes dois, ignorando o config.json.

ATENCAO: a origem dos objetos eh SEMPRE a pasta codigo_fonte\<nome do pbl>.
O script NAO varre a pasta codigo_fonte por conta propria: quem define o que
compilar eh a lista de PBLs (config.json ou argumentos). Cada PBL usa somente
a propria pasta e gera seu proprio .pbl em compilacao\.

Saida:
    LazarusIA\compilacao\<nome_da_pbl>.pbl
    LazarusIA\logs\<nome_da_pbl>.import.txt
"""
import ctypes
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comum

BASE = comum.BASE
ROOT = comum.ROOT
CODIGO_FONTE = comum.CODIGO_FONTE
COMPILACAO = comum.COMPILACAO
LOGS = comum.LOGS
CONFIG = comum.CONFIG


def agora():
    return comum.agora()

DLL_PADRAO = r'C:\Program Files (x86)\Sybase\Shared\PowerBuilder\pborc90.dll'

# Mapeia extensao .sr* -> tipo ORCA (enum pborca_type)
TIPO = {
    '.sra': 0,    # APPLICATION
    '.srd': 1,    # DATAWINDOW
    '.srf': 2,    # FUNCTION
    '.srm': 3,    # MENU
    '.srq': 4,    # QUERY
    '.srs': 5,    # STRUCTURE
    '.sru': 6,    # USEROBJECT
    '.srw': 7,    # WINDOW
}
TIPO_BINARY = 11  # PBORCA_BINARY

# Ordem de importacao (maximiza resolucao de dependencias no 1o passe)
ORDEM = ['.sra', '.srs', '.srf', '.sru', '.srd', '.srq', '.srm', '.srw']

# Codigos de retorno ORCA
OK = 0
OBJEXISTS = -8

MARCADOR_BINARIO = b'Start of PowerBuilder Binary Data Section'


class COMPERR(ctypes.Structure):
    _fields_ = [
        ('iLevel', ctypes.c_int),
        ('lpszMessageNumber', ctypes.c_char_p),
        ('lpszMessageText', ctypes.c_char_p),
        ('iColumnNumber', ctypes.c_uint),
        ('iLineNumber', ctypes.c_uint),
    ]


ERRCALLBACK = ctypes.WINFUNCTYPE(None, ctypes.POINTER(COMPERR), ctypes.c_void_p)


class OrcaSession(object):
    def __init__(self, dll_path):
        self.dll = ctypes.WinDLL(dll_path)
        self.h = None
        self._definir_prototypes()

    def _definir_prototypes(self):
        d = self.dll
        d.PBORCA_SessionOpen.restype = ctypes.c_void_p
        d.PBORCA_SessionClose.argtypes = [ctypes.c_void_p]
        d.PBORCA_SessionClose.restype = None
        d.PBORCA_SessionSetLibraryList.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p), ctypes.c_int]
        d.PBORCA_SessionSetLibraryList.restype = ctypes.c_int
        d.PBORCA_SessionSetCurrentAppl.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
        d.PBORCA_SessionSetCurrentAppl.restype = ctypes.c_int
        d.PBORCA_LibraryCreate.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
        d.PBORCA_LibraryCreate.restype = ctypes.c_int
        d.PBORCA_LibraryDelete.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        d.PBORCA_LibraryDelete.restype = ctypes.c_int
        d.PBORCA_CompileEntryImport.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int,
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_long,
            ERRCALLBACK, ctypes.c_void_p]
        d.PBORCA_CompileEntryImport.restype = ctypes.c_int

    def abrir(self):
        self.h = self.dll.PBORCA_SessionOpen()
        return self.h is not None

    def fechar(self):
        if self.h:
            self.dll.PBORCA_SessionClose(self.h)
            self.h = None

    def set_library_list(self, libs):
        arr = (ctypes.c_char_p * len(libs))(
            *[l.encode('latin-1') for l in libs])
        return self.dll.PBORCA_SessionSetLibraryList(self.h, arr, len(libs))

    def set_current_appl(self, app_lib, app_name):
        return self.dll.PBORCA_SessionSetCurrentAppl(
            self.h, app_lib.encode('latin-1'), app_name.encode('latin-1'))

    def criar_biblioteca(self, caminho, comentario=b'Lazarus IA'):
        rc = self.dll.PBORCA_LibraryDelete(self.h, caminho.encode('latin-1'))
        rc = self.dll.PBORCA_LibraryCreate(
            self.h, caminho.encode('latin-1'), comentario)
        return rc

    def importar(self, biblioteca, entry_name, tipo, sintaxe, comentario=b''):
        """Retorna (rc, erros). rc=0 sucesso; rc=OBJEXISTS ja existe."""
        erros = []

        def _onerror(comperr, userdata):
            if comperr:
                c = comperr.contents
                erros.append((c.iLevel, c.lpszMessageNumber,
                              c.lpszMessageText, c.iLineNumber))

        cb = ERRCALLBACK(_onerror)
        rc = self.dll.PBORCA_CompileEntryImport(
            self.h, biblioteca.encode('latin-1'), entry_name.encode('latin-1'),
            tipo, comentario, sintaxe, len(sintaxe), cb, None)
        return rc, erros


def carregar_config(args):
    cfg = comum.carregar_config()
    origem = cfg.get('origem', '')
    # Nome simples ("deivide" / "deivide.pbl") vira forma canonica:
    # a compilacao so deriva o nome — nao le a origem.
    pbls = [a if os.path.isfile(a) or not comum.eh_nome_simples(a)
            else (a if a.lower().endswith('.pbl') else a + '.pbl')
            for a in args]
    if not pbls:
        pbls = cfg.get('pbls', [])
    return (pbls, cfg.get('lib_list', []), cfg.get('app_name', ''),
            cfg.get('app_lib', ''), cfg.get('orca_dll', DLL_PADRAO))


def arquivos_fonte(dir_src):
    arquivos = []
    for raiz, _, fnames in os.walk(dir_src):
        for f in fnames:
            ext = os.path.splitext(f)[1].lower()
            if ext in TIPO:
                arquivos.append(os.path.join(raiz, f))
    arquivos.sort(key=lambda p: (
        ORDEM.index(os.path.splitext(p)[1].lower()),
        os.path.basename(p).lower()))
    return arquivos


def extrair_comentario(sintaxe):
    """Le a linha '$PBExportComments$...' do arquivo exportado (se houver)."""
    for linha in sintaxe.split(b'\n'):
        if linha.startswith(b'$PBExportComments$'):
            return linha[len(b'$PBExportComments$'):].rstrip(b'\r')
    return b''


def compilar_pbl(sess, pbl, lib_list, app_name, app_lib):
    nome = os.path.splitext(os.path.basename(pbl))[0]
    dir_src = os.path.join(CODIGO_FONTE, nome)
    out_pbl = os.path.join(COMPILACAO, nome + '.pbl')
    log = os.path.join(LOGS, nome + '.import.txt')
    os.makedirs(COMPILACAO, exist_ok=True)
    os.makedirs(LOGS, exist_ok=True)

    if not os.path.isdir(dir_src):
        print('!! Pasta de fonte nao encontrada:', dir_src)
        print('   Rode antes o extrair.py para este PBL.')
        return 1

    with open(log, 'w', encoding='utf-8') as lf:
        lf.write('Log de importacao de %s  [%s]\n' % (pbl, agora()))

        rc = sess.criar_biblioteca(out_pbl)
        lf.write('Criar biblioteca %s -> rc=%d\n' % (out_pbl, rc))
        print('==> Criando biblioteca %s (rc=%d)' % (out_pbl, rc))

        libs = []
        for lib in [out_pbl, pbl] + lib_list:
            if os.path.isfile(lib) and lib not in libs:
                libs.append(lib)
        if os.path.isfile(pbl) and pbl not in libs:
            libs.insert(1, pbl)
        rc = sess.set_library_list(libs)
        lf.write('Library list (%d) -> rc=%d\n' % (len(libs), rc))
        if rc != OK:
            print('!! Falha ao definir library list (rc=%d)' % rc)
            return 1

        if app_name and app_lib:
            rc = sess.set_current_appl(app_lib, app_name)
            lf.write('Application atual (%s em %s) -> rc=%d\n'
                     % (app_name, app_lib, rc))
            if rc != OK:
                print('!! Falha ao definir application atual (rc=%d)' % rc)
                return 1
        else:
            print('!! ATENCAO: sem application object no config.json.')
            print('   O ORCA exige um application; defina app_name/app_lib.')
            return 1

        pendentes = arquivos_fonte(dir_src)
        ok, falhas = [], []
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

                # Separa secao binaria (OLE etc), se existir
                marca = sintaxe.find(MARCADOR_BINARIO)
                if marca >= 0:
                    parte_fonte = sintaxe[:marca]
                    parte_bin = sintaxe[marca:]
                else:
                    parte_fonte = sintaxe
                    parte_bin = None

                comentario = extrair_comentario(parte_fonte)

                rc1, erros = sess.importar(
                    out_pbl, entry, TIPO[ext], parte_fonte, comentario)
                rc2 = OK
                if parte_bin is not None and rc1 == OK:
                    rc2, _ = sess.importar(
                        out_pbl, entry, TIPO_BINARY, parte_bin)

                if rc1 == OK and rc2 == OK:
                    ok.append(basename)
                    lf.write('OK   %s\n' % basename)
                    print('  OK  %s' % basename)
                elif rc1 == OBJEXISTS:
                    ok.append(basename)
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

        if pendentes:
            resultado = 'FALHOU (%d objeto(s) nao importado(s))' % len(pendentes)
            print('\n==> %d objeto(s) NAO importado(s):' % len(pendentes))
            for p in pendentes:
                print('    -', os.path.basename(p))
            lf.write('NAO IMPORTADOS: %s\n'
                     % ', '.join(os.path.basename(p) for p in pendentes))
        else:
            resultado = 'SUCESSO (%d objeto(s))' % len(ok)
            print('\n==> Todos os %d objetos foram importados/compilados.' % len(ok))
        lf.write('\nFim: %s  [%s]\n' % (resultado, agora()))
        return 0 if not pendentes else 2


def main():
    argv = [a for a in sys.argv[1:]
            if a not in ('--ignorar-checagem', '--ignorar-checagem-fontes')]
    pular_checagem = len(argv) != len(sys.argv) - 1
    pbls, lib_list, app_name, app_lib, orca_dll = carregar_config(argv)

    import checar_fontes
    if not pular_checagem:
        print('== Checando integridade dos fontes (encoding/acentos)...')
        erros, _ = checar_fontes.verificar(
            [os.path.basename(p) for p in pbls])
        if erros:
            print('')
            print('!! COMPILACAO BLOQUEADA: fontes com possivel perda de')
            print('   acentos/encoding. Corrija os pontos acima ou, se for')
            print('   falso positivo, rode com --ignorar-checagem.')
            return 1

    invalidos = [p for p in pbls
                 if not (os.path.isfile(p) or comum.eh_nome_simples(p))]
    if invalidos:
        print('AVISO: caminho nao encontrado, ignorado:', ', '.join(invalidos))
    pbls = [p for p in pbls
            if os.path.isfile(p) or comum.eh_nome_simples(p)]
    if not pbls:
        print('Nenhum PBL informado. Edite config.json ou passe nomes/caminhos.')
        return 1
    if not os.path.isfile(orca_dll):
        print('ERRO: pborc90.dll nao encontrado em', orca_dll)
        return 1

    sess = OrcaSession(orca_dll)
    if not sess.abrir():
        print('ERRO: nao foi possivel abrir sessao ORCA.')
        return 1
    try:
        for pbl in pbls:
            compilar_pbl(sess, pbl, lib_list, app_name, app_lib)
    finally:
        sess.fechar()
    return 0


if __name__ == '__main__':
    sys.exit(main())
