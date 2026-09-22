const databaseSeed = [
  { name: 'ERP Anexar Produção', short: 'A', version: 'Firebird 3.0', ods: 'ODS 12', env: 'Produção', tables: 86, objects: 342, routes: 124, progress: 100, status: 'Mapeado', updated: 'há 12 min' },
  { name: 'Comercial Demo', short: 'C', version: 'Firebird 3.0', ods: 'ODS 12', env: 'Homologação', tables: 54, objects: 221, routes: 76, progress: 92, status: 'Revisão', updated: 'há 1h' },
  { name: 'Provisionador Core', short: 'P', version: 'Firebird 4.0', ods: 'ODS 13.1', env: 'Produção', tables: 31, objects: 148, routes: 48, progress: 78, status: 'Mapeando', updated: 'ontem' },
  { name: 'Legado Financeiro', short: 'L', version: 'Firebird 2.5', ods: 'ODS 11.2', env: 'Desenvolvimento', tables: 42, objects: 186, routes: 0, progress: 32, status: 'Atenção', updated: 'há 3 dias' }
];

const engineProfiles = [
  { id:'firebird', name:'Firebird', icon:'🔥', ext:'.fdb, .sql', parser:'DDL + system tables', status:'Pronto' },
  { id:'postgres', name:'PostgreSQL', icon:'🐘', ext:'.sql, .dump', parser:'information_schema', status:'Pronto' },
  { id:'mysql', name:'MySQL', icon:'◆', ext:'.sql', parser:'information_schema', status:'Pronto' },
  { id:'mariadb', name:'MariaDB', icon:'◇', ext:'.sql', parser:'information_schema', status:'Pronto' },
  { id:'sqlserver', name:'SQL Server', icon:'▣', ext:'.sql, .bak, .dacpac', parser:'sys catalog', status:'Pronto' },
  { id:'mongo', name:'MongoDB', icon:'●', ext:'.json, .bson', parser:'collections + samples', status:'Experimental' },
  { id:'node', name:'Node/ORM', icon:'JS', ext:'.js, .ts, prisma', parser:'models/entities', status:'Experimental' },
  { id:'other', name:'Outro', icon:'＋', ext:'.zip, .json', parser:'adaptador futuro', status:'Planejado' }
];

const mappedRouteTemplates = {
  firebird: [
    ['GET','/clientes','CLIENTES','Tabela','clientes:read','98%'],
    ['POST','/clientes','CLIENTES','Tabela','clientes:write','96%'],
    ['GET','/produtos','PRODUTOS','Tabela','produtos:read','99%'],
    ['POST','/vendas','SP_FECHAR_VENDA','Procedure','vendas:write','91%'],
    ['GET','/estoque/saldos','SP_SALDO_ESTOQUE','Procedure','estoque:read','94%']
  ],
  postgres: [
    ['GET','/customers','public.customers','Tabela','customers:read','99%'],
    ['POST','/orders','sales.orders','Tabela','orders:write','96%'],
    ['GET','/products','catalog.products','Tabela','products:read','98%'],
    ['GET','/invoices/open','finance.open_invoices','View','finance:read','93%'],
    ['POST','/stock/recalculate','inventory.recalculate_stock()','Function','stock:write','89%']
  ],
  mysql: [
    ['GET','/clientes','clientes','Tabela','clientes:read','98%'],
    ['GET','/pedidos','pedidos','Tabela','pedidos:read','96%'],
    ['POST','/pedidos','pedidos','Tabela','pedidos:write','94%'],
    ['GET','/produtos','produtos','Tabela','produtos:read','98%']
  ],
  mariadb: [
    ['GET','/clientes','clientes','Tabela','clientes:read','97%'],
    ['GET','/vendas','vendas','Tabela','vendas:read','95%'],
    ['PATCH','/produtos/{id}','produtos','Tabela','produtos:write','92%']
  ],
  sqlserver: [
    ['GET','/dbo/customers','dbo.Customers','Tabela','customers:read','98%'],
    ['GET','/sales/orders','sales.Orders','Tabela','orders:read','97%'],
    ['POST','/sales/orders','sales.usp_CreateOrder','Procedure','orders:write','90%'],
    ['GET','/reports/cashflow','finance.vw_CashFlow','View','finance:read','93%']
  ],
  mongo: [
    ['GET','/customers','customers','Coleção','customers:read','86%'],
    ['POST','/orders','orders','Coleção','orders:write','82%'],
    ['GET','/products','products','Coleção','products:read','88%'],
    ['GET','/events/audit','audit_events','Coleção','audit:read','79%']
  ],
  node: [
    ['GET','/users','UserModel','Model','users:read','90%'],
    ['POST','/orders','OrderEntity','Entity','orders:write','88%'],
    ['GET','/products','ProductSchema','Schema','products:read','91%'],
    ['PATCH','/customers/{id}','CustomerService','Service','customers:write','76%']
  ],
  other: [
    ['GET','/resources','resource_map.json','Inferido','resources:read','62%'],
    ['POST','/resources','resource_map.json','Inferido','resources:write','58%']
  ]
};

