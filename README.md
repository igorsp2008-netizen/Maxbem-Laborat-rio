# Maxbem Laboratório

Aplicativo local de controle laboratorial de mel, reescrito com Python, SQLite e uma interface web sem dependências remotas. Autenticação e permissões no servidor, senhas com hash, backup consistente, rastreabilidade e bloqueio de alterações após liberação.

## Mac — download e instalação

- [Apple Silicon: instalador com Python incluído](downloads/Maxbem_Mac_AppleSilicon_v2_2.zip) — macOS 11+, arm64.
- [Intel: instalador com Python incluído](downloads/Maxbem_Mac_Intel_v2_2.zip) — macOS 10.15+, x86_64.
- [Guia de instalação, ícone, dados e recuperação](docs/MAC.md).
- [Segurança e limites da versão Mac](docs/RELATORIO_MAC.md).

Extraia o ZIP e execute **Instalar Maxbem.command**. O aplicativo fica em `~/Applications/Maxbem Laboratório.app`, com ícone na Área de Trabalho. Não precisa instalar Python. O banco fica separado em `~/Library/Application Support/MaxbemLaboratorio/Dados`.

**A versão Mac não tem Developer ID/notarização e ainda precisa de homologação em Macs reais.** Os testes do servidor e do navegador foram executados no Linux. O guia explica as opções normais do Gatekeeper sem desativar proteções globais.

## Desenvolver e verificar

Use Python 3.12+. Não há dependências externas para o servidor:

```sh
cd app
python3 server.py
python3 -I -B -m unittest discover -s tests -v
```

O cadastro administrativo abre no primeiro uso; não existe senha padrão. Não compartilhe a URL temporária de abertura. O teste de navegador em `app/tests/browser_smoke.py` requer Playwright e Chromium, apenas para desenvolvimento.

Gerar pacotes Mac com os runtimes fixados e checksums verificados:

```sh
python3 tools/build_macos.py --arch all
```

Os arquivos necessários são baixados do projeto Astral via HTTPS para `.cache/runtimes`; o instalador entregue ao usuário já inclui tudo e não faz downloads. O ambiente de geração pode ser Linux; isso não substitui testar os binários em Macs reais. O logo é convertido em ícone `.icns` na instalação usando `sips/iconutil` do macOS.

## Histórico Windows

`packaging/windows` mantém os instaladores e a verificação da versão Windows com runtime interno. Os relatórios históricos em `docs` descrevem a revisão original. Esses scripts precisam do pacote Windows completo e seu runtime/manifesto; não devem ser executados isoladamente. Nenhum banco de usuário, credencial real ou capacidade temporária está no repositório.

O app não constitui validação científica/legal dos métodos do laboratório, assinatura digital ou garantia de ausência de vulnerabilidades. Compare dados migrados com a responsável técnica e teste backup e recuperação antes de produção.
