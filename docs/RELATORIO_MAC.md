# Alterações e limites da versão Mac 2.2

Esta versão reutiliza o servidor e a interface reescritos, com autenticação e ACL no servidor, PBKDF2, CSRF, Host/Origin, SQLite transacional, revisões, snapshots de critérios, imutabilidade após liberação e recuperação por backup. A análise do aplicativo original está em `docs/RELATORIO_SEGURANCA.md`, que registra a etapa anterior para Windows.

## Adaptações do Mac

- Pacotes separados Apple Silicon e Intel, com CPython 3.14.8 do **Astral python-build-standalone**, release 20261003; não são instaladores macOS oficiais da PSF. SHA-256 comparado ao `SHA256SUMS` publicado pelo fornecedor em HTTPS. Versão, origem e hash são fixados em `packaging/macos/runtimes.json` e reproduzidos no pacote.
- Binário Apple Silicon identifica CPU arm64 e mínimo macOS 11.0; Intel identifica x86_64 e mínimo macOS 10.15. São inspeções de cabeçalhos Mach-O, não execução nesses sistemas.
- Instalação privada em Aplicativos da conta, runtime incluído e ícone `.icns` gerado com os utilitários do macOS. Atalho Desktop não substitui arquivo preexistente.
- Banco e logs em diretórios privados da conta, separados do aplicativo; `umask 077`, diretórios 0700 e capacidades em arquivo 0600. Trava de arquivo bloqueia atualização/restauração com servidor ativo.
- Iniciador reabre somente a instância cuja identificação pública corresponde ao PID e ao hash da capacidade do arquivo privado. Não confia apenas em uma porta aberta. Não envia requisições de loopback por proxy e não registra o endereço com capacidade nos logs.
- Encerramento do serviço exige administrador, sessão e CSRF e gera evento auditado. Não encerra processos de terceiros.
- Verificação SHA-256 do pacote antes de extrair runtime e do aplicativo antes de iniciar. Extração feita com filtro de segurança e hashes fixados do arquivo de origem. Execução isolada com `-I -B`, sem Python global ou caches no aplicativo.
- Atualização preserva a instalação anterior; desinstalação preserva banco e backups.

## Limites

Não há Developer ID ou notarização. Hashes não substituem assinatura do aplicativo; não foram removidas proteções do Gatekeeper. Pode ser necessária aprovação **por aplicativo** no macOS conforme a política do usuário/organização; a configuração global não deve ser enfraquecida. A necessidade de distribuição assinada depende do ambiente e não foi resolvida inventando certificados.

Não houve execução dos binários Mac, teste de Finder/Gatekeeper, verificação do ícone instalado ou impressão em hardware. O servidor e o navegador foram testados no Linux. A migração usa dados sintéticos porque o usuário forneceu código e não uma base de produção. As referências e limites analíticos precisam de validação profissional; laudos não são assinaturas digitais. As demais limitações de armazenamento local, backup externo e controle da conta continuam aplicáveis.
