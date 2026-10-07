'use strict';
// Todo conteúdo de cadastro entra por textContent; sem innerHTML, eval ou eventos inline.
const root=document.getElementById('app');
const printArea=document.getElementById('print-area');
let csrf='',user=null,state=null,samples=[],section='dashboard',editing=null;
const fragment=new URLSearchParams(location.hash.slice(1));
const setupToken=fragment.get('setup')||'';
let launch=fragment.get('launch')||sessionStorage.getItem('maxbem_launch')||'';
if(launch)sessionStorage.setItem('maxbem_launch',launch);
history.replaceState(null,'',location.pathname);
const perms={dashboard:'Dashboard',nova_amostra:'Nova amostra',amostras:'Lista de amostras',editar_amostra:'Editar análise',laudos:'Área de laudos',emitir_laudo:'Emitir laudo',etiqueta_zebra:'Etiqueta Zebra',exportar_excel:'Exportar Excel/CSV',produtores:'Indicadores por produtor',rastreabilidade:'Rastreabilidade',liberar_amostra:'Liberar análise'};
const roles={ADMIN:'Administrador',QUALIDADE:'Qualidade',ANALISTA:'Analista',ASSISTENTE:'Assistente'};
const fields={amostra:'Número da amostra',tambor:'Número do tambor',produtor:'Código do produtor',loteAmostra:'Lote da amostra',temperaturaAmostra:'Temperatura (°C)',dtReceb:'Data de recebimento',hrReceb:'Hora de recebimento',dtAnalise:'Data de análise',hrAnalise:'Hora de análise',florada:'Florada',obs:'Observações',acaoReprovada:'Ação em caso de reprovação'};
let logoPath='/logo.png';
function node(tag,props={},...children){
  const el=document.createElement(tag);
  for(const [key,value] of Object.entries(props)){
    if(key.startsWith('on'))el.addEventListener(key.slice(2),value);
    else if(key==='class')el.className=value;
    else if(key==='text')el.textContent=value;
    else if(['checked','disabled','required','selected','value'].includes(key))el[key]=value;
    else el.setAttribute(key,value);
  }
  for(const child of children.flat(Infinity))if(child!==null&&child!==undefined)el.append(child instanceof Node?child:document.createTextNode(String(child)));
  return el;
}
function can(p){return !!user&&(user.papel==='ADMIN'||user.permissoes[p]===true);}
function button(label,action,kind=''){return node('button',{type:'button',class:kind,onclick:()=>guard(action)},label);}
function card(...children){return node('div',{class:'card'},...children);}
let labelSeq=0;
function label(title,input,help=''){
  input.setAttribute('aria-label',title);
  const id='field-help-'+(++labelSeq);
  if(help)input.setAttribute('aria-describedby',id);
  return node('label',{},title,input,help?node('small',{id},help):null);
}
function badge(value){return node('span',{class:'badge '+(value==='APROVADA'?'ok':value==='REPROVADA'?'bad':'warn')},value);}
function table(headers,rows){return node('div',{class:'table-wrap'},node('table',{},node('thead',{},node('tr',{},headers.map(h=>node('th',{},h)))),node('tbody',{},rows.map(r=>node('tr',{},r.map(v=>node('td',{},v)))))));}
function message(text,kind='error'){
  const host=document.getElementById('message');
  if(host){host.replaceChildren(node('div',{class:kind,role:'alert'},text));host.scrollIntoView({block:'nearest'});}
}
async function guard(action){try{await action();}catch(error){message(error.message||'Operação não concluída.');}}
async function api(path,method='GET',body){
  const headers={'X-Maxbem-Launch':launch};
  if(body!==undefined)headers['Content-Type']='application/json';
  if(csrf)headers['X-CSRF-Token']=csrf;
  const res=await fetch(path,{method,headers,credentials:'same-origin',body:body===undefined?undefined:JSON.stringify(body)});
  let result;try{result=await res.json();}catch{throw new Error('Resposta inválida. A operação não foi confirmada.');}
  if(!res.ok){
    if(res.status===401&&user){user=null;csrf='';state=null;samples=[];printArea.replaceChildren();renderLogin();}
    throw new Error(result.error||'Operação não concluída.');
  }
  return result;
}
function submit(form,handler){
  form.addEventListener('submit',event=>{
    event.preventDefault();
    const buttons=[...form.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);
    guard(async()=>{try{await handler();}finally{buttons.forEach(b=>b.disabled=false);}});
  });
}
function renderLogin(setup=false){
  root.replaceChildren();
  const form=node('form');
  const login=node('input',{required:true,minLength:3,maxLength:80,autocomplete:'username'});
  const password=node('input',{type:'password',required:true,maxLength:128,minLength:setup?12:1,autocomplete:setup?'new-password':'current-password'});
  const name=node('input',{required:true,maxLength:200,autocomplete:'name'});
  const confirmation=node('input',{type:'password',required:true,minLength:12,maxLength:128,autocomplete:'new-password'});
  if(setup)form.append(label('Nome do administrador',name));
  form.append(label('Usuário',login),label('Senha',password,setup?'Use uma senha única de pelo menos 12 caracteres.':''));
  if(setup)form.append(label('Confirme a senha',confirmation));
  form.append(node('button',{type:'submit',class:'primary'},setup?'Criar administrador':'Entrar'));
  root.append(node('div',{class:'auth'},card(node('img',{src:logoPath,alt:'Maxbem'}),node('h1',{},setup?'Primeiro acesso':'Laboratório de mel'),
    node('p',{class:'muted'},setup?'Crie a primeira conta. Não há senha padrão.':'Acesso local com sessão protegida.'),
    node('div',{id:'message'}),form,node('p',{class:'muted'},'Use o iniciador do Windows para abrir o aplicativo.'))));
  submit(form,async()=>{
    if(setup){
      if(password.value!==confirmation.value)throw new Error('As senhas não coincidem.');
      await api('/api/setup','POST',{token:setupToken,nome:name.value,usuario:login.value,senha:password.value});
    }
    const result=await api('/api/login','POST',{usuario:login.value,senha:password.value});
    user=result.user;csrf=result.csrf;password.value='';confirmation.value='';await load();
  });
}
async function load(){
  state=await api('/api/state');user=state.user;
  if(['dashboard','amostras','laudos','produtores','rastreabilidade'].some(can))samples=(await api('/api/samples')).samples;
  else samples=[];
  const allowed=routes().map(r=>r[0]);if(!allowed.includes(section))section=allowed[0]||'conta';
  renderShell();await renderSection();
}
function routes(){
  const entries=[['dashboard','Dashboard','dashboard'],['nova','Nova amostra','nova_amostra'],['amostras','Amostras','amostras'],['laudos','Laudos','laudos'],['produtores','Produtores','produtores'],['rastreabilidade','Rastreabilidade','rastreabilidade']];
  const result=entries.filter(e=>can(e[2]));
  if(user.papel==='ADMIN')result.push(['usuarios','Usuários'],['especificacoes','Especificações'],['backup','Backup e auditoria']);
  result.push(['conta','Minha conta']);return result;
}
function renderShell(){
  const nav=node('nav',{'aria-label':'Menu principal'},routes().map(([id,title])=>button(title,async()=>{section=id;editing=null;renderShell();await renderSection();},section===id?'active':'')));
  root.replaceChildren(node('header',{},node('div',{class:'brand'},node('img',{src:logoPath,alt:'Maxbem'}),node('div',{},node('strong',{},'Controle laboratorial de mel'),node('div',{class:'muted'},'Banco local • acesso por usuário'))),
    node('div',{class:'account'},node('strong',{},user.nome),node('div',{class:'muted'},roles[user.papel]),button('Sair',async()=>{
      await api('/api/logout','POST',{});user=null;state=null;samples=[];csrf='';editing=null;printArea.replaceChildren();renderLogin();
    }))),node('div',{class:'layout'},nav,node('main',{},node('div',{id:'message'}),node('div',{id:'content'}))));
}
async function renderSection(){
  const content=document.getElementById('content');content.replaceChildren(node('h1',{},routes().find(r=>r[0]===section)?.[1]||''));
  switch(section){
    case 'dashboard':renderDashboard(content);break;
    case 'nova':renderSampleForm(content);break;
    case 'amostras':case 'laudos':renderSamples(content);break;
    case 'produtores':renderProducers(content);break;
    case 'rastreabilidade':renderTrace(content);break;
    case 'usuarios':await renderUsers(content);break;
    case 'especificacoes':renderSettings(content);break;
    case 'backup':renderBackup(content);break;
    case 'conta':renderAccount(content);break;
  }
}
function renderDashboard(content){
  content.append(node('div',{class:'grid'},[['Amostras',samples.length],['Aprovadas',samples.filter(s=>s.parecer==='APROVADA').length],['Reprovadas',samples.filter(s=>s.parecer==='REPROVADA').length],['Aguardando / revisão',samples.filter(s=>!['APROVADA','REPROVADA'].includes(s.parecer)).length]].map(([name,count])=>card(node('div',{class:'metric'},name,node('strong',{},count))))),card(node('h2',{},'Últimas amostras'),sampleTable(samples.slice(0,5))));
}
function sampleTable(data){
  if(!data.length)return node('p',{class:'empty'},'Nenhuma amostra registrada.');
  return table(['Laudo','Amostra / tambor','Produtor','Parecer','Situação','Ações'],data.map(s=>[
    s.lau,s.amostra+' / '+s.tambor,s.produtor,badge(s.parecer),s.status,
    node('div',{class:'actions'},
      can('editar_amostra')&&s.status!=='LIBERADA'?button('Editar',async()=>{editing=s;section='nova';renderShell();renderSampleForm(document.getElementById('content'));}):null,
      can('emitir_laudo')?button('Laudo',()=>printSample(s.id,false)):null,
      can('etiqueta_zebra')?button('Etiqueta',()=>printSample(s.id,true)):null,
      can('liberar_amostra')&&s.status!=='LIBERADA'?button('Liberar',async()=>{
        if(!confirm('Liberar '+s.lau+'? O registro ficará imutável.'))return;
        await api('/api/samples/'+encodeURIComponent(s.id)+'/release','POST',{revision:s.revision});await load();message('Análise liberada.','success');
      },'primary'):null)
  ]));
}
function renderSamples(content){
  const search=node('input',{type:'search',placeholder:'Laudo, amostra, tambor ou produtor','aria-label':'Pesquisar amostras'});
  const box=node('div');const update=()=>box.replaceChildren(sampleTable(samples.filter(s=>[s.lau,s.amostra,s.tambor,s.produtor].join(' ').toLocaleLowerCase().includes(search.value.toLocaleLowerCase()))));
  search.addEventListener('input',update);
  content.append(card(node('div',{class:'actions'},search,can('exportar_excel')?button('Exportar Excel (CSV)',exportCsv):null,button('Atualizar',load)),box));update();
}
function renderSampleForm(content){
  const old=editing;const inputs={};const resultInputs={};
  const form=node('form');
  const grid=node('div',{class:'grid'});
  for(const [key,title] of Object.entries(fields)){
    const type=key.startsWith('dt')?'date':key.startsWith('hr')?'time':'text';
    const inp=node(key==='obs'||key==='acaoReprovada'?'textarea':'input',{type,value:old?.[key]||'',required:['amostra','tambor','produtor'].includes(key),maxLength:['obs','acaoReprovada'].includes(key)?4000:200});
    inputs[key]=inp;grid.append(label(title,inp));
  }
  const params=node('div',{class:'grid'});
  for(const [key,spec] of Object.entries(state.specs)){
    if(!state.enabled[key])continue;
    const inp=node('input',{type:'text',inputMode:'decimal',maxLength:100,value:old?.results?.[key]||''});resultInputs[key]=inp;
    params.append(label(spec.label+' ('+spec.unit+')',inp,spec.method+' • Limites: '+limits(spec)));
  }
  form.append(grid,node('h2',{},'Resultados analíticos'),node('p',{class:'notice'},'O servidor valida os números e calcula o parecer considerando todas as análises habilitadas. Parâmetros sem limites exigem revisão. A ação para reprovação é obrigatória.'),params,
    node('div',{class:'actions'},node('button',{type:'submit',class:'primary'},old?'Salvar alteração':'Registrar análise'),button('Cancelar',async()=>{editing=null;await load();})));
  content.append(card(node('h2',{},old?'Editar '+old.lau:'Nova análise'),node('p',{class:'muted'},'Analista autenticado: '+user.nome),form));
  submit(form,async()=>{
    const data=Object.fromEntries(Object.entries(inputs).map(([k,v])=>[k,v.value]));data.results=Object.fromEntries(Object.entries(resultInputs).map(([k,v])=>[k,v.value]));
    if(old)data.revision=old.revision;
    const result=await api(old?'/api/samples/'+encodeURIComponent(old.id):'/api/samples',old?'PUT':'POST',data);
    editing=null;section=can('amostras')?'amostras':'nova';await load();message(result.sample.lau+' salvo. Parecer: '+result.sample.parecer,'success');
  });
}
function limits(s){return [s.min!==''?'≥ '+s.min:'',s.max!==''?'≤ '+s.max:''].filter(Boolean).join(' e ')||'Não definidos';}
function resultsTable(s){
  const specs=s.specSnapshot||state.specs;
  return table(['Parâmetro','Resultado','Unidade','Especificação','Metodologia','Situação'],Object.entries(specs).filter(([k])=>s.reportEnabled[k]).map(([k,v])=>[v.label,s.results[k]||'—',v.unit,limits(v),v.method,s.parameterStatus[k]||'PENDENTE']));
}
function sampleDetail(s){
  return card(node('h2',{},s.lau),node('div',{class:'grid'},Object.entries(fields).map(([k,title])=>node('div',{},node('strong',{},title+': '),node('span',{class:'detail'},s[k]||'—')))),node('p',{},'Análise: ',s.analista||s.createdBy||'—',' • Liberação: ',s.releasedBy||'Aguardando'),node('p',{},'Parecer: ',badge(s.parecer)),resultsTable(s),node('h3',{},'Histórico'),table(['Data','Evento','Usuário'],(s.history||[]).map(h=>[h.at,h.event,h.user])));
}
function renderTrace(content){
  const search=node('input',{type:'search',placeholder:'Digite o laudo, amostra, tambor ou produtor',required:true,'aria-label':'Consultar rastreabilidade'});const result=node('div');
  const form=node('form',{},search,node('div',{class:'actions'},node('button',{type:'submit',class:'primary'},'Consultar')));
  submit(form,async()=>{
    const q=search.value.trim().toLocaleLowerCase();result.replaceChildren();
    const matches=samples.filter(s=>[s.lau,s.amostra,s.tambor,s.produtor].some(v=>String(v).toLocaleLowerCase().includes(q)));
    result.append(...matches.slice(0,50).map(sampleDetail));if(!matches.length)result.append(node('p',{},'Nenhum registro encontrado.'));
  });content.append(card(form),result);
}
function renderProducers(content){
  const groups=new Map();for(const s of samples){const g=groups.get(s.produtor)||{total:0,approved:0,rejected:0};g.total++;if(s.parecer==='APROVADA')g.approved++;if(s.parecer==='REPROVADA')g.rejected++;groups.set(s.produtor,g);}
  content.append(card(table(['Produtor','Amostras','Aprovadas','Reprovadas','Taxa de aprovação'],[...groups].map(([p,g])=>[p,g.total,g.approved,g.rejected,Math.round(g.approved/g.total*100)+'%']))));
}
async function renderUsers(content){
  const users=(await api('/api/users')).users;
  const form=node('form');const name=node('input',{required:true,maxLength:200});const login=node('input',{required:true,minLength:3,maxLength:80});const password=node('input',{type:'password',required:true,minLength:12,maxLength:128,autocomplete:'new-password'});const role=node('select',{},Object.entries(roles).map(([k,v])=>node('option',{value:k},v)));
  form.append(node('div',{class:'grid'},label('Nome',name),label('Login',login),label('Senha inicial',password,'Mínimo de 12 caracteres; orientar troca no primeiro acesso.'),label('Perfil',role)),node('div',{class:'actions'},node('button',{type:'submit',class:'primary'},'Criar usuário')));
  submit(form,async()=>{await api('/api/users','POST',{nome:name.value,usuario:login.value,senha:password.value,papel:role.value});password.value='';await load();message('Usuário criado.','success');});
  content.append(card(node('h2',{},'Novo usuário'),form));
  for(const u of users){
    const enabled=node('input',{type:'checkbox',checked:u.ativo,disabled:u.id===user.id});const checks={};
    const grid=node('div',{class:'grid'});
    for(const [p,title] of Object.entries(perms)){checks[p]=node('input',{type:'checkbox',checked:u.permissoes[p],disabled:u.papel==='ADMIN'});grid.append(node('label',{class:'check'},checks[p],title));}
    content.append(card(node('h2',{},u.nome+' • '+u.usuario+' • '+roles[u.papel]),node('label',{class:'check'},enabled,'Conta ativa'),grid,
      node('div',{class:'actions'},button('Salvar acessos',async()=>{
        await api('/api/users/'+encodeURIComponent(u.id),'PUT',{ativo:enabled.checked,permissoes:Object.fromEntries(Object.entries(checks).map(([k,v])=>[k,v.checked]))});await load();message('Acessos atualizados. Sessões anteriores foram encerradas.','success');
      },'primary'),u.id!==user.id?button('Redefinir senha',async()=>{
        const reset=node('form');const current=node('input',{type:'password',required:true,maxLength:128,autocomplete:'current-password'});const fresh=node('input',{type:'password',required:true,minLength:12,maxLength:128,autocomplete:'new-password'});
        reset.append(node('h3',{},'Redefinir senha de '+u.usuario),label('Sua senha de administrador',current),label('Nova senha do usuário',fresh),node('div',{class:'actions'},node('button',{type:'submit',class:'primary'},'Confirmar redefinição'),button('Cancelar',()=>reset.remove())));
        content.append(card(reset));reset.scrollIntoView({block:'center'});
        submit(reset,async()=>{await api('/api/users/'+encodeURIComponent(u.id)+'/password','POST',{current:current.value,new:fresh.value});current.value='';fresh.value='';await load();message('Senha redefinida e sessões encerradas.','success');});
      }):null)));
  }
}
function renderSettings(content){
  const form=node('form');const inputs={};
  const rows=Object.entries(state.specs).map(([k,s])=>{
    const enabled=node('input',{type:'checkbox',checked:state.enabled[k]});const min=node('input',{value:s.min,maxLength:100});const max=node('input',{value:s.max,maxLength:100});const ref=node('input',{value:s.ref,maxLength:500});const method=node('input',{value:s.method,maxLength:500});inputs[k]={enabled,min,max,ref,method};
    return [s.label,s.unit,enabled,min,max,ref,method];
  });
  form.append(table(['Parâmetro','Unidade','Habilitado','Mínimo','Máximo','Referência','Método'],rows),node('div',{class:'actions'},node('button',{type:'submit',class:'primary'},'Salvar especificações')));
  submit(form,async()=>{
    const specs=structuredClone(state.specs);const enabled={};
    for(const [k,values] of Object.entries(inputs)){for(const f of ['min','max','ref','method'])specs[k][f]=values[f].value;enabled[k]=values.enabled.checked;}
    await api('/api/settings','PUT',{specs,enabled});await load();message('Configuração salva. Laudos anteriores preservam os critérios usados na análise.','success');
  });content.append(node('div',{class:'notice'},'Os limites vieram do aplicativo original e precisam de revisão pela responsável técnica. Não representam validação legal automática. Mudanças não alteram laudos já registrados.'),card(form));
}
function download(data,name,type){
  const url=URL.createObjectURL(new Blob([data],{type}));const a=node('a',{href:url,download:name});document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function safeCsv(value){
  let s=String(value??'');if(/^[\s\u0000-\u001f]*[=+\-@]/.test(s)||/^[\t\r\n]/.test(s))s="'"+s;
  return '"'+s.replaceAll('"','""')+'"';
}
async function exportCsv(){
  const data=await api('/api/export');
  const rows=[['Laudo','Amostra','Tambor','Lote','Temperatura','Produtor','Recebimento','Análise','Analista','Parecer','Status','Criado por','Liberado por',...Object.values(state.specs).map(s=>s.label)]];
  for(const s of data.samples)rows.push([s.lau,s.amostra,s.tambor,s.loteAmostra,s.temperaturaAmostra,s.produtor,s.dtReceb,s.dtAnalise,s.analista,s.parecer,s.status,s.createdBy,s.releasedBy,...Object.keys(state.specs).map(k=>s.results[k]??'')]);
  download('\ufeff'+rows.map(r=>r.map(safeCsv).join(';')).join('\r\n'),'Maxbem_Resultados.csv','text/csv;charset=utf-8');
}
function renderBackup(content){
  const input=node('input',{type:'file',accept:'.json,application/json','aria-label':'Selecionar banco ou backup antigo'});
  content.append(card(node('h2',{},'Proteção e recuperação'),node('p',{},'Banco privado por conta do sistema. Windows: %LOCALAPPDATA%\\MaxbemLaboratorio\\Dados. Mac: ~/Library/Application Support/MaxbemLaboratorio/Dados. Backups completos incluem contas e hashes de senha; proteja-os como o banco.'),
    node('p',{},'São mantidas 30 cópias locais. Copie backups também para uma mídia externa protegida. Cópias no mesmo disco não protegem contra falha do computador.'),
    node('div',{class:'actions'},button('Verificar integridade',async()=>{const r=await api('/api/integrity');message(r.message,'success');}),button('Criar backup completo',async()=>{const r=await api('/api/backup','POST',{});message('Cópia verificada: '+r.file,'success');}),button('Exportar dados JSON',async()=>{const r=await api('/api/backup/export');download(JSON.stringify(r,null,2),'Maxbem_Dados.json','application/json');})),
    node('div',{class:'actions'},button('Encerrar aplicativo',async()=>{
      if(!confirm('Encerrar o servidor Maxbem? Todas as sessões serão desconectadas.'))return;
      await api('/api/shutdown','POST',{});user=null;csrf='';state=null;samples=[];printArea.replaceChildren();
      root.replaceChildren(node('div',{class:'auth'},card(node('h1',{},'Aplicativo encerrado'),node('p',{},'Feche esta aba. Para voltar, abra o Maxbem pelo ícone.'))));
    })),
    node('p',{class:'muted'},'Para restaurar contas, liberação e histórico completos, feche o servidor e use Restaurar backup.command no Mac ou RESTAURAR_BACKUP.cmd no Windows com uma cópia SQLite. A cópia anterior será preservada.')),
    card(node('h2',{},'Migrar banco antigo / importar dados'),node('p',{class:'notice'},'Disponível somente sem amostras no banco novo. Não apaga a origem. Senhas antigas não serão importadas e liberações antigas exigirão revisão.'),input,
    node('div',{class:'actions'},button('Validar e importar',async()=>{
      const file=input.files[0];if(!file)throw new Error('Selecione store.json ou um backup JSON.');
      if(file.size>16*1024*1024)throw new Error('Arquivo acima do limite de 16 MB.');
      if(!confirm('Importar no banco novo? Revise os dados e recrie as contas depois.'))return;
      let data;try{data=JSON.parse(await file.text());}catch{throw new Error('JSON inválido.');}
      const r=await api('/api/legacy-import','POST',data);await load();message(r.message+' Amostras: '+r.count,'success');
    }))),card(node('h2',{},'Auditoria'),button('Carregar últimos 500 eventos',async()=>{
      const data=await api('/api/audit');const host=document.getElementById('audit');host.replaceChildren(table(['Data UTC','Usuário','Evento','Registro'],data.events.map(e=>[e.at,e.actor,e.event,e.target])));
    }),node('div',{id:'audit'})));
}
function renderAccount(content){
  const form=node('form');const old=node('input',{type:'password',required:true,maxLength:128,autocomplete:'current-password'});const password=node('input',{type:'password',required:true,minLength:12,maxLength:128,autocomplete:'new-password'});const confirmation=node('input',{type:'password',required:true,minLength:12,maxLength:128,autocomplete:'new-password'});
  form.append(node('div',{class:'grid'},label('Senha atual',old),label('Nova senha',password),label('Confirme a nova senha',confirmation)),node('div',{class:'actions'},node('button',{type:'submit',class:'primary'},'Alterar senha')));
  submit(form,async()=>{if(password.value!==confirmation.value)throw new Error('As senhas não coincidem.');await api('/api/password','POST',{current:old.value,new:password.value});old.value='';password.value='';confirmation.value='';user=null;state=null;samples=[];csrf='';printArea.replaceChildren();renderLogin();message('Senha alterada. Entre novamente.','success');});
  content.append(card(node('h2',{},'Trocar senha'),form));
}
async function printSample(id,labelMode){
  const result=await api('/api/samples/'+encodeURIComponent(id)+(labelMode?'/label':'/report'));
  const s=result.sample;
  document.body.classList.toggle('label-mode',labelMode);
  const out=node('div',{class:labelMode?'label-print':'report'});
  out.append(node('div',{class:'report-head'},node('img',{src:logoPath,alt:'Maxbem'}),node('div',{},node('h1',{},labelMode?'Identificação da amostra':'Laudo analítico de mel'),node('strong',{},s.lau))),
    s.status!=='LIBERADA'?node('p',{class:'report-warning'},'RASCUNHO — ANÁLISE NÃO LIBERADA'):null,
    node('div',{class:'report-meta'},Object.entries(fields).filter(([k])=>!labelMode||!['obs','acaoReprovada'].includes(k)).map(([k,title])=>node('div',{},node('strong',{},title+': '),node('span',{class:'detail'},s[k]||'—')))),
    node('p',{},'Parecer: ',s.parecer),labelMode?table(['Parâmetro','Resultado','Situação'],Object.entries(s.specSnapshot).filter(([k])=>s.reportEnabled[k]).map(([k,v])=>[v.label,(s.results[k]||'—')+' '+v.unit,s.parameterStatus[k]])):resultsTable(s),
    node('p',{},'Responsável pela análise: ',s.analista||s.createdBy||'—'),node('p',{},'Liberação: ',s.releasedBy||'Aguardando',' • ',s.releasedAt||''),
    node('div',{class:'notes'},node('p',{},'Os resultados referem-se exclusivamente à amostra identificada e aos critérios registrados na análise. Parâmetros sem especificação não demonstram conformidade. Este documento não constitui certificação orgânica nem assinatura digital.'),node('p',{},'Emitido em '+new Date().toLocaleString('pt-BR')+' • Revisão '+s.revision)));
  printArea.replaceChildren(out);
  const img=out.querySelector('img');try{await img.decode();}catch{}
  window.print();
}
window.addEventListener('afterprint',()=>{printArea.replaceChildren();document.body.classList.remove('label-mode');});
async function init(){
  // Recursos de marca em formato fixo; nenhuma dependência remota.
  for(const ext of ['png','jpeg','webp']){const r=await fetch('/logo.'+ext);if(r.ok){logoPath='/logo.'+ext;break;}}
  const health=await api('/api/health');
  if(!health.configured){renderLogin(true);if(!setupToken)message('Feche o servidor e abra pelo iniciador para autorizar o primeiro cadastro.');return;}
  try{const r=await api('/api/session');user=r.user;csrf=r.csrf;await load();}catch{renderLogin();}
}
guard(init);
