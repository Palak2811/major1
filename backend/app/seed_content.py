"""Curated Phase 2 study content: explanations, worked examples and practice questions.

Stored as `documents` (kind = explanation | worked_example) so the Phase 4 RAG pipeline
can index the same material instead of it living in code.
"""

L = "abcdefgh"


def M(topic, diff, title, body, options, correct, explanation, multi=False):
    correct = correct if isinstance(correct, list) else [correct]
    return dict(type="multi_select" if multi else "mcq", topic=topic, difficulty=diff,
                title=title, body=body,
                options=[{"id": L[i], "text": t} for i, t in enumerate(options)],
                answer={"correct": [L[i] for i in correct]}, explanation=explanation)


def N(topic, diff, title, body, value, explanation, tol=0):
    return dict(type="numerical", topic=topic, difficulty=diff, title=title, body=body,
                answer={"value": value, "tolerance": tol}, explanation=explanation)


def OP(topic, diff, title, code, expected, explanation):
    return dict(type="output_prediction", topic=topic, difficulty=diff, title=title,
                body="What does this Python snippet print?",
                meta={"code": code, "language": "python"},
                answer={"expected_output": expected}, explanation=explanation)


QUESTIONS = [
    # ---------------- Arrays / Two Pointer / Sliding Window / Prefix Sum ----------------
    M("two-pointer", "easy", "Two pointers on a sorted array",
      "In a sorted array, you look for a pair summing to a target using pointers at both ends. "
      "If the current sum is smaller than the target, what do you do?",
      ["Move the left pointer right", "Move the right pointer left", "Move both pointers",
       "Restart from the middle"], 0,
      "A larger sum is needed, and only moving the left pointer right can increase it."),
    M("two-pointer", "medium", "Two-pointer complexity",
      "What is the time complexity of the two-pointer pair-sum scan on a sorted array of n items?",
      ["O(n)", "O(n log n)", "O(n²)", "O(log n)"], 0,
      "Each step moves one pointer inward, so there are at most n − 1 steps."),
    N("two-pointer", "medium", "Pairs summing to 10",
      "Sorted array [1, 2, 3, 4, 6, 7, 8, 9]. How many distinct index pairs (i < j) sum to 10?",
      4, "(1, 9), (2, 8), (3, 7) and (4, 6) → 4 pairs."),
    M("two-pointer", "hard", "Container with most water",
      "For 'container with most water', why is it safe to move the pointer at the shorter line?",
      ["Area is limited by the shorter line; keeping it can never give a larger area",
       "The taller line is always part of the answer",
       "Moving the taller line increases width",
       "It is not safe; both must be tried"], 0,
      "Width only shrinks, so with the shorter line fixed, every narrower container is no taller."),
    M("sliding-window", "easy", "When to use a sliding window",
      "Which problem is the most natural fit for a sliding window?",
      ["Maximum sum of any k consecutive elements", "Shortest path in a graph",
       "Sorting an array", "Finding the median of two sorted arrays"], 0,
      "Contiguous subarrays of fixed or variable length are the sliding window's home turf."),
    N("sliding-window", "medium", "Max sum of window size 3",
      "Array [2, 1, 5, 1, 3, 2], window size k = 3. What is the maximum window sum?",
      9, "Windows: 8, 7, 9, 6 → maximum is 9 (5 + 1 + 3)."),
    M("sliding-window", "hard", "Longest substring without repeats",
      "Using a variable window with a last-seen index map, what is the time complexity of finding "
      "the longest substring without repeating characters in a string of length n?",
      ["O(n)", "O(n log n)", "O(n²)", "O(n·σ) where σ is the alphabet size, always"], 0,
      "Each character enters the window once and the left edge only ever moves forward."),
    N("prefix-sum", "easy", "Range sum with prefix sums",
      "Prefix array P for [3, 1, 4, 1, 5] is [0, 3, 4, 8, 9, 14]. What is the sum of elements "
      "at indices 1..3 (0-based, inclusive)?", 6, "P[4] − P[1] = 9 − 3 = 6 (1 + 4 + 1)."),
    M("prefix-sum", "medium", "Subarray sum equals k",
      "To count subarrays summing to k in O(n), what do you store in a hash map?",
      ["Frequency of each prefix sum seen so far", "Every subarray's sum",
       "Index of the maximum element", "Sorted prefix sums"], 0,
      "A subarray (i, j] sums to k when P[j] − k = P[i]; "
      "count prior prefix sums equal to P[j] − k."),
    # ---------------- Graphs / BFS / DFS ----------------
    M("bfs", "easy", "BFS data structure", "Which data structure drives breadth-first search?",
      ["Queue", "Stack", "Priority queue", "Hash set only"], 0,
      "BFS processes vertices in order of distance, which a FIFO queue guarantees."),
    M("bfs", "medium", "Shortest path in unweighted graphs",
      "Why does BFS find shortest paths in an unweighted graph?",
      ["It visits vertices in non-decreasing order of edge-count distance",
       "It always follows the smallest edge weight", "It backtracks on longer paths",
       "It visits every path"], 0,
      "All vertices at distance d are dequeued before any at distance d + 1."),
    N("bfs", "medium", "BFS levels",
      "Edges: 1-2, 1-3, 2-4, 3-4, 4-5. Starting BFS at 1, what is the distance to vertex 5?",
      3, "1 → 2 (or 3) → 4 → 5: three edges."),
    M("dfs", "easy", "DFS data structure",
      "An iterative depth-first search typically uses which structure?",
      ["Stack", "Queue", "Min-heap", "Deque used as a queue"], 0,
      "DFS explores the most recently discovered vertex first — last in, first out."),
    M("dfs", "medium", "Cycle detection in a directed graph",
      "During DFS on a directed graph, which edge proves a cycle exists?",
      ["An edge to a vertex currently on the recursion stack (grey)",
       "An edge to any visited vertex", "A tree edge", "An edge to an unvisited vertex"], 0,
      "A back edge to a grey vertex closes a cycle; edges to finished (black) vertices do not."),
    M("dfs", "hard", "Topological sort with DFS",
      "In DFS-based topological sorting, vertices are output in which order?",
      ["Reverse of their finishing order", "Order of discovery",
       "Order of finishing", "Order of in-degree"], 0,
      "A vertex finishes only after all its descendants, "
      "so reversing finish order respects edges."),
    # ---------------- Dynamic Programming ----------------
    M("1d-dp", "easy", "Recognising DP",
      "Which two properties make a problem suitable for dynamic programming?",
      ["Optimal substructure and overlapping subproblems", "Sorted input and unique values",
       "Greedy choice and matroid structure", "Recursion and randomness"], 0,
      "DP reuses stored answers to subproblems that recur, building the optimum from them."),
    N("1d-dp", "medium", "Climbing stairs",
      "You can climb 1 or 2 steps at a time. How many distinct ways are there to climb 6 steps?",
      13, "ways(n) = ways(n−1) + ways(n−2): 1, 2, 3, 5, 8, 13."),
    N("1d-dp", "hard", "House robber",
      "Houses hold [2, 7, 9, 3, 1]. You cannot rob two adjacent houses. Maximum loot?", 12,
      "dp = [2, 7, 11, 11, 12]; rob houses 1, 3 and 5 → 2 + 9 + 1 = 12."),
    M("knapsack", "medium", "0/1 knapsack complexity",
      "What is the time complexity of the standard 0/1 knapsack DP with n items and capacity W?",
      ["O(n·W)", "O(2ⁿ)", "O(n log n)", "O(W log n)"], 0,
      "One cell per (item, capacity) pair, each filled in O(1). It is pseudo-polynomial in W."),
    N("knapsack", "hard", "Small knapsack",
      "Capacity 5. Items (weight, value): (1, 1), (3, 4), (4, 5), (2, 3). Maximum value?", 7,
      "Take weights 3 + 2 → values 4 + 3 = 7; no other combination within 5 does better."),
    # ---------------- OS ----------------
    M("processes-threads", "easy", "What threads share",
      "Which of these do threads of the same process NOT share?",
      ["Stack", "Heap", "Code segment", "Open file descriptors"], 0,
      "Each thread has its own stack and registers; heap, code and files are shared."),
    M("processes-threads", "medium", "Context switch cost",
      "Why is a thread context switch usually cheaper than a process context switch?",
      ["Threads share an address space, so no page-table/TLB switch is needed",
       "Threads have no registers", "The kernel is not involved",
       "Threads cannot be pre-empted"], 0,
      "Switching processes changes the memory map, which flushes/retags the TLB."),
    M("processes-threads", "hard", "Race condition",
      "Two threads each run `count += 1` 1000 times on a shared int without locking. The final "
      "value can be less than 2000 because…",
      ["the read-modify-write is not atomic, so updates get lost",
       "threads cannot write shared memory", "the compiler removes the loop",
       "integers overflow at 1000"], 0,
      "Both threads can read the same old value and write back the same incremented result."),
    M("cpu-scheduling", "easy", "Starvation",
      "Which scheduling algorithm can starve long jobs if short jobs keep arriving?",
      ["Shortest Job First", "Round Robin", "First-Come First-Served", "None of these"], 0,
      "SJF always prefers shorter jobs; ageing is the usual fix."),
    N("cpu-scheduling", "medium", "FCFS average waiting time",
      "Three jobs arrive at t = 0 in order with bursts 24, 3, 3 ms. Average waiting time under "
      "FCFS (ms)?", 17, "Waits are 0, 24 and 27 → (0 + 24 + 27) / 3 = 17."),
    N("cpu-scheduling", "hard", "SJF average waiting time",
      "Same jobs (bursts 24, 3, 3 ms, all at t = 0) under non-preemptive SJF. Average waiting "
      "time (ms)?", 3, "Order 3, 3, 24 → waits 0, 3, 6 → 9 / 3 = 3."),
    # ---------------- DBMS ----------------
    M("normalization", "easy", "First normal form",
      "A table is in 1NF when…",
      ["every attribute holds atomic values", "there are no partial dependencies",
       "there are no transitive dependencies", "every determinant is a candidate key"], 0,
      "1NF forbids repeating groups and multi-valued cells."),
    M("normalization", "medium", "Second normal form",
      "Moving from 1NF to 2NF removes which kind of dependency?",
      ["Partial dependency of a non-key attribute on part of a composite key",
       "Transitive dependency", "Multi-valued dependency", "Join dependency"], 0,
      "2NF requires every non-key attribute to depend on the whole candidate key."),
    M("normalization", "hard", "BCNF",
      "A relation is in BCNF when, for every non-trivial FD X → Y…",
      ["X is a superkey", "Y is a prime attribute", "X is a single attribute",
       "Y is part of a candidate key"], 0,
      "BCNF strengthens 3NF by dropping the 'Y is prime' escape clause."),
    M("transactions", "easy", "ACID — isolation",
      "Which ACID property ensures concurrent transactions don't see each other's partial work?",
      ["Isolation", "Atomicity", "Consistency", "Durability"], 0,
      "Isolation makes concurrent execution equivalent to some serial order."),
    M("transactions", "medium", "Dirty read",
      "A dirty read happens when a transaction reads…",
      ["data written by another transaction that has not committed",
       "data that was deleted", "a row twice with different values",
       "new rows inserted by another transaction"], 0,
      "READ UNCOMMITTED allows it; READ COMMITTED and above prevent it."),
    # ---------------- Aptitude ----------------
    N("percentages", "easy", "Successive change",
      "A price rises by 20% and then falls by 20%. Net change in percent? (Enter a negative "
      "number for a decrease.)", -4, "1.2 × 0.8 = 0.96 → a 4% decrease."),
    N("percentages", "medium", "Percentage of a percentage",
      "What is 15% of 40% of 500?", 30, "0.40 × 500 = 200; 0.15 × 200 = 30."),
    N("percentages", "hard", "Required increase",
      "A value falls by 25%. By what percent must it rise to return to the original? "
      "(2 decimal places)", 33.33, "From 0.75 back to 1 needs 1/0.75 − 1 = 33.33%.", tol=0.01),
    N("time-work", "medium", "Three workers",
      "A, B and C finish a job alone in 6, 12 and 24 days. Together, how many days? "
      "(2 decimal places)", 3.43, "1/6 + 1/12 + 1/24 = 7/24 per day → 24/7 ≈ 3.43 days.",
      tol=0.01),
    N("time-work", "hard", "Pipes filling and emptying",
      "Pipe A fills a tank in 4 h; pipe B empties it in 6 h. Both open, how many hours to fill?",
      12, "Net rate 1/4 − 1/6 = 1/12 per hour → 12 hours."),
    N("probability", "easy", "Two dice",
      "Two fair dice are rolled. Probability the sum is 7? (4 decimal places)", 0.1667,
      "6 favourable outcomes out of 36 → 1/6.", tol=0.0005),
    # ---------------- OOP ----------------
    M("inheritance", "easy", "Is-a relationship",
      "Inheritance models which relationship?", ["is-a", "has-a", "uses-a", "depends-on"], 0,
      "A subclass is a specialised kind of its superclass; composition models has-a."),
    M("polymorphism", "medium", "Runtime polymorphism",
      "Runtime (dynamic) polymorphism in Java/C++ is achieved through…",
      ["method overriding with virtual dispatch", "method overloading",
       "operator overloading", "generics"], 0,
      "The overriding method is chosen from the object's runtime type; overloading is resolved "
      "at compile time."),
    OP("polymorphism", "medium", "Overridden method",
      "class A:\n    def who(self):\n        return 'A'\n\nclass B(A):\n    def who(self):\n"
      "        return 'B'\n\nx: A = B()\nprint(x.who())", "B",
      "Dispatch uses the object's actual class (B), not the annotated type."),
    M("encapsulation", "easy", "Encapsulation", "Encapsulation primarily means…",
      ["bundling data with methods and restricting direct access to state",
       "creating many subclasses", "writing code in one file", "using interfaces only"], 0,
      "Invariants stay protected because state changes go through the object's methods."),
    M("inheritance", "hard", "Diamond problem",
      "Which statements about the diamond problem are true?",
      ["It arises with multiple inheritance of implementation",
       "C++ addresses it with virtual inheritance",
       "Java avoids it for classes by allowing only single class inheritance",
       "It cannot occur in any language"], [0, 1, 2],
      "Java still allows multiple interface inheritance; default-method clashes must be resolved "
      "explicitly.", multi=True),
]

