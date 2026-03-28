'''
TODO
weigths
max time
'''
from collections import deque



def topo_sort(tasks):
    adj = [t["deps"] for t in tasks]
    n = len(adj)
    indegree = [0] * n
    res = []
    queue = deque()

    # Compute indegrees
    for i in range(n):
        for next_node in adj[i]:
            indegree[next_node] += 1

    # Add all nodes with indegree 0 
    # into the queue
    for i in range(n):
        if indegree[i] == 0:
            queue.append(i)

    # Kahn’s Algorithm
    while queue:
        top = queue.popleft()
        res.append(top)
        for next_node in adj[top]:
            indegree[next_node] -= 1
            if indegree[next_node] == 0:
                queue.append(next_node)

    return res

if __name__ == "__main__":
    tasks = [
        {"name": "Task 0", "deps": []},
        {"name": "Task 1", "deps": [2]},
        {"name": "Task 2", "deps": [0]}
    ]

    print("Sorted: ", topo_sort(tasks))
