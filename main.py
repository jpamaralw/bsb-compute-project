import multiprocessing
import time
import random
import json
import os
import sys
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
json_filename = "input.json"
if len(sys.argv) > 2:
    json_filename = sys.argv[2]

print(f"--- Carregando configuração de: {json_filename} ---")
CONFIG_DATA = load_config(json_filename) 

SERVER_CONFIG = CONFIG_DATA.get("server_config", [])
REQUEST_DATA = CONFIG_DATA.get("request_data", [])

if not SERVER_CONFIG or not REQUEST_DATA:
    print("A simulação não pode continuar: Dados de configuração ou requisições ausentes/inválidos.")
    exit()

# --- AUXILIAR DE TEMPO ---
def format_time(seconds: float) -> str:
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"[{minutes:02d}:{secs:02d}]"

# --- CLASSES ---
class Task:
    def __init__(self, id: int, type: str, priority: int, exec_time: float, arrival_time: float = 0.0):
        self.id = id
        self.type = type
        self.priority = priority
        self.exec_time = exec_time
        self.arrival_time = arrival_time
        self.start_time = 0.0
        self.completion_time = 0.0
        self.worker_id = None
        self.migrated = False

    def get_priority_name(self) -> str:
        prio_map = {1: 'Alta', 2: 'Média', 3: 'Baixa'}
        return prio_map.get(self.priority, 'N/A')

    def __repr__(self):
        return f"Req {self.id}"


# --- WORKER PROCESS (CORRIGIDO PARA MIGRAÇÃO) ---
def worker_process(worker_id: int, capacity: int, task_queue: Any, 
                   return_queue: Any, migration_queue: Any,
                   start_time_shared: Any):
    """
    Worker com lógica corrigida: Pega a tarefa -> Verifica Migração -> Processa.
    """
    print(f"[INIT] Servidor {worker_id} (Capacidade: {capacity}) pronto.")
    local_pending: List[Task] = []

    while True:
        # 1. Tenta pegar uma nova tarefa da fila (se não tiver nenhuma na mão)
        if not local_pending:
            try:
                # Timeout curto para não bloquear a verificação de migração
                task = task_queue.get(timeout=0.1)
                if task is None: break # Sinal de encerramento
                local_pending.append(task)
            except multiprocessing.queues.Empty:
                pass # Fila vazia, continua o loop

        # 2. Verifica se o Master pediu MIGRAÇÃO
        migrated_flag = False
        while not migration_queue.empty():
            try:
                cmd = migration_queue.get_nowait()
                if cmd.get("action") == "migrate_out" and local_pending:
                    # Temos tarefa na mão e ordem de migrar!
                    # Ordena para migrar a menos prioritária (ou a mais recente)
                    local_pending.sort(key=lambda t: -t.priority)
                    task_to_migrate = local_pending.pop(0)
                    task_to_migrate.migrated = True
                    
                    return_queue.put({
                        "status": "migrated",
                        "task": task_to_migrate,
                        "from_worker": worker_id
                    })
                    migrated_flag = True
            except:
                pass
        
        # Se migrou, volta ao início para ver se tem mais ordens ou tarefas
        if migrated_flag:
            continue

        # 3. Processamento (Se tiver tarefa na mão)
        if local_pending:
            # Ordena por prioridade para processar a mais importante
            local_pending.sort(key=lambda t: t.priority)
            task = local_pending.pop(0)

            actual_exec_time = task.exec_time / capacity
            current_sim_time = time.time() - start_time_shared.value
            task.start_time = current_sim_time
            
            mig_info = " [MIGRADA]" if task.migrated else ""
            print(f"{format_time(current_sim_time)} Servidor {worker_id} processando Req {task.id} ({task.get_priority_name()}){mig_info} (Tempo Real: {actual_exec_time:.1f}s)")
            
            # Simula processamento
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
        
        else:
            # Se não tem tarefa nem migração, dorme um pouco para economizar CPU
            time.sleep(0.1)


