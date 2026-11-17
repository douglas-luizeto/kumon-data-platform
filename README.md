## Introdução 

Este projeto visa implementar uma abordagem *data-driven* nos principais processos operacionais e pedagógicos de uma unidade Kumon ([clique aqui para conhecer melhor o negócio](https://kumon.com.br/)). Além dos ganhos tradicionais de automação — como redução de erros manuais, economia de tempo operacional e liberação da equipe para o acompanhamento pedagógico —, a arquitetura foi desenhada para viabilizar o monitoramento contínuo de indicadores-chave do negócio: 

1. **Demonstrativo de Resultados (P&L) e Fluxo de Caixa** 
2. **Taxa de Cancelamento (*Churn Rate*) e Retenção por Safra (*Cohort*)** 
3. **Relacionamento e Engajamento dos Alunos** Para construir essa estrutura do zero, substituir controles historicamente manuais e sistematizar dados que antes não eram analisados de forma integrada, o projeto foi estruturado nas seguintes etapas: 

---
### 1.1 Armazenamento e Coleta dos Dados 

- **Modelagem Relacional (`master` e `transactional`):** Estruturação de um banco PostgreSQL separando entidades cadastrais de domínio/mestre (colaboradores, responsáveis financeiros, matrículas, horários, estágios e centros de custo) de registros transacionais de alta granularidade: 
	-  Movimentações financeiras e liquidação de mensalidades 
	* Interações e frequência em sala de aula 
	* Evolução e performance mensal dos alunos 
* **Sincronização Cadastral:** Automações para manter os registros cadastrais consistentes entre os sistemas proprietários da franquia e o banco analítico. 
* **Integração Bancária:** Conexão via API com o Banco Inter para captura automatizada de extratos, cobranças e liquidações financeiras da unidade. 
* **Interfaces de Coleta Operacional:** Criação de formulários e interfaces para registro ágil de observações comportamentais em sala e fechamento mensal de performance dos alunos. 

--- 
### 1.2 Geração de Dados Sintéticos (Fase 1: Entidades Mestre) 

Para viabilizar testes locais reprodutíveis e modelagem realista de Business Intelligence sem expor dados sensíveis (LGPD), o projeto conta com um pipeline determinístico em Python (`scripts/generate_master_data.py`), construído com `Faker`, `NumPy` e `pandas`. 
#### Estratégia de Geração e Regras de Negócio 

As entidades mestre são geradas em cascata estrita de dependências (`employees` $\rightarrow$ `customers` $\rightarrow$ `accounts`), cobrindo uma **janela histórica de 2 anos (`2024-07-01` a `2026-06-30`)**: 
* **Equipe e Habilitações (`master.employees`):** Gera a equipe pedagógica da unidade (1 *Orientador* e 4 *Auxiliares*) com flags explícitas de habilitação por disciplina (`teaches_m`, `teaches_p`, `teaches_i`, `teaches_j`), garantindo que os alunos sejam alocados apenas a instrutores qualificados na respectiva matéria. 
* **Responsáveis Financeiros (`master.customers`):** Gera perfis brasileiros realistas (`pt_BR`) com CPFs únicos de 11 dígitos, telefones padronizados e CEPs formatados explicitamente como *string* para preservar zeros à esquerda e integridade relacional. * **Matrículas e Perfis de Alunos (`master.accounts`):** 
* **Modelagem de Irmãos e Multi-matéria:** Suporta múltiplas contas vinculadas a um mesmo responsável financeiro, diferenciando irmãos (`kumon_id` distintos) de alunos matriculados em mais de uma disciplina (mesmo `kumon_id` em diferentes `subject_id`). 
* **Modalidade e Suporte de Estudo:** Segmenta os alunos entre atendimento `presencial` ou `online` e material em `papel` ou `tablet` (Kumon Connect), correlacionando essas escolhas com a faixa etária e restrições da disciplina (ex.: Japonês 100% em papel). 
* **Distribuições Realistas:** Calibrado para refletir a demografia real de uma unidade nas proporções de matérias (50% Matemática, 20% Português, 13% Inglês, 17% Japonês), gênero (43% M / 57% F), faixas etárias e estágios diagnósticos iniciais (`master.stages`). 
* **Capacidade Operacional e Churn:** Atribui pares de horários semanais em dias distintos (`Seg/Qui` ou `Ter/Sex`) respeitando o limite máximo de 5 alunos simultâneos por instrutor/horário e sem misturar atendimentos presenciais e online no mesmo bloco, além de simular uma taxa histórica de cancelamento de ~32% (`cancelation_date`). 
#### Executando o Gerador de Dados Mestre 

```
bash python scripts/generate_master_data.py
```

O script executa uma auditoria automatizada de sanidade (validando proporções por disciplina, taxa de churn, exclusividade de modalidade e ocupação por instrutor/horário) antes de exportar os arquivos intermediários para `data/`.

---
### 1.3 Geração de Dados Sintéticos (Fase 2: Entidades Transacionais)

A segunda etapa do pipeline de dados (`scripts/generate_transactional_data.py`) consome as entidades mestre geradas anteriormente e simula 24 meses de operação diária e fechamentos mensais da unidade (`2024-07-01` a `2026-06-30`), preservando a integridade referencial e injetando correlações comportamentais e financeiras reais para análise.
#### Estratégia de Simulação e Regras de Negócio

- **Arquétipos Comportamentais Dinâmicos:** Cada matrícula recebe um perfil base (_exemplar_, _mediano_, _esforçado lento_, _sem dever_ ou _faltoso/risco_) ponderado por gênero e faixa etária. O simulador modela fenômenos reais da operação, como a queda de engajamento de adolescentes após os primeiros meses de estudo e a deterioração de frequência nos 60 dias que antecedem um cancelamento.
    
- **Interações em Sala e Estudo em Casa (`transactional.interactions`):**
    
    - **Calendário e Reagendamentos:** Gera todas as aulas previstas conforme os dias da semana (`Seg/Qui` ou `Ter/Sex`), simulando horários reais de chegada/saída (`start_ts`, `end_ts`), faltas justificadas ou não, e reposições vinculadas à falta original via auto-relacionamento (`rescheduled_from_id`).
        
    - **Consistência de Estudo Domiciliar:** Calcula `days_studied_since_last` respeitando estritamente o intervalo real de dias desde a última aula em que o aluno efetivamente compareceu, além de registrar qualidade de estudo, correções (com maior precisão no suporte `tablet`) e tags comportamentais (`desmotivado`, `pergunta demais`, `indisciplinado`).
        
- **Performance Mensal e Progressão Pedagógica (`transactional.monthly_performance`):**
    
    - **Ciclo de Vida e Status (`master.status`):** Rastreia a situação mensal de cada matrícula desde a entrada (`N` - Novo, `IT` - Transferência Interna, `EO` - Multi-matéria), passando pelos meses regulares (`C` - Corrente) até o encerramento (`A` - Ausente/Cancelado, `OT` - Transferência Externa), zerando a produção no mês de saída.
        
    - **Ritmo de Avanço por Estágio:** Deriva o volume líquido de folhas concluídas (`sheets_completed`, múltiplos de 10) diretamente da soma de presenças e dias estudados em casa no mês, aplicando taxas de avanço maiores nos estágios introdutórios (`7A`–`A`) e progressivamente mais lentas nos estágios avançados, atualizando `final_stage_id` e `final_lesson_number` a cada bloco de 200 folhas.
        
- **Movimentações Financeiras e Mensalidades (`transactional.financial_transactions` e `transactional.tuition_fees`):**
    
    - **Regime de Competência vs. Caixa:** Separa a data de competência (`competence_date`) da data efetiva de liquidação (`transaction_date`), aplicando os prazos de compensação (`settlement_days`) de cada meio de pagamento (Boleto, Boleto-Pix, Pix e Dinheiro).
        
    - **Atrasos e Inadimplência Silenciosa:** Simula pagamentos em atraso (3 a 35 dias) e modela a inadimplência real (~15% dos cancelamentos ocorrem sem aviso prévio acompanhados do não pagamento das últimas mensalidades, além de ~3% de inadimplência pontual na base).
        
    - **Granularidade de Despesas (DRE):** Gera lançamentos granulares por centro de custo e natureza (salários individuais por colaborador, royalties segmentados por disciplina, aluguel, utilidades discriminadas, impostos e tarifas bancárias por liquidação) calibrados para refletir a estrutura de custos e margem operacional de uma unidade real.
        
#### Executando o Gerador de Dados Transacionais

Bash

```
python scripts/generate_transactional_data.py
```

Ao final da execução, o script roda uma bateria automatizada de auditoria que valida todas as chaves estrangeiras, a consistência entre estágios e disciplinas e exibe no terminal um resumo operacional acompanhado da DRE consolidada dos 24 meses antes de salvar os arquivos em `data/`

---

### 1.4 Ingestão em Lote no PostgreSQL 

Com os arquivos CSV mestres e transacionais gerados e auditados localmente, a etapa final da camada de armazenamento consiste em carregar os dados nos schemas `master` e `transactional` do banco PostgreSQL (`kumon_db`). 
#### Arquitetura de Carga e Decisões Técnicas 

Para garantir alta performance, baixo consumo de memória e conformidade estrita com as restrições de integridade do banco, o script de ingestão foi construído utilizando `psycopg` (v3) puro com as seguintes características: 
* **Protocolo Nativo `COPY FROM STDIN`:** Em vez de utilizar `INSERT` linha a linha ou abstrações pesadas de ORMs (como `pandas.to_sql` com SQLAlchemy), os arquivos são transmitidos em *stream* de blocos binários (`64 KB`) diretamente para o motor do PostgreSQL via comando `COPY`, reduzindo o tempo de carga de dezenas de milhares de interações para frações de segundo. 
* **Transação Atômica Única (Tudo ou Nada):** Todo o pipeline de carga roda dentro de um único bloco transacional (`with psycopg.connect(...) as conn:`). Caso qualquer linha viole uma `CHECK` constraint, `UNIQUE` ou chave estrangeira, o PostgreSQL executa *rollback* completo automaticamente, impedindo estados parciais ou corrompidos no banco. 
* **Idempotência e Ordem de Dependência:** Antes da carga, o script executa `TRUNCATE TABLE ... RESTART IDENTITY CASCADE` na ordem inversa das dependências e, em seguida, carrega as tabelas respeitando a hierarquia estrita de chaves estrangeiras (`employees` $\rightarrow$ `customers` $\rightarrow$ `accounts` $\rightarrow$ `interactions` $\rightarrow$ `monthly_performance` $\rightarrow$ `financial_transactions` $\rightarrow$ `tuition_payments`). 
* **Mapeamento Dinâmico de Colunas e Sincronização de Sequences:** O script lê o cabeçalho de cada CSV dinamicamente para montar a instrução `COPY`, evitando erros por mudança na ordem de colunas, e ressincroniza as *sequences* (`setval`) após a inserção explícita de chaves seriais. 
#### Executando a Carga no Banco

Certifique-se de que o container `kumon_db` está ativo e execute: 

```
bash python scripts/load_to_postgres.py
```

--- 

