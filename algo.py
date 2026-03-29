'''
TODO
weigths
max time
'''
from collections import deque
from copy import copy, deepcopy
from dataclasses import dataclass

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

@dataclass
class TaskBitId:
    id: int
    task: int

def get_task_timeline(tasks):
    adj = [[]]*len(tasks)
    task_parts = list(range(len(tasks)))
    task_index = 0 
    extra = len(adj)
    for i, t in enumerate(tasks):
        if t["days"] == 1:
            adj[i] = t["deps"]
        elif t["days"] == 2:
            adj[i] = [extra,]
            adj.append(t["deps"])
            task_parts.append(i)
            extra += 1
        elif t["days"] >= 3:
            adj[i] = [extra,]
            task_parts.append(i)
            extra += 1
            
            for _ in range(t["days"] - 2):
                adj.append([extra,])
                task_parts.append(i)
                extra += 1

            adj.append(t["deps"])

    #render_graph(adj)
    adj = invert_graph(adj)
    indexes = organize_tasks(adj)

    arr = [] 
    for _ in range(max(indexes)+1):
        arr.append([])
    for node, index in enumerate(indexes):
        arr[index].append(node)

    return arr, task_parts

def invert_graph(tasks):
    n = len(tasks)
    inverted = [[] for _ in range(n)]
    for node in range(n):
        for neighbor in tasks[node]:
            inverted[neighbor].append(node)
    return inverted

def get_timeline_string(tasks):
    timeline, task_parts = get_task_timeline(tasks);
    
    ret = ""
    for day, task_ids in enumerate(timeline):
        ret += "Day " + str(day) + ":\n"
        for person, task_id in enumerate(task_ids):
            ret += "    - " + tasks[task_parts[task_id]]["name"] +"\n"

    return ret

def render_graph(tasks):
    import math

    n = len(tasks)
    R = 3  # "radius" of node in char units (for spacing)
    W, H = 60, 30
    cx, cy = W // 2, H // 2
    radius = 10

    # Position nodes in a circle
    pos = []
    for i in range(n):
        angle = (i / n) * 2 * math.pi - math.pi / 2
        x = int(cx + radius * math.cos(angle))
        y = int(cy + radius * math.sin(angle))
        pos.append((x, y))

    # ASCII canvas
    grid = [[' '] * W for _ in range(H)]

    def draw_line(x0, y0, x1, y1, ch='.'):
        steps = max(abs(x1 - x0), abs(y1 - y0), 1) * 3
        for i in range(steps + 1):
            t = i / steps
            x = int(round(x0 + (x1 - x0) * t))
            y = int(round(y0 + (y1 - y0) * t))
            if 0 <= y < H and 0 <= x < W:
                if grid[y][x] == ' ':
                    grid[y][x] = ch

    def arrowhead(x0, y0, x1, y1):
        dx, dy = x1 - x0, y1 - y0
        # pick arrow char based on direction
        if abs(dx) >= abs(dy) * 2:
            return '>' if dx > 0 else '<'
        elif abs(dy) >= abs(dx) * 2:
            return 'v' if dy > 0 else '^'
        elif dx > 0:
            return 'v' if dy > 0 else '^'
        else:
            return 'v' if dy > 0 else '^'

    # Draw edges
    for src, neighbors in enumerate(tasks):
        x0, y0 = pos[src]
        for dst in neighbors:
            x1, y1 = pos[dst]
            # shorten to not overlap node labels
            dx, dy = x1 - x0, y1 - y0
            length = math.sqrt(dx**2 + dy**2) or 1
            sx = int(x0 + dx / length * 2)
            sy = int(y0 + dy / length * 1)
            ex = int(x1 - dx / length * 2)
            ey = int(y1 - dy / length * 1)
            draw_line(sx, sy, ex, ey)
            if 0 <= ey < H and 0 <= ex < W:
                grid[ey][ex] = arrowhead(sx, sy, ex, ey)

    # Draw node labels (overwrite dots)
    for i, (x, y) in enumerate(pos):
        label = f'({i})'
        start = x - len(label) // 2
        for j, ch in enumerate(label):
            if 0 <= y < H and 0 <= start + j < W:
                grid[y][start + j] = ch

    print('\n'.join(''.join(row) for row in grid))

if __name__ == "__main__":
    tasks = [
        {"datetime": "", "name": "Task 0", "deps": [    ], "days": 5},
        {"datetime": "", "name": "Task 1", "deps": [2, 3], "days": 1},
        {"datetime": "", "name": "Task 2", "deps": [3, 0], "days": 2},
        {"datetime": "", "name": "Task 3", "deps": [    ], "days": 1},
        {"datetime": "", "name": "Task 4", "deps": [    ], "days": 1},
    ]

    '''
    tasks = [
        {"name": "Task 0", "deps": [    ], "days": 4},
        {"name": "Task 1", "deps": [    ], "days": 1},
        {"name": "Task 2", "deps": [0, 1], "days": 2},
    ]
    '''

    print(get_timeline_string(tasks));