# --- MASTER ORCHESTRATOR ---
def master_orchestrator(task_queues: Dict[int, Any], return_queue: Any,
                        migration_queues: Dict[int, Any], start_time_shared: Any,
                        policy: str):
    
    pending_queue: Deque[Task] = deque()
    worker_load: Dict[int, float] = {s['id']: 0.0 for s in SERVER_CONFIG}
    worker_task_count: Dict[int, int] = {s['id']: 0 for s in SERVER_CONFIG}
    active_tasks: Dict[int, Task] = {}
    
    start_simulation_time = time.time()
    start_time_shared.value = start_simulation_time
    rr_index = 0
    MIGRATION_THRESHOLD = 1.3 # Sensibilidade alta
    
    print(f"\n{format_time(0)} --- INICIANDO SIMULAÇÃO (Política: {policy}) ---\n")
    
    # Gera requisições
    all_reqs = []
    for data in REQUEST_DATA:
        delay = random.uniform(0.1, 1.5) if all_reqs else 0
        arr_time = (time.time() - start_simulation_time) + delay
        t = Task(data['id'], data['type'], data['priority'], data['exec_time'], arr_time)
        all_reqs.append(t)
        pending_queue.append(t)
        active_tasks[t.id] = t
        print(f"{format_time(arr_time)} Requisição {t.id} ({t.get_priority_name()}) chegou")
        time.sleep(delay)

    total_reqs = len(active_tasks)
    completed_reqs = 0
    all_metrics = []
    migrations_count = 0

    while completed_reqs < total_reqs:
        current_time = time.time() - start_simulation_time
        
        # Processa Retornos
        while not return_queue.empty():
            res = return_queue.get()
            
            if res["status"] == "migrated":
                task = res["task"]
                from_w = res["from_worker"]
                # Migra para o menos carregado
                best_w = find_least_loaded_worker(worker_load, SERVER_CONFIG, exclude=from_w)
                if best_w:
                    print(f"{format_time(current_time)} [MIGRATION] Requisição {task.id} movida do Servidor {from_w} para {best_w}!")
                    cap_old = get_capacity(from_w)
                    cap_new = get_capacity(best_w)
                    worker_load[from_w] -= task.exec_time / cap_old
                    worker_load[best_w] += task.exec_time / cap_new
                    worker_task_count[from_w] -= 1
                    worker_task_count[best_w] += 1
                    task_queues[best_w].put(task)
                    migrations_count += 1
                continue

            if res["status"] == "completed":
                # Atualiza métricas e carga
                wid = res["worker_id"]
                rid = res["req_id"]
                if rid in active_tasks:
                    task_orig = active_tasks[rid]
                    all_metrics.append({
                        "id": rid,
                        "turnaround_time": res["completion_time"] - task_orig.arrival_time,
                        "waiting_time": res["start_time"] - task_orig.arrival_time,
                        "exec_time_real": res["exec_time_real"],
                        "migrated": res["migrated"]
                    })
                    cap = get_capacity(wid)
                    worker_load[wid] = max(0, worker_load[wid] - (task_orig.exec_time / cap))
                    worker_task_count[wid] -= 1
                    completed_reqs += 1
                    del active_tasks[rid]
                    
                    mig_txt = " [MIGRADA]" if res["migrated"] else ""
                    print(f"{format_time(res['completion_time'])} Servidor {wid} CONCLUIU Req {rid}{mig_txt}")

        # Distribui Novas Tarefas
        if pending_queue:
            if policy == "SJF": pending_queue = deque(sorted(pending_queue, key=lambda t: t.exec_time))
            elif policy == "PRIORIDADE": pending_queue = deque(sorted(pending_queue, key=lambda t: t.priority))
            
            best_w = None
            if policy == "RR": # RR Cíclico (Burro)
                idx = rr_index % len(SERVER_CONFIG)
                best_w = SERVER_CONFIG[idx]['id']
                rr_index += 1
            else: # Outros (Inteligente)
                best_w = find_least_loaded_worker(worker_load, SERVER_CONFIG)
            
            if best_w:
                t = pending_queue.popleft()
                cap = get_capacity(best_w)
                worker_load[best_w] += t.exec_time / cap
                worker_task_count[best_w] += 1
                task_queues[best_w].put(t)
                print(f"{format_time(current_time)} [{policy}] Req {t.id} atribuída ao Servidor {best_w}")

        # Verifica Migração (SEMPRE)
        check_and_trigger_migration(worker_load, worker_task_count, migration_queues, MIGRATION_THRESHOLD)
        
        if not pending_queue:
            time.sleep(0.1)

    for w_id in task_queues: task_queues[w_id].put(None)
    return all_metrics, time.time() - start_simulation_time, migrations_count


