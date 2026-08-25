# -*- coding: latin-1 -*-
r"""Lazarus IA - Rotinas comuns (caminhos, config, hash).

O config.json fica na RAIZ do Lazarus IA (fora de scripts\) e aceita uma
variavel "origem": todo caminho informado como nome simples (sem drive)
eh resolvido automaticamente contra essa pasta. Caminhos absolutos
(com drive, ex.: F:\ni_pfc\ni_pfc_base.pbl) sao usados como vieram.

A "lib_list" aceita ainda uma segunda pasta-base, "origem_pfc" (onde ficam
as bibliotecas PFC): nomes simples sao procurados primeiro em "origem" e,
se nao existirem la, em "origem_pfc". Isso permite listar as PFC so pelo
nome, sem repetir o caminho completo.
"""
import datetime
import hashlib
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
CODIGO_FONTE = os.path.join(ROOT, 'codigo_fonte')
COMPILACAO = os.path.join(ROOT, 'compilacao')
LOGS = os.path.join(ROOT, 'logs')
PBLDUMP = os.path.join(BASE, 'pbldump', 'PblDump.exe')
CONFIG = os.path.join(ROOT, 'config.json')
HASHES = os.path.join(BASE, 'hashes.json')

TIPOS = ('.sra', '.srd', '.srf', '.srm', '.srq', '.srs', '.sru', '.srw')


def agora():
    return datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')


def resolver(caminho, origem):
    """Resolve nome simples contra a pasta origem; absoluto passa direto."""
    if not caminho:
        return caminho
    if os.path.isabs(caminho):
        return caminho
    return os.path.join(origem, caminho) if origem else caminho


def eh_nome_simples(caminho):
    """True se o argumento e so um nome ('deivide' ou 'deivide.pbl'),
    sem pasta/drive — pode ser resolvido contra a "origem" do config."""
    if not caminho or os.path.isabs(caminho):
        return False
    return not any(s in caminho for s in (os.sep, '/', ':'))


def resolver_lib(caminho, origem, origem_pfc):
    """Resolve nome da lib_list: tenta "origem" e depois "origem_pfc".

    Caminho absoluto passa direto. Se o nome nao existir em nenhuma das
    duas pastas, cai em "origem" (comportamento anterior ao origem_pfc).
    """
    if not caminho or os.path.isabs(caminho):
        return resolver(caminho, origem)
    for base in (origem, origem_pfc):
        if base:
            candidato = os.path.join(base, caminho)
            if os.path.isfile(candidato):
                return candidato
    return resolver(caminho, origem)


def carregar_config():
    """Le config.json da raiz e devolve os caminhos ja resolvidos."""
    cfg = {}
    if os.path.isfile(CONFIG):
        with open(CONFIG, 'r', encoding='utf-8') as fh:
            cfg = json.load(fh)
    origem = cfg.get('origem', '')
    origem_pfc = cfg.get('origem_pfc', '')
    cfg['origem'] = origem
    cfg['origem_pfc'] = origem_pfc
    cfg['pbls'] = [resolver_lib(p, origem, origem_pfc) for p in cfg.get('pbls', [])]
    cfg['lib_list'] = [resolver_lib(p, origem, origem_pfc)
                       for p in cfg.get('lib_list', [])]
    cfg['app_lib'] = resolver(cfg.get('app_lib', ''), origem)
    return cfg


def hash_arquivo(caminho):
    """SHA-256 do arquivo, lido em blocos (serve para arquivos grandes)."""
    h = hashlib.sha256()
    with open(caminho, 'rb') as fh:
        for bloco in iter(lambda: fh.read(65536), b''):
            h.update(bloco)
    return h.hexdigest()


def carregar_hashes():
    """Le hashes.json ({'gerado_em': ..., 'objetos': {nome: {...}}})."""
    if not os.path.isfile(HASHES):
        return {'gerado_em': '', 'objetos': {}}
    with open(HASHES, 'r', encoding='utf-8') as fh:
        dados = json.load(fh)
    if not isinstance(dados, dict) or not isinstance(dados.get('objetos'), dict):
        return {'gerado_em': '', 'objetos': {}}
    return dados


def salvar_hashes(dados):
    with open(HASHES, 'w', encoding='utf-8') as fh:
        json.dump(dados, fh, indent=2, sort_keys=True)
        fh.write('\n')


def atualizar_hashes_pbl(nome_pbl, pasta_fonte):
    r"""Recria no hashes.json as entradas dos objetos extraidos de um PBL.

    A chave eh o caminho relativo "pbl\nome.ext" (ex.: sdo01\w_ope_hec.srw),
    pois o mesmo nome pode existir em PBLs diferentes; o valor guarda o
    SHA-256 e o PBL de origem. Entradas antigas desse mesmo PBL que nao
    existem mais na pasta sao removidas.
    """
    dados = carregar_hashes()
    objetos = dados['objetos']
    atuais = {}
    for f in sorted(os.listdir(pasta_fonte)):
        if os.path.splitext(f)[1].lower() not in TIPOS:
            continue
        caminho = os.path.join(pasta_fonte, f)
        if not os.path.isfile(caminho):
            continue
        chave = os.path.join(nome_pbl, f)
        atuais[chave] = {'hash': hash_arquivo(caminho), 'pbl': nome_pbl}
    for chave in [k for k, v in objetos.items() if v.get('pbl') == nome_pbl]:
        if chave not in atuais:
            del objetos[chave]
    objetos.update(atuais)
    dados['gerado_em'] = agora()
    salvar_hashes(dados)
    return len(atuais)