const objectData = {
  tables: [
    { name:'CLIENTES', count:'28 campos' }, { name:'PRODUTOS', count:'34 campos' }, { name:'VENDAS', count:'41 campos' }, { name:'ITENS_VENDA', count:'18 campos' }, { name:'CONTAS_RECEBER', count:'26 campos' }, { name:'FORNECEDORES', count:'21 campos' }, { name:'ESTOQUE', count:'17 campos' }, { name:'EMPRESAS', count:'19 campos' }, { name:'USUARIOS', count:'14 campos' }, { name:'FORMAS_PAGAMENTO', count:'12 campos' }
  ],
  triggers: [
    { name:'TRG_CLIENTES_BI', count:'BEFORE INSERT' }, { name:'TRG_VENDAS_AI', count:'AFTER INSERT' }, { name:'TRG_ESTOQUE_AU', count:'AFTER UPDATE' }, { name:'TRG_PRODUTOS_BI', count:'BEFORE INSERT' }, { name:'TRG_AUDITORIA', count:'AFTER UPDATE' }
  ],
  procedures: [
    { name:'SP_FECHAR_VENDA', count:'7 parâmetros' }, { name:'SP_SALDO_ESTOQUE', count:'3 parâmetros' }, { name:'SP_FLUXO_CAIXA', count:'4 parâmetros' }, { name:'SP_RECALCULAR_TOTAIS', count:'2 parâmetros' }, { name:'SP_RELATORIO_VENDAS', count:'5 parâmetros' }
  ]
};

const routes = [
  { tag:'Clientes', method:'GET', path:'/clientes', title:'Listar clientes', desc:'Retorna uma coleção paginada de clientes respeitando o tenant autenticado.', permission:'clientes:read', params:[['page','query','integer','Página atual'],['limit','query','integer','Itens por página'],['search','query','string','Nome, CPF ou CNPJ']] },
  { tag:'Clientes', method:'GET', path:'/clientes/{id}', title:'Consultar cliente', desc:'Retorna os dados de um cliente pelo identificador primário.', permission:'clientes:read', params:[['id','path','integer','Identificador do cliente']] },
  { tag:'Clientes', method:'POST', path:'/clientes', title:'Criar cliente', desc:'Cria um novo cadastro de cliente dentro do tenant autenticado.', permission:'clientes:write', params:[['body','body','object','Payload do novo cliente']] },
  { tag:'Produtos', method:'GET', path:'/produtos', title:'Listar produtos', desc:'Lista produtos com preço, saldo e situação cadastral.', permission:'produtos:read', params:[['page','query','integer','Página atual'],['search','query','string','Código ou descrição'],['ativo','query','boolean','Filtrar situação']] },
  { tag:'Produtos', method:'PATCH', path:'/produtos/{id}', title:'Atualizar produto', desc:'Atualiza campos permitidos de um produto existente.', permission:'produtos:write', params:[['id','path','integer','Identificador do produto'],['body','body','object','Campos alterados']] },
  { tag:'Vendas', method:'GET', path:'/vendas', title:'Listar vendas', desc:'Consulta vendas por período, cliente ou situação.', permission:'vendas:read', params:[['inicio','query','date','Data inicial'],['fim','query','date','Data final'],['status','query','string','Situação da venda']] },
  { tag:'Vendas', method:'POST', path:'/vendas', title:'Registrar venda', desc:'Registra uma venda e seus itens em uma transação atômica.', permission:'vendas:write', params:[['body','body','object','Venda, itens e pagamentos']] },
  { tag:'Financeiro', method:'GET', path:'/financeiro/contas-receber', title:'Consultar contas a receber', desc:'Retorna títulos financeiros conforme período e situação.', permission:'financeiro:read', params:[['vencimento_inicio','query','date','Início do período'],['vencimento_fim','query','date','Fim do período']] },
  { tag:'Estoque', method:'GET', path:'/estoque/saldos', title:'Consultar saldo', desc:'Retorna saldos disponíveis por produto e depósito.', permission:'estoque:read', params:[['produto_id','query','integer','Produto consultado'],['deposito_id','query','integer','Depósito de estoque']] }
];

