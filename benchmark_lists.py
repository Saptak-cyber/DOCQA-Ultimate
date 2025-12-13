import time
import numpy as np
import psycopg2
from sklearn.metrics.pairwise import cosine_similarity

# --- CONFIG ---
DB = psycopg2.connect(
    host="localhost",
    dbname="postgres",
    user="postgres",
    password="password"
)

def fetch_all_embeddings():
    cur = DB.cursor()
    cur.execute("SELECT id, embedding FROM chunks LIMIT 50000;")
    data = cur.fetchall()
    cur.close()
    ids = [row[0] for row in data]
    vecs = np.array([row[1] for row in data])
    return ids, vecs

def brute_force(query_vec, vecs):
    sims = cosine_similarity([query_vec], vecs)[0]
    top = sims.argsort()[::-1][:20]
    return top

def ivfflat_search(query_vec, lists, probes):
    cur = DB.cursor()
    cur.execute(f"SET ivfflat.probes = {probes};")
    cur.execute(
        "SELECT id FROM chunks ORDER BY embedding <-> %s LIMIT 20;",
        (query_vec,)
    )
    result = [row[0] for row in cur.fetchall()]
    cur.close()
    return result

def recall_at_k(true_ids, retrieved_ids):
    return len(set(true_ids) & set(retrieved_ids)) / len(true_ids)

def benchmark():
    ids, vecs = fetch_all_embeddings()
    query_vec = vecs[0]

    true_top = brute_force(query_vec, vecs)
    print("Brute-force baseline ready.")

    candidates = [50, 100, 200, 400, 600, 800, 1000]
    probes = 8

    for lists in candidates:
        print(f"\nTesting lists={lists}")
        start = time.time()
        retrieved = ivfflat_search(query_vec, lists, probes)
        latency = (time.time() - start) * 1000

        recall = recall_at_k(true_top, retrieved)
        print(f"Latency: {latency:.2f} ms | Recall: {recall:.3f}")

if __name__ == "__main__":
    benchmark()
