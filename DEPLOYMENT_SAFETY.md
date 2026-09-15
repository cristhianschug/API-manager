# Deployment Safety Plan - Zero Impact

**Objetivo:** Deploy FastAPI isolado, sem afetar projetos existentes no servidor.

---

## 1. ISOLAMENTO TOTAL (Docker)

### ✅ Tudo roda em container
```
Sem instalação global
Sem mudança de sistema
Sem conflito de portas
Sem acesso a outros dados
```

### Container do FastAPI
```
├─ Image: api-anexar:1.0
├─ Container: anexar-api-prod
├─ Porta interna: 8000
├─ Porta externa: 9000 (mapeada)
├─ Network: anexar-network (isolada)
├─ User: nobody (unprivileged)
└─ Recursos: 512MB RAM max, 0.5 CPU
```

---

## 2. PORTAS (Sem Conflito)

### Mapeamento Seguro
```
Seu servidor:
├─ Porta 80 (nginx público)
├─ Porta 443 (HTTPS público)
├─ Porta 3050 (Firebird, localhost only)
├─ Porta 9000 (API interna, ← NOVA, isolada)
└─ Porta 6379 (Redis opcional, localhost only)

Outros projetos:
├─ Qualquer porta > 9000: não tocamos
└─ Nenhum conflito: ✅ SEGURO
```

### Firewall (Seu servidor)
```bash
# Porta 9000 = APENAS via nginx (proxy)
# Nunca expor 9000 diretamente
# Nginx → :9000 (interno)
# Usuários → nginx (porta 80/443)
```

---

## 3. STORAGE (Sem Conflito de Dados)

### Estrutura de Pastas
```
/home/anexar_deploy/api-anexar/          ← NOVO, isolado
├── docker-compose.prod.yml
├── .env.prod
├── main.py
├── database.py
├── models.py
├── schemas.py
├── requirements.txt
├── Dockerfile
├── logs/                                  ← Logs da API
└── .gitignore

/srv/firebird/data/                       ← EXISTENTE, não tocamos
├── clientes/...                          ← Todos os bancos de clientes

/var/www/                                 ← EXISTENTE, outros projetos
├── projeto1/
├── projeto2/
└── projeto3/

/etc/nginx/sites-available/               ← Adicionamos 1 config
└── api-anexar.conf                       ← NOVO, não toca em outras
```

### Git Repository (Isolado)
```
GitHub:
└── seu-user/api-anexar/                  ← NOVO repo
    ├── Não entra em conflito com outros
    ├── Versionamento independente
    ├── Secrets em .env.local (gitignore)
    └── CD/CD próprio (GitHub Actions)
```

---

## 4. PROCESSO DE DEPLOYMENT (Zero Risk)

### Pré-Deploy: Verificações

```bash
# 1. Confirmar porta 9000 não está em uso
$ sudo lsof -i :9000
# (resultado esperado: vazio)

# 2. Confirmar Docker instalado e funcionando
$ docker ps
# (listar containers existentes, confirmar que não há conflito)

# 3. Confirmar Firebird acessível
$ telnet localhost 3050
# (conexão OK)

# 4. Confirmar espaço em disco
$ df -h /home
# (> 5GB livre: OK)
```

### Deploy: Passos Isolados

```bash
# 1. Criar pasta isolada
$ mkdir -p /home/anexar_deploy/api-anexar
$ cd /home/anexar_deploy/api-anexar

# 2. Pull código (Git)
$ git clone https://github.com/seu-user/api-anexar.git .

# 3. Build image (local, sem afetar sistema)
$ docker build -t api-anexar:1.0 .

# 4. Rodando container (isolado)
$ docker-compose -f docker-compose.prod.yml up -d

# 5. Verificar (saúde do container)
$ curl http://localhost:9000/api/v1/health
# Response: {"status": "ok"}

# 6. Rodar testes
$ docker exec anexar-api-prod pytest tests/
```

### Pós-Deploy: Monitoramento

```bash
# 1. Logs isolados (só da API)
$ docker logs -f anexar-api-prod

# 2. Recursos usados
$ docker stats anexar-api-prod
# (esperado: <512MB RAM, <0.5 CPU)

# 3. Performance outros projetos
$ top  # Verificar se outros estão OK
$ curl http://localhost/outro-projeto/  # Testar
```