DOCS = {
    "arrays": [
        ("explanation", "Arrays: patterns that matter",
         "Most array interview problems reduce to a handful of patterns. **Two pointers** walk "
         "inward or in the same direction to avoid a nested loop. **Sliding window** maintains "
         "a contiguous range and updates it incrementally. **Prefix sums** turn any range-sum "
         "query into a subtraction. Before coding, ask: is the input sorted? Is the answer a "
         "contiguous range? Do I need many range queries? Each answer points at a pattern."),
        ("worked_example", "From O(n²) to O(n): pair with target sum",
         "Problem: sorted nums = [1, 3, 4, 6, 9], target = 10.\n\n"
         "Brute force checks all pairs: O(n²).\n\n"
         "Two pointers: l = 0, r = 4 → 1 + 9 = 10 ✓. If the sum were too small we would do "
         "l += 1; too big, r -= 1. Each step discards one element for good, so the scan is O(n) "
         "time and O(1) space."),
    ],
    "two-pointer": [
        ("explanation", "Two pointers",
         "Keep two indices and move them based on a comparison, so that each move provably "
         "discards candidates. On sorted input with a target sum: if the sum is too small, only "
         "moving the left pointer right can increase it; if too large, move the right pointer "
         "left. Because every step removes one index from consideration, the total work is O(n)."),
        ("worked_example", "Remove duplicates in place",
         "nums = [1, 1, 2, 3, 3].\n\nslow = 0. For fast in 1..4: when nums[fast] != nums[slow], "
         "slow += 1 and nums[slow] = nums[fast].\n\nfast=1 (1 = 1) skip · fast=2 (2) → slow=1, "
         "nums=[1,2,…] · fast=3 (3) → slow=2 · fast=4 (3 = 3) skip.\n\nAnswer: first slow + 1 = 3 "
         "elements [1, 2, 3]. O(n) time, O(1) space."),
    ],
    "sliding-window": [
        ("explanation", "Sliding window",
         "For problems about contiguous subarrays or substrings, keep a window [l, r] and a "
         "running summary (sum, counts, max…). Extend r one step at a time; when the window "
         "breaks a constraint, advance l until it holds again. Each index enters and leaves at "
         "most once, so the scan is O(n) even though it looks like two loops."),
        ("worked_example", "Max sum of k consecutive elements",
         "nums = [2, 1, 5, 1, 3, 2], k = 3.\n\nFirst window 2 + 1 + 5 = 8. Slide: subtract the "
         "element leaving, add the one entering: 8 − 2 + 1 = 7, 7 − 1 + 3 = 9, 9 − 5 + 2 = 6.\n\n"
         "Maximum = 9. Each slide is O(1), so total O(n) instead of O(n·k)."),
    ],
    "graphs": [
        ("explanation", "Graph traversal",
         "Represent graphs with adjacency lists (O(V + E) space). **BFS** explores level by "
         "level using a queue and gives shortest paths in unweighted graphs. **DFS** goes deep "
         "using recursion or a stack, and underlies cycle detection, topological sort and "
         "connected components. Both run in O(V + E). Always keep a visited set so each vertex "
         "is processed once."),
        ("worked_example", "Counting connected components",
         "Edges: 1-2, 2-3, 4-5, vertex 6 isolated.\n\nFor each unvisited vertex, start a DFS and "
         "count one component: from 1 we mark {1, 2, 3}; from 4 we mark {4, 5}; from 6 we mark "
         "{6}.\n\nAnswer: 3 components, in O(V + E)."),
    ],
    "bfs": [
        ("explanation", "Breadth-first search",
         "Push the source into a queue with distance 0. Repeatedly pop a vertex and push each "
         "unvisited neighbour with distance + 1, marking it visited *when enqueued* (not when "
         "dequeued) to avoid duplicates. Because all distance-d vertices leave the queue before "
         "any distance-(d + 1) vertex, the first time you reach a vertex is via a shortest path."),
        ("worked_example", "Shortest path in a grid",
         "Grid (S = start, E = end, # = wall):\n\nS . #\n. . .\n# . E\n\nBFS from S: distance 1 "
         "→ (0,1), (1,0); distance 2 → (1,1); distance 3 → (1,2), (2,1); distance 4 → (2,2) = E."
         "\n\nShortest path length = 4 moves."),
    ],
    "dfs": [
        ("explanation", "Depth-first search",
         "DFS follows one branch as far as possible before backtracking. Colour vertices white "
         "(unvisited), grey (on the current path) and black (finished). In a directed graph an "
         "edge to a grey vertex is a back edge, which proves a cycle. Reversing the order in "
         "which vertices turn black gives a topological order of a DAG."),
        ("worked_example", "Topological order of course prerequisites",
         "Edges: A→C, B→C, C→D.\n\nDFS(A): A grey → C grey → D grey → D black → C black → A "
         "black. DFS(B): B black.\n\nFinish order: D, C, A, B. Reversed: B, A, C, D — every edge "
         "points forward, so it is a valid course order."),
    ],
    "dynamic-programming": [
        ("explanation", "Dynamic programming",
         "DP applies when the optimum is built from optimal answers to subproblems (optimal "
         "substructure) and those subproblems repeat (overlap). Define the state precisely "
         "(what dp[i] means), write the transition, set base cases, and choose an order where "
         "dependencies are computed first. Memoised recursion (top-down) and tabulation "
         "(bottom-up) are equivalent; tabulation often allows space optimisation."),
        ("worked_example", "House robber",
         "Values [2, 7, 9, 3, 1]. State: dp[i] = best loot from houses 0..i.\n\nTransition: "
         "dp[i] = max(dp[i−1], dp[i−2] + v[i]).\n\ndp = 2, 7, max(7, 2+9)=11, max(11, 7+3)=11, "
         "max(11, 11+1)=12.\n\nAnswer 12. Only the last two values are needed, so O(1) space."),
    ],
    "processes-threads": [
        ("explanation", "Processes vs threads",
         "A process is an executing program with its own address space, file table and "
         "resources. Threads are units of execution inside a process: they share heap, code and "
         "open files, but each has its own stack, registers and program counter. Threads are "
         "cheaper to create and switch between, but shared memory means you need "
         "synchronisation (mutexes, semaphores) to avoid race conditions."),
        ("worked_example", "Lost update race",
         "Shared counter = 0. Thread T1 reads 0, is pre-empted; T2 reads 0, writes 1; T1 resumes "
         "and writes 1.\n\nTwo increments happened, yet counter = 1. Fix: guard the "
         "read-modify-write with a mutex, or use an atomic increment."),
    ],
    "cpu-scheduling": [
        ("explanation", "CPU scheduling",
         "Schedulers trade off throughput, waiting time and fairness. **FCFS** is simple but "
         "suffers the convoy effect. **SJF/SRTF** minimise average waiting time but need burst "
         "estimates and can starve long jobs. **Round Robin** gives each job a time quantum for "
         "responsiveness; too small a quantum wastes time on context switches. Waiting time = "
         "turnaround time − burst time."),
        ("worked_example", "FCFS vs SJF",
         "Bursts 24, 3, 3 (all arrive at 0).\n\nFCFS order 24, 3, 3 → waits 0, 24, 27 → average "
         "17.\n\nSJF order 3, 3, 24 → waits 0, 3, 6 → average 3.\n\nSame work, very different "
         "waiting — that gap is the convoy effect."),
    ],
    "normalization": [
        ("explanation", "Normalization",
         "Normalization removes redundancy that causes update anomalies. **1NF**: atomic values. "
         "**2NF**: no non-key attribute depends on part of a composite key. **3NF**: no "
         "transitive dependency of a non-key attribute on the key. **BCNF**: for every "
         "non-trivial FD X → Y, X is a superkey. Decompose using functional dependencies while "
         "keeping joins lossless."),
        ("worked_example", "Decomposing to 3NF",
         "Enrolment(student_id, course_id, student_name, dept, dept_head).\n\nFDs: student_id → "
         "student_name, dept; dept → dept_head.\n\nPartial dependency on part of the key "
         "(student_id) → split Student(student_id, student_name, dept). Transitive dependency "
         "dept → dept_head → split Dept(dept, dept_head). Keep Enrolment(student_id, course_id)."),
    ],
    "quantitative": [
        ("explanation", "Quantitative aptitude: work with rates",
         "Convert everything to a rate per unit time or a multiplier. Percentage changes chain "
         "by multiplication (a 20% rise then a 20% fall is 1.2 × 0.8). Work problems add rates: "
         "if A does a job in a days, A's rate is 1/a per day; combined rate is the sum, and the "
         "time is its reciprocal. Pipes that empty contribute negative rates."),
        ("worked_example", "Two workers",
         "A: 10 days, B: 15 days.\n\nRates 1/10 + 1/15 = 3/30 + 2/30 = 5/30 = 1/6 per day.\n\n"
         "Together: 6 days."),
    ],
    "principles": [
        ("explanation", "OOP principles",
         "**Encapsulation** hides state behind methods so invariants hold. **Inheritance** "
         "models is-a relationships and reuses behaviour. **Polymorphism** lets one interface "
         "have many implementations; with method overriding the runtime type decides which "
         "method runs. **Abstraction** exposes what an object does, not how. Prefer "
         "composition over deep inheritance hierarchies."),
        ("worked_example", "Dynamic dispatch",
         "Shape has area(); Circle and Square override it.\n\nshapes = [Circle(1), Square(2)]; "
         "total = sum(s.area() for s in shapes).\n\nThe loop never checks types — each object "
         "supplies its own area(). Adding Triangle needs no change to the loop (open/closed "
         "principle)."),
    ],
}