const clientSeed = [
  { name:'Orion Autopeças • Demo', initials:'OA', cnpj:'00.000.000/0001-01', database:'ERP Anexar Produção', keys:2, status:'Ativo' },
  { name:'Contábil Horizonte • Demo', initials:'CH', cnpj:'00.000.000/0002-02', database:'ERP Anexar Produção', keys:1, status:'Ativo' },
  { name:'Loja Aurora • Demo', initials:'LA', cnpj:'00.000.000/0003-03', database:'Comercial Demo', keys:1, status:'Homologação' },
  { name:'Nova Sul Distribuidora • Demo', initials:'NS', cnpj:'00.000.000/0004-04', database:'ERP Anexar Produção', keys:0, status:'Inativo' }
];

let databases = [...databaseSeed];
let clients = [...clientSeed];
let currentObjectTab = 'tables';
let currentObject = objectData.tables[0];
let selectedRoute = routes[0];
let routeFilter = 'ALL';
let selectedClient = clients[0];
let selectedEngine = 'firebird';
let latestMapping = { engine:'firebird', file:'erp_demo.fdb', name:'ERP Anexar Produção', env:'Homologação', routes:mappedRouteTemplates.firebird };

const $ = (s, root=document) => root.querySelector(s);
const $$ = (s, root=document) => [...root.querySelectorAll(s)];

function showToast(title, detail='Ação concluída no ambiente demonstrativo.') {
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.innerHTML = `<span>✓</span><div><strong>${title}</strong><small>${detail}</small></div>`;
  $('#toastStack').appendChild(toast);
  setTimeout(()=>{ toast.classList.add('out'); setTimeout(()=>toast.remove(),220); }, 3600);
}

function navigate(view) {
  $$('.view').forEach(v=>v.classList.toggle('active', v.id === `view-${view}`));
  $$('.nav-item').forEach(n=>n.classList.toggle('active', n.dataset.view === view));
  const labels = {overview:'Visão geral',databases:'Bancos',mapper:'Upload & rotas',catalog:'Catálogo',routes:'Rotas & Swagger',clients:'Clientes & chaves'};
  $('#currentCrumb').textContent = labels[view];
  $('#sidebar').classList.remove('open');
  window.scrollTo({top:0,behavior:'smooth'});
}

$$('.nav-item').forEach(btn=>btn.addEventListener('click',()=>navigate(btn.dataset.view)));
$$('[data-nav]').forEach(btn=>btn.addEventListener('click',()=>navigate(btn.dataset.nav)));
$('#mobileMenu').addEventListener('click',()=>$('#sidebar').classList.toggle('open'));

function statusClass(status){ return status==='Mapeado'||status==='Ativo'?'success':status==='Revisão'||status==='Homologação'?'info':status==='Atenção'||status==='Inativo'?'danger':'warning'; }

function renderEngines(){
  $('#engineGrid').innerHTML = engineProfiles.map(engine=>`
    <button class="engine-card ${selectedEngine===engine.id?'active':''}" data-engine="${engine.id}" type="button">
      <span class="engine-icon">${engine.icon}</span>
      <strong>${engine.name}</strong>
      <small>${engine.ext}</small>
      <b class="pill ${engine.status==='Pronto'?'success':engine.status==='Experimental'?'warning':'neutral'}">${engine.status}</b>
    </button>`).join('');
  $$('[data-engine]').forEach(button=>button.addEventListener('click',()=>{
    selectedEngine = button.dataset.engine;
    $('#selectedEnginePill').textContent = engineProfiles.find(e=>e.id===selectedEngine).name;
    renderEngines();
    simulateMapping({ keepName:true });
  }));
}

function simulateMapping(options={}){
  const form = $('#schemaUploadForm');
  const data = form ? new FormData(form) : new FormData();
  const profile = engineProfiles.find(e=>e.id===selectedEngine);
  latestMapping = {
    engine:selectedEngine,
    file: $('#schemaFileInput')?.files?.[0]?.name || (selectedEngine==='postgres'?'schema_postgre_demo.sql':'estrutura_demo.zip'),
    name: options.keepName ? (data.get('schemaName') || 'ERP Multibanco Demo') : (data.get('schemaName') || 'ERP Multibanco Demo'),
    env: data.get('schemaEnv') || 'Homologação',
    routes: mappedRouteTemplates[selectedEngine] || mappedRouteTemplates.other,
    profile
  };
  renderValidation();
  renderMappedRoutes();
}

