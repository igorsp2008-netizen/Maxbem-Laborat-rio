# Maxbem Laboratório

Aplicativo local de controle laboratorial de mel, reescrito com Python, SQLite e uma interface web sem dependências remotas. Autenticação e permissões no servidor, senhas com hash, backup consistente, rastreabilidade e bloqueio de alterações após liberação.

## Mac — download e instalação

- [Mac universal 2.5: Apple Silicon e Intel](downloads/Maxbem_Mac_Universal_v2_5.zip) — macOS 11+.
- [Guia de instalação, ícone, dados e recuperação](docs/MAC.md).
- [Segurança e limites da versão Mac](docs/RELATORIO_MAC.md).

Extraia o ZIP e execute **Instalar Maxbem.command**. O aplicativo fica em `~/Applications/Maxbem Laboratório.app`, com ícone na Área de Trabalho. Na primeira instalação, o script baixa e verifica o instalador oficial assinado do Python; conclua a janela de instalação do macOS. Exige internet e pode solicitar autorização administrativa nessa janela. Depois, funciona offline. O banco fica separado em `~/Library/Application Support/MaxbemLaboratorio/Dados`.

**A versão Mac não tem Developer ID/notarização e ainda precisa de homologação em Macs reais.** Os testes do servidor e do navegador foram executados no Linux. O guia explica as opções normais do Gatekeeper sem desativar proteções globais.

## Desenvolver e verificar

Use Python 3.12+. Não há dependências externas para o servidor:

```sh
cd app
python3 server.py
python3 -I -B -m unittest discover -s tests -v
```

O cadastro administrativo abre no primeiro uso; não existe senha padrão. Não compartilhe a URL temporária de abertura. O teste de navegador em `app/tests/browser_smoke.py` requer Playwright e Chromium, apenas para desenvolvimento.

Gerar pacote Mac com manifestos de integridade:

```sh
python3 tools/build_macos.py
```

O pacote 2.5 substitui o runtime portátil que foi encerrado com `Killed: 9` no Mac do usuário. Usa o Python universal oficial, valida assinatura PSF e aprovação do Gatekeeper antes de abrir seu instalador e verifica o runtime antes de executá-lo. A causa exata do encerramento anterior não foi confirmada. A geração pode ocorrer no Linux; instalação e assinatura precisam ser verificadas em um Mac real. O logo é convertido em `.icns` usando `sips/iconutil` na instalação.

## Histórico Windows

`packaging/windows` mantém os instaladores e a verificação da versão Windows com runtime interno. Os relatórios históricos em `docs` descrevem a revisão original. Esses scripts precisam do pacote Windows completo e seu runtime/manifesto; não devem ser executados isoladamente. Nenhum banco de usuário, credencial real ou capacidade temporária está no repositório.

O app não constitui validação científica/legal dos métodos do laboratório, assinatura digital ou garantia de ausência de vulnerabilidades. Compare dados migrados com a responsável técnica e teste backup e recuperação antes de produção.