SAMPLE_TEST = {
    "title": "Placement warm-up: Aptitude + DSA",
    "description": "A short timed mock with two sections and negative marking. "
                   "The coding question is scored once the Judge0 sandbox is wired (Phase 3).",
    "negative_marking": True,
    "negative_ratio": 0.25,
    "sections": [
        {"name": "Aptitude", "time_limit_seconds": 600, "topics": ["quantitative"], "count": 4,
         "types": ["mcq", "numerical"]},
        {"name": "Technical", "time_limit_seconds": 900,
         "topics": ["arrays", "graphs", "dynamic-programming", "processes-threads"], "count": 6,
         "types": ["mcq", "multi_select", "numerical", "output_prediction"],
         "extra": ["Two Sum (sorted input)"]},
    ],
}


# ---------------- Phase 3: judged coding + SQL problems ----------------
# Every hidden test below was verified by running REFERENCE_SOLUTIONS on Judge0 CE.

def CODE(topic, diff, title, body, constraints, input_format, output_format, samples, hidden,
         explanation, time_limit_ms=2000):
    return dict(type="coding", topic=topic, difficulty=diff, title=title, body=body,
                meta={"constraints": constraints, "input_format": input_format,
                      "output_format": output_format,
                      "samples": [{"input": i, "output": o} for i, o in samples],
                      "time_limit_ms": time_limit_ms, "memory_limit_mb": 256},
                answer={"hidden_tests": [{"input": i, "output": o} for i, o in hidden]},
                explanation=explanation)