function renderValidation(){
  const routeCount = latestMapping.routes.length;
  const objectCount = selectedEngine==='mongo' ? 19 : selectedEngine==='node' ? 27 : 143;
  const profile = latestMapping.profile || engineProfiles.find(e=>e.id===latestMapping.engine);
  $('#validationPanel').innerHTML = `
    <div class="validation-head"><span class="engine-icon large">${profile.icon}</span><div><h2>${profile.name}</h2><p>${profile.parser} • ${latestMapping.file}</p></div></div>
    <div class="validation-score"><span>Confiança do mapeamento</span><strong>${selectedEngine==='other'?'64':'93'}%</strong><div class="progress-bar"><i style="width:${selectedEngine==='other'?'64':'93'}%"></i></div></div>
    <div class="validation-list">
      <div><span class="check-badge">✓</span><strong>Formato reconhecido</strong><small>Extensão e origem aceitas no sandbox</small></div>
      <div><span class="check-badge">✓</span><strong>Objetos identificados</strong><small>${objectCount} tabelas, coleções, views ou modelos</small></div>
      <div><span class="check-badge">✓</span><strong>Rotas sugeridas</strong><small>${routeCount} endpoints prontos para revisão</small></div>
      <div><span class="check-badge warn">!</span><strong>Revisão necessária</strong><small>Escrita, procedures e funções críticas exigem aprovação</small></div>
    </div>
    <button class="secondary-button full" style="width:100%;margin:18px 0 0" id="openMappingSwagger">Abrir documentação gerada</button>`;
  $('#openMappingSwagger').addEventListener('click',()=>navigate('routes'));
}

function renderMappedRoutes(){
  const summary = [
    ['Origem', latestMapping.profile.name],
    ['Estrutura', latestMapping.name],
    ['Ambiente', latestMapping.env],
    ['Rotas propostas', latestMapping.routes.length]
  ];
  $('#mappingSummary').innerHTML = summary.map(item=>`<div><span>${item[0]}</span><strong>${item[1]}</strong></div>`).join('');
  $('#mappedRoutesTable').innerHTML = `
    <div class="mapped-row mapped-head"><span>MÉTODO</span><span>ROTA</span><span>ORIGEM</span><span>TIPO</span><span>ESCOPO</span><span>CONFIANÇA</span></div>
    ${latestMapping.routes.map(route=>`<div class="mapped-row"><span><b class="method ${route[0]}">${route[0]}</b></span><code>${route[1]}</code><span>${route[2]}</span><span>${route[3]}</span><span>${route[4]}</span><span>${route[5]}</span></div>`).join('')}`;
}

function renderDatabases(filter='') {
  const filtered = databases.filter(db=>`${db.name} ${db.version} ${db.env}`.toLowerCase().includes(filter.toLowerCase()));
  $('#overviewDbList').innerHTML = filtered.slice(0,3).map(db=>`
    <div class="db-row">
      <div class="db-identity"><span class="db-square">${db.short}</span><span><strong>${db.name}</strong><small>${db.version} • ${db.ods}</small></span></div>
      <div class="db-stat"><small>OBJETOS</small><strong>${db.objects}</strong></div>
      <div class="progress-cell"><div class="progress-bar"><i style="width:${db.progress}%"></i></div><b>${db.progress}%</b></div>
      <span><b class="pill ${statusClass(db.status)}">${db.status}</b></span><button class="row-chevron" data-open-db="${db.name}">›</button>
    </div>`).join('');
  $('#databaseGrid').innerHTML = filtered.map(db=>`
    <article class="panel database-card">
      <div class="database-card-header"><div class="db-identity"><span class="db-square">${db.short}</span><span><h3>${db.name}</h3><small>${db.version} • ${db.ods} • Atualizado ${db.updated}</small></span></div><button class="card-menu">•••</button></div>
      <div class="database-card-meta"><div><span>Ambiente</span><strong>${db.env}</strong></div><div><span>Objetos</span><strong>${db.objects}</strong></div><div><span>Rotas</span><strong>${db.routes}</strong></div></div>
      <div class="mapping-row"><span>Mapeamento</span><b>${db.progress}%</b></div><div class="progress-bar"><i style="width:${db.progress}%"></i></div>
      <div class="database-card-actions"><button class="secondary-button" data-open-db="${db.name}">Explorar schema</button><button class="secondary-button" data-open-routes="${db.name}">Ver rotas</button></div>
    </article>`).join('') || `<div class="panel" style="padding:30px;text-align:center;color:var(--muted)">Nenhum banco encontrado.</div>`;
  $$('[data-open-db]').forEach(b=>b.addEventListener('click',()=>{navigate('catalog');showToast('Schema selecionado',b.dataset.openDb);}));
  $$('[data-open-routes]').forEach(b=>b.addEventListener('click',()=>{navigate('routes');showToast('Rotas filtradas',b.dataset.openRoutes);}));
}

