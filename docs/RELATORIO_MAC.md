# Revisão Mac 2.5

O instalador 2.2 foi encerrado pelo macOS com `Killed: 9` antes de executar o código Python de instalação. A integridade do runtime foi verificada; a causa exata não foi confirmada.

A versão 2.5 remove o runtime portátil do pacote. Baixa o instalador universal oficial por HTTPS, exige assinatura de instalação da Python Software Foundation e avaliação `spctl`, e abre o instalador nativo. Antes de executar Python, verifica assinatura `codesign`, identidade PSF e versão final compatível das séries 3.12, 3.13 ou 3.14. Nenhuma proteção do Gatekeeper é desativada. Exige internet inicial e possível autorização administrativa na janela oficial.

Instalação usa staging, verificação dos arquivos, bloqueio do banco ativo e preservação da versão anterior. Banco e backups continuam fora do aplicativo. Ícone é gerado com ferramentas do macOS; atalho preexistente é preservado. Falhas indicam a etapa e mantêm o Terminal disponível.

O Maxbem não tem Developer ID/notarização. Manifestos detectam corrupção, mas não autenticam a origem se forem substituídos junto com os arquivos. Banco e backups não são criptografados. Controle da conta ou do sistema permite alterar os dados; recomenda-se FileVault e cópias protegidas. A segurança do backend não equivale à validação científica/legal dos laudos.

Testes Linux não validam assinatura, instalação, Finder ou execução macOS. O download oficial foi bloqueado pela política de rede cloud e não foi confirmado neste ambiente. Leia MAC.md para instalação e limitações.

A versão 2.5 verifica o código assinado do framework com `codesign --verify --strict --ignore-resources`, pois o Python instalado pode ter recursos adicionados por ensurepip/pip. O executável continua com verificação estrita completa; ambos exigem identidade PSF. A integridade de todos os recursos e pacotes Python do framework não é certificada por essa verificação. Não há remoção de quarentena, alteração de assinatura ou desativação do Gatekeeper.
