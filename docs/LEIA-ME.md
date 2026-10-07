# Maxbem Laboratório — versão reescrita 2.0

Aplicativo local para Windows 10/11. A interface e o servidor foram reescritos; não é apenas uma alteração visual do pacote original. Funciona offline depois da instalação do Python. Não há pacotes Python adicionais, serviços externos, credenciais padrão ou telemetria.

## Instalação e primeiro acesso

1. Faça uma cópia externa do banco antigo e mantenha o aplicativo antigo fechado. Não apague a instalação anterior.
2. Instale **Python 3.12 ou superior** pelo site oficial <https://www.python.org/downloads/windows/>. Inclua o Python Launcher (`py`) na instalação.
3. Extraia o ZIP inteiro e execute `INSTALAR_MAXBEM.cmd`, sem executar como administrador.
4. O instalador cria `AppSeguro` dentro de `%LOCALAPPDATA%\MaxbemLaboratorio` e um iniciador na Área de Trabalho. A janela do servidor permanece aberta durante o uso; encerre com Ctrl+C.
5. O navegador abre o cadastro do primeiro administrador, autorizado por um código temporário recebido no fragmento da URL, sem envio desse fragmento no endereço HTTP. Escolha login e senha exclusivos; a senha precisa ter de 12 a 128 caracteres.
6. Revise **Especificações** e habilite o painel adequado antes de registrar análises. Os parâmetros e referências vieram do pacote original; precisam de validação pela responsável técnica.

Também é possível executar `ABRIR_MAXBEM.cmd` diretamente na pasta extraída. O banco é o mesmo da instalação, por conta do Windows. Se faltar o Python Launcher, use `python server.py` com Python 3.12+. Se a porta 8765 estiver ocupada pelo aplicativo antigo, feche-o; para outra porta execute `py -3 server.py --port 8766`.

**A janela do servidor precisa continuar aberta.** O instalador não cria um serviço permanente. Reabrir uma segunda instância é bloqueado em vez de abrir automaticamente um serviço desconhecido. Após reiniciar o servidor, abra pelo iniciador para obter uma nova autorização temporária.

## Onde ficam os dados

- Aplicativo instalado: `%LOCALAPPDATA%\MaxbemLaboratorio\AppSeguro`.
- Banco privado: `%LOCALAPPDATA%\MaxbemLaboratorio\Dados\maxbem.sqlite3`.
- Backups completos: subpasta `Dados\Backups`.
- Auditoria: tabela `audit` no banco, consultável por administrador no menu **Backup e auditoria**.
- A instalação aplica permissões de acesso da conta do Windows e SYSTEM às pastas privadas.

O conteúdo antigo em `%PUBLIC%\Documents\MaxbemLaboratorio\BancoDados` não é migrado nem excluído automaticamente. Ele continuará exposto conforme as permissões antigas até você decidir arquivá-lo em armazenamento protegido. Não deixe cópias de dados ou senhas antigas em pastas públicas.

## Migração sem substituir a origem

1. Crie a primeira conta administrativa no aplicativo novo.
2. No menu **Backup e auditoria**, selecione o `store.json` antigo ou uma exportação JSON da versão anterior.
3. Execute **Validar e importar**. O banco novo precisa estar sem amostras. O limite é 16 MiB por requisição. Para arquivos maiores, planeje uma migração separada; não divida o arquivo arbitrariamente.
4. A migração é transacional: se houver laudos duplicados, estrutura inválida, datas inconsistentes ou resultado incompatível com um limite numérico, a importação inteira é recusada. Não há importação parcial nem descarte silencioso. Preserve a origem e corrija uma cópia após revisão técnica.
5. As informações de cada registro original ficam em `legacyRecord`, incluindo histórico e informações de liberação existentes. Os resultados e limites são reavaliados; o parecer e a situação anteriores ficam separados como dados legados. Laudos importados recebem a situação **IMPORTADA — REVISÃO NECESSÁRIA**.
6. Recrie usuários com senhas novas. **Senhas, perfis e sessões antigos não são confiados nem importados**. Revise cada amostra antes de liberar novamente. A origem permanece intacta.

A migração foi testada com dados sintéticos; os ZIPs fornecidos contêm o aplicativo, não o banco de produção. Não houve validação de uma base real do laboratório.

## Fluxos e diferenças importantes

