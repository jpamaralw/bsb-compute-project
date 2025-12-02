import multiprocessing
import time
import random
import json
import os
from collections import deque
from typing import List, Dict, Any, Deque, Optional

# --- FUNÇÃO DE CARREGAMENTO DE CONFIGURAÇÃO ---

def load_config(filepath: str) -> Dict[str, List[Dict[str, Any]]]:
    """Carrega as configurações de servidores e requisições de um arquivo JSON."""
    if not os.path.exists(filepath):
        print(f"ERRO: Arquivo de configuração não encontrado em: {filepath}")
        return {"server_config": [], "request_data": []}
    
    try:
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
CONFIG_DATA = load_config("input.json") 

SERVER_CONFIG = CONFIG_DATA.get("server_config", [])
REQUEST_DATA = CONFIG_DATA.get("request_data", [])

if not SERVER_CONFIG or not REQUEST_DATA:
    print("A simulação não pode continuar: Dados de configuração ou requisições ausentes/inválidos.")
    exit()

# --- FUNÇÃO AUXILIAR PARA FORMATAR TEMPO ---

def format_time(seconds: float) -> str:
    """Formata o tempo em [MM:SS] conforme especificado no projeto."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"[{minutes:02d}:{secs:02d}]"

# --- 1. DEFINIÇÕES DE CLASSES E DADOS ---

class Task:
    """Representa uma Requisição de Inferência (Tarefa)."""
    def __init__(self, id: int, type: str, priority: int, exec_time: float, arrival_time: float = 0.0):
        self.id = id
        self.type = type
        self.priority = priority  # 1 (Alta) > 2 (Média) > 3 (Baixa)
        self.exec_time = exec_time
        self.arrival_time = arrival_time
        self.start_time = 0.0
        self.completion_time = 0.0
        self.worker_id = None
        self.migrated = False  # Flag para indicar se a tarefa foi migrada

    def get_priority_name(self) -> str:
        """Retorna o nome da prioridade para logs."""
        prio_map = {1: 'Alta', 2: 'Média', 3: 'Baixa'}
        return prio_map.get(self.priority, 'N/A')

    def __repr__(self):
        return (f"Req {self.id} ({self.get_priority_name()}, "
                f"T={self.exec_time:.1f}s, Chegada={self.arrival_time:.1f}s)")


# --- 2. FUNÇÃO DO PROCESSO WORKER ---

def worker_process(worker_id: int, capacity: int, task_queue: Any, 
                   return_queue: Any, migration_queue: Any,
                   start_time_shared: Any):
    """
    Simula um Servidor de Inferência (Worker).
    Agora com suporte a migração de tarefas.
    """
    print(f"[INIT] Servidor {worker_id} (Capacidade: {capacity}) pronto.")
    
    # Fila local de tarefas pendentes (para possível migração)
    local_pending: List[Task] = []

    while True:
        try:
            # Verifica se há tarefas para migrar (enviadas pelo Master)
            while not migration_queue.empty():
                try:
                    migration_cmd = migration_queue.get_nowait()
                    if migration_cmd and migration_cmd.get("action") == "migrate_out":
                        # Master pediu para migrar uma tarefa - enviamos de volta as pendentes de baixa prioridade
                        if local_pending:
                            # Ordena por prioridade (maior número = menor prioridade = migrar primeiro)
                            local_pending.sort(key=lambda t: -t.priority)
                            task_to_migrate = local_pending.pop(0)
                            task_to_migrate.migrated = True
                            return_queue.put({
                                "status": "migrated",
                                "task": task_to_migrate,
                                "from_worker": worker_id
                            })
                except:
                    pass

            # Tenta pegar uma tarefa da fila principal
            task: Task = task_queue.get(timeout=0.5)
            
            # Sinal de parada
            if task is None:
                break
            
            # Adiciona à fila local (para possível migração futura)
            local_pending.append(task)
            
            # Processa tarefas da fila local em ordem de prioridade
            local_pending.sort(key=lambda t: t.priority)
            task = local_pending.pop(0)
            
            # --- SIMULAÇÃO DA EXECUÇÃO ---
            actual_exec_time = task.exec_time / capacity
            
            # Calcula tempo relativo ao início da simulação
            current_sim_time = time.time() - start_time_shared.value
            task.start_time = current_sim_time
            
            migration_info = " [MIGRADA]" if task.migrated else ""
            print(f"{format_time(current_sim_time)} Servidor {worker_id} processando Req {task.id} ({task.get_priority_name()}){migration_info} (Tempo Real: {actual_exec_time:.1f}s)")
            
            # Simula o processamento
            time.sleep(actual_exec_time)
            
            # Registra tempo de conclusão
            task.completion_time = time.time() - start_time_shared.value
            
            # Reporta conclusão ao Master
            return_queue.put({
                "status": "completed",
                "req_id": task.id,
                "worker_id": worker_id,
                "exec_time_real": actual_exec_time,
                "arrival_time": task.arrival_time,
                "completion_time": task.completion_time,
                "start_time": task.start_time,
                "migrated": task.migrated
            })
            
            print(f"{format_time(task.completion_time)} Servidor {worker_id} concluiu Requisição {task.id}")
            
        except multiprocessing.queues.Empty:
            # Processa tarefas pendentes locais se houver
            if local_pending:
                local_pending.sort(key=lambda t: t.priority)
                task = local_pending.pop(0)
                
                actual_exec_time = task.exec_time / capacity
                current_sim_time = time.time() - start_time_shared.value
                task.start_time = current_sim_time
                
                migration_info = " [MIGRADA]" if task.migrated else ""
                print(f"{format_time(current_sim_time)} Servidor {worker_id} processando Req {task.id} ({task.get_priority_name()}){migration_info}")
                
                time.sleep(actual_exec_time)
                task.completion_time = time.time() - start_time_shared.value
                
                return_queue.put({
                    "status": "completed",
                    "req_id": task.id,
                    "worker_id": worker_id,
                    "exec_time_real": actual_exec_time,
                    "arrival_time": task.arrival_time,
                    "completion_time": task.completion_time,
                    "start_time": task.start_time,
                    "migrated": task.migrated
                })
                
                print(f"{format_time(task.completion_time)} Servidor {worker_id} concluiu Requisição {task.id}")
        except KeyboardInterrupt:
            break


# --- 3. FUNÇÃO DO PROCESSO MASTER (ORQUESTRADOR) ---

def master_orchestrator(task_queues: Dict[int, Any], 
                        return_queue: Any,
                        migration_queues: Dict[int, Any],
                        start_time_shared: Any,
                        policy: str):
    """
    Simula o Orquestrador Central (Master).
    Agora com suporte a migração de tarefas entre servidores.
    """
    
    # Variáveis de controle
    pending_queue: Deque[Task] = deque()
    worker_load: Dict[int, float] = {s['id']: 0.0 for s in SERVER_CONFIG}
    worker_task_count: Dict[int, int] = {s['id']: 0 for s in SERVER_CONFIG}  # Número de tarefas em cada worker
    active_tasks: Dict[int, Task] = {}
    
    start_simulation_time = time.time()
    start_time_shared.value = start_simulation_time
    
    # Limiar de sobrecarga para migração (se um servidor tem X vezes mais carga que outro)
    MIGRATION_THRESHOLD = 2.0
    
    print(f"\n{format_time(0)} --- INICIANDO SIMULAÇÃO (Política: {policy}) ---\n")
    
    # --- GERAÇÃO DE REQUISIÇÕES COM CHEGADA ALEATÓRIA ---
    all_requests: List[Task] = []
    for data in REQUEST_DATA:
        arrival_delay = random.uniform(0.1, 1.5) if all_requests else 0
        arrival_time = (time.time() - start_simulation_time) + arrival_delay
        
        task = Task(
            id=data['id'],
            type=data['type'],
            priority=data['priority'],
            exec_time=data['exec_time'],
            arrival_time=arrival_time
        )
        all_requests.append(task)
        pending_queue.append(task)
        active_tasks[task.id] = task
        
        print(f"{format_time(arrival_time)} Requisição {task.id} ({task.get_priority_name()}) chegou - Tipo: {task.type}")
        time.sleep(arrival_delay)

    total_requests = len(active_tasks)
    completed_requests = 0
    all_metrics: List[Dict[str, Any]] = []
    migrations_count = 0

    # --- LOOP PRINCIPAL DE ORQUESTRAÇÃO ---
    while completed_requests < total_requests:
        current_time = time.time() - start_simulation_time
        
        # --- PROCESSA RETORNOS DOS WORKERS ---
        while not return_queue.empty():
            result = return_queue.get()
            
            # Tarefa migrada - redistribuir
            if result.get("status") == "migrated":
                migrated_task = result["task"]
                from_worker = result["from_worker"]
                
                # Encontra o melhor servidor para receber a tarefa
                best_worker = find_least_loaded_worker(worker_load, SERVER_CONFIG, exclude=from_worker)
                
                if best_worker:
                    print(f"{format_time(current_time)} Requisição {migrated_task.id} ({migrated_task.get_priority_name()}) "
                          f"MIGRADA do Servidor {from_worker} para Servidor {best_worker}")
                    
                    # Atualiza cargas
                    worker_load[from_worker] -= migrated_task.exec_time / get_capacity(from_worker)
                    worker_load[best_worker] += migrated_task.exec_time / get_capacity(best_worker)
                    worker_task_count[from_worker] -= 1
                    worker_task_count[best_worker] += 1
                    
                    # Envia para o novo worker
                    task_queues[best_worker].put(migrated_task)
                    migrations_count += 1
                continue
            
            # Tarefa concluída
            if result.get("status") == "completed":
                req_id = result['req_id']
                worker_id = result['worker_id']
                
                if req_id in active_tasks:
                    task = active_tasks[req_id]
                    
                    turnaround_time = result['completion_time'] - task.arrival_time
                    waiting_time = result['start_time'] - task.arrival_time
                    
                    task_metrics = {
                        "id": req_id,
                        "worker_id": worker_id,
                        "arrival_time": task.arrival_time,
                        "completion_time": result['completion_time'],
                        "turnaround_time": turnaround_time,
                        "waiting_time": waiting_time,
                        "exec_time_real": result['exec_time_real'],
                        "migrated": result.get('migrated', False)
                    }
                    all_metrics.append(task_metrics)
                    
                    # Atualiza carga do worker
                    capacity = get_capacity(worker_id)
                    worker_load[worker_id] -= task.exec_time / capacity
                    worker_load[worker_id] = max(0, worker_load[worker_id])  # Evita valores negativos
                    worker_task_count[worker_id] -= 1
                    completed_requests += 1
                    
                    migration_info = " [MIGRADA]" if result.get('migrated') else ""
                    print(f"{format_time(result['completion_time'])} Servidor {worker_id} CONCLUIU "
                          f"Requisição {req_id} ({task.get_priority_name()}){migration_info} em {turnaround_time:.2f}s")
                    
                    del active_tasks[req_id]
        
        # --- APLICA POLÍTICA DE ESCALONAMENTO E DISTRIBUIÇÃO ---
        if pending_queue:
            # Ordenação conforme política
            if policy == "SJF":
                pending_queue = deque(sorted(pending_queue, key=lambda t: t.exec_time))
            elif policy == "PRIORIDADE":
                pending_queue = deque(sorted(pending_queue, key=lambda t: t.priority))
            # RR: mantém ordem de chegada (FIFO)
            
            # Encontra o melhor worker (menor carga ajustada)
            best_worker_id = find_least_loaded_worker(worker_load, SERVER_CONFIG)
            
            if best_worker_id:
                task_to_assign = pending_queue.popleft()
                best_worker_capacity = get_capacity(best_worker_id)
                
                # Log de atribuição
                if policy == "SJF":
                    print(f"{format_time(current_time)} [SJF] Requisição {task_to_assign.id} "
                          f"({task_to_assign.exec_time}s) atribuída ao Servidor {best_worker_id}")
                elif policy == "PRIORIDADE":
                    print(f"{format_time(current_time)} [PRIO] Requisição {task_to_assign.id} "
                          f"({task_to_assign.get_priority_name()}) atribuída ao Servidor {best_worker_id}")
                else:
                    print(f"{format_time(current_time)} [RR] Requisição {task_to_assign.id} "
                          f"({task_to_assign.get_priority_name()}) atribuída ao Servidor {best_worker_id}")

                # Atualiza controles
                task_to_assign.worker_id = best_worker_id
                task_load = task_to_assign.exec_time / best_worker_capacity
                worker_load[best_worker_id] += task_load
                worker_task_count[best_worker_id] += 1
                
                # Envia para o worker
                task_queues[best_worker_id].put(task_to_assign)
                
                # --- VERIFICA NECESSIDADE DE MIGRAÇÃO ---
                check_and_trigger_migration(worker_load, worker_task_count, migration_queues, 
                                           MIGRATION_THRESHOLD, current_time)
        else:
            time.sleep(0.1)

    # Fim da simulação
    end_simulation_time = time.time()
    
    # Encerra workers
    for w_id in task_queues:
        task_queues[w_id].put(None) 
        
    return all_metrics, end_simulation_time - start_simulation_time, migrations_count


def find_least_loaded_worker(worker_load: Dict[int, float], server_config: List[Dict], 
                              exclude: Optional[int] = None) -> Optional[int]:
    """Encontra o worker com menor carga ajustada."""
    adjusted_loads = {}
    for s in server_config:
        worker_id = s['id']
        if worker_id == exclude:
            continue
        capacity = s['capacity']
        adjusted_loads[worker_id] = worker_load[worker_id] / capacity
    
    if not adjusted_loads:
        return None
    return min(adjusted_loads, key=adjusted_loads.get)


def get_capacity(worker_id: int) -> int:
    """Retorna a capacidade de um worker pelo ID."""
    for s in SERVER_CONFIG:
        if s['id'] == worker_id:
            return s['capacity']
    return 1


def check_and_trigger_migration(worker_load: Dict[int, float], worker_task_count: Dict[int, int],
                                 migration_queues: Dict[int, multiprocessing.Queue],
                                 threshold: float, current_time: float):
    """
    Verifica se algum servidor está sobrecarregado e dispara migração.
    """
    if len(worker_load) < 2:
        return
    
    loads = list(worker_load.values())
    min_load = min(loads) if min(loads) > 0 else 0.1
    max_load = max(loads)
    
    # Se a diferença de carga for maior que o threshold, migra
    if max_load > 0 and (max_load / max(min_load, 0.1)) > threshold:
        # Encontra o servidor mais carregado com mais de 1 tarefa
        overloaded_worker = None
        max_load_found = 0
        for w_id, load in worker_load.items():
            if load > max_load_found and worker_task_count.get(w_id, 0) > 1:
                max_load_found = load
                overloaded_worker = w_id
        
        if overloaded_worker:
            # Solicita migração
            migration_queues[overloaded_worker].put({"action": "migrate_out"})


# --- 4. CÁLCULO DE MÉTRICAS ---

def calculate_metrics(all_metrics: List[Dict[str, Any]], total_simulation_time: float, 
                      migrations_count: int, policy: str):
    """Calcula e exibe as métricas de desempenho finais."""
    if not all_metrics:
        print("\nNenhuma tarefa concluída para calcular métricas.")
        return

    N = len(all_metrics)
    total_turnaround_time = sum(m['turnaround_time'] for m in all_metrics)
    
    # Métricas principais
    tempo_medio_resposta = total_turnaround_time / N
    throughput = N / total_simulation_time
    
    # Utilização média da CPU
    total_real_exec_time = sum(m['exec_time_real'] for m in all_metrics)
    total_capacity = sum(s['capacity'] for s in SERVER_CONFIG)
    avg_cpu_utilization = (total_real_exec_time / total_simulation_time) / total_capacity 
    avg_cpu_utilization = min(1.0, avg_cpu_utilization) * 100
    
    # Taxa de espera máxima
    max_waiting_time = max(m['waiting_time'] for m in all_metrics)
    
    # Contagem de tarefas migradas
    migrated_tasks = sum(1 for m in all_metrics if m.get('migrated', False))

    # --- SAÍDA FINAL (FORMATO DO PROJETO) ---
    print("\n" + "-"*50)
    print("RESUMO FINAL DA EXECUÇÃO (BSB Compute)")
    print("-"*50)
    print(f"Política Utilizada:        {policy}")
    print(f"Total de Requisições:      {N}")
    print(f"Tempo Total de Simulação:  {total_simulation_time:.2f}s")
    print(f"Tempo Médio de Resposta:   {tempo_medio_resposta:.2f}s")
    print(f"Utilização média da CPU:   {avg_cpu_utilization:.2f}%")
    print(f"Taxa de espera máxima:     {max_waiting_time:.2f}s")
    print(f"Throughput (Vazão):        {throughput:.2f} tarefas/segundo")
    print(f"Migrações realizadas:      {migrations_count}")
    print(f"Tarefas migradas:          {migrated_tasks}")
    print("-"*50 + "\n")


# --- 5. INICIALIZAÇÃO DO SISTEMA ---

if __name__ == '__main__':
    # --- CONFIGURAÇÃO ---
    # Escolha a política: "RR" (Round Robin), "SJF" (Shortest Job First), ou "PRIORIDADE"
    POLICY = "RR"
    
    # --- INICIALIZAÇÃO ---
    multiprocessing.set_start_method('spawn')
    
    # Variável compartilhada para tempo de início
    start_time_shared = multiprocessing.Value('d', 0.0)
    
    # Filas de comunicação
    return_queue = multiprocessing.Queue()
    task_queues = {}
    migration_queues = {}
    
    # Inicia Workers
    workers: List[multiprocessing.Process] = []
    print("\n" + "="*50)
    print("BSB COMPUTE - Sistema de Orquestração de Tarefas")
    print("="*50)
    print("\n--- INICIALIZANDO SERVIDORES ---")
    
    for server in SERVER_CONFIG:
        task_q = multiprocessing.Queue()
        migration_q = multiprocessing.Queue()
        task_queues[server['id']] = task_q
        migration_queues[server['id']] = migration_q
        
        p = multiprocessing.Process(
            target=worker_process,
            args=(server['id'], server['capacity'], task_q, return_queue, migration_q, start_time_shared)
        )
        workers.append(p)
        p.start()

    # Aguarda workers iniciarem
    time.sleep(0.5)
    
    # Inicia o Orquestrador
    print("\n--- INICIANDO ORQUESTRADOR ---\n")
    
    all_metrics, total_time, migrations = master_orchestrator(
        task_queues, return_queue, migration_queues, start_time_shared, POLICY
    )

    # Aguarda workers terminarem
    for p in workers:
        p.join()
        
    # Exibe métricas finais
    calculate_metrics(all_metrics, total_time, migrations, POLICY)