---

## 5. ROLLBACK (Se Necessário)

### Se algo der errado

```bash
# 1. Parar container (1 comando)
$ docker-compose -f /home/anexar_deploy/api-anexar/docker-compose.prod.yml down

# 2. Remover image
$ docker rmi api-anexar:1.0

# 3. Remover pasta
$ rm -rf /home/anexar_deploy/api-anexar

# 4. Reiniciar nginx (restaura status quo)
$ sudo systemctl restart nginx

# Resultado: Servidor volta ao estado anterior
# Tempo: < 2 minutos
# Risco: ZERO (container isolado)
```

---

## 6. SEGURANÇA (Separação de Dados)

### O FastAPI pode acessar:
```
✅ Firebird (banco de dados existente)
✅ Suas próprias credenciais (.env.local)
✅ Seus logs (/home/anexar_deploy/api-anexar/logs/)
✅ Código dela (/home/anexar_deploy/api-anexar/)
```

### O FastAPI NÃO pode acessar:
```
❌ Outros projetos (/var/www/*)
❌ Outros bancos de dados
❌ Sistema (/etc, /root, etc)
❌ Dados de outros usuários
```

**Por quê?** Container roda como `nobody` (unprivileged user)

---

## 7. NGINX CONFIG (Reverse Proxy Seguro)

### Adiciona 1 bloco apenas

```nginx
# /etc/nginx/sites-available/api-anexar.conf (NOVO)

upstream api_backend {
    server 127.0.0.1:9000;
}

server {
    listen 80;
    server_name api.seu-dominio.com;

    location /api/v1/ {
        proxy_pass http://api_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Resultado:**
- ✅ Usuários acessam via nginx (80/443)
- ✅ nginx roteia para container (9000 interno)
- ✅ Container isolado, não exposto
- ✅ Outros sites não afetados

---

## 8. CHECKLIST PRÉ-DEPLOY

- [ ] Porta 9000 está livre: `lsof -i :9000` = vazio
- [ ] Docker funciona: `docker ps` = OK
- [ ] Firebird acessível: `telnet localhost 3050` = OK
- [ ] Espaço em disco: `df -h /home` > 5GB
- [ ] .env.prod preenchido e seguro
- [ ] Nginx config verificado (sem erro de sintaxe)
- [ ] Rollback plan testado (sabe como remover)

---

## 9. MONITORAMENTO CONTÍNUO (Opcional)

### Alertas para problemas
```bash
# Monitoring script (roda a cada 5min)
#!/bin/bash
API_STATUS=$(curl -s http://localhost:9000/api/v1/health)
if [[ ! $API_STATUS == *"ok"* ]]; then
    echo "ALERTA: API offline" | mail -s "API DOWN" you@email.com
fi

# Disco cheio
DISK=$(df /home | awk 'NR==2 {print $5}' | cut -d% -f1)
if [ $DISK -gt 90 ]; then
    echo "ALERTA: Disco > 90%" | mail -s "DISK FULL" you@email.com
fi
```

---

## 10. ISOLAMENTO DE RECURSOS (Limites)

### Container limitado

```yaml
# docker-compose.prod.yml
services:
  api:
    ...
    deploy:
      resources:
        limits:
          cpus: '0.5'      # Max 50% de 1 CPU
          memory: 512M     # Max 512MB RAM
        reservations:
          cpus: '0.25'     # Garantido 25% CPU
          memory: 256M     # Garantido 256MB RAM
```

**Resultado:**
- Container não rouba recursos dos outros
- Outros projetos sempre têm CPU/RAM disponível
- Se API explodir, container é freado

---

## CONCLUSÃO

✅ **ZERO impacto garantido:**
1. Container isolado (não toca sistema)
2. Porta isolada (9000, não conflita)
3. Dados isolados (pasta própria)
4. User unprivileged (não tem permissão)
5. Rollback de 1 comando (remover container)
6. Recursos limitados (não rouba dos outros)
7. Firewall restritivo (9000 só interno)

**Risco**: MUITO BAIXO  
**Tempo deploy**: ~10 minutos  
**Tempo rollback**: ~2 minutos

---

**Você aprova este plano de isolamento?** ✅