CODING_PROBLEMS = [
    CODE("1d-dp", "medium", "Maximum subarray sum",
         "Given an array of n integers, print the largest possible sum of a non-empty "
         "contiguous subarray.",
         "1 ≤ n ≤ 2·10^5; −10^4 ≤ a[i] ≤ 10^4",
         "Line 1: n. Line 2: n space-separated integers.", "A single integer.",
         [("9\n-2 1 -3 4 -1 2 1 -5 4", "6")],
         [("1\n-7", "-7"), ("5\n1 2 3 4 5", "15"), ("6\n-1 -2 -3 -4 -5 -6", "-1"),
          ("8\n5 -9 6 -2 3 -1 4 -10", "10")],
         "Kadane: best ending here = max(x, best_here + x); track the global maximum. O(n)."),
    CODE("sliding-window", "medium", "Longest unique-character substring",
         "Given a string s, print the length of the longest substring without repeating "
         "characters.",
         "0 ≤ |s| ≤ 10^5; s consists of printable ASCII without spaces",
         "One line containing s (may be empty).", "A single integer.",
         [("abcabcbb", "3"), ("bbbbb", "1")],
         [("pwwkew", "3"), ("", "0"), ("abcdef", "6"), ("abba", "2"), ("dvdf", "3")],
         "Sliding window with last-seen index: move the left edge past the previous "
         "occurrence. O(n)."),
    CODE("dfs", "medium", "Count connected components",
         "An undirected graph has n vertices (1..n) and m edges. Print the number of "
         "connected components.",
         "1 ≤ n ≤ 10^5; 0 ≤ m ≤ 2·10^5",
         "Line 1: n m. Next m lines: u v.", "A single integer.",
         [("5 3\n1 2\n2 3\n4 5", "2")],
         [("1 0", "1"), ("4 0", "4"), ("6 5\n1 2\n2 3\n3 1\n4 5\n5 6", "2"),
          ("3 3\n1 2\n2 3\n1 3", "1")],
         "Run DFS/BFS (or union-find) from every unvisited vertex and count starts. O(n + m)."),
    CODE("1d-dp", "easy", "Count ways to climb stairs",
         "You can climb 1 or 2 steps at a time. Print the number of distinct ways to reach "
         "step n.",
         "1 ≤ n ≤ 80 (the answer fits in a signed 64-bit integer)",
         "A single integer n.", "A single integer.",
         [("3", "3"), ("5", "8")],
         [("1", "1"), ("2", "2"), ("10", "89"), ("45", "1836311903"), ("80", "37889062373143906")],
         "ways(n) = ways(n−1) + ways(n−2) — Fibonacci. Use 64-bit integers."),
]