function renderObjectTree(filter='') {
  const items = objectData[currentObjectTab].filter(o=>o.name.toLowerCase().includes(filter.toLowerCase()));
  $('#objectTree').innerHTML = items.map((o,i)=>`<button class="object-item ${currentObject.name===o.name?'active':''}" data-object="${o.name}"><span class="object-icon">${currentObjectTab==='tables'?'▦':currentObjectTab==='triggers'?'⚡':'ƒ'}</span><span>${o.name}</span><small>${o.count}</small></button>`).join('');
  $$('[data-object]').forEach(b=>b.addEventListener('click',()=>{currentObject=objectData[currentObjectTab].find(o=>o.name===b.dataset.object);renderObjectTree($('#objectSearch').value);renderObjectDetail();}));
}

function renderObjectDetail(){
  const isTable=currentObjectTab==='tables';
  const fields=[['ID_CLIENTE','INTEGER','Não','PK','Identificador primário'],['NOME','VARCHAR(120)','Não','—','Nome ou razão social'],['CNPJ_CPF','VARCHAR(18)','Sim','IDX','Documento normalizado'],['EMAIL','VARCHAR(120)','Sim','—','E-mail principal'],['ATIVO','SMALLINT','Não','—','Situação do cadastro'],['DT_CADASTRO','TIMESTAMP','Não','—','Data de criação']];
  $('#objectDetail').innerHTML=`
    <div class="object-detail-head"><div><h2>${currentObject.name}</h2><p>${isTable?'Tabela de negócio mapeada automaticamente.':currentObjectTab==='triggers'?'Trigger identificado no schema Firebird.':'Stored procedure identificada no schema Firebird.'}</p></div><div class="detail-actions"><button class="secondary-button" id="viewSql">Ver DDL</button><button class="primary-button" id="goObjectRoute">${isTable?'Abrir rotas':'Ver dependências'}</button></div></div>
    <div class="detail-summary"><div><span>TIPO</span><strong>${isTable?'Tabela':currentObjectTab==='triggers'?'Trigger':'Procedure'}</strong></div><div><span>CAMPOS / PARÂMETROS</span><strong>${isTable?'28':'7'}</strong></div><div><span>DEPENDÊNCIAS</span><strong>${isTable?'6':'3'}</strong></div><div><span>CONFIANÇA</span><strong>98,4%</strong></div></div>
    <div class="detail-section"><h3>${isTable?'Campos mapeados':'Definição e dependências'}</h3>
      ${isTable?`<div class="fields-table"><div class="field-row head"><span>CAMPO</span><span>TIPO</span><span>NULO</span><span>ÍNDICE</span><span>DESCRIÇÃO</span></div>${fields.map(f=>`<div class="field-row"><code>${f[0]}${f[3]==='PK'?'<i class="field-key">PK</i>':''}</code><span>${f[1]}</span><span>${f[2]}</span><span>${f[3]}</span><span>${f[4]}</span></div>`).join('')}</div>`:`<div class="fields-table"><div class="field-row head"><span>OBJETO</span><span>OPERAÇÃO</span><span>ORDEM</span><span>ESTADO</span><span>RELAÇÃO</span></div><div class="field-row"><code>CLIENTES</code><span>INSERT</span><span>1</span><span>Ativo</span><span>Dependência direta</span></div><div class="field-row"><code>GEN_CLIENTES_ID</code><span>GEN_ID</span><span>2</span><span>Ativo</span><span>Gera chave primária</span></div></div>`}
    </div>
    <div class="detail-section"><h3>Correspondência na API</h3><div class="mapping-box"><span class="object-icon">↗</span><div><strong>/v1/${currentObject.name.toLowerCase().replaceAll('_','-')}</strong><p style="margin:4px 0 0;font-size:9px;color:var(--muted)">${isTable?'Coleção REST gerada a partir da chave primária e regras de acesso.':'Exposição indireta; requer revisão manual.'}</p></div><span class="method GET">${isTable?'GET':'INTERNO'}</span></div></div>`;
  $('#viewSql').addEventListener('click',()=>showToast('DDL carregado','Visualização simulada do objeto selecionado.'));
  $('#goObjectRoute').addEventListener('click',()=>isTable?navigate('routes'):showToast('Dependências verificadas','3 relações encontradas no schema.'));
}

function renderRoutes(filter=''){
  const filtered=routes.filter(r=>(routeFilter==='ALL'||r.method===routeFilter)&&`${r.path} ${r.tag} ${r.title}`.toLowerCase().includes(filter.toLowerCase()));
  const groups=[...new Set(filtered.map(r=>r.tag))];
  $('#routeList').innerHTML=groups.map(g=>`<div class="route-group-title">${g}</div>${filtered.filter(r=>r.tag===g).map(r=>`<button class="route-item ${selectedRoute===r?'active':''}" data-route="${r.method}|${r.path}"><span class="method ${r.method}">${r.method}</span><code>${r.path}</code></button>`).join('')}`).join('')||`<div style="padding:25px;text-align:center;color:var(--muted);font-size:10px">Nenhuma rota encontrada.</div>`;
  $$('[data-route]').forEach(b=>b.addEventListener('click',()=>{const [method,path]=b.dataset.route.split('|');selectedRoute=routes.find(r=>r.method===method&&r.path===path);renderRoutes($('#routeSearch').value);renderRouteDocument();}));
}

