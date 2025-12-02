# Projeto Prático - BSB Compute

## Sistema de Orquestração de Tarefas de IA

### Centro Universitário de Brasília - CEUB

**Disciplina:** Sistemas Operacionais | 2025.2
**Professor:** Me. Michel Junio Ferreira Rosa

---

## Integrantes

* João (Arquitetura)
* Guilherme (Escalonamento)
* Rômulo (Métricas)
* Thiago (Testes)

---

## Descrição

O **BSB Compute** é um sistema de orquestração de processos concorrentes que simula a distribuição de requisições de inferência de IA entre múltiplos servidores de um cluster. O sistema implementa:

* **Processos concorrentes** (Master/Workers) usando `multiprocessing`
* **Comunicação entre processos (IPC)** via filas de mensagens
* **Políticas de escalonamento**: Round Robin, SJF e Prioridade
* **Migração de tarefas** entre servidores sobrecarregados
* **Monitoramento de desempenho** em tempo real

---

## Como Compilar e Rodar

### Requisitos

* Python 3.8+
* Biblioteca `multiprocessing` (nativa do Python)

### Execução

1. Clone o repositório:

```bash
git clone <url-do-repositorio>
cd bsb-compute
```

2. Configure o arquivo `input.json` com os servidores e requisições desejadas.

3. Execute o orquestrador:

```bash
python main.py
```

4. Para alterar a política de escalonamento, edite a variável `POLICY` no `main.py`:

```python
POLICY = "SJF"        # Shortest Job First (padrão)
POLICY = "PRIORIDADE" # Por prioridade (1=Alta, 2=Média, 3=Baixa)
POLICY = "RR"         # Round Robin (FIFO)
```

### Teste de Estresse

```bash
# Copie o stress.json para input.json
cp stress.json input.json
python main.py
```

---

## Arquitetura do Sistema

```text
┌─────────────────────────────────────────────────────────┐
│                  ORQUESTRADOR (Master)                  │
│  - Recebe requisições                                   │
│  - Aplica política de escalonamento                     │
│  - Distribui tarefas (load balancing)                   │
│  - Gerencia migração de tarefas                         │
└─────────────────┬───────────────────┬───────────────────┘
                  │                   │
        ┌─────────▼─────┐   ┌─────────▼─────┐   ┌─────────▼─────┐
        │  Servidor 1   │   │  Servidor 2   │   │  Servidor 3   │
        │  (Worker)     │   │  (Worker)     │   │  (Worker)     │
        │  Cap: 3       │   │  Cap: 2       │   │  Cap: 1       │
        └───────────────┘   └───────────────┘   └───────────────┘
```

---

## Decisões de Projeto

### Linguagem e Bibliotecas

* **Python 3** com biblioteca `multiprocessing`
* Escolhido pela facilidade de criação de processos e IPC nativo

### Comunicação entre Processos (IPC)

* **Filas (`multiprocessing.Queue`)** para comunicação assíncrona
* Cada worker possui sua própria fila de tarefas
* Fila de retorno compartilhada para reportar conclusões

### Políticas de Escalonamento

1. **Round Robin (RR)**: Distribui tarefas na ordem de chegada (FIFO)
2. **SJF (Shortest Job First)**: Prioriza tarefas com menor tempo de execução
3. **Prioridade**: Prioriza tarefas de alta prioridade (1 > 2 > 3)

### Load Balancing

* Distribuição baseada em **menor carga ajustada** (carga/capacidade)
* Considera a capacidade de processamento de cada servidor

### Migração de Tarefas

* Detecta servidores sobrecarregados (threshold: 2x mais carga)
* Migra tarefas de baixa prioridade para servidores menos carregados
* Logs indicam claramente quando uma tarefa é migrada

---

## Formato de Entrada (input.json)

```json
{
  "server_config": [
    {"id": 1, "capacity": 3},
    {"id": 2, "capacity": 2},
    {"id": 3, "capacity": 1}
  ],
  "request_data": [
    {"id": 101, "type": "visao_computacional", "priority": 1, "exec_time": 8.0},
    {"id": 102, "type": "nlp", "priority": 3, "exec_time": 3.0}
  ]
}
```

