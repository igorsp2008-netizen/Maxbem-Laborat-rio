# Avaliação de segurança e confiabilidade — Maxbem

## Escopo e conclusão

Foram inspecionados os dois ZIPs fornecidos: a versão HTML com logo atualizado e a versão Windows com servidor PowerShell e banco JSON. A versão Windows mais recente foi usada como referência funcional, e o logo veio do primeiro pacote. Os arquivos recebidos foram preservados, sem instalar ou executar os scripts originais.

A versão original contém falhas relevantes de autenticação, autorização, armazenamento e integridade. A entrega é uma **reescrita local em Python/SQLite com interface JavaScript**, não um patch do servidor PowerShell. Foram verificados o servidor reescrito e fluxos em Chromium; o ambiente de validação é Linux. Não houve auditoria independente, pentest em Windows, inspeção de uma base de produção ou homologação regulatória.

## Achados na versão original

| Prioridade | Evidência no código recebido | Risco | Tratamento na reescrita |
| --- | --- | --- | --- |
| Crítica | `server.ps1`, rotas `/api/get` e `/api/set`, sem identificação do usuário | Leitura de usuários/senhas e modificação de qualquer chave por acesso ao serviço local, independentemente do login na tela | APIs de dados exigem sessão; cada operação tem ACL no servidor; não há API genérica para regravar todo o banco |
| Alta | `DEFAULT_USERS`, `doLogin`, `persistUsers`: `admin/admin123` e campo `senha` em texto aberto | Credencial conhecida e exposição de todas as senhas em banco/exportações | Primeiro administrador criado explicitamente; PBKDF2-HMAC-SHA256, salt aleatório e 600 mil iterações; API e exportação JSON não retornam hashes |
| Alta | `restoreSession`: confia em ID em `sessionStorage`; funções de permissão apenas no JavaScript | Simular usuário ou invocar funções diretamente pelo navegador | Sessão aleatória no servidor, cookie HttpOnly/SameSite=Strict, expiração de 30 min de inatividade/8 h absolutas; troca de senha e de acessos revoga sessões |
| Alta | `server.ps1`: sem validação de Host/Origin e sem mecanismo CSRF | Solicitações indevidas originadas de outros sites, inclusive risco de DNS rebinding contra serviço local | Host exato `127.0.0.1:porta`, origem exata, bloqueio de requisições entre sites, CSRF nas mutações; login exige capacidade temporária do iniciador |
| Alta | `renderSamples`, `renderUsers`, `reportTable`, `trace`, laudos: dados concatenados em `innerHTML` | JavaScript persistente em campos de cadastro ou backup adulterado | DOM com `textContent`, sem HTML de dados, `eval`, eventos inline ou `document.write`; CSP bloqueia scripts inline e recursos externos |
| Alta | `Load-Store`: erro de leitura/JSON retorna objeto vazio | Arquivo corrompido pode ser interpretado como banco vazio e sobrescrito na próxima gravação | Falha de integridade impede abertura; não substitui banco corrompido; restauração valida cópia antes de trocar |
| Alta | `persist`: grava especificações, amostras e sequência em requisições separadas; `/api/set` regrava o armazenamento completo | Estado parcial após falha e perda de alterações de outra janela | Transação SQLite, sequência no servidor, WAL, `synchronous=FULL`, revisão exigida para editar/liberar |
| Alta | `calcParecer`: verifica somente umidade, HMF e cinzas; `parseFloat` aceita prefixos de texto | Amostra pode aparecer aprovada mesmo com outros parâmetros habilitados reprovados ou valores inválidos | Todos os parâmetros habilitados são avaliados no servidor; números completos/finitos; pendência ou ausência de limites não resulta em aprovação automática |
| Alta | Amostras usam especificações atuais ao imprimir; responsáveis fixos em partes dos relatórios | Alterar um limite pode mudar retrospectivamente o conteúdo e interpretação de um laudo; liberação profissional aparente sem evento autenticado | Snapshot de critérios por análise; usuário liberador registrado; laudos não liberados marcados como rascunho; sem assinatura profissional fictícia |
| Alta | Banco em `%PUBLIC%\Documents`; permissões de pasta não configuradas | Outros usuários do computador podem alcançar dados, histórico e senhas conforme a ACL local | Banco sob `%LOCALAPPDATA%` por conta; instalador restringe ACL; dados antigos permanecem e precisam de arquivamento protegido |
| Média | `Read-Request` aloca corpo conforme `Content-Length`, sem teto; servidor sequencial | Exaustão de memória ou bloqueio do serviço por requisição lenta | Teto de 16 MiB, validação de JSON/tipo/comprimento, timeout de 10 s e limite de 32 handlers ativos |
| Média | `importBackup`: estrutura não validada e restauração por gravações múltiplas | Backup inválido pode trocar usuários e deixar banco parcialmente restaurado | Validação integral antes da transação; só importa em banco sem amostras; ignora credenciais antigas; preserva original de cada registro |
| Média | Exportação CSV sem neutralização de fórmulas | Planilha interpretar campo textual como fórmula | Aspas, escape de delimitadores e prefixo de apóstrofo para fórmulas/controles perigosos |
| Média | Histórico sem retenção, snapshots após alteração; auditoria limitada a chaves | Disco pode encher; recuperação e identificação de responsáveis insuficientes | Backup SQLite consistente antes de operações de recuperação/migração; startup e a cada 15 min; 30 cópias; auditoria com usuário, evento, registro e horário UTC |
| Média | Launcher usa `ExecutionPolicy Bypass`; checagem da porta aceita qualquer serviço que responda | Scripts executados ignorando a política e risco de abrir aplicação errada na porta ocupada | Iniciador Python sem PowerShell/Bypass; uma instância por banco; porta ocupada gera erro explícito |