function renderRouteDocument(){
  const r=selectedRoute;
  $('#routeDocument').innerHTML=`
    <div class="route-doc-head"><div class="route-doc-title"><span class="method ${r.method}">${r.method}</span><code>${r.path}</code><span class="pill success">Ativa</span></div><p>${r.desc}</p><div class="route-doc-meta"><span>Tag <b>${r.tag}</b></span><span>Escopo <b>${r.permission}</b></span><span>Versão <b>v1</b></span></div></div>
    <div class="doc-tabs"><button class="active">Documentação</button><button>Schema</button><button>Exemplos</button></div>
    <div class="doc-body"><h3>Parâmetros</h3><div class="parameter-table"><div class="parameter-row head"><span>NOME</span><span>LOCAL</span><span>TIPO</span><span>DESCRIÇÃO</span></div>${r.params.map(p=>`<div class="parameter-row"><code>${p[0]}</code><span>${p[1]}</span><span>${p[2]}</span><span>${p[3]}</span></div>`).join('')}</div>
      <div class="try-console"><div class="try-head"><div><h3>Testar requisição</h3><small>Execução segura com dados demonstrativos</small></div><span class="pill neutral">Sandbox</span></div><div class="try-body"><div class="try-fields"><label>Tenant<select id="tryTenant" style="border:1px solid var(--line-strong);border-radius:8px;padding:9px;font-size:10px"><option>Orion Autopeças • Demo</option><option>Contábil Horizonte • Demo</option></select></label><label>Autorização<input value="fb_live_•••••••••••A91C" readonly /></label></div>${r.method==='POST'||r.method==='PATCH'?`<label style="display:grid;gap:6px;font-size:9px;font-weight:650">Request body<textarea id="requestBody">{\n  "nome": "Cliente demonstração",\n  "ativo": true\n}</textarea></label>`:`<div class="try-fields">${r.params.slice(0,2).map(p=>`<label>${p[0]}<input class="param-input" placeholder="${p[2]}" value="${p[0]==='page'?'1':p[0]==='limit'?'20':''}" /></label>`).join('')}</div>`}<div class="execute-row"><button class="primary-button" id="executeRequest">▶ Executar requisição</button></div><div id="responseArea"><div class="empty-response">A resposta aparecerá aqui sem realizar chamadas externas.</div></div></div></div>
    </div>`;
  $('#executeRequest').addEventListener('click',executeDemoRequest);
  $$('.doc-tabs button').forEach((b,i)=>b.addEventListener('click',()=>{ $$('.doc-tabs button').forEach(x=>x.classList.remove('active'));b.classList.add('active'); if(i>0)showToast(i===1?'Schema validado':'Exemplos carregados','Conteúdo demonstrativo disponível na documentação.');}));
}

function executeDemoRequest(){
  const area=$('#responseArea');
  area.innerHTML='<div class="empty-response">Executando no sandbox…</div>';
  setTimeout(()=>{
    const payload=selectedRoute.method==='POST'?{id:3892,nome:'Cliente demonstração',ativo:true,created_at:new Date().toISOString()}:{data:[{id:101,nome:'Orion Autopeças • Demo',ativo:true},{id:102,nome:'Contábil Horizonte • Demo',ativo:true}],meta:{page:1,limit:20,total:2}};
    area.innerHTML=`<div class="response-box"><div class="response-top"><span>RESPONSE • 184 ms</span><b>${selectedRoute.method==='POST'?'201 CREATED':'200 OK'}</b></div><pre>${JSON.stringify(payload,null,2)}</pre></div>`;
    showToast('Requisição executada','Resposta demonstrativa retornada pelo sandbox.');
  },650);
}

function renderClients(filter=''){
  const filtered=clients.filter(c=>`${c.name} ${c.cnpj} ${c.database}`.toLowerCase().includes(filter.toLowerCase()));
  $('#clientCount').textContent=`${clients.length} tenants cadastrados`;
  $('#clientsTable').innerHTML=`<div class="client-row head"><span>CLIENTE</span><span>BANCO</span><span>CHAVES</span><span>STATUS</span><span></span></div>${filtered.map(c=>`<div class="client-row ${selectedClient===c?'active':''}" data-client="${c.cnpj}"><div class="client-identity"><span class="client-avatar">${c.initials}</span><span><strong>${c.name}</strong><small>${c.cnpj}</small></span></div><span>${c.database}</span><span>${c.keys} ${c.keys===1?'chave':'chaves'}</span><span><b class="pill ${statusClass(c.status)}">${c.status}</b></span><span>›</span></div>`).join('')}`;
  $$('[data-client]').forEach(row=>row.addEventListener('click',()=>{selectedClient=clients.find(c=>c.cnpj===row.dataset.client);renderClients($('#clientSearch').value);renderKeyPanel();}));
}