---

## Métricas Coletadas

| Métrica                 | Descrição                                      |
| ----------------------- | ---------------------------------------------- |
| Tempo Médio de Resposta | Média do turnaround time (conclusão - chegada) |
| Throughput              | Tarefas concluídas por segundo                 |
| Utilização da CPU       | Percentual de uso dos recursos                 |
| Taxa de Espera Máxima   | Maior tempo que uma tarefa aguardou            |
| Migrações               | Número de tarefas redistribuídas               |

---

## Análise Comparativa das Políticas de Escalonamento

### Resultados Obtidos

Valores consolidados a partir das execuções reais:

| Métrica                      | Round Robin (RR) | SJF          | Prioridade     |
| ---------------------------- | ---------------- | ------------ | -------------- |
| **Tempo Total de Simulação** | 19.33 s          | 20.18 s      | **17.02 s** ⭐  |
| **Tempo Médio de Resposta**  | 10.10 s          | **8.74 s** ⭐ | 8.75 s         |
| **Utilização da CPU**        | 21.55 %          | 19.82 %      | **26.44 %** ⭐  |
| **Taxa de Espera Máxima**    | **11.01 s** ⭐    | 13.98 s      | 11.27 s        |
| **Throughput**               | 0.52 t/s         | 0.50 t/s     | **0.59 t/s** ⭐ |

### Análise dos Resultados

#### 🥇 SJF (Shortest Job First)

* **Melhor tempo médio de resposta (8.74 s)**.
* Ideal quando o objetivo é **minimizar o tempo de espera geral**.
* Processa tarefas curtas primeiro, liberando a fila rapidamente.
* **Desvantagem:** tarefas longas podem sofrer *starvation* (espera prolongada).

#### 🥈 Prioridade

* **Tempo médio de resposta praticamente empatado com o SJF (8.75 s)**.
* **Maior throughput (0.59 t/s)** e **maior utilização de CPU (26.44%)**.
* Garante que tarefas críticas (alta prioridade) sejam processadas primeiro.
* Ideal para sistemas com **SLAs e prioridades bem definidas**.
* **Desvantagem:** tarefas de baixa prioridade ainda podem esperar mais (taxa de espera máxima maior que a do RR).

#### 🥉 Round Robin (RR)

* **Menor taxa de espera máxima (11.01 s)** → mais justo no pior caso.
* Distribui tarefas de forma equitativa na ordem de chegada.
* Bom equilíbrio entre simplicidade e justiça.
* **Desvantagem:** pior tempo médio de resposta (10.10 s) entre as três políticas e não considera prioridade nem tempo de execução.

### Recomendações de Uso

| Cenário                                      | Política Recomendada |
| -------------------------------------------- | -------------------- |
| Minimizar tempo médio de resposta            | **SJF**              |
| Garantir justiça e evitar starvation         | **Round Robin**      |
| Sistema com SLAs e prioridades bem definidas | **Prioridade**       |
| Maximizar throughput                         | **Prioridade**       |

---

## Exemplos de Execução Real

### Política SJF

