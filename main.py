import multiprocessing
import time
import random
import json
import os
from collections import deque
from typing import List, Dict, Any, Deque

# --- FUNÇÃO DE CARREGAMENTO DE CONFIGURAÇÃO ---

def load_config(filepath: str) -> Dict[str, List[Dict[str, Any]]]:
    """Carrega as configurações de servidores e requisições de um arquivo JSON."""
    if not os.path.exists(filepath):
        # A mensagem de erro agora usa o nome de arquivo especificado
        print(f"ERRO: Arquivo de configuração não encontrado em: {filepath}")
        # Retorna configuração vazia para evitar crash
        return {"server_config": [], "request_data": []}
    
    try:
        # Abertura do arquivo de configuração (input.json)
        with open(filepath, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config
    except json.JSONDecodeError as e:
        print(f"ERRO: Falha ao decodificar JSON do arquivo {filepath}: {e}")
        return {"server_config": [], "request_data": []}
    except Exception as e:
        print(f"ERRO: Ocorreu um erro ao ler o arquivo {filepath}: {e}")
        return {"server_config": [], "request_data": []}


# --- CARREGAR DADOS DO JSON ---
# O orquestrador está configurado para ler o arquivo input.json por padrão.
CONFIG_DATA = load_config("input.json") 

# Se o carregamento falhar, estas listas estarão vazias e a simulação parará.
SERVER_CONFIG = CONFIG_DATA.get("server_config", [])
REQUEST_DATA = CONFIG_DATA.get("request_data", [])

# Verifica se há dados para simular
if not SERVER_CONFIG or not REQUEST_DATA:
    print("A simulação não pode continuar: Dados de configuração ou requisições ausentes/inválidos.")
    exit()

# --- 1. DEFINIÇÕES DE CLASSES E DADOS ---

class Task:
    """Representa uma Requisição de Inferência (Tarefa)."""
    def __init__(self, id: int, type: str, priority: int, exec_time: float, arrival_time: float):
        self.id = id
        self.type = type
        self.priority = priority  # 1 (Alta) > 2 (Média) > 3 (Baixa)
        self.exec_time = exec_time  # Tempo de execução base (sem ajuste pela capacidade)
        self.arrival_time = arrival_time
        self.start_time = 0.0
        self.completion_time = 0.0
        self.worker_id = None

    def __repr__(self):
        # Representação da tarefa para logs
        prio_map = {1: 'Alta', 2: 'Média', 3: 'Baixa'}
        return (f"Req {self.id} ({prio_map.get(self.priority, 'N/A')}, "
                f"T={self.exec_time:.1f}s, Chegada={self.arrival_time:.1f}s)")

# Variáveis globais de controle para o Master
PENDING_QUEUE: Deque[Task] = deque()
# WORKER_LOAD armazena a carga pendente de trabalho (em segundos base) para cada servidor.
WORKER_LOAD: Dict[int, float] = {s['id']: 0.0 for s in SERVER_CONFIG}
ACTIVE_TASKS: Dict[int, Task] = {}

# --- 2. FUNÇÃO DO PROCESSO WORKER ---

def worker_process(worker_id: int, capacity: int, task_queue: multiprocessing.Queue, return_queue: multiprocessing.Queue):
    """
    Simula um Servidor de Inferência (Worker).
    Recebe tarefas, simula o processamento e reporta a conclusão.
    """
    current_time = time.time()
    print(f"[INIT] Servidor {worker_id} (Capacidade: {capacity}) pronto.")

    while True:
        try:
            # Tenta pegar uma tarefa da fila, espera no máximo 1 segundo
            task: Task = task_queue.get(timeout=1)
            
            # Sinal de parada (Master envia None para encerrar o Worker)
            if task is None:
                break
            
            # --- 2.1 SIMULAÇÃO DA EXECUÇÃO ---
            
            # Ajusta o tempo de execução pela capacidade do servidor (Critério 2.2)
            actual_exec_time = task.exec_time / capacity
            
            # Registra tempo de início relativo à simulação (start_time do Master)
            task.start_time = time.time() - current_time 
            
            print(f"[{task.start_time:04.1f}s] Servidor {worker_id} processando {task} (Tempo Real: {actual_exec_time:.1f}s)")
            
            # Simula o processamento da IA
            time.sleep(actual_exec_time)
            
            # Registra tempo de conclusão relativo à simulação
            task.completion_time = time.time() - current_time 
            
            # --- 2.2 REPORTA CONCLUSÃO (IPC) ---
            
            # Envia a tarefa completa de volta ao Master
            return_queue.put({
                "status": "completed",
                "req_id": task.id,
                "worker_id": worker_id,
                "exec_time_real": actual_exec_time,
                "arrival_time": task.arrival_time,
                "completion_time": task.completion_time,
                "start_time": task.start_time
            })
            
            # Log simples de conclusão no Worker
            print(f"[{task.completion_time:04.1f}s] Servidor {worker_id} concluiu Req {task.id}")
            
        except multiprocessing.queues.Empty:
            # Se a fila estiver vazia, espera um pouco e verifica novamente
            pass
        except KeyboardInterrupt:
            # Permite parar o worker com Ctrl+C
            break

# --- 3. FUNÇÃO DO PROCESSO MASTER (ORQUESTRADOR) ---

def master_orchestrator(task_queues: Dict[int, multiprocessing.Queue], return_queue: multiprocessing.Queue, policy: str):
    """
    Simula o Orquestrador Central (Master).
    Gerencia a fila, aplica a política de escalonamento e distribui tarefas.
    """
    
    global PENDING_QUEUE, WORKER_LOAD, ACTIVE_TASKS
    
    start_simulation_time = time.time()
    
    # 3.0 Geração de requisições e simulação de chegada
    
    # Geração de requisições com tempo de chegada simulado (Critério 5.1)
    for data in REQUEST_DATA:
        # Tempo de chegada aleatório (0.1 a 1.5s entre requisições)
        arrival_delay = random.uniform(0.1, 1.5) if PENDING_QUEUE else 0
        arrival_time = (time.time() - start_simulation_time) + arrival_delay
        
        # Cria a instância da Tarefa
        task = Task(arrival_time=arrival_time, **data)
        PENDING_QUEUE.append(task)
        ACTIVE_TASKS[task.id] = task
        print(f"[{arrival_time:04.1f}s] MASTER: Nova requisição recebida: {task}")
        time.sleep(arrival_delay) # Simula o tempo de chegada

    total_requests = len(ACTIVE_TASKS)
    completed_requests = 0
    
    # Lista para armazenar métricas
    all_metrics: List[Dict[str, Any]] = []

    # Loop principal de orquestração (Critério 5.1)
    while completed_requests < total_requests:
        current_time = time.time() - start_simulation_time
        
        # --- 3.1 PROCESSA CONCLUSÕES DOS WORKERS (IPC) ---
        
        while not return_queue.empty():
            # Recebe mensagens de conclusão da fila de retorno
            result = return_queue.get()
            req_id = result['req_id']
            worker_id = result['worker_id']
            
            # Verifica se a tarefa ainda está no registro de ativas (deve estar)
            if req_id in ACTIVE_TASKS:
                task = ACTIVE_TASKS[req_id]
                
                # O tempo de vida (tempo_vida) é o turnaround time (tempo_conclusão - tempo_chegada)
                turnaround_time = result['completion_time'] - task.arrival_time
                waiting_time = result['start_time'] - task.arrival_time
                
                # Coleta métricas
                task_metrics = {
                    "id": req_id,
                    "worker_id": worker_id,
                    "arrival_time": task.arrival_time,
                    "completion_time": result['completion_time'],
                    "turnaround_time": turnaround_time,
                    "waiting_time": waiting_time,
                    "exec_time_real": result['exec_time_real']
                }
                all_metrics.append(task_metrics)
                
                # Libera a carga do Worker
                capacity = SERVER_CONFIG[worker_id-1]['capacity']
                
                # O valor exato do exec_time da requisição é usado para liberar a carga
                original_exec_time = task.exec_time
                WORKER_LOAD[worker_id] -= original_exec_time / capacity
                completed_requests += 1
                
                # Log de conclusão solicitado 
                print(f"[{result['completion_time']:04.1f}s] Servidor {worker_id} CONCLUIU Requisição {req_id} em {turnaround_time:.2f}s")
                
                del ACTIVE_TASKS[req_id]
        
        # --- 3.2 APLICA POLÍTICA DE ESCALONAMENTO E DISTRIBUIÇÃO ---
        
        if PENDING_QUEUE:
            
            # 1. Escalonamento (Ordenação da fila - Critério 4.0)
            
            # SJF
            if policy == "SJF":
                # Ordena a fila pelo menor tempo de execução estimado
                # PENDIN_QUEUE é reordenado no Master antes de distribuir o próximo item
                PENDING_QUEUE = deque(sorted(PENDING_QUEUE, key=lambda t: t.exec_time))
                print(f"[{current_time:04.1f}s] MASTER: INICIANDO SJF (Shortest Job First)")
            
            # Prioridade
            elif policy == "PRIORIDADE":
                # Ordena a fila pela prioridade (1 é maior prioridade)
                # PENDIN_QUEUE é reordenado no Master antes de distribuir o próximo item
                PENDING_QUEUE = deque(sorted(PENDING_QUEUE, key=lambda t: t.priority))
                print(f"[{current_time:04.1f}s] MASTER: INICIANDO PRIORIDADE")
            
            # Round Robin (RR) - Ordem de chegada (FIFO), não precisa reordenar
            
            # 2. Distribuição para o Worker menos carregado (Load Balancing - Menor Carga Ajustada)
            
            # Calcula a carga ajustada (carga/capacidade) para encontrar o "melhor" worker
            adjusted_loads = {}
            for s in SERVER_CONFIG:
                worker_id = s['id']
                capacity = s['capacity']
                adjusted_loads[worker_id] = WORKER_LOAD[worker_id] / capacity
            
            # Encontra o worker com a menor carga ajustada
            best_worker_id = min(adjusted_loads, key=adjusted_loads.get)
            best_worker_capacity = SERVER_CONFIG[best_worker_id-1]['capacity']
            
            # Pega a próxima tarefa da fila escalonada
            task_to_assign = PENDING_QUEUE.popleft()
            
            # Log de atribuição de acordo com a política
            if policy == "SJF":
                print(f"[{current_time:04.1f}s] [SJF] Req {task_to_assign.id} ({task_to_assign.exec_time}s) -> Servidor {best_worker_id}")
            elif policy == "PRIORIDADE":
                print(f"[{current_time:04.1f}s] [PRIO] Req {task_to_assign.id} (Prio: {task_to_assign.priority}) -> Servidor {best_worker_id}")
            else: # RR
                 print(f"[{current_time:04.1f}s] [RR] Req {task_to_assign.id} -> Servidor {best_worker_id}")

            # Atribui a tarefa
            task_to_assign.worker_id = best_worker_id
            task_to_assign.start_time = current_time 
            
            # Atualiza a carga do worker no Master
            task_load = task_to_assign.exec_time / best_worker_capacity
            WORKER_LOAD[best_worker_id] += task_load
            
            # Envia para a Fila do Worker (IPC)
            task_queues[best_worker_id].put(task_to_assign)
            
        else:
            # Espera se não houver tarefas pendentes
            time.sleep(0.1)

    # Fim da simulação
    end_simulation_time = time.time()
    
    # Terminar workers (enviando sinal de parada)
    for w_id in task_queues:
        task_queues[w_id].put(None) 
        
    return all_metrics, end_simulation_time - start_simulation_time

# --- 4. CÁLCULO DE MÉTRICAS (Critério 6.0) ---

def calculate_metrics(all_metrics: List[Dict[str, Any]], total_simulation_time: float):
    """Calcula e exibe as métricas de desempenho finais."""
    if not all_metrics:
        print("\nNenhuma tarefa concluída para calcular métricas.")
        return

    N = len(all_metrics)
    total_turnaround_time = sum(m['turnaround_time'] for m in all_metrics)
    
    # Cálculo das Métricas Principais (Rômulo)
    tempo_medio_resposta = total_turnaround_time / N
    throughput = N / total_simulation_time
    
    # Cálculo de Utilização Média da CPU (Completo)
    total_real_exec_time = sum(m['exec_time_real'] for m in all_metrics)
    total_capacity = sum(s['capacity'] for s in SERVER_CONFIG)
    
    # Utilização = (Tempo Total de Processamento Real) / (Tempo Total de Simulação * Capacidade Total)
    avg_cpu_utilization = (total_real_exec_time / total_simulation_time) / total_capacity 
    avg_cpu_utilization = min(1.0, avg_cpu_utilization) * 100 # Limita a 100%
    
    # Taxa de Espera Máxima (Completo)
    max_waiting_time = max(m['waiting_time'] for m in all_metrics)


    # --- SAÍDA FINAL (FORMATO SOLICITADO) ---
    print("\n" + "="*40)
    print("RESUMO FINAL DA EXECUÇÃO (BSB Compute)")
    print("="*40)
    print(f"Política Utilizada: {POLICY}")
    print(f"Tempo Total de Simulação: {total_simulation_time:.2f}s")
    print(f"Tempo Médio de Resposta:  {tempo_medio_resposta:.2f}s")
    print(f"Throughput (Vazão):       {throughput:.2f} tarefas/segundo")
    # Métricas adicionais para o relatório completo:
    print(f"Utilização média da CPU: {avg_cpu_utilization:.2f}%")
    print(f"Taxa de espera máxima: {max_waiting_time:.2f}s")
    print("="*40 + "\n")


# --- 5. INICIALIZAÇÃO DO SISTEMA ---

if __name__ == '__main__':
    # --- CONFIGURAÇÃO MANUAL ---
    # Escolha a política: "RR" (Round Robin), "SJF" (Shortest Job First), ou "PRIORIDADE"
    POLICY = "SJF" # Mude esta variável para testar as outras políticas
    
    # --- INICIALIZAÇÃO AUTOMÁTICA ---
    multiprocessing.set_start_method('spawn') # Garante compatibilidade
    
    # 1. Configurar IPC (Filas)
    return_queue = multiprocessing.Queue()
    task_queues = {}
    
    # 2. Iniciar Processos Worker
    workers: List[multiprocessing.Process] = []
    print("\n--- INICIALIZANDO SERVIDORES ---")
    for server in SERVER_CONFIG:
        q = multiprocessing.Queue()
        task_queues[server['id']] = q
        
        p = multiprocessing.Process(
            target=worker_process,
            args=(server['id'], server['capacity'], q, return_queue)
        )
        workers.append(p)
        p.start()

    # 3. Iniciar Processo Master
    print("\n--- INICIALIZANDO ORQUESTRADOR ---")
    
    # Inicia o orquestrador e espera que todas as tarefas sejam concluídas
    all_metrics, total_time = master_orchestrator(task_queues, return_queue, POLICY)

    # 4. Finalizar Processos Worker
    # Encerramento dos processos é feito dentro do master_orchestrator 
    # (envio de sinal None) antes do return.
    for p in workers:
        p.join() # Espera o worker terminar
        
    # 5. Calcular e Apresentar Métricas Finais
    calculate_metrics(all_metrics, total_time)