function renderKeyPanel(){
  const c=selectedClient;
  $('#keyPanel').innerHTML=`<div class="key-panel-header"><div><h2>${c.name}</h2><p>${c.cnpj}<br>${c.database}</p></div><b class="pill ${statusClass(c.status)}">${c.status}</b></div><div class="key-summary"><div><span>CHAVES ATIVAS</span><strong>${c.keys}</strong></div><div><span>ÚLTIMO ACESSO</span><strong>${c.keys?'há 8 min':'—'}</strong></div></div>${c.keys?`<div class="key-card"><div class="key-card-head"><strong>Integração principal</strong><span class="pill success">Ativa</span></div><div class="masked-key"><span>fb_live_•••••••••••A91C</span><button title="Segredos não podem ser copiados">PROTEGIDA</button></div><div class="key-meta"><span>Fingerprint: 6F:2A:91:C4</span><span>Criada em 02/09/2026</span><span>Escopo: leitura</span><span>Expira em 90 dias</span></div><div class="key-actions"><button class="secondary-button" id="rotateKey">Rotacionar</button><button class="danger-button" id="revokeKey">Revogar</button></div></div>`:`<div style="padding:25px 10px;text-align:center;color:var(--muted);font-size:10px">Nenhuma credencial ativa para este tenant.</div>`}<button class="primary-button full" style="width:100%;margin:16px 0 0" data-open-modal="key">＋ Gerar nova API key</button>`;
  const rotate=$('#rotateKey'); if(rotate) rotate.addEventListener('click',()=>openModal('key'));
  const revoke=$('#revokeKey'); if(revoke) revoke.addEventListener('click',()=>{showToast('Chave revogada','A credencial demonstrativa deixou de aceitar requisições.');});
  $$('[data-open-modal="key"]').forEach(b=>b.addEventListener('click',()=>openModal('key')));
}

function openModal(type){const modal=$(`#${type}Modal`);modal.classList.add('open');modal.setAttribute('aria-hidden','false');setTimeout(()=>modal.querySelector('input')?.focus(),80)}
function closeModal(modal){modal.classList.remove('open');modal.setAttribute('aria-hidden','true')}
$$('[data-open-modal]').forEach(b=>b.addEventListener('click',()=>openModal(b.dataset.openModal)));
$$('[data-close-modal]').forEach(b=>b.addEventListener('click',()=>closeModal(b.closest('.modal-backdrop'))));
$$('.modal-backdrop').forEach(m=>m.addEventListener('click',e=>{if(e.target===m)closeModal(m)}));

$('#databaseForm').addEventListener('submit',e=>{e.preventDefault();const data=new FormData(e.currentTarget);const name=data.get('name');const engine=data.get('engine');const version=data.get('version')||'auto';const ods=engine==='Firebird'?(version.includes('4')?'ODS 13.1':version.includes('2.5')?'ODS 11.2':'ODS 12'):'Schema metadata';databases.unshift({name,short:name[0].toUpperCase(),version:`${engine} ${version}`,ods,env:data.get('environment'),tables:0,objects:0,routes:0,progress:8,status:'Mapeando',updated:'agora'});renderDatabases();closeModal($('#databaseModal'));e.currentTarget.reset();navigate('mapper');showToast('Estrutura cadastrada','A leitura demonstrativa foi enviada para validação multibanco.');});
$('#clientForm').addEventListener('submit',e=>{e.preventDefault();const data=new FormData(e.currentTarget);const name=data.get('name');const initials=name.split(' ').slice(0,2).map(x=>x[0]).join('').toUpperCase();const c={name,initials,cnpj:data.get('cnpj'),database:data.get('database'),keys:0,status:'Homologação'};clients.unshift(c);selectedClient=c;renderClients();renderKeyPanel();closeModal($('#clientModal'));e.currentTarget.reset();showToast('Tenant criado','Isolamento e vínculo de banco configurados.');});
$('#keyForm').addEventListener('submit',e=>{e.preventDefault();selectedClient.keys+=1;renderClients($('#clientSearch').value);renderKeyPanel();closeModal($('#keyModal'));showToast('API key provisionada','Segredo protegido; fingerprint 8B:11:7E:A2 registrado.');});