```text
==================================================
BSB COMPUTE - Sistema de Orquestração de Tarefas
==================================================
--- INICIALIZANDO SERVIDORES ---
[INIT] Servidor 1 (Capacidade: 3) pronto.
[INIT] Servidor 2 (Capacidade: 2) pronto.
[INIT] Servidor 3 (Capacidade: 1) pronto.
--- INICIANDO ORQUESTRADOR ---
[00:00] --- INICIANDO SIMULAÇÃO (Política: SJF) ---
[00:00] Requisição 101 (Alta) chegou - Tipo: visao_computacional
[00:01] Requisição 102 (Baixa) chegou - Tipo: nlp
[00:02] Requisição 103 (Média) chegou - Tipo: voz
[00:02] Requisição 104 (Média) chegou - Tipo: visao_computacional
[00:04] Requisição 105 (Alta) chegou - Tipo: nlp
[00:05] Requisição 106 (Baixa) chegou - Tipo: voz
[00:05] Requisição 107 (Média) chegou - Tipo: visao_computacional
[00:06] Requisição 108 (Alta) chegou - Tipo: nlp
[00:07] Requisição 109 (Baixa) chegou - Tipo: voz
[00:07] Requisição 110 (Alta) chegou - Tipo: visao_computacional
[00:07] [SJF] Requisição 105 (2.0s) atribuída ao Servidor 1
[00:07] [SJF] Requisição 102 (3.0s) atribuída ao Servidor 2
[00:07] Servidor 1 processando Req 105 (Alta) (Tempo Real: 0.7s)
[00:07] [SJF] Requisição 110 (3.0s) atribuída ao Servidor 3
[00:07] Servidor 2 processando Req 102 (Baixa) (Tempo Real: 1.5s)
[00:07] [SJF] Requisição 107 (4.0s) atribuída ao Servidor 1
[00:07] Servidor 3 processando Req 110 (Alta) (Tempo Real: 3.0s)
[00:07] [SJF] Requisição 103 (5.0s) atribuída ao Servidor 1
[00:07] [SJF] Requisição 104 (6.0s) atribuída ao Servidor 2
[00:07] [SJF] Requisição 108 (7.0s) atribuída ao Servidor 1
[00:07] [SJF] Requisição 101 (8.0s) atribuída ao Servidor 1
[00:07] [SJF] Requisição 109 (9.0s) atribuída ao Servidor 2
[00:07] [SJF] Requisição 106 (10.0s) atribuída ao Servidor 1
[00:08] Servidor 1 concluiu Requisição 105
[00:08] Servidor 1 processando Req 107 (Média) (Tempo Real: 1.3s)
[00:08] Servidor 1 CONCLUIU Requisição 105 (Alta) em 4.59s
[00:09] Servidor 2 concluiu Requisição 102
[00:09] Servidor 2 processando Req 104 (Média) (Tempo Real: 3.0s)
[00:09] Servidor 2 CONCLUIU Requisição 102 (Baixa) em 8.45s
[00:09] Servidor 1 concluiu Requisição 107
[00:09] Servidor 1 processando Req 103 (Média) (Tempo Real: 1.7s)
[00:09] Servidor 1 CONCLUIU Requisição 107 (Média) em 4.36s
[00:10] Servidor 3 concluiu Requisição 110
[00:10] Servidor 3 CONCLUIU Requisição 110 (Alta) em 3.01s
[00:11] Servidor 1 concluiu Requisição 103
[00:11] Servidor 1 processando Req 108 (Alta) (Tempo Real: 2.3s)
[00:11] Servidor 1 CONCLUIU Requisição 103 (Média) em 9.52s
[00:12] Servidor 2 concluiu Requisição 104
[00:12] Servidor 2 processando Req 109 (Baixa) (Tempo Real: 4.5s)
[00:12] Servidor 2 CONCLUIU Requisição 104 (Média) em 9.91s
[00:13] Servidor 1 concluiu Requisição 108
[00:13] Servidor 1 processando Req 101 (Alta) (Tempo Real: 2.7s)
[00:13] Servidor 1 CONCLUIU Requisição 108 (Alta) em 7.09s
[00:16] Servidor 1 concluiu Requisição 101
[00:16] Servidor 1 processando Req 106 (Baixa) (Tempo Real: 3.3s)
[00:16] Servidor 1 CONCLUIU Requisição 101 (Alta) em 16.65s
[00:16] Servidor 2 concluiu Requisição 109
[00:16] Servidor 2 CONCLUIU Requisição 109 (Baixa) em 9.15s
[00:19] Servidor 1 concluiu Requisição 106
[00:19] Servidor 1 CONCLUIU Requisição 106 (Baixa) em 14.72s
--------------------------------------------------
RESUMO FINAL DA EXECUÇÃO (BSB Compute)
--------------------------------------------------
Política Utilizada:        SJF
Total de Requisições:      10
Tempo Total de Simulação:  20.18s
Tempo Médio de Resposta:   8.74s
Utilização média da CPU:   19.82%
Taxa de espera máxima:     13.98s
Throughput (Vazão):        0.50 tarefas/segundo
Migrações realizadas:      0
Tarefas migradas:          0
--------------------------------------------------
```