SQL_PROBLEMS = [
    dict(type="sql", topic="aggregation", difficulty="easy", title="Employees per department",
         body="Return each department and its number of employees as `dept, headcount`, "
              "ordered by headcount descending, then dept ascending.",
         meta={"schema_sql": "CREATE TABLE employees (id INT PRIMARY KEY, name TEXT, "
                             "dept TEXT, salary INT);",
               "seed_sql": "INSERT INTO employees VALUES (1,'Asha','Eng',120),(2,'Ben','Eng',"
                           "110),(3,'Chen','Ops',90),(4,'Dev','Eng',100),(5,'Eli','HR',70),"
                           "(6,'Fay','Ops',95);"},
         answer={"reference_query": "SELECT dept, COUNT(*) AS headcount FROM employees "
                                    "GROUP BY dept ORDER BY headcount DESC, dept ASC;"},
         explanation="GROUP BY the department and COUNT(*) rows per group."),
]

SECOND_HIGHEST_SEED = ("INSERT INTO employees VALUES (1, 300), (2, 200), (3, 300), (4, 100);")

REFERENCE_SOLUTIONS = {
    "Maximum subarray sum": """import sys
d=sys.stdin.read().split();n=int(d[0]);a=list(map(int,d[1:1+n]))
b=c=a[0]
for x in a[1:]:
    c=max(x,c+x);b=max(b,c)
print(b)""",
    "Longest unique-character substring": """import sys
s=sys.stdin.read().strip();last={};l=best=0
for r,ch in enumerate(s):
    if ch in last and last[ch]>=l: l=last[ch]+1
    last[ch]=r;best=max(best,r-l+1)
print(best)""",
    "Count connected components": """import sys
d=sys.stdin.read().split();n,m=int(d[0]),int(d[1]);p=list(range(n+1))
def f(x):
    while p[x]!=x: p[x]=p[p[x]];x=p[x]
    return x
for i in range(m):
    a,b=f(int(d[2+2*i])),f(int(d[3+2*i]))
    if a!=b: p[a]=b
print(len({f(i) for i in range(1,n+1)}))""",
    "Count ways to climb stairs": """n=int(input());a,b=1,1
for _ in range(n-1): a,b=b,a+b
print(b)""",
    "Two Sum (sorted input)": """import sys
d=sys.stdin.read().split();n,t=int(d[0]),int(d[1]);a=list(map(int,d[2:2+n]));l,r=0,n-1
while l<r:
    s=a[l]+a[r]
    if s==t: break
    if s<t: l+=1
    else: r-=1
print(l+1,r+1)""",
}