- Cadastro e edição de amostras, análises habilitadas, dashboard, produtores e rastreabilidade.
- Perfis Administrador, Qualidade, Analista e Assistente; permissões individuais verificadas no servidor.
- Administração de usuários, ativação/desativação, redefinição de senha com confirmação da senha do administrador e troca da própria senha.
- Edição usa a revisão do registro. Uma alteração concorrente gera conflito e solicita atualizar a lista. Não se sobrescreve a mudança de outra sessão.
- Código `LAU` é sequencial e atribuído numa transação no servidor. O usuário não escolhe o responsável autenticado, código, parecer ou liberação.
- **Amostras liberadas são imutáveis.** Uma retificação exige novo registro e identificação clara da referência ao original nas observações; não há recurso de excluir ou reabrir um laudo liberado.
- Cada análise guarda o painel, critérios e métodos usados. Uma mudança de especificações não altera laudos anteriores. Editar uma análise ainda não liberada recalcula com a configuração vigente.
- Qualquer parâmetro habilitado fora dos limites causa reprovação, e a ação de tratamento é obrigatória. Uma pendência causa `AGUARDANDO`; ausência de limites causa `REVISÃO NECESSÁRIA`; sem análises habilitadas não há aprovação. Todos os resultados habilitados devem estar preenchidos antes da liberação.
- Resultados com limites exigem número completo e finito. Parâmetros sem limites podem conter descrição qualitativa, mas não justificam aprovação automática. Unidades e interpretações precisam de revisão técnica.
- Laudos usam o usuário que realmente liberou a análise. Não há assinatura ou nome profissional fixo que simule uma liberação. **Não há assinatura digital nem certificação regulatória automática.** Relatórios ainda não liberados exibem marca de rascunho.
- Exportação para Excel é **CSV UTF-8 com separador `;`**, sem macros, com neutralização de fórmulas em campos textuais. Pode exigir a opção de importação do Excel conforme a configuração regional. Não foi mantido o formato XML `.xls` do app antigo.
- Etiqueta é impressão pelo navegador no formato 100 × 60 mm. Configure a impressora Zebra, desative cabeçalhos/rodapés e use escala 100%. Muitos resultados podem produzir mais de uma página para evitar corte silencioso. Não há envio ZPL direto.
- A interface foi refeita: não mantém exatamente o layout original. O logo do primeiro ZIP foi reutilizado. Recursos não implementados: rede multiestação, integração com equipamentos, certificados digitais e atualizador automático.

## Backup e recuperação

O banco usa SQLite com WAL, gravações transacionais e `synchronous=FULL`. A inicialização valida a integridade estrutural; um banco corrompido não é substituído por banco vazio.

- Uma cópia completa validada é criada ao iniciar; enquanto o servidor está ativo, outra é criada a cada **15 minutos**. Também é possível criar uma cópia manual pelo menu.
- São mantidas as **30 cópias mais recentes**. Cópias locais no mesmo disco não protegem contra falha do computador. Guarde cópias externas protegidas e teste a recuperação periodicamente.
- O backup SQLite contém contas, hashes de senha, amostras e auditoria. Trate-o como dado sensível. Não copie somente o arquivo principal enquanto o banco estiver aberto: use o backup fornecido, que inclui as alterações do WAL.
- A exportação JSON contém dados de amostras e configuração, **sem contas ou hashes**. Reimportá-la em um banco sem amostras segue a revisão de migração; não substitui uma recuperação integral.

**Restauração integral:** feche o servidor, arraste uma cópia `.sqlite3` da pasta `Backups` sobre `RESTAURAR_BACKUP.cmd`, confirme e abra o aplicativo. O comando valida a cópia e preserva o banco anterior num arquivo `antes-restauracao-*.sqlite3` antes da troca. Use backups produzidos por esta versão e de origem confiável. A restauração recupera os dados até o instante do backup, inclusive as senhas e permissões daquele momento.

**Recuperar senha administrativa esquecida:** com o servidor fechado, execute `RECUPERAR_ADMIN.cmd`, informe o login administrativo e defina a senha no terminal. A operação exige acesso à conta do Windows que possui o banco e fica registrada na auditoria. Uma cópia anterior é preservada. Esse acesso local faz parte do limite de confiança do aplicativo.

**Desinstalação:** execute `DESINSTALAR_PRESERVANDO_DADOS.cmd` no pacote extraído. São removidos o aplicativo seguro e seu iniciador, preservando banco, backups e instalação antiga. Não encerra processos de terceiros.

## Validação e limites

Os testes de servidor e de navegador estão incluídos em `tests`. Para repetir o servidor: `py -3 -m unittest discover -s tests -v`. O teste de navegador é ferramenta de desenvolvimento, requer Playwright e Chromium e foi executado no Linux; esses componentes não são necessários para usar o aplicativo.

A execução do servidor e os fluxos da interface foram validados em Linux com Python 3.12 e Chromium. **O instalador, as ACLs, a impressão física Zebra e a operação em Windows ainda precisam de homologação em Windows 10/11.** Não há garantia de ausência de vulnerabilidades nem validação científica/legal dos critérios do laboratório.

SQLite, backups e auditoria não são criptografados nem protegidos contra alguém com controle da mesma conta do Windows, administrador do sistema ou malware local. Use contas Windows separadas, disco protegido (por exemplo BitLocker) e backup externo com controle de acesso. O serviço escuta apenas em `127.0.0.1`; não exponha a porta na rede ou na internet. Ele usa HTTP local e não se destina a implantação remota.

Antes de adotar em produção, faça a migração em uma cópia, compare os laudos com a responsável técnica, teste impressão e recuperação numa máquina Windows e mantenha a origem arquivada de forma protegida.
