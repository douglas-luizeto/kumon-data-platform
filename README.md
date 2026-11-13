
## Introdução

Este projeto visa trazer uma abordagem "data-driven" para os principais processos de uma unidade Kumon ([clique aqui para conhecer melhor o negócio](https://kumon.com.br/)). Além dos objetivos tradicionais relacionados à automações, como redução de erros, economia de tempo e liberação da mão de obra para tarefas mais produtivas, este projeto visa possibilitar análises em tempo real de algumas dores do negócio, as principais sendo:

1. P&L
2. Taxa de cancelamento (churn rate)
3. Relacionamento com clientes (métricas de engajamento)  

A fim de criar essa estrutura do zero e substituir processos historicamente manuais e coletar dados nunca antes analisados de maneira sistemática, os seguintes passos foram tomados: 

### 1. Armazenamento e coleta dos dados

- Criação de um banco de dados para informações de cadastro (dados mestres).
- Criação de um banco de dados para informações transacionais:
	- Dados financeiros
	- Dados comportamentais
	- Dados de performance dos clientes
- Criação de automações para manter os cadastros em diferentes sistemas (proprietários) sincronizados.
- Integração com API do Banco Inter para a obtenção dos dados financeiros da empresa. 
- Criação de interfaces para a coleta de dados comportamentais e de performance mensal dos alunos.  