---

### Política Round Robin (RR)

```text
==================================================
BSB COMPUTE - Sistema de Orquestração de Tarefas
==================================================

--- INICIALIZANDO SERVIDORES ---
[INIT] Servidor 1 (Capacidade: 3) pronto.
[INIT] Servidor 2 (Capacidade: 2) pronto.
[INIT] Servidor 3 (Capacidade: 1) pronto.

--- INICIANDO ORQUESTRADOR ---


[00:00] --- INICIANDO SIMULAÇÃO (Política: RR) ---

[00:00] Requisição 101 (Alta) chegou - Tipo: visao_computacional
[00:00] Requisição 102 (Baixa) chegou - Tipo: nlp
[00:00] Requisição 103 (Média) chegou - Tipo: voz
[00:02] Requisição 104 (Média) chegou - Tipo: visao_computacional
[00:02] Requisição 105 (Alta) chegou - Tipo: nlp
[00:03] Requisição 106 (Baixa) chegou - Tipo: voz
[00:04] Requisição 107 (Média) chegou - Tipo: visao_computacional
[00:05] Requisição 108 (Alta) chegou - Tipo: nlp
[00:05] Requisição 109 (Baixa) chegou - Tipo: voz
[00:07] Requisição 110 (Alta) chegou - Tipo: visao_computacional
[00:07] [RR] Requisição 101 (Alta) atribuída ao Servidor 1
[00:07] [RR] Requisição 102 (Baixa) atribuída ao Servidor 2
[00:07] Servidor 1 processando Req 101 (Alta) (Tempo Real: 2.7s)
[00:07] [RR] Requisição 103 (Média) atribuída ao Servidor 3
[00:07] Servidor 2 processando Req 102 (Baixa) (Tempo Real: 1.5s)
[00:07] [RR] Requisição 104 (Média) atribuída ao Servidor 2
[00:07] Servidor 3 processando Req 103 (Média) (Tempo Real: 5.0s)
[00:07] [RR] Requisição 105 (Alta) atribuída ao Servidor 1
[00:07] [RR] Requisição 106 (Baixa) atribuída ao Servidor 1
[00:07] [RR] Requisição 107 (Média) atribuída ao Servidor 1
[00:07] [RR] Requisição 108 (Alta) atribuída ao Servidor 2
[00:07] [RR] Requisição 109 (Baixa) atribuída ao Servidor 1
[00:07] [RR] Requisição 110 (Alta) atribuída ao Servidor 1
[00:08] Servidor 2 concluiu Requisição 102
[00:08] Servidor 2 processando Req 104 (Média) (Tempo Real: 3.0s)
[00:08] Servidor 2 CONCLUIU Requisição 102 (Baixa) em 8.17s
[00:09] Servidor 1 concluiu Requisição 101
[00:09] Servidor 1 processando Req 105 (Alta) (Tempo Real: 0.7s)
[00:09] Servidor 1 CONCLUIU Requisição 101 (Alta) em 9.81s
[00:10] Servidor 1 concluiu Requisição 105
[00:10] Servidor 1 processando Req 106 (Baixa) (Tempo Real: 3.3s)
[00:10] Servidor 1 CONCLUIU Requisição 105 (Alta) em 7.65s
[00:11] Servidor 2 concluiu Requisição 104
[00:11] Servidor 2 processando Req 108 (Alta) (Tempo Real: 3.5s)
[00:11] Servidor 2 CONCLUIU Requisição 104 (Média) em 9.34s
[00:12] Servidor 3 concluiu Requisição 103
[00:12] Servidor 3 CONCLUIU Requisição 103 (Média) em 11.28s
[00:13] Servidor 1 concluiu Requisição 106
[00:13] Servidor 1 processando Req 107 (Média) (Tempo Real: 1.3s)
[00:13] Servidor 1 CONCLUIU Requisição 106 (Baixa) em 10.64s
[00:15] Servidor 2 concluiu Requisição 108
[00:15] Servidor 1 concluiu Requisição 107
[00:15] Servidor 1 processando Req 109 (Baixa) (Tempo Real: 3.0s)
[00:15] Servidor 2 CONCLUIU Requisição 108 (Alta) em 9.31s
[00:15] Servidor 1 CONCLUIU Requisição 107 (Média) em 10.58s
[00:18] Servidor 1 concluiu Requisição 109
[00:18] Servidor 1 processando Req 110 (Alta) (Tempo Real: 1.0s)
[00:18] Servidor 1 CONCLUIU Requisição 109 (Baixa) em 12.16s
[00:19] Servidor 1 concluiu Requisição 110
[00:19] Servidor 1 CONCLUIU Requisição 110 (Alta) em 12.01s

--------------------------------------------------
RESUMO FINAL DA EXECUÇÃO (BSB Compute)
--------------------------------------------------
Política Utilizada:        RR
Total de Requisições:      10
Tempo Total de Simulação:  19.33s
Tempo Médio de Resposta:   10.10s
Utilização média da CPU:   21.55%
Taxa de espera máxima:     11.01s
Throughput (Vazão):        0.52 tarefas/segundo
Migrações realizadas:      0
Tarefas migradas:          0
--------------------------------------------------
```