# ---------------- Phase 4: extra knowledge-base material (indexed for RAG) ----------------

KB_DOCS = [
    ("interview_faq", "Behavioural interviews: the STAR method", None,
     "Behavioural questions (\"Tell me about a time when...\") are best answered with STAR: "
     "Situation (brief context), Task (what you were responsible for), Action (what YOU did, "
     "in specific steps) and Result (the measurable outcome and what you learned).\n\n"
     "Keep the Situation and Task short and spend most of the answer on Action and Result. "
     "Prepare 5-6 stories from projects, internships and team work that can be adapted to "
     "questions about conflict, failure, leadership, tight deadlines and learning something "
     "quickly. Quantify results where you can (\"cut build time from 10 to 3 minutes\")."),
    ("company_prep", "Online assessment strategy", None,
     "Online assessments usually mix aptitude MCQs with 2-3 coding problems under a strict "
     "timer. Read every coding problem first and start with the one you are most confident "
     "about. For each problem, confirm the constraints: n up to 10^5 usually needs O(n log n) "
     "or better, while n up to 20 allows exponential search.\n\n"
     "Test your code against the samples and at least one edge case (empty input, a single "
     "element, all-equal values, negative numbers) before submitting. When negative marking "
     "applies, skip MCQs you cannot narrow down to two options."),
    ("interview_faq", "Explaining time complexity in interviews", "arrays",
     "Interviewers expect you to state time and space complexity for every solution. Count "
     "how many times the innermost operation runs as a function of input size. A single loop "
     "over n elements is O(n); two nested loops over n are O(n^2); halving the search space "
     "each step (binary search) is O(log n); sorting is O(n log n).\n\n"
     "Mention the trade-off you are making, for example using a hash map for O(n) time at "
     "the cost of O(n) extra space instead of an O(n^2) time, O(1) space brute force."),
]
