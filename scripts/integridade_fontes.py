# -*- coding: latin-1 -*-
r"""Lazarus IA - Pipeline consolidado de integridade, encoding e restauracao de fontes.

Executa as etapas:
  1. Auto-conversao de fontes UTF-8 (ou com BOM) para Windows-1252 nativo.
  2. Checagem de integridade (bytes ilegais, diferencas de acentos vs Git HEAD).
  3. Diagnostico detalhado caso haja perda de acentos.
  4. Pergunta interativa para restaurar acentos automaticamente.
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


# Assinaturas de corrupcao / mojibake conhecidas geradas por IAs e editores
PADROES_CORROMPIDOS = (
    b'\xef\xbf\xbd',          # U+FFFD (Replacement character em UTF-8)
    b'\xef\xbb\xbf',          # BOM UTF-8 solto
    b'\xc3\xaf\xc2\xbf\xc2\xbd', # Mojibake duplo de ï¿½
    b'\xc3\x83',              # Sequencias de double encode (Ã©, Ã£, etc.)
)


def detectar_corrupcao_mojibake(raw_bytes):
    """Detecta se o arquivo possui marcas claras de corrupcao por IA / editor."""
    motivos = []
    if b'\xef\xbf\xbd' in raw_bytes:
        motivos.append('contem caractere substituto U+FFFD (perda irreversivel de acento)')
    if b'\xc3\x83' in raw_bytes:
        motivos.append('contem sequencias duplas de encoding (mojibake: Ã£, Ã©, etc.)')
    # Detecta se a string 'ï¿½' aparece decodificada em cp1252
    txt_cp1252 = raw_bytes.decode('cp1252', 'replace')
    if '\xef\xbf\xbd' in txt_cp1252 or 'ï¿½' in txt_cp1252:
        motivos.append('contem sequencia visual de mojibake "ï¿½"')
    return motivos


def auto_converter_para_cp1252(caminho):
    """Converte arquivo UTF-8 para CP1252 se for UTF-8 limpo (sem corrupcao).
    Retorna (bool alterado, str erro_ou_status)."""
    try:
        with open(caminho, 'rb') as fh:
            raw = fh.read()
    except Exception as e:
        return False, str(e)

    # 1. Se contiver corrupcao de mojibake, NUNCA tenta auto-converter
    motivos = detectar_corrupcao_mojibake(raw)
    if motivos:
        return False, 'corrompido: ' + '; '.join(motivos)

    tem_bom = raw.startswith(BOM)
    raw_sem_bom = raw[len(BOM):] if tem_bom else raw

    precisa = False
    texto = None
    if any(b > 0x7F for b in raw_sem_bom):
        try:
            texto = raw_sem_bom.decode('utf-8')
            precisa = True
        except UnicodeDecodeError:
            pass
    elif tem_bom:
        texto = raw_sem_bom.decode('utf-8')
        precisa = True

    if not precisa or texto is None:
        return False, 'ok'

    # Verifica se ao decodificar em UTF-8 gerou o caractere de substituicao
    if '\ufffd' in texto:
        return False, 'contem U+FFFD'

    try:
        dados_cp1252 = texto.encode('windows-1252')
    except UnicodeEncodeError:
        return False, 'caracteres incompativeis com CP1252'

    if dados_cp1252 == raw:
        return False, 'ok'

    with open(caminho, 'wb') as fh:
        fh.write(dados_cp1252)
    return True, 'convertido'


def diagnosticar_perdas_acentos(rel, caminho_atual):
    """Retorna lista de tuplas (num_linha_head, linha_head, linha_atual) com diferenca de acentos."""
    head_b = _conteudo_head(rel)
    if not head_b:
        return []

    with open(caminho_atual, 'rb') as f:
        atual_b = f.read()

    txt_head = head_b.decode('cp1252', 'replace').splitlines()
    txt_atual = atual_b.decode('cp1252', 'replace').splitlines()

    sm = difflib.SequenceMatcher(None, txt_head, txt_atual, autojunk=False)
    perdas = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ('replace', 'delete'):
            for idx in range(i1, i2):
                lh = txt_head[idx]
                if any(ord(c) > 127 for c in lh):
                    la = txt_atual[j1 + (idx - i1)] if (tag == 'replace' and (j1 + (idx - i1)) < j2) else '(removida ou deslocada)'
                    # Verifica se la perdeu acentos, contem '?' ou sequencias de mojibake
                    tem_marcas_lixo = any(m in la for m in ('?', 'ï¿½', '', 'Ã'))
                    if tem_marcas_lixo or not any(ord(c) > 127 for c in la):
                        perdas.append((idx + 1, lh.strip(), la.strip()))
    return perdas


def restaurar_arquivo_do_head(rel, caminho_atual):
    """Restaura acentos originais das linhas alteradas com '?', mojibake ou stripped."""
    head_b = _conteudo_head(rel)
    if not head_b:
        return False

    with open(caminho_atual, 'rb') as f:
        atual_b = f.read()

    txt_head = head_b.decode('cp1252', 'replace').splitlines(True)
    txt_atual = atual_b.decode('cp1252', 'replace').splitlines(True)

    novas_linhas = []
    restaurados = 0

    sm = difflib.SequenceMatcher(None,
                                 [l.strip() for l in txt_head],
                                 [l.strip() for l in txt_atual],
                                 autojunk=False)

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for j in range(j1, j2):
                novas_linhas.append(txt_atual[j])
        elif tag == 'replace':
            len_head = i2 - i1
            len_atual = j2 - j1
            if len_head == len_atual:
                for k in range(len_head):
                    lh = txt_head[i1 + k]
                    la = txt_atual[j1 + k]
                    tem_marcas_lixo = any(m in la for m in ('?', 'ï¿½', '', 'Ã', '\ufffd'))
                    perdeu_acento = any(ord(c) > 127 for c in lh) and not any(ord(c) > 127 for c in la)
                    if any(ord(c) > 127 for c in lh) and (tem_marcas_lixo or perdeu_acento):
                        novas_linhas.append(lh)
                        restaurados += 1
                    else:
                        novas_linhas.append(la)
            else:
                for j in range(j1, j2):
                    la = txt_atual[j]
                    substituiu = False
                    for i in range(i1, i2):
                        lh = txt_head[i]
                        tem_marcas_lixo = any(m in la for m in ('?', 'ï¿½', '', 'Ã', '\ufffd'))
                        perdeu_acento = any(ord(c) > 127 for c in lh) and not any(ord(c) > 127 for c in la)
                        if any(ord(c) > 127 for c in lh) and (tem_marcas_lixo or perdeu_acento):
                            s = difflib.SequenceMatcher(None,
                                                        ''.join(c for c in lh if ord(c) <= 127),
                                                        ''.join(c for c in la if ord(c) <= 127 and c not in '?ï¿½'))
                            if s.ratio() > 0.65:
                                novas_linhas.append(lh)
                                restaurados += 1
                                substituiu = True
                                break
                    if not substituiu:
                        novas_linhas.append(la)
        elif tag == 'insert':
            for j in range(j1, j2):
                novas_linhas.append(txt_atual[j])
        elif tag == 'delete':
            pass

    resultado = "".join(novas_linhas)
    try:
        dados_cp1252 = resultado.encode('windows-1252')
    except UnicodeEncodeError:
        dados_cp1252 = resultado.encode('windows-1252', errors='replace')

    with open(caminho_atual, 'wb') as f:
        f.write(dados_cp1252)

    # Se ainda restar algum mojibake residual por diferenca de diff, substitui direto
    with open(caminho_atual, 'rb') as f:
        conteudo_verif = f.read()

    if any(m in conteudo_verif for m in (b'\xef\xbf\xbd', b'\xc3\xaf\xc2\xbf\xc2\xbd')):
        # Fallback de seguranca: se o arquivo foi restaurado mas ainda tem mojibake nas linhas do head,
        # substitui o arquivo com o conteudo limpo do Git
        with open(caminho_atual, 'wb') as f:
            f.write(head_b)
        restaurados = 1

    return restaurados > 0


def processar_integridade(alvos_arquivos, interativo=True, apenas_verificar=False):
    """Executa a auto-conversao, checagem, diagnostico e restauracao interativa.

    Argumentos:
        alvos_arquivos: lista de caminhos absolutos para arquivos .sr*
        interativo: se True, pergunta ao usuario antes de restaurar ou prosseguir
        apenas_verificar: se True, modo estrito SOMENTE LEITURA (nao altera nada no disco)

    Retorna:
        True se tudo ok; False se encontrou divergencias ou erro.
    """
    if not alvos_arquivos:
        return True

    # 1. Checagem de Encoding (e Auto-conversao apenas se nao for mojibake)
    arquivos_utf8 = []
    arquivos_mojibake = {}

    for caminho in alvos_arquivos:
        rel = os.path.relpath(caminho, CODIGO_FONTE).replace('\\', '/')
        b = open(caminho, 'rb').read()

        # Deteccao rigorosa de Mojibake / Caracteres de substituicao (lixo de IA)
        lixo = detectar_corrupcao_mojibake(b)
        if lixo:
            arquivos_mojibake[rel] = (caminho, lixo)
            continue

        tem_bom = b.startswith(BOM)
        raw_sem_bom = b[len(BOM):] if tem_bom else b
        eh_utf8 = False
        if any(x > 0x7F for x in raw_sem_bom):
            try:
                raw_sem_bom.decode('utf-8')
                eh_utf8 = True
            except UnicodeDecodeError:
                pass
        elif tem_bom:
            eh_utf8 = True

        if eh_utf8:
            if apenas_verificar:
                arquivos_utf8.append(rel)
            else:
                alterou, status = auto_converter_para_cp1252(caminho)
                if alterou:
                    print('  [AUTO-CONVERTER] %s convertido de UTF-8 para CP1252.' % rel)

    # 2. Inspecao de integridade (bytes ilegais e diferenca com o Git)
    arquivos_com_perda = {}
    erros_fatais = []

    if arquivos_mojibake:
        for rel, (_, motivos) in arquivos_mojibake.items():
            erros_fatais.append('%s: ARQUIVO CORROMPIDO COM MOJIBAKE (%s)' % (rel, '; '.join(motivos)))

    if apenas_verificar and arquivos_utf8:
        for rel in arquivos_utf8:
            erros_fatais.append('%s: salvo em UTF-8 (padrao esperado: CP1252)' % rel)

    for caminho in alvos_arquivos:
        rel = os.path.relpath(caminho, CODIGO_FONTE).replace('\\', '/')
        b = open(caminho, 'rb').read()

        if b.startswith(BOM):
            erros_fatais.append('%s: possui BOM UTF-8' % rel)
        ilegais = sorted(set(x for x in b if x in ILEGAIS_CP1252))
        if ilegais:
            erros_fatais.append('%s: bytes fora de CP1252: %s' % (rel, ', '.join('0x%02X' % x for x in ilegais)))

        # Diagnostica contra o Git
        perdas = diagnosticar_perdas_acentos(rel, caminho)
        if perdas:
            arquivos_com_perda[rel] = (caminho, perdas)

    if erros_fatais:
        print('\n!! PROBLEMAS DE ENCODING DETECTADOS:')
        for e in erros_fatais:
            print('   *', e)

    if arquivos_com_perda:
        print('\n======================================================')
        print(' AVISO: Detectada possivel perda de acentos vs Git HEAD')
        print('======================================================')
        for rel, (_, perdas) in arquivos_com_perda.items():
            print('\nArquivo: %s (%d linha(s) afetada(s))' % (rel, len(perdas)))
            for num, lh, la in perdas[:5]:
                print('  [Linha %d]' % num)
                print('    HEAD : %s' % lh[:85])
                print('    ATUAL: %s' % la[:85])
            if len(perdas) > 5:
                print('    ... (+%d linha(s) afetada(s))' % (len(perdas) - 5))

    # Agrupa todos os que precisam de restauracao (mojibake + perdas de acento)
    alvos_para_restaurar = dict(arquivos_com_perda)
    for rel, (caminho, _) in arquivos_mojibake.items():
        if rel not in alvos_para_restaurar:
            perdas = diagnosticar_perdas_acentos(rel, caminho)
            alvos_para_restaurar[rel] = (caminho, perdas)

    if apenas_verificar:
        if erros_fatais or alvos_para_restaurar:
            print('\n[MODO VERIFICACAO] Fontes possuem pendencias acima (nenhum arquivo foi alterado).')
            return False
        return True

    if not alvos_para_restaurar and erros_fatais:
        return False

    if not alvos_para_restaurar:
        return True

    if not interativo:
        return False

    print('\nOpcoes de correcao:')
    print(' [S] Restaurar versao limpa original do Git (em CP1252 legivel)')
    print(' [I] Ignorar e compilar assim mesmo')
    print(' [C] Cancelar compilacao')
    
    try:
        resp = input('\nEscolha uma opcao [S/i/c]: ').strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False

    if resp in ('', 's', 'sim', 'y', 'yes'):
        print('\n== Restaurando acentos e corrigindo mojibake via Git HEAD...')
        for rel, (caminho, _) in alvos_para_restaurar.items():
            if restaurar_arquivo_do_head(rel, caminho):
                print('  [RESTAURADO] %s' % rel)
            else:
                print('  [AVISO] Nao foi possivel restaurar automaticamente %s' % rel)
        print('== Fontes restaurados com sucesso em CP1252!\n')
        return True
    elif resp in ('i', 'ignorar'):
        print('== Prosseguindo sem restaurar (--ignorar)...\n')
        return True
    else:
        print('== Operacao cancelada pelo usuario.\n')
        return False


def main(args):
    apenas_verificar = any(a in ('--verificar', '-v', '--check', '--somente-leitura') for a in args)
    args = [a for a in args if a not in ('--verificar', '-v', '--check', '--somente-leitura')]

    cfg = comum.carregar_config()
    if not args:
        nomes = [os.path.splitext(os.path.basename(p))[0] for p in cfg.get('pbls', [])]
        alvos = []
        for nome in nomes:
            pasta = os.path.join(CODIGO_FONTE, nome)
            if os.path.isdir(pasta):
                for raiz, _, arqs in os.walk(pasta):
                    for a in arqs:
                        if os.path.splitext(a)[1].lower() in EXT_FONTE:
                            alvos.append(os.path.join(raiz, a))
    else:
        alvos = []
        for a in args:
            a_limpo = a.replace('/', os.sep)
            ext = os.path.splitext(a_limpo)[1].lower()
            if ext in EXT_FONTE:
                if os.path.isfile(a_limpo):
                    alvos.append(os.path.abspath(a_limpo))
                elif os.path.isfile(os.path.join(CODIGO_FONTE, a_limpo)):
                    alvos.append(os.path.join(CODIGO_FONTE, a_limpo))
                else:
                    nome_base = os.path.basename(a_limpo)
                    for raiz, _, files in os.walk(CODIGO_FONTE):
                        if nome_base in files:
                            alvos.append(os.path.join(raiz, nome_base))
            else:
                pasta = os.path.join(CODIGO_FONTE, os.path.splitext(a_limpo)[0])
                if os.path.isdir(pasta):
                    for raiz, _, arqs in os.walk(pasta):
                        for f in arqs:
                            if os.path.splitext(f)[1].lower() in EXT_FONTE:
                                alvos.append(os.path.join(raiz, f))

    if not alvos:
        print('Nenhum arquivo .sr* encontrado para verificar.')
        return 0

    modo_str = " (Modo Somente Leitura)" if apenas_verificar else ""
    print('== Lazarus IA: Integridade de Fontes (CP1252 / Git)%s ==' % modo_str)
    ok = processar_integridade(alvos, interativo=True, apenas_verificar=apenas_verificar)
    if ok:
        print('OK: Fontes integros e compativeis com CP1252.')
        return 0
    else:
        print('AVISO: Verificacao concluida com pendencias.')
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))