---

### Política de Prioridade

```text
==================================================
BSB COMPUTE - Sistema de Orquestração de Tarefas
==================================================

--- INICIALIZANDO SERVIDORES ---
[INIT] Servidor 1 (Capacidade: 3) pronto.
[INIT] Servidor 2 (Capacidade: 2) pronto.
[INIT] Servidor 3 (Capacidade: 1) pronto.

--- INICIANDO ORQUESTRADOR ---


[00:00] --- INICIANDO SIMULAÇÃO (Política: PRIORIDADE) ---

[00:00] Requisição 101 (Alta) chegou - Tipo: visao_computacional
[00:01] Requisição 102 (Baixa) chegou - Tipo: nlp
[00:02] Requisição 103 (Média) chegou - Tipo: voz
[00:03] Requisição 104 (Média) chegou - Tipo: visao_computacional
[00:03] Requisição 105 (Alta) chegou - Tipo: nlp
[00:03] Requisição 106 (Baixa) chegou - Tipo: voz
[00:04] Requisição 107 (Média) chegou - Tipo: visao_computacional
[00:05] Requisição 108 (Alta) chegou - Tipo: nlp
[00:05] Requisição 109 (Baixa) chegou - Tipo: voz
[00:06] Requisição 110 (Alta) chegou - Tipo: visao_computacional
[00:06] [PRIO] Requisição 101 (Alta) atribuída ao Servidor 1
[00:06] [PRIO] Requisição 105 (Alta) atribuída ao Servidor 2
[00:06] Servidor 1 processando Req 101 (Alta) (Tempo Real: 2.7s)
[00:06] [PRIO] Requisição 108 (Alta) atribuída ao Servidor 3
[00:06] Servidor 2 processando Req 105 (Alta) (Tempo Real: 1.0s)
[00:06] [PRIO] Requisição 110 (Alta) atribuída ao Servidor 2
[00:06] Servidor 3 processando Req 108 (Alta) (Tempo Real: 7.0s)
[00:06] [PRIO] Requisição 103 (Média) atribuída ao Servidor 1
[00:06] [PRIO] Requisição 104 (Média) atribuída ao Servidor 2
[00:06] [PRIO] Requisição 107 (Média) atribuída ao Servidor 1
[00:06] [PRIO] Requisição 102 (Baixa) atribuída ao Servidor 1
[00:06] [PRIO] Requisição 106 (Baixa) atribuída ao Servidor 1
[00:06] [PRIO] Requisição 109 (Baixa) atribuída ao Servidor 2
[00:07] Servidor 2 concluiu Requisição 105
[00:07] Servidor 2 processando Req 110 (Alta) (Tempo Real: 1.5s)
[00:07] Servidor 2 CONCLUIU Requisição 105 (Alta) em 4.26s
[00:09] Servidor 2 concluiu Requisição 110
[00:09] Servidor 2 processando Req 104 (Média) (Tempo Real: 3.0s)
[00:09] Servidor 2 CONCLUIU Requisição 110 (Alta) em 2.51s
[00:09] Servidor 1 concluiu Requisição 101
[00:09] Servidor 1 processando Req 103 (Média) (Tempo Real: 1.7s)
[00:09] Servidor 1 CONCLUIU Requisição 101 (Alta) em 9.49s
[00:11] Servidor 1 concluiu Requisição 103
[00:11] Servidor 1 processando Req 107 (Média) (Tempo Real: 1.3s)
[00:11] Servidor 1 CONCLUIU Requisição 103 (Média) em 8.89s
[00:12] Servidor 2 concluiu Requisição 104
[00:12] Servidor 2 processando Req 109 (Baixa) (Tempo Real: 4.5s)
[00:12] Servidor 2 CONCLUIU Requisição 104 (Média) em 9.32s
[00:12] Servidor 1 concluiu Requisição 107
[00:12] Servidor 1 processando Req 102 (Baixa) (Tempo Real: 1.0s)
[00:12] Servidor 1 CONCLUIU Requisição 107 (Média) em 8.04s
[00:13] Servidor 1 concluiu Requisição 102
[00:13] Servidor 1 processando Req 106 (Baixa) (Tempo Real: 3.3s)
[00:13] Servidor 1 CONCLUIU Requisição 102 (Baixa) em 12.27s
[00:13] Servidor 3 concluiu Requisição 108
[00:13] Servidor 3 CONCLUIU Requisição 108 (Alta) em 8.43s
[00:16] Servidor 1 concluiu Requisição 106
[00:16] Servidor 2 concluiu Requisição 109
[00:16] Servidor 1 CONCLUIU Requisição 106 (Baixa) em 13.14s
[00:16] Servidor 2 CONCLUIU Requisição 109 (Baixa) em 11.11s

--------------------------------------------------
RESUMO FINAL DA EXECUÇÃO (BSB Compute)
--------------------------------------------------
Política Utilizada:        PRIORIDADE
Total de Requisições:      10
Tempo Total de Simulação:  17.02s
Tempo Médio de Resposta:   8.75s
Utilização média da CPU:   26.44%
Taxa de espera máxima:     11.27s
Throughput (Vazão):        0.59 tarefas/segundo
Migrações realizadas:      0
Tarefas migradas:          0
--------------------------------------------------
```

---

## Estrutura de Arquivos

```text
bsb-compute/
├── main.py         # Código principal (Master + Workers)
├── input.json      # Configuração de servidores e requisições
├── stress.json     # Arquivo de teste de estresse
└── README.md       # Este arquivo
```

---

## Conclusão

O sistema **BSB Compute** demonstrou ser capaz de:

1. **Gerenciar múltiplos processos** de forma concorrente e eficiente
2. **Aplicar diferentes políticas de escalonamento** com resultados distintos
3. **Balancear carga** entre servidores com capacidades diferentes
4. **Monitorar e reportar métricas** de desempenho em tempo real

A escolha da política de escalonamento deve ser baseada nos requisitos específicos do sistema:

* **SJF** para melhor tempo médio de resposta
* **Round Robin** para maior justiça (menor espera máxima)
* **Prioridade** para sistemas com SLAs e quando se deseja maior throughput

---

## Licença

Projeto acadêmico desenvolvido para a disciplina de Sistemas Operacionais - CEUB 2025.2.