$('#dbSearch').addEventListener('input',e=>renderDatabases(e.target.value));
$('#objectSearch').addEventListener('input',e=>renderObjectTree(e.target.value));
$('#routeSearch').addEventListener('input',e=>renderRoutes(e.target.value));
$('#clientSearch').addEventListener('input',e=>renderClients(e.target.value));
$('#schemaFileInput').addEventListener('change',e=>{$('#schemaFileLabel').textContent=e.target.files[0]?.name || 'Selecionar estrutura, dump, JSON, modelos Node ou pacote .zip';});
$('#schemaUploadForm').addEventListener('submit',e=>{e.preventDefault();simulateMapping();showToast('Upload validado','Rotas sugeridas a partir da estrutura selecionada.');});
$('#loadDemoSchema').addEventListener('click',()=>{selectedEngine='postgres';$('#selectedEnginePill').textContent='PostgreSQL';$('#schemaFileLabel').textContent='schema_postgre_demo.sql';$('#schemaUploadForm').schemaName.value='Marketplace PostgreSQL Demo';renderEngines();simulateMapping();showToast('Demo PostgreSQL carregada','Estrutura demonstrativa pronta para revisão.');});
$('#promoteMappedRoutes').addEventListener('click',()=>{
  const promoted = latestMapping.routes.map(route=>({tag:latestMapping.profile.name,method:route[0],path:route[1],title:`${route[0]} ${route[2]}`,desc:`Rota gerada a partir de ${route[3].toLowerCase()} ${route[2]} no mapeamento ${latestMapping.profile.name}.`,permission:route[4],params:[['tenant','header','string','Tenant autorizado'],['api_key','header','string','Chave mascarada e validada por fingerprint']]}));
  routes.splice(0,0,...promoted);
  selectedRoute=routes[0];
  renderRoutes();
  renderRouteDocument();
  navigate('routes');
  showToast('Rotas enviadas para Swagger','Endpoints demonstrativos adicionados à documentação interativa.');
});
$$('[data-object-tab]').forEach(b=>b.addEventListener('click',()=>{currentObjectTab=b.dataset.objectTab;currentObject=objectData[currentObjectTab][0];$$('[data-object-tab]').forEach(x=>x.classList.toggle('active',x===b));renderObjectTree();renderObjectDetail();}));
$$('[data-method]').forEach(b=>b.addEventListener('click',()=>{routeFilter=b.dataset.method;$$('[data-method]').forEach(x=>x.classList.toggle('active',x===b));renderRoutes($('#routeSearch').value);}));
$('#syncCatalog').addEventListener('click',e=>{e.currentTarget.textContent='↻ Sincronizando…';setTimeout(()=>{e.currentTarget.textContent='↻ Sincronizar schema';showToast('Schema sincronizado','Nenhuma alteração estrutural encontrada.');},900)});
$('#publishRoutes').addEventListener('click',()=>showToast('Revisão preparada','18 rotas aguardam aprovação antes da publicação real.'));
$('#exportOpenApi').addEventListener('click',()=>{const spec={openapi:'3.1.0',info:{title:'Firebird API Demo',version:'1.0.0'},paths:Object.fromEntries(routes.map(r=>[r.path,{[r.method.toLowerCase()]:{summary:r.title}}]))};const blob=new Blob([JSON.stringify(spec,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='firebird-openapi-demo.json';a.click();URL.revokeObjectURL(a.href);showToast('OpenAPI exportado','Arquivo demonstrativo gerado localmente.');});
$$('[data-copy]').forEach(b=>b.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(b.dataset.copy);showToast('URL copiada')}catch{showToast('URL disponível',b.dataset.copy)}}));
$('#globalSearch').addEventListener('keydown',e=>{if(e.key==='Enter'){const q=e.target.value.toLowerCase();if(routes.some(r=>r.path.includes(q))){navigate('routes');$('#routeSearch').value=q;renderRoutes(q)}else if(databases.some(d=>d.name.toLowerCase().includes(q))){navigate('databases');$('#dbSearch').value=q;renderDatabases(q)}else if(clients.some(c=>c.name.toLowerCase().includes(q))){navigate('clients');$('#clientSearch').value=q;renderClients(q)}else showToast('Nenhum resultado','Tente buscar por “clientes”, “Anexar” ou “Orion”.')}});
document.addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();$('#globalSearch').focus()}if(e.key==='Escape')$$('.modal-backdrop.open').forEach(closeModal)});

renderDatabases();
renderEngines();
simulateMapping({keepName:true});
renderObjectTree();
renderObjectDetail();
renderRoutes();
renderRouteDocument();
renderClients();
renderKeyPanel();