A gravidade considera dados e autorizações do laboratório. Escutar apenas em loopback reduz a exposição de rede, mas não transforma API sem autenticação em API segura. Os achados originais foram estabelecidos por inspeção de código, não por exploração de uma instalação Windows real.

## Verificação da entrega

O pacote inclui testes repetíveis. A suíte de servidor cobre:

1. Hashes de senha, ausência de hashes na API e rejeição da credencial antiga.
2. Bloqueio de acesso não autenticado.
3. Host, Origin, CSRF e autorização temporária do login.
4. Impossibilidade de repetir o cadastro administrativo inicial.
5. SQL parametrizado e rejeição de números inválidos.
6. ACL no servidor, revogação de sessões e bloqueio de liberação/edição/relatórios por perfil sem acesso.
7. Cálculo do parecer, inclusive resultado zero, pendências e ausência de limites.
8. Revisões, imutabilidade de amostra liberada e preservação de especificações históricas.
9. Bloqueio de liberação pendente.
10. Criação concorrente de amostras com códigos distintos.
11. Backup e restauração com verificação de integridade.
12. Preservação de arquivo corrompido.
13. Migração atômica, códigos sequenciais e não importação de senhas.
14. Limite de tentativas de login.
15. Expiração de sessão.
16. Cookie e CSP; ausência de sinks HTML perigosos na interface.
17. Limites de corpo e validação de transporte/tipo.
18. Rollback após exceção simulada dentro de transação.
19. Política de senha e validação de datas.
20. Resultado qualitativo sem limite exige revisão.
21. Redefinição de senha exige administrador e confirmação da senha; revoga sessão antiga.
22. Tentativa de restaurar backup inválido preserva banco atual.
23. Restauração sobre banco corrompido recupera o serviço e preserva os bytes anteriores para diagnóstico.

O teste em Chromium real percorre primeiro cadastro, login, configuração do painel, criação de amostra, exportação CSV, liberação, laudo, etiqueta, rastreabilidade, criação de operador, integridade, backup, logout e acesso de Assistente. Um valor contendo `<img ... onerror=...>` permanece texto tanto na tabela quanto no relatório; o código injetado não executa. A interface é verificada quanto a erros JavaScript. Impressão é exercitada com substituição de `window.print`, sem impressora física.

O arquivo `VALIDACAO.txt` registra a execução final dos testes. Dados de teste são temporários; o pacote não inclui banco pré-configurado, usuário pronto, token de sessão ou senha fixa.

## Limites e adoção

- **Homologação Windows ainda necessária:** instalação/atualização, ACLs, atalhos, recuperação pela linha de comando, navegador Windows, impressão e funcionamento do Python Launcher não foram executados neste Linux.
- **Critérios técnicos:** unidades, limites, referências legais e validação de metodologias exigem a responsável técnica. A reescrita não prova conformidade legal do laboratório ou validade científica de um laudo.
- **Compatibilidade:** interface refeita, Python obrigatório, Excel em CSV e sem envio ZPL direto. A importação é validada com dados sintéticos; compare uma cópia do banco real antes da adoção.
- **Proteção local:** banco e backups não são criptografados. Malware ou alguém com controle da conta Windows pode ler/modificar os arquivos. ACL não substitui proteção do disco e dos backups.
- **Auditoria:** rastreia eventos do aplicativo, mas não é assinada nem imutável contra administração do sistema. Não é trilha probatória resistente a adulteração por quem controla o computador.
- **Rede:** HTTP exclusivamente local, sem TLS; não exponha a porta remotamente. Não é uma solução multiestação ou servidor internet.
- **Recuperação:** 30 backups locais não protegem contra falha de disco; organize cópia externa protegida. Teste restauração e mantenha o banco antigo intacto durante homologação.
- **Garantia:** os testes mostram comportamentos específicos sob as condições descritas; não são uma garantia de ausência de vulnerabilidades.
