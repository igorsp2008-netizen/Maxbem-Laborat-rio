# Maxbem para Mac — 2.2

Dois pacotes estão disponíveis: **Apple Silicon** (M1/M2/M3/M4 e posteriores, arquitetura arm64, macOS 11+) e **Intel** (x86_64, macOS 10.15+). Ambos incluem CPython 3.14.8 distribuído pelo projeto Astral `python-build-standalone`. Não é preciso instalar Python, Homebrew ou bibliotecas; não há downloads durante a instalação.

## Instalar e criar o ícone

1. Baixe o ZIP adequado ao processador. Consulte o menu Apple → Sobre Este Mac: `Chip` identifica Apple Silicon; `Processador Intel` identifica Intel.
2. Extraia todo o ZIP no Finder. Não execute arquivos de dentro do ZIP.
3. Abra `Instalar Maxbem.command`. O script verifica os hashes, instala o aplicativo e seu runtime em **`~/Applications/Maxbem Laboratório.app`**, gera um ícone `.icns` a partir do logotipo e cria o ícone na Área de Trabalho. Não usa sudo nem modifica o Python do sistema.
4. O navegador padrão abre o cadastro do primeiro administrador. Crie uma senha exclusiva com pelo menos 12 caracteres.
5. Revise o painel de análises e os critérios com a responsável técnica antes de emitir laudos.

O macOS pode pedir permissão do Terminal para criar o ícone na Área de Trabalho. Se você não conceder, o aplicativo continua disponível na pasta Aplicativos **da sua conta**, acessível pelo Finder em sua pasta pessoal. O instalador preserva um ícone preexistente para não substituir arquivos seus.

**O aplicativo não foi assinado com Developer ID nem notarizado pela Apple.** O Gatekeeper pode bloquear o `.command` ou o `.app`. Verifique a origem do ZIP e seu SHA-256 publicado no repositório. Quando o macOS oferecer a opção por aplicativo, use o procedimento normal documentado pela Apple, como Ajustes do Sistema → Privacidade e Segurança → Abrir Mesmo Assim, para esse arquivo verificado. Não desative o Gatekeeper globalmente, não remova verificações de integridade e não use comandos para ignorar a política de segurança. Em computadores corporativos, siga a política do administrador; se a execução for proibida, será necessária uma distribuição assinada e homologada.

## Usar, atualizar e encerrar

- Abra pelo ícone da Área de Trabalho ou pelo aplicativo em `~/Applications`. Se já estiver ativo, o iniciador verifica a identidade da instância e reabre o navegador; não inicia outro banco.
- O serviço funciona somente neste Mac, em `127.0.0.1:8765`. Não exponha a porta em rede.
- Para encerrar, use **Backup e auditoria → Encerrar aplicativo**, com acesso de administrador. Fechar só a aba do navegador não encerra o servidor. O encerramento desconecta todas as sessões.
- Antes de atualizar, encerre o servidor. O instalador preserva a instalação anterior como `Maxbem Laboratório.app.anterior`. Se essa cópia já existir, arquive-a antes da próxima atualização; não será apagada automaticamente.
- Banco e backups não ficam dentro do aplicativo; reinstalar não os apaga.

## Dados, backup e recuperação

- Banco: `~/Library/Application Support/MaxbemLaboratorio/Dados/maxbem.sqlite3`.
- Backups: subpasta `Dados/Backups`, com as 30 cópias mais recentes; criação ao iniciar, a cada 15 minutos e manualmente.
- Log do servidor: `~/Library/Logs/MaxbemLaboratorio/server.log`. Capacidades temporárias de abertura não são registradas nesse log.
- `launch.json` é um arquivo privado temporário que permite ao iniciador abrir a instância correta. Não compartilhe esse arquivo; ele é removido no encerramento normal.

No menu Backup, uma base antiga `store.json` ou uma exportação JSON pode ser importada **somente em banco sem amostras**. Copie a origem antes. Senhas antigas não são importadas; liberações antigas exigem revisão. Dados sintéticos validaram a migração; nenhuma base real foi fornecida.

Para restaurar uma cópia integral SQLite, encerre o aplicativo e abra `Restaurar backup.command`, que solicita o arquivo e uma confirmação. A cópia atual é preservada. Para senha administrativa esquecida, use `Recuperar administrador.command` com o servidor encerrado; a senha é solicitada no terminal e a operação é auditada. Ambos usam o runtime instalado, sem Python externo.

Para remover, encerre o servidor e execute `Desinstalar preservando dados.command` do pacote extraído. Ele remove o aplicativo e somente o atalho que aponta para ele, preservando banco, backups e a instalação anterior arquivada. Mantenha o ZIP para recuperação/reinstalação.

## Segurança e compatibilidade

Login e permissões são verificados no servidor; senhas usam PBKDF2 com salt; mutações exigem sessão e CSRF. As gravações são transacionais, edições usam revisão e amostras liberadas são imutáveis. Os critérios da análise são preservados no laudo. A saída Excel é CSV; etiqueta usa impressão pelo navegador. Documentos não equivalem a assinatura digital ou certificação legal automática.

O ZIP e a instalação usam manifestos SHA-256. Isso detecta corrupção e alteração dos arquivos declarados, mas não prova a autenticidade se alguém alterar também o manifesto. Runtimes foram verificados contra SHA-256 publicado pelo projeto fornecedor via HTTPS. Não há assinatura Developer ID do Maxbem. Banco, backups e auditoria não são criptografados e não resistem a alguém com controle da sua conta ou do sistema; use contas separadas, FileVault e cópias externas protegidas.

**Validação disponível:** servidor, interface em Chromium, identidade da instância, arquivo privado e encerramento autenticado foram testados no Linux. Arquitetura e requisitos mínimos dos binários Mac foram inspecionados e seus hashes verificados. **O runtime macOS, o Finder/Gatekeeper, a instalação, o ícone gerado por `sips/iconutil` e a impressão física ainda precisam ser testados em Macs reais de ambas as arquiteturas.** Não considere a entrega homologada em macOS apenas porque os testes Linux passaram.
