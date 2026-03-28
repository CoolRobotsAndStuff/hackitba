'''
TODO
weigths
max time
'''
from collections import deque
from copy import copy, deepcopy

def accesible_from(node, adj):
    ret = []
    q = deque()
    q.append(node)
    while q:
        n = q.popleft()
        ret.append(n)
        for d in adj[n]:
            if d not in q: q.append(d)
    print(ret, "are accesible from", node)
    return ret

def topo_sort(tasks):
    adj = [t["deps"] for t in tasks]
    n = len(adj)
    indegree = [0] * n
    qs = []

    # Compute indegrees
    for i in range(n):
        for next_node in adj[i]:
            indegree[next_node] += 1

    # Add all nodes with indegree 0 
    # into the queue
    for i in range(n):
        if indegree[i] == 0:
            queue = deque()
            queue.append(i)
            qs.append(queue)


    print(qs)
    
    reses = []
    indegrees = []
    for i in range(len(qs)):
        reses.append([])

        indegree = [0] * n
        for j, a in enumerate(accesible_from(qs[i][0], adj)):
            for next_node in adj[j]:
                indegree[next_node] += 1
        indegrees.append(deepcopy(indegree))

    # Kahn’s Algorithm
    for i, queue in enumerate(qs):
        print(queue)
        while queue:
            top = qs[i].popleft()
            reses[i].append(top)
            print(i, reses[i])
            for next_node in adj[top]:
                indegrees[i][next_node] -= 1
                print(i, indegrees[i])
                if indegrees[i][next_node] == 0:
                    qs[i].append(next_node)

    return reses

def longest_path(tasks, src, dst):
    from collections import deque

    n = len(tasks)

    in_degree = [0] * n
    for node in range(n):
        for neighbor in tasks[node]:
            in_degree[neighbor] += 1

    queue = deque(i for i in range(n) if in_degree[i] == 0)
    topo_order = []
    while queue:
        node = queue.popleft()
        topo_order.append(node)
        for neighbor in tasks[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    dist = [-1] * n
    dist[src] = 0

    for node in topo_order:
        if dist[node] == -1:
            continue
        for neighbor in tasks[node]:
            dist[neighbor] = max(dist[neighbor], dist[node] + 1)

    return dist[dst]

def longest_chain_length(node, adj):
    n = len(adj)
    indegree = [0]*n
    for i in range(n):
        for next_node in adj[i]:
            indegree[next_node] += 1
    
    longest = 0
    for root, ind in enumerate(indegree):
        if ind == 0:
            longest = max(longest, longest_path(adj, root, node))
    return longest


def organize_tasks(adj):
    n = len(adj)
    index = []
    for node in range(n):
        index.append(longest_chain_length(node, adj))

    return index

def most_repeated_count(arr):
    from collections import Counter
    element, count = Counter(arr).most_common(1)[0]
    return count

def get_task_timeline(tasks):
    adj = [t["deps"] for t in tasks]
    adj = invert_graph(adj)
    indexes = organize_tasks(adj)

    arr = [] 
    for _ in range(max(indexes)+1):
        arr.append([])
    for node, index in enumerate(indexes):
        arr[index].append(node)

    return arr

def invert_graph(tasks):
    n = len(tasks)
    inverted = [[] for _ in range(n)]
    for node in range(n):
        for neighbor in tasks[node]:
            inverted[neighbor].append(node)
    return inverted

def get_timeline_string(tasks, people):
    timeline = get_task_timeline(tasks);
    
    ret = ""
    for day, task_ids in enumerate(timeline):
        ret += "Day " + str(day) + ":\n"
        for person, task_id in enumerate(task_ids):
            ret += "    - " + tasks[task_id]["name"] + " | " + people[person] +"\n"

    return ret

if __name__ == "__main__":
    tasks = [
        {"name": "Task 0", "deps": []},
        {"name": "Task 1", "deps": [2, 3]},
        {"name": "Task 2", "deps": [3, 0]},
        {"name": "Task 3", "deps": []},
        {"name": "Task 4", "deps": []},
    ]

    people = [
        "Pedro",
        "Juan",
        "María",
        "Lucas",
        "Cacho",
    ]

    print(get_timeline_string(tasks, people));