# --- FUNÇÕES UTILITÁRIAS ---
def find_least_loaded_worker(worker_load, server_config, exclude=None):
    loads = {}
    for s in server_config:
        if s['id'] == exclude: continue
        loads[s['id']] = worker_load[s['id']] / s['capacity']
    return min(loads, key=loads.get) if loads else None

def get_capacity(wid):
    for s in SERVER_CONFIG:
        if s['id'] == wid: return s['capacity']
    return 1

def check_and_trigger_migration(worker_load, worker_task_count, migration_queues, threshold):
    if len(worker_load) < 2: return
    loads = list(worker_load.values())
    min_l = max(min(loads), 0.1)
    max_l = max(loads)
    
    if max_l > 0 and (max_l / min_l) > threshold:
        overloaded = None
        max_found = 0
        for wid, l in worker_load.items():
            # Só migra se tiver mais de 1 tarefa (não tira a que está rodando)
            if l > max_found and worker_task_count.get(wid, 0) > 1:
                max_found = l
                overloaded = wid
        
        if overloaded:
            migration_queues[overloaded].put({"action": "migrate_out"})

def calculate_metrics(metrics, total_time, mig_count, policy):
    if not metrics: return
    N = len(metrics)
    avg_resp = sum(m['turnaround_time'] for m in metrics) / N
    throughput = N / total_time
    total_exec = sum(m['exec_time_real'] for m in metrics)
    total_cap = sum(s['capacity'] for s in SERVER_CONFIG)
    cpu_util = (total_exec / total_time) / total_cap * 100
    max_wait = max(m['waiting_time'] for m in metrics)
    migrated = sum(1 for m in metrics if m['migrated'])

    print("\n" + "-"*50)
    print("RESUMO FINAL DA EXECUÇÃO (BSB Compute)")
    print("-"*50)
    print(f"Política:              {policy}")
    print(f"Tempo Total:           {total_time:.2f}s")
    print(f"Tempo Médio Resposta:  {avg_resp:.2f}s")
    print(f"Throughput:            {throughput:.2f} req/s")
    print(f"CPU Utilização:        {cpu_util:.2f}%")
    print(f"Migrações Realizadas:  {mig_count}")
    print(f"Tarefas Migradas:      {migrated}")
    print("-" * 50)

# --- MAIN ---
if __name__ == '__main__':
    multiprocessing.set_start_method('spawn')
    
    # Argumentos CLI
    POLICY = "RR"
    if len(sys.argv) > 1: POLICY = sys.argv[1].upper()
    if POLICY not in ["RR", "SJF", "PRIORIDADE"]: POLICY = "RR"

    start_time_shared = multiprocessing.Value('d', 0.0)
    return_queue = multiprocessing.Queue()
    task_queues = {}
    migration_queues = {}
    workers = []

    print(f"\nBSB COMPUTE | Política: {POLICY} | Config: {json_filename}")
    
    for s in SERVER_CONFIG:
        tq = multiprocessing.Queue()
        mq = multiprocessing.Queue()
        task_queues[s['id']] = tq
        migration_queues[s['id']] = mq
        p = multiprocessing.Process(target=worker_process, args=(s['id'], s['capacity'], tq, return_queue, mq, start_time_shared))
        workers.append(p)
        p.start()
    
    time.sleep(1) # Wait workers
    
    metrics, t_total, migs = master_orchestrator(task_queues, return_queue, migration_queues, start_time_shared, POLICY)
    
    for p in workers: p.join()
    
    calculate_metrics(metrics, t_total, migs, POLICY)