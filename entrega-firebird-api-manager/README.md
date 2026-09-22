# Firebird API Manager — Entrega do Protótipo

Esta pasta contém o front-end do protótipo e o escopo técnico inicial do projeto.

## Estrutura

```txt
entrega-firebird-api-manager/
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
└── docs/
    └── ESCOPO_PROJETO.md
```

## Como abrir o front

Abra o arquivo:

```txt
frontend/index.html
```

O protótipo roda direto no navegador, sem instalação.

## O que está incluso

- Dashboard do gerenciador;
- cadastro de estruturas;
- upload e validação demonstrativa;
- suporte visual a Firebird, PostgreSQL, MySQL, MariaDB, SQL Server, MongoDB, Node/ORM e outros;
- catálogo de tabelas, campos, triggers e procedures;
- geração demonstrativa de rotas;
- documentação estilo Swagger;
- teste simulado de requisições;
- gestão de clientes;
- API keys mascaradas, sem exposição de segredo em claro.

## Observação importante

Este pacote contém o front-end e o escopo do projeto.

As funcionalidades de upload real, leitura de banco, introspecção de schema, geração real de rotas e autenticação por API key precisam de backend para funcionar em produção.
